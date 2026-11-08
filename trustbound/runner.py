"""Trusted controller for fixed Python tests in disposable Linux containers."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import uuid

from .contracts import ExecutionResult


IMAGE = "python@sha256:b18b261e1b4974b4f321451ad5251ded85abb22c2b8b262da527dda1d031ab30"
MEMORY_LIMIT_BYTES = 128 * 1024 * 1024
CPU_LIMIT_NANOS = 500_000_000
PID_LIMIT = 32
WEB_WORKER_LABEL = "org.trustbound.owner=private-web-runner-v1"


def sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def docker(*arguments, timeout=30):
    executable = shutil.which("docker")
    if not executable and os.name == "nt":
        executable = str(Path(os.environ["LOCALAPPDATA"])
                         / "Programs/DockerDesktop/resources/bin/docker.exe")
    if not executable:
        raise RuntimeError("Docker CLI not found")
    return subprocess.run([executable, *arguments], capture_output=True,
                          text=True, encoding="utf-8", errors="replace", timeout=timeout)


def checked(*arguments):
    result = docker(*arguments)
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip())
    return result.stdout


def _execute_fixed_tests(code: bytes, tests: bytes, phase: str, timeout_seconds: int, *, work_root=None, worker_owned=False):
    """Stage the fixed candidate and independently selected test file."""
    return _execute_sandbox({"billing.py": code, "checks.py": tests}, "checks.py", phase,
                            sha256(code), sha256(tests), timeout_seconds,
                            work_root=work_root, worker_owned=worker_owned)


def _execute_sandbox(payload, script, phase, artifact_hash, test_hash, timeout_seconds,
                     *, work_root=None, worker_owned=False):
    """Stage validated bytes and run a trusted, fixed script path inside Docker."""
    name = "trustbound-" + uuid.uuid4().hex
    state, stdout, stderr, reason, error = {}, "", "", None, None
    status, cleanup, limits_verified = "ERROR", False, False
    with tempfile.TemporaryDirectory(prefix="trustbound-", dir=work_root) as directory:
        workspace = Path(directory)
        for filename, data in payload.items():
            path = workspace / filename
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
            if work_root is not None:
                path.chmod(0o444)
        if work_root is not None:
            # Only the mounted staging tree is readable by the mapped UID.
            for directory in workspace.rglob("*"):
                if directory.is_dir():
                    directory.chmod(0o755)
            workspace.chmod(0o755)
        try:
            checked(
                "create", "--pull", "never", "--name", name,
                *(("--label", WEB_WORKER_LABEL) if worker_owned else ()),
                "--network", "none", "--read-only", "--user", "65534:65534",
                "--cap-drop", "ALL", "--security-opt", "no-new-privileges",
                "--memory", str(MEMORY_LIMIT_BYTES), "--memory-swap", str(MEMORY_LIMIT_BYTES),
                "--cpus", str(CPU_LIMIT_NANOS / 1_000_000_000),
                "--pids-limit", str(PID_LIMIT), "--log-driver", "local",
                "--log-opt", "max-size=1m", "--log-opt", "max-file=2",
                "--mount", f"type=bind,src={workspace},dst=/work,readonly",
                IMAGE, "python", "-I", "-B", "-u", f"/work/{script}",
            )
            inspected = json.loads(checked("inspect", name))[0]
            host, mounts = inspected["HostConfig"], inspected["Mounts"]
            limits_verified = (
                host["NetworkMode"] == "none" and host["ReadonlyRootfs"]
                and inspected["Config"]["User"] == "65534:65534"
                and host["CapDrop"] == ["ALL"]
                and "no-new-privileges" in host["SecurityOpt"]
                and host["Memory"] == host["MemorySwap"] == MEMORY_LIMIT_BYTES
                and host["NanoCpus"] == CPU_LIMIT_NANOS and host["PidsLimit"] == PID_LIMIT
                and len(mounts) == 1 and mounts[0]["Destination"] == "/work"
                and not mounts[0]["RW"] and mounts[0]["Type"] == "bind"
                and not host["Privileged"]
            )
            if not limits_verified:
                raise RuntimeError("Sandbox configuration did not match trusted policy")
            checked("start", name)
            try:
                waited = docker("wait", name, timeout=timeout_seconds)
                if waited.returncode:
                    raise RuntimeError(waited.stderr)
                status = "EXITED"
            except subprocess.TimeoutExpired:
                status = "TIMED_OUT"
                reason = f"Host deadline exceeded: {timeout_seconds} seconds after start"
                checked("kill", name)
            state = json.loads(checked("inspect", name, "--format", "{{json .State}}"))
            logs = docker("logs", name)
            if logs.returncode:
                raise RuntimeError(logs.stderr)
            stdout, stderr = logs.stdout, logs.stderr
        except (OSError, RuntimeError, subprocess.TimeoutExpired, ValueError) as exc:
            status, error = "ERROR", str(exc)
        finally:
            # A controller failure must not skip removal or become a success result.
            try:
                removed = docker("rm", "-f", name)
                remaining = docker("ps", "-a", "--filter", f"name=^/{name}$", "-q")
                cleanup = (removed.returncode == 0 and remaining.returncode == 0
                           and not remaining.stdout.strip())
            except (OSError, RuntimeError, subprocess.TimeoutExpired) as exc:
                error = f"{error or ''} Cleanup error: {exc}"
        try:
            unchanged = all((workspace / filename).read_bytes() == data
                            for filename, data in payload.items())
        except OSError:
            unchanged = False
    return ExecutionResult(
        phase, name, IMAGE, artifact_hash, test_hash, status,
        state.get("ExitCode"), stdout, stderr, reason, cleanup, unchanged,
        limits_verified, error,
        oom_killed=state.get("OOMKilled") if type(state.get("OOMKilled")) is bool else None,
    )
