import json
import os
import time
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from trustbound.api import create_app
from trustbound.contracts import ExecutionResult
from trustbound.custom_policy import CUSTOM_TASK, build_custom_driver, validate_solution
from trustbound.custom_tasks import CustomRunRequest, execute_custom
from trustbound.runner import IMAGE, sha256
from trustbound.runner_worker import execute_request


SOURCE = "def solve(value):\n    return value\n"
FIX = "def solve(value):\n    return -value if value < 0 else value\n"
TASK = {"source": SOURCE, "requirements": "Return absolute value.",
        "public": [{"input": 2, "expected": 2}],
        "acceptance": [{"input": -3, "expected": 3}],
        "challenges": [{"input": 0, "expected": 0}]}
FLAGS = {"TRUSTBOUND_ENABLE_CUSTOM_TASK": "1", "TRUSTBOUND_RUNNER_SOCKET": "/run/example.sock",
         "TRUSTBOUND_ENABLE_LIVE": "0", "TRUSTBOUND_ENABLE_RECOVERY_LIVE": "0"}


def sandbox_evidence(code, driver, phase, *, task_id, cases):
    assert task_id == CUSTOM_TASK.task_id
    rows = [{"input": value, "actual": abs(value) if code == FIX.encode() else value, "error": None}
            for value in cases]
    return ExecutionResult(phase, f"test-only-{phase}", IMAGE, sha256(code), sha256(driver),
                           "EXITED", 0, json.dumps(rows), "", None, True, True, True)


class CustomTaskTests(unittest.TestCase):
    def test_profile_blocks_code_that_could_interfere_with_the_harness(self):
        validate_solution(FIX)
        for code in ("import os\n" + SOURCE, "def solve(value):\n    return open(value)\n",
                     "def solve(value=0):\n    return value\n",
                     "def solve(value):\n    return value.__class__\n",
                     "def solve(value):\n    return 2 ** value\n"):
            with self.subTest(code=code), self.assertRaises(ValueError):
                validate_solution(code)

    @patch.dict(os.environ, FLAGS)
    @patch("trustbound.runner_worker._execute_fixed_tests")
    def test_worker_rejects_expected_outputs_and_arbitrary_options(self, docker):
        request = {"task_id": CUSTOM_TASK.task_id, "phase": "acceptance", "candidate": FIX,
                   "candidate_sha256": sha256(FIX.encode()), "cases": [-3]}
        for bad in (dict(request, cases=[{"input": -3, "expected": 3}]),
                    dict(request, command="python"), dict(request, cases=[True])):
            with self.assertRaises(ValueError):
                execute_request(bad)
        docker.assert_not_called()
        docker.return_value = sandbox_evidence(FIX.encode(), build_custom_driver([-3]), "acceptance",
                                                task_id=CUSTOM_TASK.task_id, cases=[-3])
        execute_request(request)
        harness = docker.call_args.args[1].decode()
        self.assertTrue(harness.startswith("inputs = [-3]\n"))
        self.assertNotIn("expected", harness)

    @patch("trustbound.custom_tasks.run_through_worker", side_effect=sandbox_evidence)
    def test_host_comparison_and_evidence_scope(self, _):
        for options, formal, final in (
            ({"replacement": FIX}, "VERIFIED", "VERIFIED"),
            ({}, "FAILED", "FAILED"),
            ({"replacement": FIX, "acceptance": []}, "INCONCLUSIVE", "INCONCLUSIVE"),
            ({"replacement": FIX, "challenges": [{"input": 0, "expected": 1}]}, "VERIFIED", "FAILED"),
            ({"replacement": "import os\n" + SOURCE}, "REJECTED", "REJECTED"),
        ):
            with self.subTest(options=options):
                outcome = execute_custom(CustomRunRequest.model_validate(dict(TASK, **options)))
                self.assertEqual(outcome["verification"]["status"], formal)
                self.assertEqual(outcome["final_decision"]["status"], final)
                self.assertEqual(outcome["llm_source"], "NONE")

    @patch.dict(os.environ, FLAGS)
    @patch("trustbound.custom_tasks.run_through_worker", side_effect=sandbox_evidence)
    def test_private_routes_are_opt_in_and_do_not_expose_custom_records_through_billing(self, _):
        with TestClient(create_app(report_directory=None), base_url="http://127.0.0.1") as client:
            with patch.dict(os.environ, {"TRUSTBOUND_ENABLE_LIVE": "1"}):
                self.assertEqual(client.post("/api/custom-runs", json=TASK).status_code, 503)
            for bad in (dict(TASK, image="python:latest"), dict(TASK, acceptance=TASK["public"])):
                self.assertEqual(client.post("/api/custom-runs", json=bad).status_code, 422)
            response = client.post("/api/custom-runs", json=dict(TASK, replacement=FIX))
            self.assertEqual(response.status_code, 202)
            run_id = response.json()["run_id"]
            for _ in range(50):
                record = client.get(f"/api/custom-runs/{run_id}").json()
                if record["state"] in ("ERROR", "COMPLETED"):
                    break
                time.sleep(.01)
            self.assertEqual(record["state"], "COMPLETED")
            self.assertEqual(record["final_decision"]["status"], "VERIFIED")
            self.assertEqual(client.get(f"/api/runs/{run_id}").status_code, 404)
