"""Exercise review, export and the evidence boundary without Docker or Vultr."""
from dataclasses import replace
from io import BytesIO
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import time
import unittest
from unittest.mock import Mock, patch
from zipfile import ZipFile

from fastapi.testclient import TestClient

from trustbound.api import create_app
from trustbound.contracts import ExecutionResult
from trustbound.inference import InferenceError
from trustbound.runner import IMAGE
from trustbound.workspace_execution import (PROFILE, StartWorkspaceRun, _messages, invocation_hash,
                                            project_candidate, run_workspace_case, workspace_model_choices,
                                            workspace_retry_context)


class WorkspaceExecutionTests(unittest.TestCase):
    def setUp(self):
        tmp = self.enterContext(TemporaryDirectory())
        self.token = "test-only-token-with-enough-characters"
        self.enterContext(patch.dict(os.environ, {
            "TRUSTBOUND_PUBLIC_DEMO": "0", "TRUSTBOUND_ENABLE_WORKSPACE": "1",
            "TRUSTBOUND_WORKSPACE_TOKEN": self.token,
            "TRUSTBOUND_WORKSPACE_DB": str(Path(tmp) / "workspace.sqlite3"),
            "TRUSTBOUND_ENABLE_WORKSPACE_LIVE": "0", "TRUSTBOUND_QUOTA_DB": "",
        }))
        with patch("trustbound.api.workspace_transport", return_value="ROOTLESS_WORKER"):
            self.client = self.enterContext(TestClient(create_app(report_directory=None),
                                                       base_url="http://127.0.0.1"))
        self.client.headers["Authorization"] = "Bearer " + self.token
        self.base = "/api/workspace/projects"
        response = self.client.post(self.base, json={"files": [{"path": "main.py", "content": "before"}]})
        self.assertEqual(response.status_code, 201)
        self.project = self.base + "/" + response.json()["project_id"]
        self.plan = {"implementation": ["Multiply input by two"], "constraints": ["Only main.py"], "risks": ["Check input boundaries"],
            "acceptance_basis": "Requirement doubles numeric input: 3 * 2 = 6.",
            "goal": "Return double the input", "entrypoint": "main.py:solve",
            "allowed_write_paths": ["main.py"], "public_cases": [{"input": 2, "expected": 4}],
            "acceptance_cases": [{"input": 3, "expected": 6}],
        }
        self.assertEqual(self.client.post(self.project + "/plan", json={**self.plan, "revision": 0}).status_code, 200)
        self.frozen = self.client.post(self.project + "/freeze", json={"confirm_acceptance": True, "revision": 1}).json()

    def evidence(self, request, phase, artifact, test):
        self.assertEqual(set(request["case"]), {"entrypoint", "input"})
        self.assertEqual(test, invocation_hash(request["case"]))
        return ExecutionResult(phase, "trustbound-test-double", IMAGE, artifact, test, "EXITED", 0,
                               json.dumps(request["case"]["input"] * 2), "", None, True, True, True)

    def run_candidate(self, worker, files=None):
        with patch("trustbound.workspace_execution.run_worker_request", side_effect=worker):
            response = self.client.post(self.project + "/runs", json={
                "revision": 2, "mode": "offline", "files": files or {"main.py": "after"}})
            self.assertEqual(response.status_code, 202, response.text)
            run_id = response.json()["run_id"]
            route = self.project + "/runs/" + run_id
            for _ in range(100):
                record = self.client.get(route).json()
                if record["state"] not in ("RUNNING", "QUEUED"):
                    break
                time.sleep(0.01)
            self.assertEqual(record["state"], "COMPLETED", record)
        self.assertEqual(self.client.get("/api/runs/" + run_id).status_code, 404)
        return route, record["workspace_report"]

    def test_verified_review_and_identity_bound_export(self):
        route, report = self.run_candidate(self.evidence)
        self.assertEqual(report["status"], "VERIFIED")
        self.assertEqual([case["phase"] for case in report["cases"]], ["public", "acceptance"])
        self.assertEqual(self.client.get(route + "/export/zip").status_code, 409)
        self.assertEqual(self.client.post(route + "/review/ACCEPTED", json={}).json()["review"], "ACCEPTED")
        self.assertEqual(self.client.post(route + "/review/REJECTED", json={}).status_code, 409)
        self.assertEqual(self.client.post(self.project + "/plan", json={**self.plan, "revision": 2}).status_code, 200)
        with ZipFile(BytesIO(self.client.get(route + "/export/zip").content)) as archive:
            self.assertEqual(archive.read("main.py"), b"after")
            self.assertEqual(json.loads(archive.read("TRUSTBOUND_PLAN.json"))["goal"], self.plan["goal"])
        self.assertIn(b"\\ No newline at end of file", self.client.get(route + "/export/patch").content)

    def test_manual_versions_preserve_historical_source_and_run_evidence(self):
        route, report = self.run_candidate(self.evidence)
        self.assertEqual(self.client.post(route + "/review/ACCEPTED", json={}).status_code, 200)
        version_route = self.project + "/versions"
        project = self.frozen
        for index in range(3):
            response = self.client.post(version_route, json={"revision": project["revision"],
                "files": [{"path": "main.py", "content": f"version {index}"}], "folders": ["notes"]})
            self.assertEqual(response.status_code, 200, response.text)
            project = response.json()
            self.assertIsNone(project["frozen_hash"])
            self.assertEqual(project["folders"], ["notes"])
        fourth = {"revision": project["revision"], "files": [{"path": "main.py", "content": "fourth"}]}
        self.assertEqual(self.client.post(version_route, json=fourth).status_code, 409)
        self.assertEqual(self.client.post(version_route, json={**fourth, "replace_oldest": True}).status_code, 200)
        self.assertEqual([row["revision"] for row in self.client.get(version_route).json()], [6, 5, 4])
        self.assertEqual(self.client.post(self.project + "/runs", json={"revision": 2, "mode": "original"}).status_code, 409)
        historical = self.client.get(route + "?source=true").json()
        self.assertEqual(historical["workspace_report"], report)
        self.assertEqual(historical["historical_source"]["files"][0]["content"], "before")
        self.assertEqual(self.client.get(self.project + "/runs").json()[0]["status"], "VERIFIED")
        with ZipFile(BytesIO(self.client.get(route + "/export/zip").content)) as archive:
            self.assertEqual(archive.read("main.py"), b"after")
        other = self.client.post(self.base, json={"files": [{"path": "main.py", "content": "other"}]}).json()
        self.assertEqual(self.client.get(self.base + "/" + other["project_id"] + "/versions").json(), [])

    def test_interrupted_run_is_discoverable_without_resubmitting(self):
        run_id = "a" * 32
        app = self.client.app
        app.state.projects.save_run({
            "run_id": run_id, "project_id": self.frozen["project_id"], "owner": "private-operator",
            "frozen_hash": self.frozen["frozen_hash"], "task_id": PROFILE, "revision": 2,
            "state": "QUEUED", "created_at": "2026-11-07T00:00:00+00:00",
        })
        item = self.client.get(self.project + "/runs").json()[0]
        self.assertEqual((item["run_id"], item["status"]), (run_id, "INCONCLUSIVE"))
        record = self.client.get(self.project + "/runs/" + run_id + "?source=true").json()
        self.assertEqual(record["error"]["code"], "WORKSPACE_RUN_INTERRUPTED")
        self.assertNotIn("retry", record)
        self.assertIsNone(app.state.runs.active)

    def test_model_failures_are_archived_without_retry_or_docker_execution(self):
        with (patch.dict(os.environ, {"TRUSTBOUND_ENABLE_WORKSPACE_LIVE": "1",
                "TRUSTBOUND_ENABLE_RECOVERY_LIVE": "1", "VULTR_INFERENCE_API_KEY": "test-placeholder",
                "VULTR_MODEL": "test-model"}),
              patch("trustbound.api.workspace_transport", return_value="ROOTLESS_WORKER"),
              patch("trustbound.api.deployment_settings", return_value=(False, "", Mock()))):
            app = create_app(report_directory=None)
            with TestClient(app, base_url="http://127.0.0.1", headers=self.client.headers) as live:
                for code in ("TIMEOUT_BILLING_UNKNOWN", "MODEL_QUOTA_EXHAUSTED"):
                    with (
                        self.subTest(code=code),
                        patch("trustbound.workspace_execution._live_replacements", side_effect=InferenceError(code)) as model,
                        patch("trustbound.workspace_execution.run_worker_request") as worker,
                    ):
                        started = live.post(self.project + "/runs",
                                            json={"revision": 2, "mode": "live", "authorize_source": True})
                        self.assertEqual(started.status_code, 202, started.text)
                        run_id = started.json()["run_id"]
                        for _ in range(100):
                            record = live.get(self.project + "/runs/" + run_id).json()
                            if record["state"] == "COMPLETED":
                                break
                            time.sleep(0.01)
                        self.assertEqual(record["workspace_report"]["status"], "INCONCLUSIVE")
                        self.assertEqual(record["workspace_report"]["reason"], code)
                        self.assertNotIn("retry", record)
                        self.assertEqual(live.get(self.project + "/runs").json()[0]["summary"], code)
                        model.assert_called_once()
                        worker.assert_not_called()

    def test_approved_challenge_and_recovery_recheck_the_candidate(self):
        updated = self.client.post(self.project + "/plan", json={**self.plan, "revision": 2,
            "adversarial_cases": [{"input": 5, "expected": 10}]}).json()
        frozen = self.client.post(self.project + "/freeze", json={"confirm_acceptance": True, "revision": updated["revision"]}).json()
        with patch("trustbound.workspace_execution.run_worker_request", side_effect=self.evidence) as worker:
            def complete(payload):
                response = self.client.post(self.project + "/runs", json={"revision": frozen["revision"], **payload})
                self.assertEqual(response.status_code, 202, response.text)
                run_id = response.json()["run_id"]
                path = self.project + "/runs/" + run_id
                for _ in range(100):
                    record = self.client.get(path).json()
                    if record["state"] == "COMPLETED":
                        return path, record["workspace_report"]
                    time.sleep(.01)
                self.fail("Workspace did not complete")

            path, report = complete({"mode": "offline", "files": {"main.py": "after"}})
            self.assertEqual([row["phase"] for row in report["cases"]], ["public", "acceptance", "adversarial"])
            self.assertEqual(self.client.post(path + "/review/ACCEPTED", json={}).status_code, 200)
            _, restored = complete({"mode": "restore", "restore_run_id": report["run_id"]})
            self.assertEqual(restored["restored_from"], report["run_id"])
            self.assertEqual(restored["artifact_hash"], report["artifact_hash"])
            self.assertEqual(restored["status"], "VERIFIED")
            self.assertEqual(worker.call_count, 6)

    def test_untrusted_claim_and_wrong_result_do_not_pass(self):
        for stdout, verdict in (("tests passed", "INCONCLUSIVE"), ("5", "FAILED")):
            route, report = self.run_candidate(lambda *args: replace(self.evidence(*args), stdout=stdout))
            self.assertEqual(report["status"], verdict)
            self.assertEqual(self.client.post(route + "/review/ACCEPTED", json={}).status_code, 409)

    def test_permission_and_evidence_binding(self):
        def never(*args):
            self.fail("Denied candidate reached Worker")
        _, denied = self.run_candidate(never, {"protected.py": "x"})
        self.assertEqual(denied["status"], "REJECTED")
        _, report = self.run_candidate(lambda *args: replace(self.evidence(*args), test_hash="old"))
        self.assertEqual(report["status"], "INCONCLUSIVE")
        self.assertEqual(self.client.post(self.project + "/runs", json={
            "revision": 2, "mode": "live", "authorize_source": True}).status_code, 503)

    def test_worker_stages_inputs_only_and_model_context_omits_acceptance(self):
        user_data = json.loads(_messages(self.frozen)[1]["content"])
        self.assertEqual(user_data["public_cases"], self.plan["public_cases"])
        self.assertNotIn("acceptance_cases", user_data)
        project, _, _ = project_candidate(self.frozen, {"main.py": "after"})
        case = {"entrypoint": "main.py:solve", "input": 3}
        with patch("trustbound.workspace_execution._execute_sandbox",
                   return_value=self.evidence({"case": case}, "acceptance", project["snapshot_hash"],
                                              invocation_hash(case))) as docker:
            run_workspace_case({"task_id": PROFILE, "phase": "acceptance",
                                "files": [{"path": "main.py", "content": "after"}],
                                "candidate_sha256": project["snapshot_hash"], "case": case})
            staged = docker.call_args.args[0]
        self.assertEqual(set(staged), {"entry.py", "input.json", "project/main.py"})
        self.assertEqual(json.loads(staged["input.json"]), case)

    def test_model_picker_intersects_live_catalog_with_operator_allowlist(self):
        text = {"output_modalities": ["text"]}
        with patch.dict(os.environ, {"VULTR_MODEL": "approved-main",
                                     "TRUSTBOUND_WORKSPACE_MODELS": "approved-extra,image-only,missing"}):
            with patch("trustbound.workspace_execution.VultrClient") as client:
                client.return_value.catalog.return_value = {"data": [
                    {"id": "approved-main", "architecture": text},
                    {"id": "approved-extra", "architecture": text},
                    {"id": "unapproved", "architecture": text},
                    {"id": "image-only", "architecture": {"output_modalities": ["image"]}},
                ]}
                self.assertEqual(workspace_model_choices(), ["approved-main", "approved-extra"])
                client.return_value.complete.assert_not_called()
        with self.assertRaises(ValueError):
            StartWorkspaceRun(mode="original", revision=2, model_id="approved-main")

    def test_retry_discloses_one_confirmed_case_and_rechecks_the_new_candidate(self):
        prior_path, prior = self.run_candidate(lambda *args: replace(self.evidence(*args), stdout="5"))
        with (patch.dict(os.environ, {"TRUSTBOUND_ENABLE_WORKSPACE_LIVE": "1",
                "TRUSTBOUND_ENABLE_RECOVERY_LIVE": "1", "VULTR_INFERENCE_API_KEY": "test-placeholder",
                "VULTR_MODEL": "test-model"}),
              patch("trustbound.api.workspace_transport", return_value="ROOTLESS_WORKER"),
              patch("trustbound.api.deployment_settings", return_value=(False, "", Mock()))):
            app = create_app(report_directory=None)
            with TestClient(app, base_url="http://127.0.0.1", headers=self.client.headers) as live:
                offer = live.get(prior_path).json()["retry"]
                self.assertEqual(offer["failure"]["actual"], 5)
                payload = {"revision": 2, "mode": "live", "retry_run_id": prior["run_id"]}
                self.assertEqual(live.post(self.project + "/runs", json=payload).status_code, 422)
                with (patch("trustbound.workspace_execution._live_replacements", return_value={"main.py": "fixed"}) as model,
                      patch("trustbound.workspace_execution.run_worker_request", side_effect=self.evidence) as worker):
                    response = live.post(self.project + "/runs", json={**payload, "authorize_source": True})
                    self.assertEqual(response.status_code, 202, response.text)
                    target = self.project + "/runs/" + response.json()["run_id"]
                    for _ in range(100):
                        record = live.get(target).json()
                        if record["state"] == "COMPLETED":
                            break
                        time.sleep(.01)
                    self.assertEqual(record["workspace_report"]["status"], "VERIFIED")
                    self.assertEqual(record["workspace_report"]["retried_from"], prior["run_id"])
                    context = model.call_args.args[2]
                    request = json.loads(_messages(self.frozen, context)[1]["content"])
                    self.assertEqual(request["files"]["main.py"], "after")
                    self.assertEqual(request["confirmed_failure"], offer["failure"])
                    self.assertNotIn("acceptance_cases", request)
                    self.assertEqual(worker.call_count, 2)
                    duplicate = live.post(self.project + "/runs", json={**payload, "authorize_source": True})
                    self.assertEqual(duplicate.status_code, 202)
                    self.assertEqual(duplicate.json()['run_id'], response.json()['run_id'])
                    self.assertEqual(model.call_count, 1)

    def test_retry_rejects_sealed_acceptance_failed_integrity_and_exhaustion(self):
        def fail_acceptance(*args):
            observed = self.evidence(*args)
            return replace(observed, stdout="99") if observed.phase == "acceptance" else observed

        route, _ = self.run_candidate(fail_acceptance)
        self.assertIsNone(workspace_retry_context(self.frozen, self.client.get(route).json()))
        route, _ = self.run_candidate(lambda *args: replace(self.evidence(*args), stdout="99"))
        prior = self.client.get(route).json()
        prior["workspace_report"]["cases"][0]["execution"]["cleanup_confirmed"] = False
        self.assertIsNone(workspace_retry_context(self.frozen, prior))
        prior["workspace_report"]["cases"][0]["execution"]["cleanup_confirmed"] = True
        prior["workspace_report"]["retry_attempt"] = 2
        self.assertIsNone(workspace_retry_context(self.frozen, prior))

    def test_discard_preserves_the_report_and_blocks_export(self):
        route, report = self.run_candidate(self.evidence)
        discarded = self.client.post(route + "/review/REJECTED", json={}).json()
        self.assertEqual(discarded["review"], "REJECTED")
        self.assertEqual(discarded["workspace_report"], report)
        self.assertEqual(self.client.get(route + "/export/zip").status_code, 409)
