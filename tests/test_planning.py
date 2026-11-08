"""Planning routes, advisory model validation, and approval integrity."""
import json
import os
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory
import unittest
from contextlib import closing
from unittest.mock import patch

from fastapi.testclient import TestClient

from trustbound.api import create_app
from trustbound.workspace import PlanDraft
from trustbound.inference import InferenceError
from trustbound.planning import generate_plan, rule_triage, semantic_triage


DRAFT = {"implementation": ["Implement the stated fixture requirement"], "constraints": ["Modify only approved paths"], "risks": ["Boundary cases require independent checks"], "acceptance_basis": "User-specified fixture contract, independently computed for distinct inputs.", "goal": "Fix the rounding threshold", "allowed_write_paths": ["main.py"],
         "entrypoint": "main.py:solve", "public_cases": [{"input": 1, "expected": 2}],
         "acceptance_cases": [{"input": 2, "expected": 4}]}
CATALOG = {"data": [{"id": "review-model", "architecture": {"output_modalities": ["text"]}}]}


class PlanningTests(unittest.TestCase):
    def setUp(self):
        temporary = self.enterContext(TemporaryDirectory())
        self.db = Path(temporary) / "workspace.sqlite3"
        self.enterContext(patch.dict(os.environ, {
            "TRUSTBOUND_PUBLIC_DEMO": "0", "TRUSTBOUND_ENABLE_WORKSPACE": "1",
            "TRUSTBOUND_WORKSPACE_LOCAL_PREVIEW": "0", "TRUSTBOUND_QUOTA_DB": "",
            "TRUSTBOUND_WORKSPACE_DB": str(self.db), "TRUSTBOUND_WORKSPACE_TOKEN": "p" * 40,
        }))
        with patch("trustbound.api.workspace_transport", return_value="ROOTLESS_WORKER"):
            self.client = self.enterContext(TestClient(create_app(report_directory=None), base_url="http://127.0.0.1"))
        self.client.headers["Authorization"] = "Bearer " + "p" * 40
        created = self.client.post("/api/workspace/projects", json={"files": [
            {"path": "main.py", "content": "def solve(value): return value"},
            {"path": "helper.py", "content": "FACTOR = 2"},
        ]})
        self.assertEqual(created.status_code, 201)
        self.path = "/api/workspace/projects/" + created.json()["project_id"]

    def triage(self, revision=0, **updates):
        response = self.client.post(self.path + "/triage", json={**DRAFT, "revision": revision, **updates})
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def freeze(self, revision, approval="formal"):
        return self.client.post(self.path + "/freeze", json={"revision": revision, "approval": approval, "confirm_acceptance": True})

    def run_at(self, revision):
        return self.client.post(self.path + "/runs", json={"revision": revision, "mode": "original"})

    def test_direct_is_compact_but_still_requires_matching_approval(self):
        draft = self.triage()
        self.assertEqual(draft["plan"]["planning"]["route"], "DIRECT")
        self.assertEqual(self.run_at(draft["revision"]).status_code, 409)
        self.assertEqual(self.freeze(draft["revision"]).status_code, 409)
        frozen = self.freeze(draft["revision"], "direct")
        self.assertEqual(frozen.status_code, 200)
        with closing(sqlite3.connect(self.db)) as db:
            spec = json.loads(db.execute("SELECT spec FROM freezes").fetchone()[0])
            self.assertEqual(db.execute("SELECT count(*) FROM planning_events").fetchone()[0], 2)
        self.assertEqual(spec["snapshot_hash"], draft["snapshot_hash"])
        self.assertEqual(spec["policy"]["timeout_per_case_seconds"], 3)
        self.assertEqual(spec["policy"]["network"], "none")

    def test_clarification_retriage_and_stale_revision(self):
        first = self.triage(acceptance_cases=[])
        self.assertEqual(first["plan"]["planning"]["route"], "CLARIFY")
        self.assertEqual(first["plan"]["planning"]["missing_requirements"], ["acceptance_cases"])
        self.assertEqual(self.freeze(first["revision"]).status_code, 409)
        next_draft = self.triage(first["revision"])
        self.assertEqual(next_draft["plan"]["planning"]["route"], "DIRECT")
        self.assertEqual(self.freeze(first["revision"], "direct").status_code, 409)

    def test_hard_rules_never_consult_vultr_or_accept_direct_approval(self):
        with patch("trustbound.api.semantic_triage") as model:
            first = self.triage(allowed_write_paths=["main.py", "helper.py"], authorize_model=True)
            for goal in ("Fix authentication", "Delete the database", "Fix rounding and add a cache"):
                first = self.triage(first["revision"], goal=goal, authorize_model=True)
                self.assertEqual(first["plan"]["planning"]["route"], "PLAN_REQUIRED")
                self.assertEqual(self.freeze(first["revision"], "direct").status_code, 409)
            model.assert_not_called()
        self.assertEqual(self.freeze(first["revision"]).status_code, 200)

    def test_quick_mode_cannot_bypass_risk_clarification_or_approval(self):
        quick = self.triage(goal="Normalize the supplied function output", quick_mode=True)
        self.assertEqual(quick["plan"]["planning"]["route"], "DIRECT")
        self.assertEqual(self.run_at(quick["revision"]).status_code, 409)
        frozen = self.freeze(quick["revision"], "direct")
        self.assertEqual(frozen.status_code, 200)
        self.assertTrue(frozen.json()["plan"]["quick_mode"])
        incomplete = self.triage(frozen.json()["revision"], quick_mode=True, acceptance_cases=[])
        self.assertEqual(incomplete["state"], "CLARIFYING")
        self.assertEqual(self.freeze(incomplete["revision"], "direct").status_code, 409)
        high_risk = self.triage(incomplete["revision"], quick_mode=True, goal="Change authentication")
        self.assertEqual(high_risk["plan"]["planning"]["route"], "PLAN_REQUIRED")
        self.assertEqual(self.freeze(high_risk["revision"], "direct").status_code, 409)

    def test_generated_plan_requires_review_and_valid_existing_scope(self):
        from trustbound.workspace import PlanDraft
        with (patch.dict(os.environ, {"TRUSTBOUND_ENABLE_WORKSPACE_LIVE": "1",
                "VULTR_INFERENCE_API_KEY": "test-placeholder", "VULTR_MODEL": "review-model"}),
              patch("trustbound.api.workspace_transport", return_value="ROOTLESS_WORKER"),
              patch("trustbound.api.deployment_settings", return_value=(False, "", object()))):
            app = create_app(report_directory=None)
        with TestClient(app, base_url="http://127.0.0.1", headers=self.client.headers) as live:
            body = {"revision": 0, "goal": DRAFT["goal"], "model_id": "review-model", "authorize_model": True}
            # The API checks configuration at request time, so keep credentials scoped to the test.
            with (patch.dict(os.environ, {"TRUSTBOUND_ENABLE_WORKSPACE_LIVE": "1",
                    "VULTR_INFERENCE_API_KEY": "test-placeholder", "VULTR_MODEL": "review-model"}),
                  patch("trustbound.api.inference_admission"),
                  patch("trustbound.api.generate_plan") as generate):
                generate.return_value = (PlanDraft(revision=99, **DRAFT), {"live_request_count": 1})
                reply = live.post(self.path + "/generate-plan", json=body)
                self.assertEqual(reply.status_code, 200, reply.text)
                draft = reply.json()
                self.assertEqual(draft["state"], "PLAN_READY")
                self.assertEqual(draft["revision"], 1)
                self.assertIsNone(draft["frozen_hash"])
                self.assertEqual(draft["plan"]["source"], "VULTR_PLAN")
                self.assertEqual(self.run_at(1).status_code, 409)
                self.assertEqual(self.freeze(1).status_code, 200)
                generate.return_value = (PlanDraft(revision=0, **{**DRAFT, "allowed_write_paths": ["missing.py"]}), {})
                self.assertEqual(live.post(self.path + "/generate-plan", json={**body, "revision": 2}).status_code, 422)
                generate.side_effect = InferenceError("INVALID_PLAN_RESPONSE")
                self.assertEqual(live.post(self.path + "/generate-plan", json={**body, "revision": 2}).status_code, 502)

    def test_ai_plan_context_contains_only_goal_source_and_schema(self):
        project = {"files": [{"path": "main.py", "content": "def solve(x): return x * 2"}],
                   "plan": {"acceptance_cases": [{"input": "protected-answer", "expected": 99}]}}
        with patch("trustbound.planning.VultrClient") as client:
            client.return_value.catalog.return_value = CATALOG
            client.return_value.complete.return_value = json.dumps({**PlanDraft(revision=0, **DRAFT).model_dump(), "implementation": ["Update threshold in solve"], "constraints": ["Only main.py"], "risks": ["Check boundary rounding"]})
            draft, _ = generate_plan(project, "Return twice the input", "review-model")
            self.assertEqual(draft.allowed_write_paths, ["main.py"])
            call = client.return_value.complete.call_args
            messages = call.args[1]
            content = json.loads(messages[1]["content"])
            self.assertEqual(set(content), {"goal", "files", "schema", "user_details", "correctness_verification"})
            self.assertNotIn("protected-answer", json.dumps(messages))
            self.assertEqual(call.args[2], 4096)
            client.assert_called_once_with(timeout=60, max_attempts=1, output_limit=4096)
            client.return_value.complete.return_value = "{"
            with self.assertRaises(InferenceError):
                generate_plan(project, "Return twice the input", "review-model")

    def test_source_change_invalidates_approval_even_if_stored_hash_is_unchanged(self):
        draft = self.triage()
        frozen = self.freeze(draft["revision"], "direct").json()
        with closing(sqlite3.connect(self.db)) as db, db:
            project_id, payload = db.execute("SELECT id, snapshot FROM projects").fetchone()
            snapshot = json.loads(payload)
            snapshot["files"][0]["content"] += "\n# changed"
            db.execute("UPDATE projects SET snapshot=? WHERE id=?", (json.dumps(snapshot), project_id))
        response = self.run_at(frozen["revision"])
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["error"]["code"], "WORKSPACE_FREEZE_INVALID")

    def test_model_schema_fallback_and_scope_check(self):
        plan = {**DRAFT, "goal": "Normalize rounding behavior for the supplied fixture"}
        rules = rule_triage(plan)
        self.assertTrue(rules["semantic_eligible"])
        valid = {"route": "DIRECT", "reasons": ["One bounded function."], "missing_requirements": [],
                 "affected_scope": ["main.py"], "risk_flags": []}
        with (patch.dict(os.environ, {"VULTR_MODEL": "review-model"}),
              patch("trustbound.planning.VultrClient") as client):
            client.return_value.catalog.return_value = CATALOG
            complete = client.return_value.complete
            for text in ("{", json.dumps({**valid, "affected_scope": ["unknown.py"]})):
                complete.return_value = text
                decision = semantic_triage(plan, rules, ["main.py", "helper.py"])
                self.assertEqual(decision["route"], "PLAN_REQUIRED")
                self.assertEqual(decision["source"], "CONSERVATIVE_FALLBACK")
            complete.side_effect = InferenceError("TIMEOUT_BILLING_UNKNOWN")
            self.assertEqual(semantic_triage(plan, rules, ["main.py"])["route"], "PLAN_REQUIRED")
            complete.side_effect = None
            complete.return_value = json.dumps(valid)
            self.assertEqual(semantic_triage(plan, rules, ["main.py"])["route"], "DIRECT")
            user_context = complete.call_args.args[1][1]["content"]
            self.assertNotIn("acceptance_cases", user_context)
            self.assertNotIn("expected", user_context)

