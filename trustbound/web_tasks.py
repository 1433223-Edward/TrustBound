"""Trusted task metadata and mode dispatch; execution stays in the existing service."""
from dataclasses import asdict
import json
import os

from .executor import run_executor
from .inference import DEFAULT_MODEL, VultrClient
from .runner import sha256
from .service import CANDIDATES, ROOT, TASK, run_task
from .adversarial import build_context, final_decision, offline_adversarial_client, run_adversarial
from .adversarial_contracts import AdversarialReport


def task_details():
    return {
        "spec": asdict(TASK), "title": "Currency rounding",
        "description": "修复金额转换时的小数截断错误，验证正负半分边界。",
        "goal": "将十进制金额字符串转换为整数分，最近值舍入，半分远离零。",
        "constraints": ["Only billing.py may change", "Acceptance tests are protected",
                        "No network · no host credentials", "3s execution deadline"],
        "acceptance_goals": ["1.239 → 124 cents", "1.005 → 101 cents", "−1.005 → −101 cents"],
        "original": {"path": "billing.py", "content": (ROOT / "fixtures/billing/original.py").read_text(encoding="utf-8")},
    }


def live_availability():
    if not os.environ.get("VULTR_INFERENCE_API_KEY", "").strip():
        return {"enabled": False, "reason": "MISSING_VULTR_INFERENCE_API_KEY"}
    if not os.environ.get("VULTR_MODEL", "").strip():
        return {"enabled": False, "reason": "MISSING_VULTR_MODEL"}
    if os.environ.get("TRUSTBOUND_ENABLE_LIVE") != "1":
        return {"enabled": False, "reason": "LIVE_REQUIRES_EXPLICIT_OPT_IN"}
    return {"enabled": True, "reason": "CONFIGURED_NOT_AUTHENTICATED_UNTIL_REQUEST"}


def offline_client():
    """Inject a fixed model response only; never replace Runner or Verifier results."""
    def transport(method, path, payload, api_key, timeout):
        if method == "GET" and path.startswith("/models"):
            return {"data": [{"id": DEFAULT_MODEL, "architecture": {"output_modalities": ["text"]}, "pricing": {}}]}
        content = "READY" if payload["max_completion_tokens"] == 64 else json.dumps({
            "analysis": "OFFLINE SIMULATION: use the reviewed half-up Decimal replacement.",
            "files": {"billing.py": (ROOT / "fixtures/billing/fixed.py").read_text(encoding="utf-8")},
        })
        return {"model": DEFAULT_MODEL, "choices": [{"finish_reason": "stop", "message": {"content": content}}],
                "usage": None}
    return VultrClient("offline-placeholder-not-a-credential", transport=transport)


def _execute_base_run(task_id, mode, candidate):
    if mode == "fixture":
        code = (ROOT / "fixtures/billing" / CANDIDATES[candidate]).read_bytes()
        verification = run_task(task_id, candidate).to_dict()
        if sha256(code) != verification["artifact_hash"]:
            raise RuntimeError("Fixture changed during execution")
        return {"proposal": None, "candidate": {"path": "billing.py", "content": code.decode("utf-8"), "source": "FIXTURE"},
                "verification": verification, "executor": None, "llm_source": "NONE", "error": None}
    if mode == "offline_executor":
        result = run_executor(offline_client(), model_id=DEFAULT_MODEL)
    elif os.environ.get("TRUSTBOUND_EXECUTOR_SINGLE_PROPOSAL") == "1":
        # The operator already checked credentials. Reserve room for the JSON
        # proposal after reasoning without adding a second request or retry.
        client = VultrClient(timeout=60, max_attempts=1, output_limit=4096)
        result = run_executor(client, smoke_check=False, proposal_tokens=4096,
                              reasoning_tokens=1536)
    else:
        result = run_executor(VultrClient())
    suggestion = result.get("model_suggestion") or {}
    return {"proposal": suggestion.get("parsed"), "candidate": None,
            "verification": result.get("verification"), "executor": result,
            "llm_source": result["source"],
            "error": {"code": result["error"] or result["status"], "message": "Executor 未产生正式验收报告。"}
            if result.get("verification") is None else None}


