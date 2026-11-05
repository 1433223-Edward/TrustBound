"""Recovery control tests use captured Stage 2 records and explicit verification doubles.

These tests do not claim fresh container execution; the HTTP integration script does.
"""
from copy import deepcopy
import json
import unittest
from unittest.mock import Mock, patch

from trustbound.recovery import (run_recovery, offline_recovery_client, recovery_eligibility,
    build_recovery_context, recovery_messages, complete_success, confirmed_failures)
from trustbound.runner import sha256
from trustbound.service import ROOT, TASK

RECORDS = json.loads((ROOT / "docs/adversarial-integration-results.json").read_text(encoding="utf-8"))


def outcome(experiment="E2"):
    record = deepcopy(next(r["snapshot"] for r in RECORDS if r["experiment"] == experiment))
    return {k: record.get(k) for k in ("candidate", "verification", "proposal", "executor", "llm_source",
                                      "adversarial_report", "final_decision", "error")}


def verified_double(proposal):
    """Synthetic per-version report for loop unit tests only."""
    correct = 'still incorrect' not in proposal["files"]["billing.py"]
    result = outcome("E1" if correct else "E2")
    code = proposal["files"]["billing.py"]
    artifact = sha256(code.encode())
    result["proposal"] = proposal
    result["candidate"]["content"] = code
    result["verification"]["artifact_hash"] = artifact
    result["adversarial_report"]["artifact_hash"] = artifact
    result["final_decision"]["artifact_hash"] = artifact
    for e in result["verification"]["executions"] + [result["adversarial_report"]["execution"]]:
        e["artifact_hash"] = artifact
    return result


