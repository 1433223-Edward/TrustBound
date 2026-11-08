"""Offline proposal diagnostics: mocked inference and forbidden sandbox execution."""
import json
import unittest
from unittest.mock import Mock, patch

from trustbound.executor import ProposalError
from trustbound.workspace_execution import (
    StartWorkspaceRun, WorkspaceJob, _live_replacements, execute_workspace,
)


class ProposalDiagnosticsTests(unittest.TestCase):
    def parse(self, text):
        client = Mock()
        client.catalog.return_value = {"data": [{
            "id": "fixture-model", "architecture": {"output_modalities": ["text"]},
        }]}
        client.complete.return_value = text
        with (patch("trustbound.workspace_execution.VultrClient", return_value=client) as factory,
              patch("trustbound.workspace_execution._messages", return_value=[]),
              patch("trustbound.workspace_execution.workspace_model_allowlist", return_value=("fixture-model",))):
            try:
                return _live_replacements({}, "fixture-model")
            finally:
                factory.assert_called_once_with(timeout=60, max_attempts=1, output_limit=4096)
                client.complete.assert_called_once()

    def test_valid_proposal_and_optional_explanation_still_accepted(self):
        for explanation in (None, {"description": {"en": "Fix", "zh": "修复"},
                                   "reason": {"en": "Boundary", "zh": "边界"}}):
            value = {"files": {"inventory.py": "VALUE = 1\n"}, "explanation": explanation}
            with self.subTest(explanation=explanation):
                self.assertEqual(self.parse(json.dumps(value)), value)

    def test_invalid_json_and_duplicate_keys_have_distinct_codes(self):
        for text, code in (("not json", "WORKSPACE_PROPOSAL_INVALID_JSON"),
                           ('{"files":{},"files":{}}', "DUPLICATE_JSON_KEY")):
            with self.subTest(code=code), self.assertRaisesRegex(ProposalError, "^" + code + "$"):
                self.parse(text)

    def test_invalid_shapes_remain_rejected(self):
        for value in ([], {}, {"files": []}, {"files": {}},
                      {"files": {"inventory.py": "VALUE = 1"}, "tests": []}):
            with self.subTest(value=value), self.assertRaisesRegex(
                    ProposalError, "^WORKSPACE_PROPOSAL_INVALID_SHAPE$"):
                self.parse(json.dumps(value))

    def test_invalid_explanation_has_constant_code_without_echoing_input(self):
        value = {"files": {"inventory.py": "VALUE = 1"},
                 "explanation": {"description": "SYNTHETIC_PRIVATE_MARKER", "reason": "text"}}
        with self.assertRaises(ProposalError) as raised:
            self.parse(json.dumps(value))
        self.assertEqual(str(raised.exception), "WORKSPACE_PROPOSAL_INVALID_EXPLANATION")
        self.assertNotIn("SYNTHETIC_PRIVATE_MARKER", str(raised.exception))

    def test_specific_codes_reach_report_without_running_sandbox(self):
        project = {"project_id": "b" * 32, "revision": 2, "frozen_hash": "c" * 64,
                   "snapshot_hash": "e" * 64,
                   "plan": {"public_cases": [{}], "acceptance_cases": [{}]}}
        request = StartWorkspaceRun(revision=2, mode="live", authorize_source=True,
                                    model_id="fixture-model")
        for code in ("WORKSPACE_PROPOSAL_INVALID_JSON", "DUPLICATE_JSON_KEY",
                     "WORKSPACE_PROPOSAL_INVALID_SHAPE", "WORKSPACE_PROPOSAL_INVALID_EXPLANATION"):
            with (self.subTest(code=code),
                  patch("trustbound.workspace_execution._live_replacements", side_effect=ProposalError(code)) as model,
                  patch("trustbound.workspace_execution.run_worker_request") as worker,
                  patch("trustbound.workspace_execution.run_workspace_case") as local):
                report = execute_workspace(WorkspaceJob(project, request, "ROOTLESS_WORKER"), "d" * 32)
                self.assertEqual(report["reason"], code)
                self.assertEqual(report["status"], "INCONCLUSIVE")
                self.assertEqual(report["cases"], [])
                model.assert_called_once()
                worker.assert_not_called()
                local.assert_not_called()


if __name__ == "__main__":
    unittest.main()
