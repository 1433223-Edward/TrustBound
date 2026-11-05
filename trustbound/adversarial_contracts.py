"""Additive adversarial contracts; Stage 1 verification records remain unchanged."""
from dataclasses import asdict, dataclass

from .contracts import ExecutionResult


@dataclass(frozen=True)
class AdversarialChallenge:
    challenge_id: str
    amount: str
    requirement_id: str
    reason: str


@dataclass(frozen=True)
class ChallengeValidationResult:
    challenge: AdversarialChallenge
    status: str
    expected: int | None = None
    actual: int | str | None = None
    actual_type: str | None = None
    reason: str = ""

    def __post_init__(self):
        if self.status not in {"INVALID", "INCONCLUSIVE", "CONFIRMED", "NOT_CONFIRMED"}:
            raise ValueError("Invalid challenge validation status")
        if self.status == "CONFIRMED" and (type(self.expected) is not int or not self.actual_type):
            raise ValueError("Confirmed challenges require a reference and observed result")


@dataclass(frozen=True)
class AdversarialReport:
    task_id: str
    artifact_hash: str
    status: str
    source: str
    reason: str
    context: dict
    challenges: tuple[ChallengeValidationResult, ...] = ()
    execution: ExecutionResult | None = None
    driver_hash: str | None = None
    raw_response: str | None = None
    calls: tuple[dict, ...] = ()
    request_budget: dict | None = None

    def __post_init__(self):
        if self.status not in {"SKIPPED", "UNAVAILABLE", "GENERATION_FAILED", "INCOMPLETE", "COMPLETED"}:
            raise ValueError("Invalid adversarial report status")
        if self.status == "COMPLETED" or any(row.status == "CONFIRMED" for row in self.challenges):
            e = self.execution
            confirmed = any(row.status == "CONFIRMED" for row in self.challenges)
            if (not e or e.status != "EXITED" or e.exit_code != int(confirmed)
                    or e.phase != "adversarial" or not e.cleanup_confirmed or not e.workspace_unchanged
                    or not e.limits_verified or e.error or e.artifact_hash != self.artifact_hash
                    or e.test_hash != self.driver_hash):
                raise ValueError("Completed adversarial validation needs intact matching sandbox evidence")
            if not any(row.status in {"CONFIRMED", "NOT_CONFIRMED"} for row in self.challenges):
                raise ValueError("Completed validation needs at least one executed challenge")

    def to_dict(self):
        result = asdict(self)
        request_budget = result.pop("request_budget")
        result.update(generated_count=len(self.challenges) if self.challenges else None,
                      valid_count=sum(row.status != "INVALID" for row in self.challenges),
                      confirmed_count=sum(row.status == "CONFIRMED" for row in self.challenges),
                      generation_parsed=self.raw_response is not None and bool(self.challenges),
                      budget=request_budget or {"max_challenges": 4, "max_completion_tokens": 768, "timeout_seconds": 30, "max_attempts": 2})
        return result