class RecoveryTests(unittest.TestCase):
    def run_case(self, profile="fixed", initial=None, verify=verified_double, **options):
        return run_recovery(initial or outcome(), verify,
                            lambda index: offline_recovery_client(profile, index), run_id="unit-job", **options)

    def test_success_requires_fresh_formal_and_adversarial_evidence(self):
        original = outcome()
        result = self.run_case(initial=original)
        report = result["recovery_report"]
        self.assertEqual(report["final_status"], "VERIFIED")
        self.assertEqual(report["stop_reason"], "VERIFIED")
        self.assertEqual(len(report["attempts"]), 2)
        first, second = report["attempts"]
        self.assertEqual(first["final_decision"]["status"], "FAILED")
        self.assertEqual(first["candidate_hash"], second["previous_candidate_hash"])
        self.assertNotEqual(first["candidate_hash"], second["candidate_hash"])
        self.assertTrue(complete_success(second))
        self.assertEqual(original["final_decision"]["status"], "FAILED")
        self.assertEqual(second["context"]["remaining_recovery_attempts"], 1)

    def test_host_stops_after_two_distinct_unsuccessful_recoveries(self):
        report = self.run_case("exhausted")["recovery_report"]
        self.assertEqual(report["stop_reason"], "RECOVERY_LIMIT_REACHED")
        self.assertEqual(report["final_status"], "FAILED")
        self.assertEqual([a["attempt_index"] for a in report["attempts"]], [0, 1, 2])
        self.assertEqual(len({a["candidate_hash"] for a in report["attempts"]}), 3)
        self.assertEqual(report["attempts"][-1]["context"]["remaining_recovery_attempts"], 0)
        for value in [0, 3, True]:
            with self.assertRaises(ValueError):
                self.run_case(max_attempts=value)

    def test_permission_denial_stops_without_another_model_call(self):
        def denied(proposal):
            result = outcome()
            code = (ROOT / "fixtures/billing/original.py").read_bytes().decode()
            result["candidate"]["content"] = code
            v = result["verification"]
            v.update(status="REJECTED", artifact_hash=sha256(code.encode()), executions=[])
            result["adversarial_report"] = None
            result["final_decision"].update(status="REJECTED", artifact_hash=v["artifact_hash"])
            return result
        report = self.run_case("unauthorized", verify=denied)["recovery_report"]
        self.assertEqual(report["final_status"], "REJECTED")
        self.assertEqual(report["stop_reason"], "FORMAL_REJECTED")
        self.assertEqual(len(report["attempts"]), 2)

    def test_inconclusive_invalid_or_unavailable_stage_never_requests_recovery(self):
        for experiment in ["E3", "E4-timeout", "E4-failure", "E4-unavailable"]:
            factory = Mock(side_effect=AssertionError("Must not call recovery model"))
            result = run_recovery(outcome(experiment), Mock(), factory)
            self.assertEqual(result["recovery_report"]["final_status"], "INCONCLUSIVE")
            self.assertEqual(len(result["recovery_report"]["attempts"]), 1)
            factory.assert_not_called()

    def test_model_errors_are_counted_and_never_inherit_success(self):
        for profile in ["invalid_json", "empty", "failure", "timeout"]:
            verify = Mock(side_effect=AssertionError("Must not execute invalid response"))
            report = self.run_case(profile, verify=verify)["recovery_report"]
            self.assertEqual(report["final_status"], "INCONCLUSIVE")
            self.assertEqual(len(report["attempts"]), 2)
            self.assertIsNone(report["attempts"][-1]["verification"])
            self.assertTrue(report["attempts"][-1]["model_call_metadata"])
            verify.assert_not_called()

    def test_previous_candidate_success_cannot_validate_different_generated_code(self):
        result = self.run_case("exhausted", verify=lambda _: outcome("E1"))
        report = result["recovery_report"]
        self.assertEqual(report["stop_reason"], "CANDIDATE_IDENTITY_MISMATCH")
        self.assertEqual(report["final_status"], "INCONCLUSIVE")
        self.assertIsNone(report["attempts"][-1]["verification"])

    def test_cleanup_timeout_integrity_and_hash_failures_block_recovery(self):
        changes = [{"cleanup_confirmed": False}, {"workspace_unchanged": False}, {"limits_verified": False},
                   {"status": "TIMED_OUT", "exit_code": 137}, {"error": "Docker unavailable"},
                   {"artifact_hash": "old-code"}, {"test_hash": "wrong-tests"}]
        for change in changes:
            initial = outcome(); initial["verification"]["executions"][0].update(change)
            factory = Mock()
            result = run_recovery(initial, Mock(), factory)
            factory.assert_not_called()
            self.assertNotEqual(result["recovery_report"]["final_status"], "VERIFIED")

    def test_counterexamples_must_match_observed_stdout_and_host_oracle(self):
        initial = outcome(); artifact = initial["verification"]["artifact_hash"]
        for mutate in [lambda a: a.update(artifact_hash="wrong"),
                       lambda a: a["execution"].update(stdout="not JSON"),
                       lambda a: a["challenges"][0].update(expected=999),
                       lambda a: a["execution"].update(cleanup_confirmed=False)]:
            report = deepcopy(initial["adversarial_report"]); mutate(report)
            self.assertEqual(confirmed_failures(report, artifact), [])

    def test_recovery_context_is_allowlisted_without_agent_history_or_hidden_tests(self):
        initial = outcome()
        initial["executor"] = {"private_history": "SECRET_HISTORY", "api_key": "SECRET_KEY"}
        initial["adversarial_report"]["raw_response"] = "SECRET_ADV_REASON"
        trigger, failures, problem = recovery_eligibility(initial)
        self.assertIsNone(problem)
        context = build_recovery_context(initial, failures, 1)
        self.assertEqual(set(context), {"task_id", "requirement", "candidate", "confirmed_failures", "remaining_recovery_attempts"})
        payload = json.dumps(recovery_messages(context))
        for forbidden in ["SECRET_HISTORY", "SECRET_KEY", "SECRET_ADV_REASON", "acceptance/billing_v1.py", "docker.sock"]:
            self.assertNotIn(forbidden, payload)
        self.assertIn("untrusted data", recovery_messages(context)[0]["content"])
        self.assertEqual(len(failures), 2)

    def test_duplicate_code_consumes_one_attempt_then_stops(self):
        initial = outcome()
        client = offline_recovery_client("exhausted", 1)
        generated = "# Offline recovery attempt 1: still incorrect\n" + candidate(initial)
        initial = verified_double({"analysis": "unit", "files": {"billing.py": generated}})
        verify = Mock()
        result = run_recovery(initial, verify, lambda _: client)
        self.assertEqual(result["recovery_report"]["stop_reason"], "DUPLICATE_CANDIDATE")
        verify.assert_not_called()

    def test_initial_success_cannot_skip_complete_stage2_evidence(self):
        initial = outcome("E1")
        initial["adversarial_report"]["artifact_hash"] = "old-candidate"
        result = run_recovery(initial, Mock(), Mock())
        self.assertEqual(result["recovery_report"]["final_status"], "INCONCLUSIVE")

    def test_unsafe_initial_success_is_not_reported_as_verified(self):
        initial = outcome("E1")
        initial["verification"]["executions"][0]["cleanup_confirmed"] = False
        report = run_recovery(initial, Mock(), Mock())["recovery_report"]
        self.assertEqual(report["final_status"], "INCONCLUSIVE")

    @patch.dict("os.environ", {"TRUSTBOUND_ENABLE_RECOVERY_LIVE": ""})
    @patch("trustbound.web_tasks._execute_base_run")
    def test_direct_live_entry_is_blocked_before_any_execution_or_paid_call(self, base):
        from trustbound.web_tasks import execute_web_run
        with self.assertRaises(ValueError):
            execute_web_run(TASK.task_id, "fixture", "double_rounding", "offline", recovery_mode="live")
        base.assert_not_called()

    def test_unsupported_ast_is_rejected_before_permission_execution(self):
        client = offline_recovery_client("fixed", 1)
        transport = client.transport
        def response(method, path, payload, key, timeout):
            data = transport(method, path, payload, key, timeout)
            if method == "POST":
                data["choices"][0]["message"]["content"] = json.dumps({"analysis": "Request unlimited retries", "files": {"billing.py": "import os\n"}})
            return data
        client.transport = response
        verify = Mock()
        report = run_recovery(outcome(), verify, lambda _: client)["recovery_report"]
        self.assertEqual(report["final_status"], "REJECTED")
        self.assertEqual(len(report["attempts"]), 2)
        verify.assert_not_called()

    def test_progress_snapshots_are_independent_and_record_attempts(self):
        updates = []
        result = self.run_case(on_progress=updates.append)
        self.assertEqual(updates[0]["attempts"][0]["final_decision"]["status"], "FAILED")
        self.assertEqual(updates[-1]["final_status"], "VERIFIED")
        self.assertEqual(result["recovery_report"]["run_id"], "unit-job")


def candidate(record):
    return record["candidate"]["content"]
