"""Local-only asynchronous Web API over the trusted sandbox execution paths."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from copy import deepcopy
from datetime import datetime, timezone
import json
import os
import threading
from typing import Literal
import uuid

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict
from starlette.middleware.trustedhost import TrustedHostMiddleware

from .custom_tasks import CustomRunRequest, custom_enabled, execute_custom
from .service import ROOT, TASK
from .web_tasks import execute_web_run, live_availability, task_details


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
    def __init__(self, execute, directory):
        self.execute, self.directory = execute, directory
        self.lock = threading.RLock()
        self.pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="trustbound-web")
        self.records, self.active = {}, None

    def save(self, snapshot):
        if self.directory is not None:
            directory = self.directory / snapshot["run_id"]
            directory.mkdir(parents=True, exist_ok=True)
            temporary = directory / "report.tmp"
            temporary.write_text(json.dumps(snapshot, indent=2, ensure_ascii=False), encoding="utf-8")
            temporary.replace(directory / "report.json")

    def submit(self, body):
        with self.lock:
            if self.active is not None:
                raise HTTPException(429, detail={"code": "RUN_CAPACITY_REACHED", "message": "已有一个任务正在执行，请稍后再试。"})
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
            self.save(snapshot)
            self.records[run_id], self.active = snapshot, run_id
            try:
                self.pool.submit(self.work, run_id, body)
            except Exception:
                self.active = None
                del self.records[run_id]
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

            options = {} if body.recovery_mode == "off" else {
                "recovery_mode": body.recovery_mode, "recovery_fixture": body.recovery_fixture,
                "run_id": run_id, "on_progress": progress}
            outcome = (execute_custom(body) if isinstance(body, CustomRunRequest)
                       else self.execute(body.task_id, body.mode, body.candidate_id,
                                         body.adversarial_mode, body.adversarial_fixture, **options))
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
                    self.save(record)
                except Exception:
                    record.update(state="ERROR", error={"code": "EVIDENCE_SAVE_FAILED", "message": "报告持久化失败。"})
                self.active = None

    def get(self, run_id):
        with self.lock:
            if run_id not in self.records:
                raise HTTPException(404, detail={"code": "RUN_NOT_FOUND", "message": "任务记录不存在，服务重启后不恢复旧运行态。"})
            return deepcopy(self.records[run_id])


def create_app(*, execute=execute_web_run, report_directory=ROOT / "artifacts/web-runs"):
    @asynccontextmanager
    async def lifespan(app):
        app.state.runs = RunManager(execute, report_directory)
        yield
        # Finish the owned task on graceful shutdown so Runner's finally can clean up.
        app.state.runs.pool.shutdown(wait=True)

    app = FastAPI(title="TrustBound Local API", version="0.1.0", lifespan=lifespan)
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=["localhost", "127.0.0.1"])

    @app.middleware("http")
    async def local_request_policy(request: Request, call_next):
        if request.method == "POST":
            origin = request.headers.get("origin")
            if origin and origin not in {"http://localhost:5173", "http://127.0.0.1:5173",
                                         "http://localhost:8000", "http://127.0.0.1:8000"}:
                return JSONResponse({"error": {"code": "ORIGIN_DENIED", "message": "只接受本地工作区请求。"}}, status_code=403)
            # The opt-in custom path accepts bounded source and structured data only.
            limit = 8192 if request.url.path == "/api/custom-runs" and custom_enabled() else 4096
            body = bytearray()
            async for chunk in request.stream():
                if len(body) + len(chunk) > limit:
                    return JSONResponse({"error": {"code": "REQUEST_TOO_LARGE", "message": f"请求超过 {limit} 字节。"}}, status_code=413)
                body.extend(chunk)
            request._body = bytes(body)
        return await call_next(request)

    @app.exception_handler(HTTPException)
    async def http_error(request, exc):
        return JSONResponse({"error": exc.detail}, status_code=exc.status_code)

    @app.exception_handler(RequestValidationError)
    async def validation_error(request, exc):
        if request.url.path == "/api/custom-runs":
            return JSONResponse({"error": {"code": "INVALID_CUSTOM_REQUEST", "message": "只接受单文件源码、需求和独立的整数输入/预期值。"}}, status_code=422)
        return JSONResponse({"error": {"code": "INVALID_RUN_REQUEST", "message": "仅接受预定义 task_id、mode 和 candidate_id，不接受代码、路径或命令。"}}, status_code=422)

    @app.get("/api/health")
    async def health():
        with app.state.runs.lock:
            active = app.state.runs.active
        return {"status": "ok", "active_run_id": active, "max_concurrent_runs": 1,
                "docker": "checked_by_execution_not_health", "custom_task": {"enabled": custom_enabled()}, "modes": {
                    "fixture": {"enabled": True}, "offline_executor": {"enabled": True},
                    "live_executor": live_availability()}}

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
        if not custom_enabled():
            raise HTTPException(503, detail={"code": "CUSTOM_TASK_DISABLED", "message": "自定义任务只在显式启用的私有 Runner 环境可用。"})
        return {"run_id": app.state.runs.submit(body), "state": "QUEUED"}

    @app.get("/api/runs/{run_id}")
    async def run(run_id: uuid.UUID):
        snapshot = app.state.runs.get(run_id.hex)
        if snapshot["mode"] == CustomRunRequest.mode:
            raise HTTPException(404, detail={"code": "RUN_NOT_FOUND", "message": "任务记录不存在。"})
        return snapshot

    @app.get("/api/custom-runs/{run_id}")
    async def custom_run(run_id: uuid.UUID):
        if not custom_enabled():
            raise HTTPException(503, detail={"code": "CUSTOM_TASK_DISABLED", "message": "私有自定义任务已关闭。"})
        snapshot = app.state.runs.get(run_id.hex)
        if snapshot["mode"] != CustomRunRequest.mode:
            raise HTTPException(404, detail={"code": "RUN_NOT_FOUND", "message": "任务记录不存在。"})
        return snapshot

    return app


app = create_app()
