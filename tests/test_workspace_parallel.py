"""Offline tests for independent Workspace proposals and trustworthy challenge judgments."""
from dataclasses import replace
import json
import os
from pathlib import Path
import threading
import unittest
from unittest.mock import patch

from trustbound.contracts import ExecutionResult
from trustbound.inference import InferenceError, VultrClient
from trustbound.admission import inference_admission
from trustbound.runner import IMAGE
from trustbound.workspace import ImportProject, PlanDraft, offline_plan, project_snapshot
from trustbound.workspace_adversarial import challenge_messages, generate_challenges
from trustbound.workspace_execution import (PROFILE, StartWorkspaceRun, WorkspaceJob, _messages,
                                           execute_workspace, workspace_retry_context)
from trustbound.workspace_reference import reference_result
from trustbound.workspace_samples import sample


class ParallelWorkspaceTests(unittest.TestCase):
    def setUp(self):
        imported, draft, self.fixed = sample("inventory")
        self.project = {**project_snapshot(imported), "project_id": "b" * 32, "frozen_hash": "c" * 64,
                        "revision": 2, "owner": "private-operator"}
        self.project["plan"] = {**offline_plan(self.project, draft), "adversarial_enabled": True}
        self.input = {"stock": {"a": 4}, "order": []}

    def proposals(self):
        return {"status": "GENERATED", "source": "OFFLINE_TEST", "frozen_hash": self.project["frozen_hash"],
                "snapshot_hash": self.project["snapshot_hash"], "challenges": [{
                    "challenge_id": "live-1", "input": self.input, "reason": "Empty order",
                    "expected": reference_result("inventory", self.input), "status": "VALID"}]}

    def observe(self, payload, phase, artifact, test_hash):
        expected = reference_result("inventory", payload["case"]["input"])
        return ExecutionResult(phase, "trustbound-test-double", IMAGE, artifact, test_hash,
                               "EXITED", 0, json.dumps(expected), "", None, True, True, True)

    def run_parallel(self, executor=None, adversary=None, observer=None, retry=None, enabled=True):
        request = StartWorkspaceRun(revision=2, mode="live", authorize_source=True,
                                    adversarial_enabled=enabled, model_id="test-model")
        job = WorkspaceJob(self.project, request, "ROOTLESS_WORKER", retry=retry)
        with (patch("trustbound.workspace_execution._live_replacements", side_effect=executor or (lambda *args: self.fixed)),
              patch("trustbound.workspace_execution.generate_challenges", side_effect=adversary or (lambda *args: self.proposals())) as model,
              patch("trustbound.workspace_execution.run_worker_request", side_effect=observer or self.observe)):
            result = execute_workspace(job, "d" * 32)
        return result, model.call_count

    def test_independent_contexts_and_actual_parallel_entry(self):
        barrier = threading.Barrier(2)
        contexts = []
        def executor(project, *args):
            contexts.append(json.loads(_messages(project)[1]["content"]))
            barrier.wait(timeout=3)
            return self.fixed
        def adversary(project, *args):
            contexts.append(json.loads(challenge_messages(project)[1]["content"]))
            barrier.wait(timeout=3)
            return self.proposals()
        report, calls = self.run_parallel(executor, adversary)
        self.assertEqual(report["status"], "VERIFIED")
        self.assertEqual(calls, 1)
        self.assertEqual(contexts[0]["frozen_hash"], contexts[1]["frozen_hash"])
        for context in contexts:
            self.assertNotIn("acceptance_cases", context)
            self.assertNotIn("retry_evidence", context)
        self.assertEqual(report["adversarial_report"]["verification_status"], "COMPLETED")

    def test_off_switch_and_unapproved_on(self):
        report, calls = self.run_parallel(enabled=False)
        self.assertEqual(calls, 0)
        self.assertEqual(report["status"], "VERIFIED")
        self.project["plan"]["adversarial_enabled"] = False
        report, calls = self.run_parallel()
        self.assertEqual((report["status"], calls), ("REJECTED", 0))

    def test_parallel_http_contract_preserves_admission_and_separate_usage(self):
        barrier = threading.Barrier(2)
        reserved = []
        reserve_lock = threading.Lock()
        class Admission:
            def reserve_model(self, outputs):
                with reserve_lock:
                    reserved.append(outputs)
        def transport(method, path, payload, key, timeout):
            if method == "GET":
                return {"data": [{"id": "test-model", "architecture": {"output_modalities": ["text"]}}]}
            barrier.wait(timeout=3)
            executor = "minimal Python repair" in payload["messages"][0]["content"]
            content = {"files": self.fixed} if executor else {"challenges": [
                {"input": self.input, "basis": "approved_reference", "reason": "Empty order"}]}
            return {"model": "test-model", "usage": {"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30},
                    "choices": [{"finish_reason": "stop", "message": {"content": json.dumps(content)}}]}
        def client(**kwargs):
            instance = VultrClient("unit-test-placeholder", transport=transport, **kwargs)
            # Emulate the production admission path without network transport.
            instance.source = "VULTR_LIVE_HTTP"
            return instance
        request = StartWorkspaceRun(revision=2, mode="live", authorize_source=True,
                                    adversarial_enabled=True, model_id="test-model")
        with (patch.dict(os.environ, {"VULTR_MODEL": "test-model"}),
              patch("trustbound.workspace_execution.VultrClient", side_effect=client),
              patch("trustbound.workspace_adversarial.VultrClient", side_effect=client),
              patch("trustbound.workspace_execution.run_worker_request", side_effect=self.observe),
              inference_admission(Admission())):
            report = execute_workspace(WorkspaceJob(self.project, request, "ROOTLESS_WORKER"), "e" * 32)
        self.assertEqual(report["status"], "VERIFIED")
        self.assertEqual(sorted(reserved), [4096, 4096])
        self.assertEqual(report["inference_usage"]["request_count"], 2)
        self.assertEqual(report["inference_usage"]["completion_tokens"], 40)

    def test_counterexample_is_confirmed_and_recovery_revalidates(self):
        def wrong(payload, *args):
            observed = self.observe(payload, *args)
            if payload["case"]["input"] == self.input:
                return replace(observed, stdout=json.dumps({"ok": False, "stock": {"a": 4}}))
            return observed
        report, _ = self.run_parallel(observer=wrong)
        self.assertEqual((report["formal_status"], report["status"]), ("VERIFIED", "FAILED"))
        self.assertEqual(report["adversarial_report"]["challenges"][0]["status"], "CONFIRMED")
        context = workspace_retry_context(self.project, {"state": "COMPLETED", "review": None, "workspace_report": report})
        self.assertEqual(context["failure"]["input"], self.input)
        repaired, _ = self.run_parallel(retry=context)
        self.assertEqual(repaired["status"], "VERIFIED")
        self.assertTrue(any(case.get("origin") == "CONFIRMED_REPLAY" for case in repaired["cases"]))
        tampered = json.loads(json.dumps(report))
        tampered["cases"][-1]["expected"] = {}
        self.assertIsNone(workspace_retry_context(self.project,
            {"state": "COMPLETED", "review": None, "workspace_report": tampered}))

    def test_generation_error_or_unconfirmed_requirements_never_certify_success(self):
        for code in ("TIMEOUT_BILLING_UNKNOWN", "MODEL_QUOTA_EXHAUSTED"):
            def failure(*args):
                raise InferenceError(code)
            report, _ = self.run_parallel(adversary=failure)
            self.assertEqual((report["formal_status"], report["status"]), ("VERIFIED", "INCONCLUSIVE"))
            self.assertEqual(report["adversarial_report"]["reason"], code)
        pending = self.proposals()
        pending["challenges"][0]["status"] = "NEEDS_CONFIRMATION"
        pending["challenges"][0].pop("expected")
        report, _ = self.run_parallel(adversary=lambda *args: pending)
        self.assertEqual(report["status"], "INCONCLUSIVE")

    def test_input_generation_does_not_trust_expected_values(self):
        with (patch.dict(os.environ, {"VULTR_MODEL": "test-model"}),
              patch("trustbound.workspace_adversarial.VultrClient") as client):
            client.return_value.catalog.return_value = {"data": [{"id": "test-model",
                "architecture": {"output_modalities": ["text"]}}]}
            proposal = {"input": self.input, "basis": "approved_reference", "reason": "Empty order"}
            client.return_value.complete.return_value = json.dumps({"challenges": [proposal]})
            result = generate_challenges(self.project, "test-model")
            self.assertEqual(result["challenges"][0]["expected"], {"ok": True, "stock": {"a": 4}})
            client.return_value.complete.return_value = json.dumps({"challenges": [{**proposal, "expected": "invented"}]})
            with self.assertRaises(ValueError):
                generate_challenges(self.project, "test-model")
            client.return_value.complete.return_value = json.dumps({"challenges": [{**proposal, "input": "../host"}]})
            self.assertEqual(generate_challenges(self.project, "test-model")["challenges"][0]["status"], "INVALID")

    def test_reference_rules_cover_atomicity_and_log_boundaries(self):
        value = {"stock": {"a": 2, "b": 0}, "order": [["a", 1], ["b", 1]]}
        self.assertEqual(reference_result("inventory", value), {"ok": False, "stock": value["stock"]})
        logs = {"lines": ["1 INFO contains ERROR", "2 ERROR end", "-1 WARN bad", "x"],
                "start": 1, "end": 2}
        self.assertEqual(reference_result("logs", logs),
                         {"counts": {"INFO": 1, "WARN": 0, "ERROR": 0}, "invalid": 2})
