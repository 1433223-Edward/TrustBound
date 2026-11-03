"""Regression checks for policy and evidence gates; no candidate imports on host."""
from dataclasses import replace
import unittest
from unittest.mock import patch

from trustbound.contracts import ExecutionResult, TaskSpec, VerificationReport
from trustbound.runner import IMAGE
from trustbound.service import ROOT, TASK, run_task


def evidence(phase="public", **changes):
    return replace(ExecutionResult(
        phase, "unit-test-only", IMAGE, "code-hash", "test-hash", "EXITED",
        0, "", "", None, True, True, True), **changes)


def verified_report(executions):
    return VerificationReport("unit-test", TASK, "fixed", "code-hash", "test-hash",
                              "VERIFIED", "Allowed", ("billing.py",), "",
                              tuple(executions), ())


class ContractTests(unittest.TestCase):
    def test_valid_evidence(self):
        self.assertEqual(verified_report([evidence(), evidence("acceptance")]).status,
                         "VERIFIED")

    def test_invalid_task_contract(self):
        for paths, timeout in [(("../escape.py",), 3), (("C:/escape",), 3),
                               (("/absolute",), 3), (("billing.py",), 0), ((), 3)]:
            with self.subTest(paths=paths, timeout=timeout), self.assertRaises(ValueError):
                TaskSpec("billing", "v1", paths, timeout)

    def test_no_verified_without_independent_acceptance(self):
        with self.assertRaises(ValueError):
            verified_report([evidence()])

    def test_no_verified_with_bad_execution_evidence(self):
        failures = [dict(exit_code=1), dict(cleanup_confirmed=False),
                    dict(workspace_unchanged=False), dict(limits_verified=False),
                    dict(artifact_hash="different-code"), dict(test_hash="different-test"),
                    dict(status="TIMED_OUT", timeout_reason="deadline", exit_code=137),
                    dict(error="controller failure")]
        for change in failures:
            with self.subTest(change=change), self.assertRaises(ValueError):
                verified_report([evidence(), evidence("acceptance", **change)])

    def test_timeout_requires_reason(self):
        with self.assertRaises(ValueError):
            evidence(status="TIMED_OUT")


class PolicyTests(unittest.TestCase):
    @patch("trustbound.service._execute_fixed_tests")
    def test_protected_write_rejected_before_execution(self, execute):
        protected = ROOT / "acceptance/billing_v1.py"
        before = protected.read_bytes()
        report = run_task(TASK.task_id, "unauthorized")
        self.assertEqual(report.status, "REJECTED")
        self.assertIn("protected", report.policy_reason)
        execute.assert_not_called()
        self.assertEqual(protected.read_bytes(), before)

    def test_unknown_inputs_rejected(self):
        for task_id, candidate_id in [("custom", "fixed"), (TASK.task_id, "../../file")]:
            with self.subTest(task=task_id, candidate=candidate_id):
                with self.assertRaises(ValueError):
                    run_task(task_id, candidate_id)

    @patch("trustbound.service._execute_fixed_tests")
    def test_public_failure_cannot_be_verified(self, execute):
        execute.return_value = evidence(exit_code=1)
        self.assertEqual(run_task(TASK.task_id, "original").status, "FAILED")
        self.assertEqual(execute.call_count, 1)

    @patch("trustbound.service._execute_fixed_tests")
    def test_acceptance_failure_cannot_be_verified(self, execute):
        execute.side_effect = [evidence(), evidence("acceptance", exit_code=1)]
        self.assertEqual(run_task(TASK.task_id, "public_only").status, "FAILED")
        self.assertEqual(execute.call_count, 2)
        self.assertNotEqual(execute.call_args_list[0].args[1],
                            execute.call_args_list[1].args[1])

    @patch("trustbound.service._execute_fixed_tests")
    def test_cleanup_failure_is_inconclusive(self, execute):
        execute.return_value = evidence(cleanup_confirmed=False)
        self.assertEqual(run_task(TASK.task_id, "fixed").status, "INCONCLUSIVE")


if __name__ == "__main__":
    unittest.main()
