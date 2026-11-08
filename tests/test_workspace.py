"""Exercise the private Workspace before introducing any execution path."""
import base64
from contextlib import closing
from io import BytesIO
import json
import os
from pathlib import Path
import sqlite3
import stat
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
import zipfile

from fastapi.testclient import TestClient

from trustbound.api import create_app
from trustbound.workspace import ImportProject, WorkspaceError, WorkspaceStore, digest, project_snapshot


TOKEN = "t" * 40
HEADERS = {"Authorization": f"Bearer {TOKEN}"}
PROJECTS = "/api/workspace/projects"
FILES = {"files": [{"path": "lib/main.py", "content": 'raise RuntimeError("must not execute")'}]}
PLAN = {"implementation": ["Implement the stated fixture requirement"], "constraints": ["Modify only approved paths"], "risks": ["Boundary cases require independent checks"], "acceptance_basis": "User-specified fixture contract, independently computed for distinct inputs.", "goal": "修正计数规则", "entrypoint": "lib/main.py:solve",
        "allowed_write_paths": ["lib/main.py"],
        "public_cases": [{"input": [1], "expected": 1}],
        "acceptance_cases": [{"input": [2, 3], "expected": 2}]}


def archive(entries):
    data = BytesIO()
    with zipfile.ZipFile(data, "w", compression=zipfile.ZIP_DEFLATED) as output:
        for name, content in entries:
            output.writestr(name, content)
    return base64.b64encode(data.getvalue()).decode()


