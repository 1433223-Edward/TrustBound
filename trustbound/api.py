"""Local-only asynchronous Web API over the trusted sandbox execution paths."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import ExitStack, asynccontextmanager
from copy import deepcopy
from datetime import datetime, timezone
import hmac
import json
import os
from pathlib import Path
import re
import sqlite3
from tempfile import TemporaryDirectory
import threading
from typing import Literal
import uuid

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict
from starlette.middleware.trustedhost import TrustedHostMiddleware

from .admission import Admission, AdmissionError, deployment_settings, inference_admission, model_request_identity
from .custom_tasks import CustomRunRequest, custom_enabled, execute_custom
from .service import ROOT, TASK
from .inference import InferenceError
from .planning import generate_plan, rule_triage, semantic_triage
from .web_tasks import execute_web_run, live_availability, task_details
from .workspace import (FreezeRequest, ImportProject, MAX_IMPORT_REQUEST, MAX_PLAN_REQUEST, PLAN_FILENAME,
                        GeneratePlan, PlanDraft, Revision, SaveSource, TriageDraft, WorkspaceError, WorkspaceStore, offline_plan, plan_document, digest, run_fingerprint)
from .workspace_execution import (PROFILE, StartWorkspaceRun, WorkspaceJob,
                                  execute_workspace, export_workspace, workspace_model_allowlist,
                                  workspace_model_choices, workspace_retry_context, workspace_transport)
from .workspace_samples import sample
from .quick_chat import QuickChat, quick_chat
from .workspace_explanation import ExplainRun, generate_explanation
from .model_journal import JournalError


class RunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    task_id: Literal["billing-rounding-01"]
    mode: Literal["fixture", "offline_executor", "live_executor"] = "fixture"
    candidate_id: Literal["original", "fixed", "public_only", "unauthorized", "timeout", "double_rounding"] | None = None
    adversarial_mode: Literal["off", "offline", "live"] = "off"
    adversarial_fixture: Literal["standard", "invalid", "timeout", "failure"] = "standard"
    recovery_mode: Literal["off", "offline", "live"] = "off"
    recovery_fixture: Literal["fixed", "exhausted", "unauthorized", "invalid_json", "empty", "failure", "timeout"] = "fixed"


def utc_now():
    return datetime.now(timezone.utc).isoformat()


class RunManager:
    def __init__(self, execute, directory, admission=None, projects=None):
        self.execute, self.directory = execute, directory
        self.admission = admission
        self.projects = projects
        self.lock = threading.RLock()
        self.pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="trustbound-web")
        self.records, self.active = {}, None

    def save(self, snapshot):
        if snapshot["mode"] == PROFILE:
            return self.projects.save_run(snapshot)
        if self.directory is not None:
            data = json.dumps(snapshot, indent=2, ensure_ascii=False).encode("utf-8")
            if self.admission is not None:
                # Include the existing report while budgeting its atomic replacement.
                used = sum(path.stat().st_size for path in self.directory.glob("*/*") if path.is_file())
                if len(data) > 512 * 1024 or used + len(data) > 64 * 1024 * 1024:
                    raise OSError("Evidence storage limit exceeded")
            directory = self.directory / snapshot["run_id"]
            directory.mkdir(parents=True, exist_ok=True)
            temporary = directory / "report.tmp"
            temporary.write_bytes(data)
            temporary.replace(directory / "report.json")

    def submit(self, body):
        with self.lock:
            workspace = isinstance(body, WorkspaceJob)
            if workspace:
                existing = self.projects.request_run(body.project['owner'], body.project['project_id'], body.request)
                if existing:
                    return existing
            if self.active is not None:
                raise HTTPException(429, detail={"code": "RUN_CAPACITY_REACHED", "message": "已有一个任务正在执行，请稍后再试。"})
            if self.admission is not None and not workspace:
                try:
                    self.admission.reserve_run()
                except AdmissionError as error:
                    unavailable = error.code == "QUOTA_STORE_UNAVAILABLE"
                    raise HTTPException(
                        503 if unavailable else 429,
                        detail={"code": error.code, "message": "执行配额不可用。" if unavailable else "已达到运行频率或总次数上限。"},
                        headers={"Retry-After": str(error.retry_after)} if error.retry_after else None,
                    ) from None
            while len(self.records) >= 50:
                del self.records[next(iter(self.records))]
            run_id = uuid.uuid4().hex
            snapshot = {"run_id": run_id, "task_id": body.task_id, "source": "LIVE", "mode": body.mode,
                        "candidate_id": body.candidate_id, "state": "QUEUED", "created_at": utc_now(),
                        "started_at": None, "finished_at": None, "proposal": None, "candidate": None,
                        "verification": None, "executor": None, "llm_source": "NONE", "error": None,
                        "adversarial_mode": body.adversarial_mode, "adversarial_fixture": body.adversarial_fixture,
                        "adversarial_report": None, "final_decision": None,
                        "recovery_mode": body.recovery_mode, "recovery_fixture": body.recovery_fixture,
                        "recovery_report": None, "current_attempt": 0 if body.recovery_mode != "off" else None}
            if isinstance(body, WorkspaceJob):
                snapshot.update(project_id=body.project["project_id"], owner=body.project["owner"],
                                frozen_hash=body.project["frozen_hash"], workspace_report=None,
                                snapshot_hash=body.project["snapshot_hash"], revision=body.project["revision"],
                                task_title=body.project["plan"]["goal"][:120])
                snapshot.update(idempotency_key=body.request.idempotency_key,
                                request_fingerprint=run_fingerprint(body.request),
                                request_mode=body.request.mode, request_journal_version=1)
                snapshot['verification_mode'] = 'FUNCTIONAL' if body.request.correctness_verification else 'SECURITY_ONLY'
                if body.retry:
                    snapshot["retry_parent"] = body.request.retry_run_id
            try:
                saved_id = self.save(snapshot)
                if workspace and saved_id != run_id:
                    return saved_id
            except WorkspaceError:
                raise
            except (OSError, ValueError, sqlite3.Error):
                raise HTTPException(503, detail={"code": "EVIDENCE_STORE_UNAVAILABLE",
                                                 "message": "证据存储不可用，任务未启动。"}) from None
            # Claim the durable identity before reserving quota or starting work.
            if workspace and self.admission is not None:
                try:
                    self.admission.reserve_run(run_id)
                    snapshot['admission_state'] = 'RESERVED'
                except AdmissionError as error:
                    snapshot.update(state='ERROR', billing_state='SAFE_TO_RETRY', error={'code': error.code})
                    self.save(snapshot)
                    raise HTTPException(503 if error.code == 'QUOTA_STORE_UNAVAILABLE' else 429,
                                        detail={'code': error.code}) from None
            self.records[run_id], self.active = snapshot, run_id
            try:
                self.pool.submit(self.work, run_id, body)
            except Exception:
                self.active = None
                del self.records[run_id]
                if workspace:
                    snapshot.update(state='ERROR', billing_state='SAFE_TO_RETRY', error={'code': 'RUN_DISPATCH_FAILED'})
                    self.save(snapshot)
                raise
            return run_id

    def work(self, run_id, body):
        try:
            with self.lock:
                record = self.records[run_id]
                record.update(state="RUNNING", started_at=utc_now())
                self.save(record)
            # No lock or ASGI event-loop work is held across Docker/model calls.
            def progress(report):
                with self.lock:
                    record.update(recovery_report=report, current_attempt=report["current_attempt"])
                    self.save(record)

            def workspace_progress(report):
                with self.lock:
                    record["workspace_report"] = report
                    self.save(record)

            options = {} if body.recovery_mode == "off" else {
                "recovery_mode": body.recovery_mode, "recovery_fixture": body.recovery_fixture,
                "run_id": run_id, "on_progress": progress}
            with inference_admission(self.admission):
                if isinstance(body, WorkspaceJob):
                    outcome = {"workspace_report": execute_workspace(body, run_id, on_progress=workspace_progress)}
                elif isinstance(body, CustomRunRequest):
                    outcome = execute_custom(body)
                else:
                    outcome = self.execute(body.task_id, body.mode, body.candidate_id,
                                           body.adversarial_mode, body.adversarial_fixture, **options)
            with self.lock:
                record.update(outcome)
                record["state"] = "ERROR" if outcome.get("error") else "COMPLETED"
        except Exception:
            with self.lock:
                record = self.records[run_id]
                record.update(state="ERROR", error={"code": "RUN_CONTROLLER_ERROR", "message": "执行或证据保存失败；未宣称验证通过。"})
        finally:
            with self.lock:
                record["finished_at"] = utc_now()
                try:
                    if isinstance(body, WorkspaceJob) and isinstance(self.admission, Admission):
                        journal = self.admission.journal
                        journal.finalize(run_id, (record.get('workspace_report') or {}).get('status', 'INCONCLUSIVE'))
                        summary = journal.summary(run_id)
                        record.update(billing_state=summary['state'], model_requests=summary['requests'])
                    self.save(record)
                except Exception:
                    record.update(state="ERROR", verification=None, final_decision=None,
                                  error={"code": "EVIDENCE_SAVE_FAILED", "message": "报告持久化失败。"})
                    if body.mode == PROFILE:
                        record["workspace_report"] = None
                self.active = None

    def get(self, run_id):
        with self.lock:
            if run_id not in self.records:
                raise HTTPException(404, detail={"code": "RUN_NOT_FOUND", "message": "任务记录不存在，服务重启后不恢复旧运行态。"})
            return deepcopy(self.records[run_id])


def create_app(*, execute=execute_web_run, report_directory=ROOT / "artifacts/web-runs"):
    public, domain, admission = deployment_settings()
    if public and report_directory is None:
        raise ValueError("Public demo requires private evidence storage")
    workspace_enabled = not public and os.environ.get("TRUSTBOUND_ENABLE_WORKSPACE") == "1"
    transport = workspace_transport() if workspace_enabled else None
    local_workspace = (transport == "LOCAL_DOCKER"
                       and os.environ.get("TRUSTBOUND_WORKSPACE_LOCAL_PREVIEW") == "1")
    workspace_db = None
    if workspace_enabled and (not local_workspace or os.environ.get("TRUSTBOUND_WORKSPACE_DB")):
        workspace_db = Path(os.environ.get("TRUSTBOUND_WORKSPACE_DB", ""))
        if not workspace_db.is_absolute():
            raise ValueError("Workspace requires an absolute database path")
    if workspace_enabled and not local_workspace:
        workspace_token = os.environ.get("TRUSTBOUND_WORKSPACE_TOKEN", "")
        if not re.fullmatch(r"[A-Za-z0-9_-]{32,128}", workspace_token):
            raise ValueError("Private Workspace requires a dedicated token")
        workspace_auth = f"Bearer {workspace_token}".encode("ascii")
    workspace_owner = "private-operator"

    def workspace_live_enabled():
        return bool(transport and admission and os.environ.get("TRUSTBOUND_ENABLE_WORKSPACE_LIVE") == "1"
                    and os.environ.get("VULTR_INFERENCE_API_KEY", "").strip()
                    and os.environ.get("VULTR_MODEL", "").strip())

    def workspace_retry_enabled():
        return workspace_live_enabled() and os.environ.get("TRUSTBOUND_ENABLE_RECOVERY_LIVE") == "1"

    @asynccontextmanager
    async def lifespan(app):
        with ExitStack() as resources:
            app.state.projects = None
            if local_workspace and workspace_db is None:
                # Workspace requests use separate SQLite connections within one preview session.
                directory = resources.enter_context(TemporaryDirectory(prefix="trustbound-workspace-"))
                app.state.projects = WorkspaceStore(Path(directory) / "workspace.sqlite3")
            elif workspace_enabled:
                app.state.projects = WorkspaceStore(workspace_db)
            if workspace_enabled:
                journal = admission.journal if isinstance(admission, Admission) else None
                if journal:
                    journal.reconcile()
                app.state.projects.reconcile_interrupted(journal)
            app.state.runs = RunManager(execute, report_directory, admission, app.state.projects)
            # Drain the Runner and its report writes before removing the temporary database.
            resources.callback(app.state.runs.pool.shutdown, wait=True)
            yield

    app = FastAPI(title="TrustBound Local API", version="0.1.0", lifespan=lifespan)
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=["localhost", "127.0.0.1"] + ([domain] if public else []))

    @app.middleware("http")
    async def local_request_policy(request: Request, call_next):
        path = request.url.path
        workspace_request = path == "/api/workspace" or path.startswith("/api/workspace/")
        if workspace_request:
            if not workspace_enabled or request.headers.get("x-trustbound-public") == "1":
                return JSONResponse({"error": {"code": "WORKSPACE_DISABLED"}}, status_code=404)
            if local_workspace:
                # This profile assumes a single trusted desktop operator.
                if (request.client is None or request.client.host not in {"127.0.0.1", "::1"}
                        or request.headers.get("sec-fetch-site") == "cross-site"):
                    return JSONResponse({"error": {"code": "WORKSPACE_LOCAL_ONLY"}}, status_code=403)
            else:
                supplied = request.headers.getlist("authorization")
                if len(supplied) != 1 or not hmac.compare_digest(supplied[0].encode("latin-1"), workspace_auth):
                    return JSONResponse({"error": {"code": "WORKSPACE_AUTH_REQUIRED"}}, status_code=401)
        # Caddy overwrites this marker after authentication. The marker can
        # restrict a request but can never grant access or model privileges.
        if request.headers.get("x-trustbound-public") == "1" and not public:
            return JSONResponse({"error": {"code": "PUBLIC_DEMO_DISABLED", "message": "公网执行入口已关闭。"}}, status_code=503)
        if request.method == "POST":
            origin = request.headers.get("origin")
            if ((public and origin != f"https://{domain}")
                    or (not public and origin and origin not in {
                        "http://localhost:5173", "http://127.0.0.1:5173",
                        "http://localhost:8000", "http://127.0.0.1:8000"})):
                return JSONResponse({"error": {"code": "ORIGIN_DENIED", "message": "请求来源不在工作区白名单。"}}, status_code=403)
            # The opt-in custom path accepts bounded source and structured data only.
            limit = 8192 if not public and request.url.path == "/api/custom-runs" and custom_enabled() else 4096
            if workspace_request:
                limit = MAX_IMPORT_REQUEST if path.rstrip("/") == "/api/workspace/projects" or path.endswith("/versions") else MAX_PLAN_REQUEST
            body = bytearray()
            async for chunk in request.stream():
                if len(body) + len(chunk) > limit:
                    return JSONResponse({"error": {"code": "REQUEST_TOO_LARGE", "message": f"请求超过 {limit} 字节。"}}, status_code=413)
                body.extend(chunk)
            request._body = bytes(body)
        response = await call_next(request)
        if workspace_request:
            response.headers["Cache-Control"] = "no-store"
        return response

    @app.exception_handler(HTTPException)
    async def http_error(request, exc):
        return JSONResponse({"error": exc.detail}, status_code=exc.status_code, headers=exc.headers)

    @app.exception_handler(RequestValidationError)
    async def validation_error(request, exc):
        if request.url.path.startswith("/api/workspace/"):
            return JSONResponse({"error": {"code": "INVALID_WORKSPACE_REQUEST"}}, status_code=422)
        if request.url.path == "/api/custom-runs":
            return JSONResponse({"error": {"code": "INVALID_CUSTOM_REQUEST", "message": "只接受单文件源码、需求和独立的整数输入/预期值。"}}, status_code=422)
        return JSONResponse({"error": {"code": "INVALID_RUN_REQUEST", "message": "仅接受预定义 task_id、mode 和 candidate_id，不接受代码、路径或命令。"}}, status_code=422)

    @app.get("/api/health")
    async def health():
        with app.state.runs.lock:
            active = app.state.runs.active
        return {"status": "ok", "active_run_id": active, "max_concurrent_runs": 1,
                "docker": "checked_by_execution_not_health", "public_demo": public,
                "persistent_quota": admission is not None,
                "custom_task": {"enabled": not public and custom_enabled()},
                "workspace": {"enabled": workspace_enabled, "execution": transport,
                              "access": ("local" if local_workspace else "token") if workspace_enabled else None,
                              "retry_enabled": workspace_retry_enabled(),
                              "live_enabled": workspace_live_enabled()}, "modes": {
                    "fixture": {"enabled": True}, "offline_executor": {"enabled": True},
                    "live_executor": ({"enabled": False, "reason": "PUBLIC_OFFLINE_ONLY"} if public else live_availability())}}

    @app.get("/api/tasks")
    async def tasks():
        return {"tasks": [task_details()]}

    @app.get("/api/tasks/{task_id}")
    async def task(task_id: str):
        if task_id != TASK.task_id:
            raise HTTPException(404, detail={"code": "TASK_NOT_FOUND", "message": "未知预定义任务。"})
        return task_details()

    @app.post("/api/runs", status_code=202)
    async def start(body: RunRequest):
        if public and (body.mode == "live_executor" or body.adversarial_mode == "live"
                       or body.adversarial_fixture != "standard" or body.recovery_mode != "off"):
            raise HTTPException(403, detail={"code": "PUBLIC_OFFLINE_ONLY",
                                             "message": "公网只接受 Billing 固定或标准离线执行。"})
        if body.recovery_mode != "off" and body.adversarial_mode == "off":
            raise HTTPException(422, detail={"code": "RECOVERY_REQUIRES_ADVERSARIAL", "message": "恢复必须重新执行全部验证，请启用对抗阶段。"})
        if body.recovery_mode != "offline" and body.recovery_fixture != "fixed":
            raise HTTPException(422, detail={"code": "OFFLINE_RECOVERY_PRESET_ONLY", "message": "恢复响应预设仅用于显式离线模式。"})
        if body.recovery_mode == "live":
            if os.environ.get("TRUSTBOUND_ENABLE_RECOVERY_LIVE") != "1":
                raise HTTPException(503, detail={"code": "RECOVERY_LIVE_NOT_AUTHORIZED", "message": "真实恢复推理需用户单独授权并由宿主启用。"})
            if not live_availability()["enabled"]:
                raise HTTPException(503, detail={"code": live_availability()["reason"], "message": "真实恢复模型配置不可用。"})
        if body.adversarial_mode != "offline" and body.adversarial_fixture != "standard":
            raise HTTPException(422, detail={"code": "OFFLINE_ADVERSARIAL_PRESET_ONLY", "message": "对抗错误响应预设仅允许用于显式离线模式。"})
        if body.mode == "fixture":
            body = body.model_copy(update={"candidate_id": body.candidate_id or "fixed"})
        elif body.mode == "offline_executor" and body.candidate_id not in (None, "fixed"):
            raise HTTPException(422, detail={"code": "OFFLINE_FIXED_RESPONSE_ONLY", "message": "离线 Executor 仅注入固定正确补丁响应；业务测试仍真实执行。"})
        elif body.mode == "live_executor":
            if body.candidate_id is not None:
                raise HTTPException(422, detail={"code": "LIVE_CANDIDATE_FORBIDDEN", "message": "真实模型模式不接收固定候选。"})
            availability = live_availability()
            if not availability["enabled"]:
                raise HTTPException(503, detail={"code": availability["reason"], "message": "Vultr 模式尚不可用，请检查后端凭据、模型和显式启用配置。"})
        run_id = app.state.runs.submit(body)
        return {"run_id": run_id, "state": "QUEUED"}

    @app.post("/api/custom-runs", status_code=202)
    async def start_custom(body: CustomRunRequest):
        if public or not custom_enabled():
            raise HTTPException(503, detail={"code": "CUSTOM_TASK_DISABLED", "message": "自定义任务只在显式启用的私有 Runner 环境可用。"})
        return {"run_id": app.state.runs.submit(body), "state": "QUEUED"}

    @app.get("/api/runs/{run_id}")
    async def run(run_id: uuid.UUID):
        snapshot = app.state.runs.get(run_id.hex)
        if snapshot["mode"] in (CustomRunRequest.mode, PROFILE):
            raise HTTPException(404, detail={"code": "RUN_NOT_FOUND", "message": "任务记录不存在。"})
        return snapshot

    @app.get("/api/custom-runs/{run_id}")
    async def custom_run(run_id: uuid.UUID):
        if public or not custom_enabled():
            raise HTTPException(503, detail={"code": "CUSTOM_TASK_DISABLED", "message": "私有自定义任务已关闭。"})
        snapshot = app.state.runs.get(run_id.hex)
        if snapshot["mode"] != CustomRunRequest.mode:
            raise HTTPException(404, detail={"code": "RUN_NOT_FOUND", "message": "任务记录不存在。"})
        return snapshot

    @app.exception_handler(WorkspaceError)
    async def workspace_error(request, exc):
        return JSONResponse({"error": {"code": str(exc)}}, status_code=exc.status)

    @app.post("/api/workspace/projects", status_code=201)
    def import_project(body: ImportProject):
        return app.state.projects.import_project(workspace_owner, body)

    @app.post("/api/workspace/projects/samples/{sample_id}", status_code=201)
    def import_sample(sample_id: Literal["inventory", "logs"]):
        body, plan, offline_files = sample(sample_id)
        project = app.state.projects.import_project(workspace_owner, body)
        draft = app.state.projects.change(workspace_owner, project["project_id"], plan, "plan")
        return {**draft, "offline_files": offline_files}

    @app.get("/api/workspace/projects/models")
    def workspace_models():
        if not workspace_live_enabled():
            raise WorkspaceError("WORKSPACE_EXECUTION_MODE_UNAVAILABLE", 503)
        try:
            return {"models": workspace_model_choices()}
        except (InferenceError, AttributeError, TypeError, ValueError):
            raise WorkspaceError("WORKSPACE_MODEL_UNAVAILABLE", 503) from None

    @app.get("/api/workspace/projects")
    def list_workspace_projects():
        return app.state.projects.projects(workspace_owner)

    @app.get("/api/workspace/projects/{project_id}")
    def workspace_project(project_id: uuid.UUID):
        return app.state.projects.read(workspace_owner, project_id.hex)

    @app.post("/api/workspace/projects/{project_id}/chat")
    def workspace_chat(project_id: uuid.UUID, body: QuickChat):
        if app.state.projects.revision(workspace_owner, project_id.hex) != body.revision:
            raise WorkspaceError("STALE_WORKSPACE_REVISION", 409)
        if not workspace_live_enabled():
            raise WorkspaceError("WORKSPACE_EXECUTION_MODE_UNAVAILABLE", 503)
        if body.model_id and body.model_id not in workspace_model_allowlist():
            raise WorkspaceError("WORKSPACE_MODEL_UNAVAILABLE", 422)
        context = None
        if body.context_path is not None:
            if not body.authorize_context:
                raise WorkspaceError("WORKSPACE_CONTEXT_NOT_AUTHORIZED", 403)
            project = app.state.projects.read(workspace_owner, project_id.hex)
            if project['revision'] != body.revision:
                raise WorkspaceError('STALE_WORKSPACE_REVISION', 409)
            file = next((row for row in project["files"] if row["path"] == body.context_path), None)
            if file is None:
                raise WorkspaceError("INVALID_PROJECT_PATH")
            context = {"path": file["path"], "content": file["content"]}
        elif body.authorize_context:
            raise WorkspaceError("INVALID_PROJECT_PATH")
        try:
            with inference_admission(admission):
                return quick_chat(body, context)
        except InferenceError as error:
            raise WorkspaceError(str(error), 502) from None
        except (ValueError, TypeError, RecursionError):
            raise WorkspaceError("INVALID_CHAT_RESPONSE", 502) from None

    @app.get("/api/workspace/projects/{project_id}/versions")
    def workspace_versions(project_id: uuid.UUID):
        return app.state.projects.versions(workspace_owner, project_id.hex)

    @app.post("/api/workspace/projects/{project_id}/versions")
    def save_workspace_source(project_id: uuid.UUID, body: SaveSource):
        with app.state.runs.lock:
            if app.state.runs.active is not None:
                raise WorkspaceError("WORKSPACE_RUN_ACTIVE", 409)
            return app.state.projects.save_source(workspace_owner, project_id.hex, body)

    @app.get("/api/workspace/projects/{project_id}/runs")
    def workspace_history(project_id: uuid.UUID):
        with app.state.runs.lock:
            records = app.state.projects.history(workspace_owner, project_id.hex)
            active = app.state.runs.active
        history = []
        for record in records:
            report = record.get("workspace_report") or {}
            state = record["state"]
            interrupted = state in ("QUEUED", "RUNNING") and record["run_id"] != active
            history.append({"run_id": record["run_id"], "created_at": record["created_at"],
                            "title": record.get("task_title", record["task_id"]),
                            "frozen_hash": record["frozen_hash"],
                            "verification_mode": record.get('verification_mode', report.get('verification_mode', 'FUNCTIONAL')),
                            "state": "ERROR" if interrupted else state,
                            "status": "INCONCLUSIVE" if interrupted else report.get("status"),
                            "summary": "WORKSPACE_RUN_INTERRUPTED" if interrupted else
                            report.get("reason") or (record.get("error") or {}).get("code")})
        return history

    @app.post("/api/workspace/projects/{project_id}/plan")
    def plan_project(project_id: uuid.UUID, body: PlanDraft):
        return app.state.projects.change(workspace_owner, project_id.hex, body, "plan")

    @app.post("/api/workspace/projects/{project_id}/generate-plan")
    def generate_project_plan(project_id: uuid.UUID, body: GeneratePlan):
        if not workspace_live_enabled():
            raise WorkspaceError("WORKSPACE_LIVE_UNAVAILABLE", 503)
        if body.model_id not in workspace_model_allowlist():
            raise WorkspaceError("WORKSPACE_MODEL_NOT_ALLOWED", 422)
        projects = app.state.projects
        project = projects.read(workspace_owner, project_id.hex)
        if project["revision"] != body.revision:
            raise WorkspaceError("STALE_WORKSPACE_REVISION", 409)
        try:
            with inference_admission(admission):
                draft, usage = generate_plan(project, body.goal, body.model_id)
            draft = draft.model_copy(update={"revision": body.revision, "quick_mode": False,
                "correctness_verification": body.correctness_verification,
                "reference_profile": (project.get("plan") or {}).get("reference_profile", "none")})
            plan = offline_plan(project, draft)
            decision = {**rule_triage(plan, requested=True), "source": "VULTR_PLAN", "inference_usage": usage}
            return projects.change(workspace_owner, project_id.hex, draft, "plan", planning=decision)
        except InferenceError as error:
            raise WorkspaceError(str(error), 502) from None

    @app.post("/api/workspace/projects/{project_id}/triage")
    def triage_project(project_id: uuid.UUID, body: TriageDraft):
        projects = app.state.projects
        project = projects.read(workspace_owner, project_id.hex)
        if body.revision != project["revision"]:
            raise WorkspaceError("STALE_WORKSPACE_REVISION", 409)
        plan = offline_plan(project, body)
        decision = rule_triage(plan, requested=body.request_formal)
        if body.authorize_model and decision["semantic_eligible"]:
            if workspace_live_enabled():
                with inference_admission(admission):
                    decision = semantic_triage(plan, decision, [item["path"] for item in project["files"]])
            else:
                decision.update(source="CONSERVATIVE_FALLBACK", fallback_reason="TRIAGE_LIVE_UNAVAILABLE")
        return projects.change(workspace_owner, project_id.hex, body, "plan", planning=decision)

    @app.post("/api/workspace/projects/{project_id}/freeze")
    def freeze_project(project_id: uuid.UUID, body: FreezeRequest):
        return app.state.projects.change(workspace_owner, project_id.hex, body, "freeze")

    @app.get("/api/workspace/projects/{project_id}/plan-document/{revision}")
    def workspace_plan_document(project_id: uuid.UUID, revision: int):
        project = app.state.projects.frozen_project(workspace_owner, project_id.hex, revision)
        return Response(plan_document(project["plan"]), media_type="application/json",
                        headers={"Content-Disposition": f'attachment; filename="{PLAN_FILENAME}"'})

    @app.post("/api/workspace/projects/{project_id}/reject")
    def reject_project(project_id: uuid.UUID, body: Revision):
        return app.state.projects.change(workspace_owner, project_id.hex, body, "reject")

    @app.post("/api/workspace/projects/{project_id}/runs", status_code=202)
    def start_workspace_run(project_id: uuid.UUID, body: StartWorkspaceRun):
        existing = app.state.projects.request_run(workspace_owner, project_id.hex, body)
        if existing:
            record = app.state.projects.run(workspace_owner, project_id.hex, existing)
            return {'run_id': existing, 'state': record['state']}
        if not transport or ((body.mode == "live" or body.authorize_explanation) and not workspace_live_enabled()):
            raise WorkspaceError("WORKSPACE_EXECUTION_MODE_UNAVAILABLE", 503)
        if body.model_id is not None and body.model_id not in workspace_model_allowlist():
            raise WorkspaceError("WORKSPACE_MODEL_UNAVAILABLE", 422)
        project = app.state.projects.frozen_project(workspace_owner, project_id.hex, body.revision)
        if body.correctness_verification and not project['plan'].get('correctness_verification', True):
            raise WorkspaceError('WORKSPACE_FUNCTIONAL_REAPPROVAL_REQUIRED', 409)
        if body.adversarial_enabled and not project["plan"].get("adversarial_enabled"):
            raise WorkspaceError("WORKSPACE_ADVERSARIAL_REAPPROVAL_REQUIRED", 409)
        restored_files = None
        retry = None
        if body.retry_run_id:
            if not workspace_retry_enabled():
                raise WorkspaceError("WORKSPACE_RETRY_UNAVAILABLE", 503)
            prior = app.state.projects.run(workspace_owner, project_id.hex, body.retry_run_id)
            retry = workspace_retry_context(project, prior) if not prior["retried"] else None
            if retry is None:
                raise WorkspaceError("WORKSPACE_RETRY_UNAVAILABLE", 409)
        if body.restore_run_id:
            prior = app.state.projects.run(workspace_owner, project_id.hex, body.restore_run_id)
            report = prior["workspace_report"]
            if (prior["review"] != "ACCEPTED" or not report or report["status"] != "VERIFIED"
                    or report["frozen_hash"] != project["frozen_hash"]):
                raise WorkspaceError("WORKSPACE_RESTORE_REQUIRES_ACCEPTED_RUN", 409)
            restored_files = report["replacements"]
        run_id = app.state.runs.submit(WorkspaceJob({**project, "owner": workspace_owner}, body, transport,
                                                    restored_files, retry))
        record = app.state.projects.run(workspace_owner, project_id.hex, run_id)
        return {"run_id": run_id, "state": record['state']}

    @app.get("/api/workspace/projects/{project_id}/runs/{run_id}")
    def workspace_run(project_id: uuid.UUID, run_id: uuid.UUID, source: bool = False):
        record = app.state.projects.run(workspace_owner, project_id.hex, run_id.hex)
        if record["state"] in ("QUEUED", "RUNNING"):
            with app.state.runs.lock:
                active = app.state.runs.active == run_id.hex
                latest = app.state.runs.records.get(run_id.hex)
            if not active:
                if latest and latest["state"] in ("COMPLETED", "ERROR"):
                    record = app.state.projects.run(workspace_owner, project_id.hex, run_id.hex)
                if record["state"] in ("QUEUED", "RUNNING"):
                    record.update(state="ERROR", error={"code": "WORKSPACE_RUN_INTERRUPTED"})
        report = record.get("workspace_report") or {}
        revision = report.get("revision", record.get("revision"))
        if source and revision is not None:
            snapshot = app.state.projects.frozen_project(workspace_owner, project_id.hex, revision, historical=True)
            if snapshot["frozen_hash"] != record["frozen_hash"]:
                raise WorkspaceError("WORKSPACE_FREEZE_INVALID", 409)
            record["historical_source"] = {"files": snapshot["files"], "snapshot_hash": snapshot["snapshot_hash"]}
        if workspace_retry_enabled() and report.get("status") == "FAILED" and not record["retried"]:
            try:
                project = app.state.projects.frozen_project(workspace_owner, project_id.hex, report["revision"])
                retry = workspace_retry_context(project, record)
            except (ValueError, KeyError, TypeError):
                retry = None
            if retry:
                record["retry"] = {"attempt": retry["attempt"], "failure": retry["failure"]}
        return record

    @app.post("/api/workspace/projects/{project_id}/runs/{run_id}/review/{decision}")
    def review_workspace_run(project_id: uuid.UUID, run_id: uuid.UUID, decision: Literal["ACCEPTED", "REJECTED", "KEPT_UNVERIFIED"]):
        return app.state.projects.run(workspace_owner, project_id.hex, run_id.hex, decision=decision)

    @app.post('/api/workspace/projects/{project_id}/runs/{run_id}/explanation')
    def explain_workspace_run(project_id: uuid.UUID, run_id: uuid.UUID, body: ExplainRun):
        store = app.state.projects
        record = store.run(workspace_owner, project_id.hex, run_id.hex)
        report = record.get('workspace_report')
        if record['state'] not in ('COMPLETED', 'ERROR') or not report:
            raise WorkspaceError('WORKSPACE_REVIEW_UNAVAILABLE', 409)
        if report.get('explanation'):
            return record
        if not workspace_live_enabled():
            raise WorkspaceError('WORKSPACE_EXECUTION_MODE_UNAVAILABLE', 503)
        if body.model_id and body.model_id not in workspace_model_allowlist():
            raise WorkspaceError('WORKSPACE_MODEL_UNAVAILABLE', 422)
        project = store.frozen_project(workspace_owner, project_id.hex, report['revision'], historical=True)
        if report['frozen_hash'] != project['frozen_hash']:
            raise WorkspaceError('WORKSPACE_FREEZE_INVALID', 409)
        try:
            with inference_admission(admission), model_request_identity(run_id.hex, 'explanation'):
                explanation = generate_explanation(project, report, body.model_id)
            store.annotate_run(workspace_owner, project_id.hex, run_id.hex,
                               {'explanation': explanation, 'explanation_status': 'COMPLETED'})
        except (InferenceError, JournalError, ValueError, TypeError, RecursionError) as error:
            code = str(error) if isinstance(error, (InferenceError, JournalError)) else 'INVALID_EXPLANATION'
            # Another caller may be completing the same durable request. Never overwrite its result.
            if code != 'MODEL_REQUEST_ALREADY_RECORDED':
                store.annotate_run(workspace_owner, project_id.hex, run_id.hex,
                                   {'explanation_status': 'UNAVAILABLE', 'explanation_error': code})
            raise WorkspaceError(code, 409 if code == 'MODEL_REQUEST_ALREADY_RECORDED' else 502) from None
        if isinstance(admission, Admission):
            admission.journal.finalize(run_id.hex, report['status'])
        return store.run(workspace_owner, project_id.hex, run_id.hex)

    @app.get("/api/workspace/projects/{project_id}/runs/{run_id}/export/{kind}")
    def export_workspace_run(project_id: uuid.UUID, run_id: uuid.UUID, kind: Literal["patch", "zip"]):
        record = app.state.projects.run(workspace_owner, project_id.hex, run_id.hex)
        report = record["workspace_report"]
        if (not report or record['review'] not in ('ACCEPTED', 'KEPT_UNVERIFIED')
                or record['review'] == 'ACCEPTED' and report['status'] != 'VERIFIED'):
            raise WorkspaceError("WORKSPACE_EXPORT_REQUIRES_ACCEPTANCE", 409)
        project = app.state.projects.frozen_project(workspace_owner, project_id.hex, report["revision"], historical=True)
        if project["frozen_hash"] != report["frozen_hash"]:
            raise WorkspaceError("WORKSPACE_EXPORT_IDENTITY_MISMATCH", 409)
        data = export_workspace(project, report, kind)
        label = 'trustbound-unverified' if record['review'] == 'KEPT_UNVERIFIED' else 'trustbound'
        return Response(data, media_type="application/zip" if kind == "zip" else "text/plain",
                        headers={"Content-Disposition": f'attachment; filename="{label}-{run_id.hex}.{kind}"'})

    # The Windows review profile can serve the built UI on the same loopback
    # origin. The deployed Web service continues to use its existing proxy.
    static_directory = ROOT / "frontend" / "dist"
    if transport == "LOCAL_DOCKER" and static_directory.is_dir():
        app.mount("/", StaticFiles(directory=static_directory, html=True), name="workspace-preview")

    return app


app = create_app()
