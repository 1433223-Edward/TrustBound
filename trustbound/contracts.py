"""Small immutable records for trusted policy, execution evidence and decisions."""
from dataclasses import asdict, dataclass
from typing import Literal


@dataclass(frozen=True)
class TaskSpec:
    task_id: str
    acceptance_id: str
    allowed_write_paths: tuple[str, ...]
    timeout_seconds: int

    def __post_init__(self):
        if not self.task_id or not self.acceptance_id:
            raise ValueError("Task and acceptance IDs are required")
        if not self.allowed_write_paths or not 1 <= self.timeout_seconds <= 30:
            raise ValueError("Invalid write scope or timeout budget")
        if any(path.startswith(("/", "\\")) or ".." in path.split("/")
               or "\\" in path or ":" in path for path in self.allowed_write_paths):
            raise ValueError("Write paths must be relative canonical paths")


@dataclass(frozen=True)
class ExecutionResult:
    phase: str
    container_name: str
    image: str
    artifact_hash: str
    test_hash: str
    status: Literal["EXITED", "TIMED_OUT", "ERROR"]
    exit_code: int | None
    stdout: str
    stderr: str
    timeout_reason: str | None
    cleanup_confirmed: bool
    workspace_unchanged: bool
    limits_verified: bool
    error: str | None = None
    oom_killed: bool | None = None

    def __post_init__(self):
        if self.status not in ("EXITED", "TIMED_OUT", "ERROR"):
            raise ValueError("Unknown execution status")
        if self.status == "EXITED" and self.exit_code is None:
            raise ValueError("Completed execution needs an exit code")
        if self.status == "TIMED_OUT" and not self.timeout_reason:
            raise ValueError("Timeout requires a reason")


@dataclass(frozen=True)
class VerificationReport:
    run_id: str
    task: TaskSpec
    candidate_id: str
    artifact_hash: str
    acceptance_hash: str
    status: Literal["VERIFIED", "FAILED", "INCONCLUSIVE", "REJECTED"]
    policy_reason: str
    changed_paths: tuple[str, ...]
    diff: str
    executions: tuple[ExecutionResult, ...]
    limitations: tuple[str, ...]

    def __post_init__(self):
        if self.status not in ("VERIFIED", "FAILED", "INCONCLUSIVE", "REJECTED"):
            raise ValueError("Unknown verification status")
        if self.status == "VERIFIED":
            if {item.phase for item in self.executions} != {"public", "acceptance"}:
                raise ValueError("VERIFIED requires public and independent acceptance")
            if not all(execution_passed(item) for item in self.executions):
                raise ValueError("VERIFIED requires successful, cleaned, intact execution")
            if any(item.artifact_hash != self.artifact_hash for item in self.executions):
                raise ValueError("Evidence must match the candidate artifact")
            if next(item.test_hash for item in self.executions
                    if item.phase == "acceptance") != self.acceptance_hash:
                raise ValueError("Acceptance evidence must match trusted tests")

    def to_dict(self):
        return asdict(self)


def execution_passed(item: ExecutionResult) -> bool:
    return (item.status == "EXITED" and item.exit_code == 0
            and item.cleanup_confirmed and item.workspace_unchanged
            and item.limits_verified and item.error is None)