class WorkspaceTests(unittest.TestCase):
    def setUp(self):
        tmp = self.enterContext(TemporaryDirectory())
        self.db = Path(tmp) / "workspace.sqlite3"
        self.enterContext(patch.dict(os.environ, {
            "TRUSTBOUND_PUBLIC_DEMO": "0", "TRUSTBOUND_ENABLE_WORKSPACE": "1",
            "TRUSTBOUND_WORKSPACE_TOKEN": TOKEN, "TRUSTBOUND_WORKSPACE_DB": str(self.db),
        }))
        self.client = self.enterContext(TestClient(create_app(report_directory=None), base_url="http://127.0.0.1"))

    def post(self, path, body, expected=200):
        reply = self.client.post(path, json=body, headers=HEADERS)
        self.assertEqual(reply.status_code, expected, reply.text)
        self.assertEqual(reply.headers["cache-control"], "no-store")
        return reply.json()

    def test_import_plan_freeze_and_keep_original_approval(self):
        project = self.post(PROJECTS, FILES, 201)
        path = f"{PROJECTS}/{project['project_id']}"
        self.assertEqual(project["state"], "IMPORTED")
        draft = self.post(path + "/plan", {"goal": "修复计数", "revision": 0})
        self.assertEqual(draft["state"], "CLARIFYING")
        self.assertTrue(draft["plan"]["questions"])
        self.post(path + "/freeze", {"revision": 1}, 409)
        ready = self.post(path + "/plan", {**PLAN, "revision": 1})
        self.assertEqual(ready["state"], "PLAN_READY")
        self.assertEqual(ready["plan"]["source"], "OFFLINE_RULES")
        self.post(path + "/freeze", {"revision": 1}, 409)
        frozen = self.post(path + "/freeze", {"revision": 2, "confirm_acceptance": True})
        self.assertEqual(frozen["state"], "FROZEN")
        self.assertEqual(frozen["snapshot_hash"], project["snapshot_hash"])
        revised = self.post(path + "/plan", {**PLAN, "revision": 3, "goal": "新的计数规则"})
        self.assertIsNone(revised["frozen_hash"])
        self.assertEqual(self.post(path + "/reject", {"revision": 4})["state"], "REJECTED")
        self.post(path + "/freeze", {"revision": 5}, 409)
        with closing(sqlite3.connect(self.db)) as db:
            spec = json.loads(db.execute("SELECT spec FROM freezes").fetchone()[0])
        self.assertEqual(digest(spec), frozen["frozen_hash"])
        self.assertEqual(spec["plan"]["goal"], PLAN["goal"])
        self.assertEqual(WorkspaceStore(self.db).read("private-operator", project["project_id"])["state"], "REJECTED")
        self.assertIsNone(self.client.get("/api/health").json()["active_run_id"])

    def test_requires_private_access_and_does_not_enable_execution(self):
        self.assertEqual(self.client.post(PROJECTS, json=FILES).status_code, 401)
        self.assertEqual(self.client.post(PROJECTS, json=FILES, headers={
            **HEADERS, "x-trustbound-public": "1"}).status_code, 404)
        self.assertEqual(self.client.post(PROJECTS, json=FILES, headers={
            **HEADERS, "Origin": "https://untrusted.invalid"}).status_code, 403)
        project = self.post(PROJECTS, FILES, 201)
        self.assertEqual(self.client.post(f"{PROJECTS}/{project['project_id']}/run",
                                          json=FILES, headers=HEADERS).status_code, 404)
        with self.assertRaises(WorkspaceError) as err:
            WorkspaceStore(self.db).read("other-operator", project["project_id"])
        self.assertEqual(err.exception.status, 404)
        with patch.dict(os.environ, {"TRUSTBOUND_ENABLE_WORKSPACE": "0"}):
            with TestClient(create_app(report_directory=None), base_url="http://127.0.0.1") as disabled:
                self.assertEqual(disabled.post(PROJECTS, json=FILES, headers=HEADERS).status_code, 404)

    def test_public_profile_cannot_activate_workspace(self):
        with (patch("trustbound.api.deployment_settings", return_value=(True, "demo.example.com", None)),
              patch.dict(os.environ, {"TRUSTBOUND_WORKSPACE_LOCAL_PREVIEW": "1"})):
            app = create_app(report_directory=self.db.parent / "reports")
        with TestClient(app, base_url="http://127.0.0.1") as public:
            self.assertFalse(public.get("/api/health").json()["workspace"]["enabled"])
            self.assertEqual(public.post(PROJECTS, json=FILES, headers=HEADERS).status_code, 404)

    def test_local_preview_imports_without_a_token_and_rejects_remote_clients(self):
        with (patch("trustbound.api.workspace_transport", return_value="LOCAL_DOCKER"),
              patch.dict(os.environ, {"TRUSTBOUND_WORKSPACE_LOCAL_PREVIEW": "1", "TRUSTBOUND_WORKSPACE_TOKEN": "",
                                      "TRUSTBOUND_WORKSPACE_DB": ""})):
            app = create_app(report_directory=None)
        with TestClient(app, base_url="http://127.0.0.1", client=("127.0.0.1", 50000)) as local:
            self.assertEqual(local.get("/api/health").json()["workspace"]["access"], "local")
            project = local.post(PROJECTS, json=FILES)
            self.assertEqual(project.status_code, 201)
            project_path = f"{PROJECTS}/{project.json()['project_id']}"
            self.assertEqual(local.get(project_path).status_code, 200)
            self.assertEqual(local.get(project_path, headers={"Sec-Fetch-Site": "cross-site"}).status_code, 403)
            local.base_url = "http://127.0.0.1:57787"
            self.assertEqual(local.post(PROJECTS, json=FILES,
                headers={"Origin": "http://127.0.0.1:57787"}).status_code, 201)
            self.assertEqual(local.post(PROJECTS, json=FILES,
                headers={"Origin": "http://127.0.0.1:57788"}).status_code, 403)
            preview_db = app.state.projects.path
        self.assertFalse(preview_db.exists())
        with TestClient(app, base_url="http://127.0.0.1", client=("127.0.0.1", 50000)) as restarted:
            self.assertEqual(restarted.get(project_path).status_code, 404)
            self.assertEqual(restarted.post(PROJECTS, json=FILES).status_code, 201)
        with TestClient(app, base_url="http://127.0.0.1", client=("192.0.2.1", 50000)) as remote:
            self.assertEqual(remote.post(PROJECTS, json=FILES).status_code, 403)

    def test_local_preview_switch_cannot_bypass_worker_authentication(self):
        with (patch("trustbound.api.workspace_transport", return_value="ROOTLESS_WORKER"),
              patch.dict(os.environ, {"TRUSTBOUND_WORKSPACE_LOCAL_PREVIEW": "1"})):
            app = create_app(report_directory=None)
        with TestClient(app, base_url="http://127.0.0.1", client=("127.0.0.1", 50000)) as local:
            self.assertEqual(local.get("/api/health").json()["workspace"]["access"], "token")
            self.assertEqual(local.post(PROJECTS, json=FILES).status_code, 401)

    def test_rejects_untrusted_scope_and_acceptance_overlap(self):
        project = self.post(PROJECTS, FILES, 201)
        route = f"{PROJECTS}/{project['project_id']}/plan"
        for invalid in [
            {"allowed_write_paths": ["../main.py"]},
            {"entrypoint": "lib/main.py:solve()"},
            {"acceptance_cases": PLAN["public_cases"]},
            {"docker_args": ["--privileged"]},
        ]:
            self.post(route, {**PLAN, "revision": 0, **invalid}, 422)

    def test_snapshot_hash_matches_across_folder_and_zip(self):
        folder = self.post(PROJECTS, FILES, 201)
        zipped = self.post(PROJECTS, {"zip_base64": archive([
            ("lib/", ""), ("lib/main.py", FILES["files"][0]["content"]),
        ])}, 201)
        self.assertEqual(folder["snapshot_hash"], zipped["snapshot_hash"])

    def test_imported_plan_requires_new_approval_and_stays_outside_source(self):
        project = self.post(PROJECTS, {"files": [*FILES["files"], {
            "path": "TRUSTBOUND_PLAN.json", "content": json.dumps({"version": 1, **PLAN}),
        }]}, 201)
        self.assertEqual(project["state"], "PLAN_READY")
        self.assertIsNone(project["frozen_hash"])
        self.assertEqual([file["path"] for file in project["files"]], ["lib/main.py"])
        route = f"{PROJECTS}/{project['project_id']}"
        self.assertEqual(self.client.get(route + "/plan-document/0", headers=HEADERS).status_code, 409)
        frozen = self.post(route + "/freeze", {"revision": 0, "confirm_acceptance": True})
        saved = self.client.get(route + f"/plan-document/{frozen['revision']}", headers=HEADERS)
        self.assertEqual(saved.json()["acceptance_cases"], PLAN["acceptance_cases"])

    def test_path_and_archive_guards(self):
        symlink = zipfile.ZipInfo("alias.py")
        symlink.create_system = 3
        symlink.external_attr = (stat.S_IFLNK | 0o777) << 16
        for entries in [
            [("../escape.py", "x")], [("C:/escape.py", "x")],
            [("a.py", "x"), ("A.py", "y")], [("lib/main.py", "x"), ("Lib/other.py", "y")],
            [("lib.py", "x"), ("lib.py/child.py", "y")],
            [("con.py", "x")], [("credentials.py", "x")],
            [(symlink, "../secret.py")],
        ]:
            with self.subTest(entries=entries):
                self.post(PROJECTS, {"zip_base64": archive(entries)}, 422)
        self.post(PROJECTS, {"zip_base64": archive([("large.py", "x" * 4097)])}, 413)
        self.post(PROJECTS, {"zip_base64": "!"}, 422)
        response = self.client.post(PROJECTS, content=b"x" * (96 * 1024 + 1), headers=HEADERS)
        self.assertEqual(response.status_code, 413)
        with self.assertRaises(WorkspaceError):
            project_snapshot(ImportProject(files=[{"path": "a.py", "content": "x\x00"}]))
