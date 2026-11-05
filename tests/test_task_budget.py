"""Task-wide request reservations; all transports here are explicit unit doubles."""
import unittest
from unittest.mock import Mock
from trustbound.inference import TaskInferenceBudget, task_inference_budget, VultrClient, InferenceError

MODEL = {"id": "unit-model"}

class TaskBudgetTests(unittest.TestCase):
    def test_fresh_clients_share_request_and_token_limits(self):
        budget = TaskInferenceBudget(max_requests=1, max_output_tokens=64)
        transport = Mock(side_effect=TimeoutError())
        with task_inference_budget(budget):
            with self.assertRaises(InferenceError):
                VultrClient("unit-only", transport=transport).complete(MODEL, [], 64)
            with self.assertRaisesRegex(InferenceError, "BUDGET_EXHAUSTED"):
                VultrClient("unit-only", transport=transport).complete(MODEL, [], 1)
        self.assertEqual(transport.call_count, 1)
        self.assertEqual(budget.to_dict()["reserved_output_tokens"], 64)
        self.assertIsNone(budget.to_dict()["estimated_usd"])

    def test_output_reservation_and_scope_reset(self):
        budget = TaskInferenceBudget(max_requests=2, max_output_tokens=1)
        client = VultrClient("unit-only", transport=Mock(side_effect=TimeoutError()))
        with task_inference_budget(budget):
            with self.assertRaisesRegex(InferenceError, "BUDGET_EXHAUSTED"):
                client.complete(MODEL, [], 2)
        client.transport.assert_not_called()
        with self.assertRaisesRegex(InferenceError, "TIMEOUT"):
            client.complete(MODEL, [], 2)

    def test_unknown_live_usage_is_not_reported_as_zero(self):
        budget = TaskInferenceBudget()
        budget.reserve({"max_completion_tokens": 64, "usage": None, "estimated_usd": None}, "VULTR_LIVE_HTTP")
        report = budget.to_dict()
        self.assertIsNone(report["prompt_tokens"])
        self.assertIsNone(report["estimated_usd"])
        self.assertEqual(report["live_request_count"], 1)
