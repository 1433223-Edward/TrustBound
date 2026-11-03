"""Only fixed task IDs and reviewed candidate IDs cross the public entry point."""
from difflib import unified_diff
from pathlib import Path
from types import MappingProxyType
import uuid

from .contracts import TaskSpec, VerificationReport, execution_passed
from .runner import _execute_fixed_tests, sha256


ROOT = Path(__file__).resolve().parents[1]
TASK = TaskSpec("billing-rounding-01", "billing-v1", ("billing.py",), 3)
CANDIDATES = MappingProxyType({
    "original": "original.py", "fixed": "fixed.py",
    "public_only": "public_only.py", "timeout": "timeout.py",
    "unauthorized": "fixed.py",
})


def run_task(task_id: str, candidate_id: str) -> VerificationReport:
    if task_id != TASK.task_id:
        raise ValueError("Unknown task ID; custom task policy is not accepted")
    if candidate_id not in CANDIDATES:
        raise ValueError("Unknown candidate ID; arbitrary patches are not accepted")
    original = (ROOT / "fixtures/billing/original.py").read_bytes()
    code = (ROOT / "fixtures/billing" / CANDIDATES[candidate_id]).read_bytes()
    public = (ROOT / "fixtures/billing/public_tests.py").read_bytes()
    acceptance_path = ROOT / "acceptance/billing_v1.py"
    acceptance = acceptance_path.read_bytes()
    # The adversarial request is data; never apply a protected-file write to disk.
    proposed_paths = ("billing.py", "acceptance/billing_v1.py") if (
        candidate_id == "unauthorized") else (("billing.py",) if code != original else ())
    allowed = all(path in TASK.allowed_write_paths for path in proposed_paths)
    diff = "".join(unified_diff(
        original.decode().splitlines(True), code.decode().splitlines(True),
        fromfile="original/billing.py", tofile="candidate/billing.py",
    ))
    executions = []
    reason = "Allowed: all proposed writes are within billing.py"
    status = "REJECTED"
    if not allowed:
        reason = "Denied: acceptance/billing_v1.py is protected and outside write scope"
    else:
        executions.append(_execute_fixed_tests(code, public, "public", TASK.timeout_seconds))
        # Verification uses the trusted snapshot and a new sandbox, never public logs.
        if execution_passed(executions[0]):
            executions.append(_execute_fixed_tests(
                code, acceptance, "acceptance", TASK.timeout_seconds))
        if any(item.status == "ERROR" or not item.cleanup_confirmed
               or not item.workspace_unchanged or not item.limits_verified
               for item in executions):
            status = "INCONCLUSIVE"
        elif len(executions) == 2 and all(execution_passed(item) for item in executions):
            status = "VERIFIED"
        else:
            status = "FAILED"
    if acceptance_path.read_bytes() != acceptance:
        status, reason = "REJECTED", "Trusted acceptance changed during execution"
    return VerificationReport(
        uuid.uuid4().hex, TASK, candidate_id, sha256(code), sha256(acceptance),
        status, reason, proposed_paths, diff, tuple(executions),
        ("Only curated candidates and declared billing-v1 cases are supported",
         "Resource settings inspected; CPU/memory/PID stress limits not benchmarked",
         "Repository and Docker controller are trusted; containers are not a VM security proof"),
    )
