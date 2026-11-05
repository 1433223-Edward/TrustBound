"""Linux worker that owns the Rootless Docker connection and trusted test selection."""
from dataclasses import asdict, replace
import json
import os
from pathlib import Path
import re
import socket
import struct

from .adversarial import AMOUNT, MAX_CHALLENGES, REQUIREMENT_ID, build_driver, reference_cents
from .adversarial_contracts import AdversarialChallenge, ChallengeValidationResult
from .executor import validate_billing_code
from .runner import _execute_fixed_tests, checked, sha256
from .runner_ipc import (MAX_CANDIDATE_BYTES, MAX_OUTPUT_CHARS, MAX_REQUEST,
                         MAX_RESPONSE, read_message, write_message)
from .service import CANDIDATES, ROOT, TASK


SOCKET_PATH = "/run/trustbound-runner.sock"
WORK_ROOT = Path("/var/lib/trustbound-runner")
FIXED_TESTS = {"public": "fixtures/billing/public_tests.py",
               "acceptance": "acceptance/billing_v1.py"}


def _challenge_driver(cases):
    if type(cases) is not list or not 1 <= len(cases) <= MAX_CHALLENGES:
        raise ValueError("Invalid challenge count")
    ids, amounts, rows = set(), set(), []
    for case in cases:
        if type(case) is not dict or set(case) != {"id", "amount"}:
            raise ValueError("Invalid challenge fields")
        case_id, amount = case["id"], case["amount"]
        if (type(case_id) is not str or not re.fullmatch(r"challenge-[1-4]", case_id)
                or type(amount) is not str or not AMOUNT.fullmatch(amount)
                or case_id in ids or amount in amounts):
            raise ValueError("Invalid or duplicate challenge")
        ids.add(case_id)
        amounts.add(amount)
        challenge = AdversarialChallenge(case_id, amount, REQUIREMENT_ID, "")
        rows.append(ChallengeValidationResult(challenge, "INCONCLUSIVE",
                                              expected=reference_cents(amount)))
    return build_driver(rows)


def execute_request(request):
    if type(request) is not dict or request.get("task_id") != TASK.task_id:
        raise ValueError("Unknown task")
    phase = request.get("phase")
    fields = {"task_id", "phase", "candidate", "candidate_sha256"}
    if phase == "adversarial":
        fields.add("cases")
    elif type(phase) is not str or phase not in FIXED_TESTS:
        raise ValueError("Unknown phase")
    if set(request) != fields or type(request["candidate"]) is not str:
        raise ValueError("Invalid request fields")
    candidate = request["candidate"]
    code = candidate.encode("utf-8")
    if not 1 <= len(code) <= MAX_CANDIDATE_BYTES or sha256(code) != request["candidate_sha256"]:
        raise ValueError("Invalid candidate size or identity")
    if phase == "adversarial":
        validate_billing_code(candidate)
        tests = _challenge_driver(request["cases"])
    else:
        # Exact shipped fixtures preserve the policy and timeout demonstrations.
        reviewed = any(code == (ROOT / "fixtures/billing" / filename).read_bytes()
                       for filename in set(CANDIDATES.values()))
        if not reviewed:
            validate_billing_code(candidate)
        tests = (ROOT / FIXED_TESTS[phase]).read_bytes()
    result = _execute_fixed_tests(code, tests, phase, TASK.timeout_seconds, work_root=WORK_ROOT)
    if len(result.stdout) > MAX_OUTPUT_CHARS or len(result.stderr) > MAX_OUTPUT_CHARS:
        return replace(result, status="ERROR", stdout=result.stdout[:MAX_OUTPUT_CHARS],
                       stderr=result.stderr[:MAX_OUTPUT_CHARS], error="RUNNER_OUTPUT_LIMIT_EXCEEDED")
    return replace(result, error="RUNNER_SANDBOX_ERROR") if result.error else result


def _handle(connection, web_uid):
    credentials = connection.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, struct.calcsize("3i"))
    _, uid, _ = struct.unpack("3i", credentials)
    if uid != web_uid:
        return
    try:
        response = asdict(execute_request(read_message(connection, MAX_REQUEST, 3)))
    except (OSError, ValueError, TypeError, RecursionError):
        response = {"error": "RUNNER_REQUEST_REJECTED_OR_UNAVAILABLE"}
    try:
        write_message(connection, response, MAX_RESPONSE, 3)
    except OSError:
        # The Web client can disconnect while a sandbox finishes and is cleaned up.
        pass


def _configure_docker(uid):
    import pwd

    if uid == 0 or uid != pwd.getpwnam("trustbound-runner").pw_uid:
        raise RuntimeError("Expected the dedicated runner identity")
    parent = WORK_ROOT.stat()
    if WORK_ROOT.is_symlink() or parent.st_uid != uid or parent.st_mode & 0o777 != 0o700:
        raise RuntimeError("Expected a private runner workspace")
    os.environ.pop("DOCKER_CONTEXT", None)
    os.environ["DOCKER_HOST"] = f"unix:///run/user/{uid}/docker.sock"
    info = json.loads(checked("info", "--format", "{{json .}}"))
    if ("name=rootless" not in info["SecurityOptions"] or str(info["CgroupVersion"]) != "2"
            or info["CgroupDriver"] != "systemd"):
        raise RuntimeError("Expected Rootless Docker with systemd and cgroup v2")
    controllers = Path(f"/sys/fs/cgroup/user.slice/user-{uid}.slice/user@{uid}.service/cgroup.controllers")
    if not {"cpu", "memory", "pids"} <= set(controllers.read_text().split()):
        raise RuntimeError("Required Rootless Docker cgroup controllers are not delegated")


def main():
    import pwd

    if os.environ.get("LISTEN_PID") != str(os.getpid()) or os.environ.get("LISTEN_FDS") != "1":
        raise SystemExit("Start the worker through its systemd socket")
    _configure_docker(os.getuid())
    web_uid = pwd.getpwnam("trustbound-web").pw_uid
    with socket.socket(fileno=3) as listener:
        if listener.family != socket.AF_UNIX or listener.getsockname() != SOCKET_PATH:
            raise SystemExit("Unexpected runner socket")
        while True:
            connection, _ = listener.accept()
            with connection:
                _handle(connection, web_uid)


if __name__ == "__main__":
    main()
