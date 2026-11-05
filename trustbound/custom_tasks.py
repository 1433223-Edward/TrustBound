"""Opt-in private Custom Task execution with frozen, user-supplied assertions."""
from dataclasses import asdict
from difflib import unified_diff
import json
import os
from typing import ClassVar
import uuid

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .contracts import VerificationReport, execution_passed
from .custom_policy import (CUSTOM_TASK, MAX_CASES, MAX_EXPECTED, MAX_VALUE,
                            build_custom_driver, parse_custom_observations, validate_solution)
from .executor import parse_proposal
from .runner import sha256
from .runner_ipc import run_through_worker, worker_enabled


class CustomCase(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)
    input: int = Field(ge=-MAX_VALUE, le=MAX_VALUE)
    expected: int = Field(ge=-MAX_EXPECTED, le=MAX_EXPECTED)


class CustomRunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)
    task_id: ClassVar[str] = CUSTOM_TASK.task_id
    mode: ClassVar[str] = "custom_offline"
    candidate_id: ClassVar[None] = None
    adversarial_mode: ClassVar[str] = "off"
    adversarial_fixture: ClassVar[None] = None
    recovery_mode: ClassVar[str] = "off"
    recovery_fixture: ClassVar[None] = None
    source: str = Field(min_length=1, max_length=2000)
    requirements: str = Field(min_length=1, max_length=800)
    replacement: str | None = Field(default=None, min_length=1, max_length=2000)
    public: tuple[CustomCase, ...] = Field(strict=False, min_length=1, max_length=MAX_CASES)
    acceptance: tuple[CustomCase, ...] = Field(default=(), strict=False, max_length=MAX_CASES)
    challenges: tuple[CustomCase, ...] = Field(default=(), strict=False, max_length=MAX_CASES)

    @model_validator(mode="after")
    def validate_inputs(self):
        values = [case.input for case in (*self.public, *self.acceptance, *self.challenges)]
        if len(values) != len(set(values)):
            raise ValueError("Use distinct inputs across all phases")
        if not self.requirements.strip():
            raise ValueError("Requirements must be nonempty")
        for text in (self.source, self.requirements, self.replacement or ""):
            text.encode("utf-8")
        return self


def custom_enabled():
    return (os.environ.get("TRUSTBOUND_ENABLE_CUSTOM_TASK") == "1" and worker_enabled()
            and os.environ.get("TRUSTBOUND_ENABLE_LIVE") != "1"
            and os.environ.get("TRUSTBOUND_ENABLE_RECOVERY_LIVE") != "1")


def _check_cases(code, phase, cases):
    inputs = [case.input for case in cases]
    driver = build_custom_driver(inputs)
    execution = run_through_worker(code, driver, phase, task_id=CUSTOM_TASK.task_id, cases=inputs)
    if not execution_passed(execution):
        return execution, "INCONCLUSIVE", []
    try:
        observed = parse_custom_observations(execution.stdout, inputs)
    except (ValueError, RecursionError):
        return execution, "INCONCLUSIVE", []
    checked = [dict(row, expected=case.expected,
                    matched=row["error"] is None and row["actual"] == case.expected)
               for row, case in zip(observed, cases)]
    return execution, ("VERIFIED" if all(row["matched"] for row in checked) else "FAILED"), checked


def execute_custom(body):
    """Validate a user-provided replacement via the existing proposal parser.

    The private version never asks a model to infer an oracle from natural language.
    Independent evidence comes from separate containers and host-side comparison.
    """
    candidate = body.source
    proposal = None
    if body.replacement is not None:
        proposal = parse_proposal(json.dumps({
            "analysis": "Operator-supplied offline proposal; no model inference.",
            "files": {"solution.py": body.replacement},
        }))
        candidate = proposal["files"]["solution.py"]
    code = candidate.encode("utf-8")
    fixed_cases = body.model_dump(mode="json", include={"public", "acceptance", "challenges"})
    cases_hash = sha256(json.dumps(fixed_cases, sort_keys=True, separators=(",", ":")).encode())
    acceptance_hash = sha256(build_custom_driver([c.input for c in body.acceptance])) if body.acceptance else sha256(b"")
    executions, observed, challenge_execution = [], {}, None
    policy_reason = "Allowed: only the restricted solution.py expression may run"
    try:
        validate_solution(candidate)
    except ValueError:
        formal, reason = "REJECTED", "Unsupported Python profile; no container started"
        policy_reason = reason
    else:
        execution, formal, observed["public"] = _check_cases(code, "public", body.public)
        executions.append(execution)
        reason = ("Public cases did not all pass" if formal == "FAILED"
                  else "Public execution evidence is incomplete")
        if formal == "VERIFIED":
            if not body.acceptance:
                formal, reason = "INCONCLUSIVE", "No independent acceptance cases supplied"
            else:
                execution, formal, observed["acceptance"] = _check_cases(code, "acceptance", body.acceptance)
                executions.append(execution)
                reason = ("Independent execution evidence is incomplete" if formal == "INCONCLUSIVE"
                          else "Formal comparison against frozen user-supplied cases")
    final = formal
    challenge_status = "NOT_REQUESTED"
    if body.challenges:
        challenge_status = "SKIPPED"
        if formal == "VERIFIED":
            challenge_execution, final, observed["challenges"] = _check_cases(
                code, "adversarial", body.challenges)
            challenge_status = "INCONCLUSIVE" if final == "INCONCLUSIVE" else "COMPLETED"
            reason = {"FAILED": "Supplied counterexample confirmed",
                      "INCONCLUSIVE": "Challenge execution evidence is incomplete",
                      "VERIFIED": "Comparison against frozen user-supplied challenge cases"}[final]
    scope = "Against supplied tests only; natural-language requirements are not independently proven"
    report = VerificationReport(
        uuid.uuid4().hex, CUSTOM_TASK, "custom-offline", sha256(code), acceptance_hash, formal,
        policy_reason, ("solution.py",) if body.source != candidate else (),
        "".join(unified_diff(body.source.splitlines(True), candidate.splitlines(True),
                             fromfile="original/solution.py", tofile="candidate/solution.py")),
        tuple(executions), (scope,),
    )
    return {"proposal": proposal, "candidate": {"path": "solution.py", "content": candidate,
                                                "source": "OPERATOR_SUPPLIED"},
            "verification": report.to_dict(),
            "llm_source": "NONE",
            "final_decision": {"status": final, "formal_status": formal, "reason": reason,
                               "scope": scope, "artifact_hash": report.artifact_hash,
                               "formal_report_id": report.run_id, "adversarial_status": challenge_status},
            "custom_evidence": {"requirements": body.requirements, "cases_sha256": cases_hash,
                                "declared_cases": fixed_cases, "observations": observed,
                                "challenge_execution": asdict(challenge_execution) if challenge_execution else None}}
