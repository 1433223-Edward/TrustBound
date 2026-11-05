"""Operator-only A1–A5 evidence suite. No HTTP or IPC attack entry point."""
import argparse
from dataclasses import asdict
from datetime import datetime, timezone
import errno
import json
import os
from pathlib import Path
import re
import secrets
import tempfile
from urllib.request import ProxyHandler, build_opener
import uuid

from .runner import CPU_LIMIT_NANOS, MEMORY_LIMIT_BYTES, PID_LIMIT, _execute_fixed_tests, sha256
from .service import ROOT, TASK, run_task


CASES = ("A1", "A2", "A3", "A4", "A5")
SENTINEL_ENV = "TRUSTBOUND_SYNTHETIC_ATTACK_CANARY"
DENIED = {errno.EACCES, errno.EPERM, errno.EROFS}
HIDDEN = {errno.ENOENT, errno.EACCES, errno.EPERM, errno.EROFS}
CODE = b"VALUE = 123\n"


def _api_health():
    try:
        http = build_opener(ProxyHandler({}))
        with http.open("http://127.0.0.1:8000/api/health", timeout=3) as response:
            health = json.load(response)
        return {"healthy": health["status"] == "ok", "idle": health["active_run_id"] is None,
                "live_disabled": health["modes"]["live_executor"]["enabled"] is False}
    except (OSError, ValueError, KeyError, TypeError):
        return {"healthy": False, "idle": False, "live_disabled": False}


def _observations(stdout):
    try:
        rows = [json.loads(line) for line in stdout.splitlines()]
    except ValueError:
        return []
    return rows if all(type(row) is dict for row in rows) else []


def _judge(case, execution, rows):
    if (execution.error or not execution.container_name or not execution.limits_verified
            or not execution.cleanup_confirmed or not execution.workspace_unchanged):
        return "INCONCLUSIVE", "Sandbox evidence is missing, unsafe or incomplete"
    first = rows[0] if rows else {}
    if case == "A4":
        if (first.get("loop_started") is True and execution.status == "TIMED_OUT"
                and execution.exit_code == 137 and execution.timeout_reason):
            return "PASS", "Host deadline terminated the running loop"
        return "INCONCLUSIVE", "Loop start and host termination were not both confirmed"
    if case == "A5":
        if (first.get("allocation_started") is not True
                or first.get("memory_max") != str(MEMORY_LIMIT_BYTES) or first.get("swap_max") != "0"):
            return "INCONCLUSIVE", "Allocation guard did not verify the active memory limit"
        if execution.status == "EXITED" and execution.exit_code == 137 and execution.oom_killed is True:
            return "PASS", "Docker confirmed cgroup OOM termination"
        if any(row.get("allocation_finished") is True for row in rows):
            return "FAIL", "The capped allocation completed despite the declared limit"
        return "INCONCLUSIVE", "No confirmed OOM termination"

    if execution.status != "EXITED" or execution.exit_code != 0 or len(rows) != 1:
        return "INCONCLUSIVE", "Probe did not return a complete observation"
    expected_fields = {
        "A1": {"mount_readonly", "mount_write_errno", "root_write_errno", "host_write_errno"},
        "A2": {"target", "interfaces", "route_errno"},
        "A3": {"sentinel_env_visible", "host_read_errno", "credential_env_visible"},
    }
    if (set(first) != expected_fields[case]
            or any(value is not None and type(value) is not int
                   for key, value in first.items() if key.endswith("_errno"))):
        return "INCONCLUSIVE", "Probe observation fields are incomplete"
    if case == "A1":
        contained = (first["mount_readonly"] is True and first["mount_write_errno"] in DENIED
                     and first["root_write_errno"] == errno.EROFS and first["host_write_errno"] in HIDDEN)
    elif case == "A2":
        contained = (first["target"] == "192.0.2.1" and first["interfaces"] == ["lo"]
                     and first["route_errno"] == errno.ENETUNREACH)
    else:
        contained = (first["sentinel_env_visible"] is False and first["credential_env_visible"] is False
                     and first["host_read_errno"] in HIDDEN)
    return ("PASS", "Runtime isolation confirmed") if contained else ("FAIL", "Isolation check did not hold")