def complete_verification(outcome, task_id, adversarial_mode, adversarial_fixture):
    """Attach Stage 2 evidence to an already formally checked candidate."""
    verification = outcome["verification"]
    adversarial = None
    if verification is not None and adversarial_mode != "off":
        content = (outcome.get("candidate") or {}).get("content")
        if content is None:
            content = (outcome.get("proposal") or {}).get("files", {}).get("billing.py", "")
        code = content.encode("utf-8")
        artifact_hash = verification["artifact_hash"]
        if verification["status"] != "VERIFIED":
            adversarial = AdversarialReport(task_id, artifact_hash, "SKIPPED", "NO_LIVE_CALL",
                                            "Formal acceptance did not verify the candidate; no adversarial execution authorized", {})
        elif adversarial_mode == "live" and not live_availability()["enabled"]:
            adversarial = AdversarialReport(task_id, artifact_hash, "UNAVAILABLE", "NO_LIVE_CALL",
                                            live_availability()["reason"], build_context(code, artifact_hash))
        else:
            # Fresh client and freshly constructed messages; executor conversations
            # and its explanation never cross this boundary into the challenger.
            if adversarial_mode == "offline":
                adversarial = run_adversarial(code, artifact_hash, offline_adversarial_client(adversarial_fixture),
                                              model_id=DEFAULT_MODEL)
            else:
                client = VultrClient(timeout=60, max_attempts=1, output_limit=4096)
                adversarial = run_adversarial(code, artifact_hash, client, completion_tokens=4096, compact=True)
    outcome["adversarial_report"] = adversarial.to_dict() if adversarial else None
    outcome["final_decision"] = final_decision(verification, adversarial) if verification else None
    return outcome


def _execute_web_run(task_id, mode, candidate, adversarial_mode="off", adversarial_fixture="standard",
                    *, recovery_mode="off", recovery_fixture="fixed", run_id=None, on_progress=None):
    if recovery_mode not in {"off", "offline", "live"} or (recovery_mode != "off" and adversarial_mode == "off"):
        raise ValueError("Recovery requires a declared mode and the full adversarial stage")
    if recovery_mode == "live" and (os.environ.get("TRUSTBOUND_ENABLE_RECOVERY_LIVE") != "1" or not live_availability()["enabled"]):
        raise ValueError("Live recovery requires separate host authorization and valid configuration")
    outcome = complete_verification(_execute_base_run(task_id, mode, candidate), task_id,
                                    adversarial_mode, adversarial_fixture)
    if recovery_mode == "off":
        return outcome
    # The same Web job owns every attempt; no second scheduler or execution path.
    from .recovery import run_recovery, offline_recovery_client
    from .executor import validate_billing_code
    from .service import verify_patch

    def verify(proposal):
        files = proposal["files"]
        if set(files) == set(TASK.allowed_write_paths):
            validate_billing_code(files["billing.py"])
        verification = verify_patch(task_id, files).to_dict()
        candidate = {"path": "billing.py", "content": files.get("billing.py", (ROOT / "fixtures/billing/original.py").read_bytes().decode("utf-8")), "source": "RECOVERY_PROPOSAL"}
        result = {"proposal": proposal, "candidate": candidate, "verification": verification,
                  "executor": None, "llm_source": "OFFLINE_TEST" if recovery_mode == "offline" else "VULTR_LIVE_HTTP", "error": None}
        return complete_verification(result, task_id, adversarial_mode, adversarial_fixture)

    def client_factory(index):
        return offline_recovery_client(recovery_fixture, index) if recovery_mode == "offline" else VultrClient()

    return run_recovery(outcome, verify, client_factory, run_id=run_id, on_progress=on_progress)


def execute_web_run(task_id, mode, candidate, adversarial_mode="off", adversarial_fixture="standard", **options):
    """Share only the host budget across clients; preserve each agent's own messages."""
    from .inference import TaskInferenceBudget, task_inference_budget
    budget = TaskInferenceBudget()
    with task_inference_budget(budget):
        outcome = _execute_web_run(task_id, mode, candidate, adversarial_mode, adversarial_fixture, **options)
    outcome["inference_usage"] = budget.to_dict()
    return outcome
