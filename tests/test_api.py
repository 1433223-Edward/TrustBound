"""API contract/control tests; business execution is covered separately over HTTP."""
import os
import threading
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from trustbound.api import create_app
from trustbound.service import TASK


class ApiTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(create_app(report_directory=None), base_url="http://127.0.0.1")
        self.client.__enter__()

    def tearDown(self):
        self.client.__exit__(None, None, None)

    def test_health_and_task_details(self):
        self.assertEqual(self.client.get("/api/health").json()["max_concurrent_runs"], 1)
        tasks = self.client.get("/api/tasks").json()["tasks"]
        detail = self.client.get(f"/api/tasks/{TASK.task_id}").json()
        self.assertEqual(tasks[0], detail)
        self.assertIn("def to_cents", detail["original"]["content"])
        self.assertEqual(detail["spec"]["allowed_write_paths"], ["billing.py"])

    def test_unknown_task_and_run(self):
        self.assertEqual(self.client.get("/api/tasks/unknown").status_code, 404)
        self.assertEqual(self.client.get("/api/runs/00000000-0000-0000-0000-000000000000").status_code, 404)
        self.assertEqual(self.client.get("/api/runs/not-an-id").status_code, 422)

    def test_untrusted_input_is_rejected_before_execution(self):
        bodies = [{"task_id": "other"}, {"task_id": TASK.task_id, "candidate_id": "../../escape"},
                  {"task_id": TASK.task_id, "command": "docker run"},
                  {"task_id": TASK.task_id, "files": {"acceptance/billing_v1.py": "x"}},
                  {"task_id": TASK.task_id, "run_id": "client-id"},
                  {"task_id": TASK.task_id, "mode": "unknown"}]
        for body in bodies:
            with self.subTest(body=body):
                self.assertEqual(self.client.post("/api/runs", json=body).status_code, 422)
        self.assertIsNone(self.client.get("/api/health").json()["active_run_id"])

    def test_adversarial_request_preserves_strict_data_only_boundary(self):
        for extra in [{"adversarial_mode": "arbitrary"}, {"adversarial_mode": "offline", "challenges": ["1.005"]},
                      {"adversarial_fixture": "timeout"}, {"adversarial_mode": "live", "adversarial_fixture": "failure"}]:
            with self.subTest(extra=extra):
                result = self.client.post("/api/runs", json={"task_id": TASK.task_id, **extra})
                self.assertEqual(result.status_code, 422)
        self.assertIsNone(self.client.get("/api/health").json()["active_run_id"])

    def test_recovery_cannot_override_budget_policy_or_requirements(self):
        for extra in [{"recovery_mode": "offline"}, {"recovery_mode": "arbitrary"},
                      {"recovery_mode": "offline", "adversarial_mode": "offline", "max_attempts": 100},
                      {"recovery_fixture": "exhausted"}, {"recovery_mode": "offline", "adversarial_mode": "offline", "recovery_context": {}}]:
            result = self.client.post("/api/runs", json={"task_id": TASK.task_id, **extra})
            self.assertEqual(result.status_code, 422)
        self.assertIsNone(self.client.get("/api/health").json()["active_run_id"])

    @patch.dict(os.environ, {"TRUSTBOUND_ENABLE_RECOVERY_LIVE": ""})
    def test_live_recovery_requires_separate_host_opt_in_without_calling_model(self):
        response = self.client.post("/api/runs", json={"task_id": TASK.task_id,
            "recovery_mode": "live", "adversarial_mode": "offline"})
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["error"]["code"], "RECOVERY_LIVE_NOT_AUTHORIZED")

    def test_offline_mode_only_accepts_reviewed_response(self):
        result = self.client.post("/api/runs", json={"task_id": TASK.task_id, "mode": "offline_executor", "candidate_id": "timeout"})
        self.assertEqual(result.status_code, 422)

    @patch.dict(os.environ, {"VULTR_INFERENCE_API_KEY": ""})
    def test_missing_live_key_returns_unavailable_without_creating_run(self):
        result = self.client.post("/api/runs", json={"task_id": TASK.task_id, "mode": "live_executor"})
        self.assertEqual(result.status_code, 503)
        self.assertEqual(result.json()["error"]["code"], "MISSING_VULTR_INFERENCE_API_KEY")
        self.assertIsNone(self.client.get("/api/health").json()["active_run_id"])

    def test_cross_origin_and_large_requests_rejected(self):
        self.assertEqual(self.client.post("/api/runs", json={"task_id": TASK.task_id},
                                         headers={"Origin": "https://untrusted.example"}).status_code, 403)
        self.assertEqual(self.client.post("/api/runs", content=b"x" * 4097).status_code, 413)

    def test_busy_run_does_not_block_health_or_allow_second_execution(self):
        entered, release = threading.Event(), threading.Event()

        def blocked_control_test(*args):
            entered.set()
            release.wait(5)
            raise RuntimeError("Control test only; no simulated test verdict")

        with TestClient(create_app(execute=blocked_control_test, report_directory=None), base_url="http://127.0.0.1") as client:
            try:
                first = client.post("/api/runs", json={"task_id": TASK.task_id})
                self.assertEqual(first.status_code, 202)
                self.assertTrue(entered.wait(2))
                health = client.get("/api/health")
                self.assertEqual(health.status_code, 200)
                self.assertEqual(health.json()["active_run_id"], first.json()["run_id"])
                self.assertEqual(client.post("/api/runs", json={"task_id": TASK.task_id}).status_code, 429)
                self.assertEqual(client.get("/api/runs/" + first.json()["run_id"]).json()["state"], "RUNNING")
            finally:
                release.set()


if __name__ == "__main__":
    unittest.main()