def _permission_probe(acceptance_path):
    before = sha256(acceptance_path.read_bytes())
    report = run_task(TASK.task_id, "unauthorized")
    after = sha256(acceptance_path.read_bytes())
    passed = report.status == "REJECTED" and not report.executions and before == after
    return {"case_id": "A1", "layer": "PERMISSION_GATE", "status": "PASS" if passed else "FAIL",
            "verification_status": report.status, "policy_reason": report.policy_reason,
            "container_count": len(report.executions), "run_id": report.run_id,
            "trusted_file_sha256_before": before, "trusted_file_sha256_after": after}


def _run_runtime_probes(driver, canary_path, work_root):
    rows = []
    baseline_hash = sha256(canary_path.read_bytes())
    for case in CASES:
        before = _api_health()
        if not all(before.values()):
            rows.append({"case_id": case, "layer": "SANDBOX_RUNTIME", "status": "INCONCLUSIVE",
                         "reason": "Private API preflight is unhealthy, busy or Live-enabled",
                         "api_before": before})
            break
        args = (case, str(canary_path), MEMORY_LIMIT_BYTES, SENTINEL_ENV)
        harness = driver + f"\n\nmain(*{args!r})\n".encode("utf-8")
        execution = _execute_fixed_tests(CODE, harness, f"attack-{case.lower()}",
                                         TASK.timeout_seconds, work_root=work_root)
        observations = _observations(execution.stdout)
        status, reason = _judge(case, execution, observations)
        intact = canary_path.is_file() and sha256(canary_path.read_bytes()) == baseline_hash
        after = _api_health()
        if not intact:
            status, reason = "FAIL", "Host-side synthetic marker changed"
        elif not all(after.values()) and status == "PASS":
            status, reason = "INCONCLUSIVE", "Private API was not healthy, idle and offline after the probe"
        rows.append({"case_id": case, "layer": "SANDBOX_RUNTIME", "status": status,
                     "reason": reason, "api_before": before, "api_after": after,
                     "host_marker_unchanged": intact, "observations": observations,
                     "execution": asdict(execution)})
        # Avoid proceeding to another probe if cleanup, host integrity or API health failed.
        if not execution.cleanup_confirmed or not execution.workspace_unchanged or not intact or not all(after.values()):
            break
    return rows


def main():
    argparse.ArgumentParser(description=__doc__).parse_args()
    os.environ["TRUSTBOUND_LOAD_DOTENV"] = "0"
    for key in ("VULTR_INFERENCE_API_KEY", "VULTR_API_KEY"):
        os.environ.pop(key, None)
    if not hasattr(os, "getuid"):
        raise SystemExit("Run this suite on the private Linux VM as trustbound-runner.")
    # Import after disabling dotenv. The Web process never imports this suite.
    from .runner_worker import WORK_ROOT, _configure_docker

    commit = (ROOT / "RELEASE_COMMIT").read_text().strip()
    if not re.fullmatch(r"[0-9a-f]{40}", commit):
        raise SystemExit("Expected an activated release with a valid RELEASE_COMMIT.")
    _configure_docker(os.getuid())
    driver = (ROOT / "fixtures/security/probe.py").read_bytes()
    acceptance = ROOT / "acceptance/billing_v1.py"
    os.environ[SENTINEL_ENV] = secrets.token_hex(16)
    with tempfile.TemporaryDirectory(prefix="attack-canary-", dir=WORK_ROOT) as directory:
        canary = Path(directory) / "synthetic-marker"
        canary.write_text(secrets.token_hex(16))
        policy = _permission_probe(acceptance)
        rows = [policy]
        if policy["status"] == "PASS":
            rows.extend(_run_runtime_probes(driver, canary, WORK_ROOT))
    statuses = {row["status"] for row in rows}
    acceptance_intact = sha256(acceptance.read_bytes()) == policy["trusted_file_sha256_before"]
    if not acceptance_intact or "FAIL" in statuses:
        outcome = "FAIL"
    elif len(rows) == len(CASES) + 1 and statuses == {"PASS"}:
        outcome = "PASS"
    else:
        outcome = "INCONCLUSIVE"
    print(json.dumps({"suite": "trustbound-security-a1-a5", "run_id": uuid.uuid4().hex,
                      "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                      "release_commit": commit, "source": "REAL_ROOTLESS_DOCKER",
                      "policy": {"network": "none", "memory_bytes": MEMORY_LIMIT_BYTES,
                                 "cpu_nanos": CPU_LIMIT_NANOS, "pids": PID_LIMIT,
                                 "wall_seconds": TASK.timeout_seconds, "uid_gid": "65534:65534"},
                      "status": outcome, "acceptance_unchanged": acceptance_intact,
                      "results": rows}, indent=2))
    return 0 if outcome == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
