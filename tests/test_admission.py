from concurrent.futures import ThreadPoolExecutor
import os
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch
from urllib.error import HTTPError

from fastapi.testclient import TestClient

from trustbound.admission import Admission, AdmissionError, inference_admission, initialize
from trustbound.api import create_app
from trustbound.inference import InferenceError, TaskInferenceBudget, VultrClient, task_inference_budget
from trustbound.runner_worker import _reconcile_owned_containers


BODY = {"task_id": "billing-rounding-01"}
DOMAIN = "demo.example.test"


class AdmissionTests(unittest.TestCase):
    def test_concurrent_reservations_and_reopen_preserve_one_cap(self):
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "budget.sqlite"
            initialize(database)
            quota = Admission(database, max_runs=2, min_run_seconds=0)

            def submit():
                try:
                    quota.reserve_run()
                except AdmissionError as error:
                    return error.code
                return "accepted"

            with ThreadPoolExecutor(max_workers=6) as pool:
                results = list(pool.map(lambda _: submit(), range(6)))
            self.assertEqual(results.count("accepted"), 2)
            self.assertEqual(results.count("RUN_QUOTA_EXHAUSTED"), 4)
            with self.assertRaisesRegex(AdmissionError, "RUN_QUOTA_EXHAUSTED"):
                Admission(database, max_runs=2).reserve_run()
            with self.assertRaises(FileExistsError):
                initialize(database)
            database.unlink()
            with self.assertRaisesRegex(AdmissionError, "QUOTA_STORE_UNAVAILABLE"):
                quota.reserve_run()
            self.assertFalse(database.exists())

    def test_rate_reservation_reports_the_remaining_wait(self):
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "budget.sqlite"
            initialize(database)
            Admission(database, min_run_seconds=10)._reserve(now=100)
            with self.assertRaises(AdmissionError) as raised:
                Admission(database, min_run_seconds=10)._reserve(now=104)
            self.assertEqual((raised.exception.code, raised.exception.retry_after), ("RUN_RATE_LIMITED", 6))

    def test_provider_retry_cannot_exceed_the_persistent_reservation(self):
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "budget.sqlite"
            initialize(database)
            attempts = []

            def fake_provider(*arguments):
                attempts.append(arguments[0])
                raise HTTPError("", 429, "", {}, None)

            client = VultrClient("test-only", transport=fake_provider)
            client.source = "VULTR_LIVE_HTTP"
            quota = Admission(database, max_model_calls=1, max_output_tokens=100)
            with inference_admission(quota), task_inference_budget(TaskInferenceBudget()):
                with self.assertRaisesRegex(InferenceError, "MODEL_QUOTA_EXHAUSTED"):
                    client.complete({"id": "test"}, [{"role": "user", "content": "test"}], 100)
            self.assertEqual(attempts, ["POST"])
            with self.assertRaisesRegex(AdmissionError, "MODEL_QUOTA_EXHAUSTED"):
                Admission(database, max_model_calls=1, max_output_tokens=100).reserve_model(1)

    def test_public_profile_rejects_live_custom_and_origin_then_enforces_quota(self):
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "budget.sqlite"
            initialize(database)
            env = {"TRUSTBOUND_PUBLIC_DEMO": "1", "TRUSTBOUND_PUBLIC_DOMAIN": DOMAIN,
                   "TRUSTBOUND_QUOTA_DB": str(database), "TRUSTBOUND_RUNNER_SOCKET": "/run/runner.sock",
                   "TRUSTBOUND_MAX_RUNS": "2", "TRUSTBOUND_MIN_RUN_SECONDS": "60",
                   "TRUSTBOUND_ENABLE_CUSTOM_TASK": "0", "TRUSTBOUND_ENABLE_LIVE": "0",
                   "TRUSTBOUND_ENABLE_RECOVERY_LIVE": "0"}
            started = []

            def execute(*args, **kwargs):
                started.append(args)
                return {"error": None}

            with patch.dict(os.environ, env), TestClient(
                create_app(execute=execute, report_directory=Path(directory) / "reports"),
                base_url=f"https://{DOMAIN}",
            ) as client:
                headers = {"Origin": f"https://{DOMAIN}"}
                self.assertEqual(client.post("/api/runs", json=BODY).status_code, 403)
                self.assertEqual(client.post("/api/runs", headers=headers,
                                             json=dict(BODY, adversarial_mode="live")).status_code, 403)
                self.assertEqual(client.post("/api/runs", headers=headers,
                                             json=dict(BODY, mode="live_executor")).status_code, 403)
                self.assertFalse(client.get("/api/health").json()["custom_task"]["enabled"])
                self.assertEqual(client.get("/api/custom-runs/" + "0" * 32).status_code, 503)
                self.assertEqual(client.get("/api/health", headers={"Host": "wrong.test"}).status_code, 400)
                self.assertEqual(client.post("/api/runs", headers=headers, json=BODY).status_code, 202)
                for _ in range(100):
                    if client.get("/api/health").json()["active_run_id"] is None:
                        break
                    time.sleep(.01)
                rate = client.post("/api/runs", headers=headers, json=BODY)
                self.assertEqual(rate.status_code, 429)
                self.assertEqual(rate.json()["error"]["code"], "RUN_RATE_LIMITED")
                self.assertGreater(int(rate.headers["Retry-After"]), 0)
                database.unlink()
                self.assertEqual(client.post("/api/runs", headers=headers, json=BODY).status_code, 503)
                self.assertEqual(len(started), 1)

    @patch.dict(os.environ, {"TRUSTBOUND_PUBLIC_DEMO": "0"})
    def test_caddy_marked_requests_do_not_bypass_disabled_profile(self):
        with TestClient(create_app(report_directory=None), base_url="http://127.0.0.1") as client:
            self.assertEqual(client.post("/api/runs", json=BODY,
                                         headers={"X-TrustBound-Public": "1"}).status_code, 503)

    @patch("trustbound.runner_worker.checked")
    def test_orphan_reconciliation_is_labeled_and_refuses_unexpected_names(self, docker):
        docker.side_effect = ["abcdefabcdef trustbound-" + "a" * 32, "", ""]
        _reconcile_owned_containers()
        self.assertIn("label=org.trustbound.owner=private-web-runner-v1", docker.call_args_list[0].args)
        self.assertEqual(docker.call_args_list[1].args, ("rm", "-f", "abcdefabcdef"))
        docker.reset_mock(side_effect=True)
        docker.return_value = "abcdefabcdef unrelated"
        with self.assertRaisesRegex(RuntimeError, "Unexpected owned"):
            _reconcile_owned_containers()
        docker.assert_called_once()
