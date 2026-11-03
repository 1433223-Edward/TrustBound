"""Offline tests use explicit fake transport, never claim a Vultr live response."""
import io
import json
import os
import unittest
from unittest.mock import Mock, patch
from urllib.error import HTTPError, URLError

from trustbound.executor import parse_proposal, validate_billing_code, ProposalError, run_executor
from trustbound.inference import VultrClient, InferenceError, DEFAULT_MODEL, select_model
from trustbound.service import ROOT

MODEL = {"id": DEFAULT_MODEL, "architecture": {"output_modalities": ["text"]},
         "pricing": {"prompt": "0.00000015", "completion": "0.0000006"}}
CATALOG = {"data": [MODEL]}
CODE = (ROOT / "fixtures/billing/fixed.py").read_text()
PROPOSAL = json.dumps({"analysis": "Use half-up rounding instead of truncation",
                       "files": {"billing.py": CODE}})


def response(text, **extra):
    return {"model": DEFAULT_MODEL, "choices": [{"finish_reason": "stop",
             "message": {"content": text}}],
            "usage": {"prompt_tokens": 100, "completion_tokens": 20, "total_tokens": 120},
            **extra}


class InferenceTests(unittest.TestCase):
    def test_missing_key_makes_no_calls(self):
        transport = Mock()
        report = run_executor(VultrClient("", transport=transport))
        transport.assert_not_called()
        self.assertEqual(report["status"], "BLOCKED")
        self.assertEqual(report["source"], "NO_LIVE_CALL")
        self.assertEqual(report["calls"], [])

    def test_catalog_requires_selected_live_model(self):
        self.assertEqual(select_model(CATALOG), MODEL)
        with self.assertRaises(InferenceError):
            select_model({"data": []})

    def test_usage_and_estimated_cost(self):
        transport = Mock(return_value=response("READY"))
        client = VultrClient("offline-test-secret", transport=transport)
        self.assertEqual(client.complete(MODEL, [], 64), "READY")
        self.assertEqual(client.calls[0]["estimated_usd"], "0.00002700")
        self.assertEqual(transport.call_args.args[-1], 30)
        self.assertEqual(transport.call_args.args[2]["max_completion_tokens"], 64)
        self.assertNotIn("offline-test-secret", json.dumps(client.calls))

    def test_unknown_usage_is_not_zero_cost(self):
        client = VultrClient("offline-key", transport=Mock(return_value=response("OK", usage=None)))
        client.complete(MODEL, [], 64)
        self.assertIsNone(client.calls[0]["estimated_usd"])

    def test_api_errors_and_timeout_not_retried(self):
        for failure in [TimeoutError(), URLError(TimeoutError()), URLError("do not log this body"),
                        HTTPError("url", 401, "secret body", {}, io.BytesIO()),
                        HTTPError("url", 500, "secret body", {}, io.BytesIO())]:
            with self.subTest(failure=type(failure).__name__):
                transport = Mock(side_effect=failure)
                client = VultrClient("offline-key", transport=transport)
                with self.assertRaises(InferenceError):
                    client.complete(MODEL, [], 64)
                self.assertEqual(transport.call_count, 1)
                self.assertNotIn("secret body", json.dumps(client.calls))

    @patch("trustbound.inference.time.sleep")
    def test_rate_limit_retry_is_bounded(self, sleep):
        failure = HTTPError("url", 429, "rate limit", {}, io.BytesIO())
        transport = Mock(side_effect=failure)
        client = VultrClient("offline-key", transport=transport)
        with self.assertRaises(InferenceError):
            client.complete(MODEL, [], 64)
        self.assertEqual(transport.call_count, 2)
        self.assertEqual(sleep.call_count, 1)

    def test_truncation_and_model_mismatch_rejected(self):
        truncated = response("partial")
        truncated["choices"][0]["finish_reason"] = "length"
        for result in [truncated, response("OK", model="other"), {}, []]:
            with self.subTest(result=result), self.assertRaises(InferenceError):
                VultrClient("offline-key", transport=Mock(return_value=result)).complete(MODEL, [], 64)

    def test_secret_echo_is_redacted(self):
        client = VultrClient("offline-secret", transport=Mock(return_value=response("offline-secret")))
        self.assertEqual(client.complete(MODEL, [], 64), "[REDACTED]")


class ProposalTests(unittest.TestCase):
    def test_valid_structure_and_decimal_expression(self):
        validate_billing_code(parse_proposal(PROPOSAL)["files"]["billing.py"])

    def test_invalid_structures(self):
        for text in ["not json", "[]", "{}", '{"analysis":"x","files":{}}',
                     PROPOSAL[:-1], PROPOSAL[:-1] + ',"command":"docker run"}']:
            with self.subTest(text=text[:50]), self.assertRaises(ProposalError):
                parse_proposal(text)

    def test_duplicate_json_keys_rejected(self):
        with self.assertRaises(ProposalError):
            parse_proposal('{"analysis":"x","analysis":"y","files":{"billing.py":"x"}}')

    def test_reject_code_that_can_forge_results(self):
        for code in ["import sys\nsys.exit(0)",
                     "from decimal import Decimal\ndef to_cents(amount):\n return __import__('os')",
                     "from decimal import Decimal\ndef to_cents(amount):\n while True: pass",
                     "from decimal import Decimal\n@print('x')\ndef to_cents(amount):\n return 1",
                     "from decimal import Decimal\ndef to_cents(amount=open('x')):\n return 1"]:
            with self.subTest(code=code), self.assertRaises(ProposalError):
                validate_billing_code(code)

    @patch("trustbound.service._execute_fixed_tests")
    def test_unauthorized_patch_reuses_permission_gate(self, execute):
        forbidden = json.dumps({"analysis": "test rejection", "files": {"acceptance/billing_v1.py": "x"}})
        transport = Mock(side_effect=[CATALOG, response("READY"), response(forbidden)])
        report = run_executor(VultrClient("offline-key", transport=transport))
        self.assertEqual(report["source"], "OFFLINE_TEST")
        self.assertEqual(report["status"], "REJECTED")
        self.assertEqual(len(report["verification"]["executions"]), 0)
        execute.assert_not_called()

    @patch("trustbound.executor.verify_patch")
    def test_valid_proposal_routes_to_existing_verifier(self, verify):
        verify.return_value.status = "FAILED"
        verify.return_value.to_dict.return_value = {"status": "FAILED", "unit_test_mock": True}
        transport = Mock(side_effect=[CATALOG, response("READY"), response(PROPOSAL)])
        report = run_executor(VultrClient("offline-key", transport=transport))
        self.assertEqual(report["status"], "FAILED")
        self.assertEqual(verify.call_args.args[1], {"billing.py": CODE})
        self.assertNotIn("acceptance/billing_v1.py", json.dumps(report["requests"]))

    @patch("trustbound.executor.verify_patch")
    def test_bad_model_format_does_not_execute(self, verify):
        transport = Mock(side_effect=[CATALOG, response("READY"), response("bad JSON")])
        report = run_executor(VultrClient("offline-key", transport=transport))
        self.assertEqual(report["status"], "REJECTED")
        verify.assert_not_called()

    def test_api_failure_is_recorded_without_verification(self):
        for failure in [TimeoutError(), URLError("private server details")]:
            transport = Mock(side_effect=[CATALOG, failure])
            report = run_executor(VultrClient("offline-key", transport=transport))
            self.assertEqual(report["status"], "API_FAILED")
            self.assertIsNone(report["verification"])


if __name__ == "__main__":
    unittest.main()
