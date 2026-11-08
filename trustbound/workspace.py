"""Private project snapshots, offline planning and immutable approvals."""
import base64
import binascii
from contextlib import closing, contextmanager
from datetime import datetime, timezone
from hashlib import sha256
from io import BytesIO
import json
import os
from pathlib import Path
import re
import sqlite3
import stat
import uuid
import zipfile
import zlib
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, JsonValue, model_validator

from .planning import ShortText, rule_triage
from .runner import CPU_LIMIT_NANOS, IMAGE, MEMORY_LIMIT_BYTES, PID_LIMIT
from .workspace_reference import REFERENCE_RULES, reference_result


MAX_FILES = 20
MAX_FILE_BYTES = 4096
MAX_PROJECT_BYTES = 24 * 1024
MAX_ZIP_BYTES = 64 * 1024
MAX_IMPORT_REQUEST = 96 * 1024
MAX_PLAN_REQUEST = 16 * 1024
MAX_PROJECTS = 16
MAX_FREEZES = 8
MAX_RUNS_PER_PROJECT = 12
MAX_PLANNING_EVENTS = 256
PLAN_FILENAME = "TRUSTBOUND_PLAN.json"
WORKSPACE_CASE_TIMEOUT = 3
WORKSPACE_MODEL_OUTPUT = 4096
PART = re.compile(r"[A-Za-z0-9_][A-Za-z0-9_.-]{0,47}")
RESERVED = re.compile(r"con|prn|aux|nul|com[0-9]|lpt[0-9]", re.IGNORECASE)
PRIVATE_NAMES = {"__pycache__", "secrets", "credentials", "id_rsa", "id_ed25519", "env"}


class WorkspaceError(ValueError):
    def __init__(self, code, status=422):
        super().__init__(code)
        self.status = status


class StrictBody(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class ProjectFile(StrictBody):
    path: str = Field(min_length=1, max_length=160)
    content: str = Field(max_length=MAX_PLAN_REQUEST)


class ImportProject(StrictBody):
    files: list[ProjectFile] | None = Field(default=None, min_length=1, max_length=MAX_FILES + 1)
    zip_base64: str | None = Field(default=None, min_length=1, max_length=4 * ((MAX_ZIP_BYTES + 2) // 3))

    @model_validator(mode="after")
    def one_source(self):
        if (self.files is None) == (self.zip_base64 is None):
            raise ValueError("Provide files or a ZIP")
        return self


class Case(StrictBody):
    input: JsonValue
    expected: JsonValue


class Revision(StrictBody):
    revision: int = Field(ge=0, le=2**31 - 1)


class SaveSource(Revision):
    files: list[ProjectFile] = Field(min_length=1, max_length=MAX_FILES)
    folders: list[str] = Field(default_factory=list, max_length=24)
    replace_oldest: bool = False


class PlanDraft(Revision):
    correctness_verification: bool = True
    quick_mode: bool = False
    reference_profile: Literal["none", "inventory", "logs"] = "none"
    goal: str = Field(min_length=1, max_length=1200)
    allowed_write_paths: list[str] = Field(default_factory=list, max_length=MAX_FILES)
    entrypoint: str = Field(default="", max_length=180)
    public_cases: list[Case] = Field(default_factory=list, max_length=4)
    acceptance_cases: list[Case] = Field(default_factory=list, max_length=4)
    adversarial_cases: list[Case] = Field(default_factory=list, max_length=3)
    implementation: list[ShortText] = Field(default_factory=list, max_length=5)
    constraints: list[ShortText] = Field(default_factory=list, max_length=5)
    risks: list[ShortText] = Field(default_factory=list, max_length=5)
    acceptance_basis: str = Field(default="", max_length=1200)
    questions: list[ShortText] = Field(default_factory=list, max_length=8)


class TriageDraft(PlanDraft):
    request_formal: bool = False
    authorize_model: bool = False


class GeneratePlan(Revision):
    correctness_verification: bool = True
    goal: str = Field(min_length=1, max_length=1200)
    model_id: str = Field(min_length=1, max_length=120)
    authorize_model: Literal[True]


class FreezeRequest(Revision):
    approval: Literal["direct", "formal"] = "formal"
    adversarial_enabled: bool = False
    confirm_acceptance: bool = False


def workspace_policy(adversarial_enabled=False):
    return {"image": IMAGE, "timeout_per_case_seconds": WORKSPACE_CASE_TIMEOUT,
            "memory_bytes": MEMORY_LIMIT_BYTES, "cpu_nanos": CPU_LIMIT_NANOS, "pids": PID_LIMIT,
            "network": "none", "read_only_root": True, "user": "65534:65534",
            "model_requests": 2 if adversarial_enabled else 1,
            "model_output_tokens": WORKSPACE_MODEL_OUTPUT * (2 if adversarial_enabled else 1)}


def canonical(value):
    return json.dumps(value, ensure_ascii=False, allow_nan=False, sort_keys=True,
                      separators=(",", ":")).encode("utf-8")


def digest(value):
    return sha256(canonical(value)).hexdigest()


def run_fingerprint(body):
    data = body.model_dump(exclude={'idempotency_key'})
    # Preserve pre-mode idempotency identities for the unchanged default behavior.
    if data.get('correctness_verification', True):
        data.pop('correctness_verification', None)
        data.pop('execution_input', None)
    return digest(data)


def check_path(path, *, directory=False):
    parts = path.split("/")
    if ((directory or path != PLAN_FILENAME)
            and any(part.casefold() == PLAN_FILENAME.casefold() for part in parts)):
        raise WorkspaceError("RESERVED_PROJECT_PLAN")
    if (len(path) > 160 or len(parts) > 5
            or any(not PART.fullmatch(part) or part.endswith(".")
                   or RESERVED.fullmatch(part.split(".")[0])
                   or part.split(".")[0].lower() in PRIVATE_NAMES for part in parts)):
        raise WorkspaceError("INVALID_PROJECT_PATH")
    if not directory and path != PLAN_FILENAME and Path(path).suffix not in {".py", ".md", ".txt"}:
        raise WorkspaceError("UNSUPPORTED_PROJECT_FILE")
    return parts


def read_zip(encoded):
    try:
        raw = base64.b64decode(encoded, validate=True)
        if len(raw) > MAX_ZIP_BYTES:
            raise WorkspaceError("PROJECT_TOO_LARGE", 413)
        with zipfile.ZipFile(BytesIO(raw)) as archive:
            entries = archive.infolist()
            if len(entries) > 32:
                raise WorkspaceError("PROJECT_TOO_LARGE", 413)
            paths, files, total = {}, [], 0
            for entry in entries:
                path = entry.orig_filename
                directory = path.endswith("/")
                path = path[:-1] if directory else path
                check_path(path, directory=directory)
                mode = stat.S_IFMT(entry.external_attr >> 16)
                if (path.casefold() in paths or entry.flag_bits & 1
                        or entry.compress_type not in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED)
                        or mode not in (0, stat.S_IFDIR if directory else stat.S_IFREG)
                        or (not directory and entry.external_attr & 0x10)):
                    raise WorkspaceError("UNSUPPORTED_ZIP_ENTRY")
                paths[path.casefold()] = (path, directory)
                if directory:
                    if entry.file_size:
                        raise WorkspaceError("UNSUPPORTED_ZIP_ENTRY")
                    continue
                file_limit = MAX_PLAN_REQUEST if path == PLAN_FILENAME else MAX_FILE_BYTES
                if (len(files) >= MAX_FILES + 1 or entry.file_size > file_limit
                        or total + entry.file_size > MAX_PROJECT_BYTES + MAX_PLAN_REQUEST):
                    raise WorkspaceError("PROJECT_TOO_LARGE", 413)
                with archive.open(entry) as stream:
                    data = stream.read(file_limit + 1)
                if len(data) != entry.file_size:
                    raise WorkspaceError("INVALID_ZIP")
                total += len(data)
                files.append(ProjectFile(path=path, content=data.decode("utf-8")))
            for path, _ in paths.values():
                parts = path.split("/")
                for end in range(1, len(parts)):
                    prefix = "/".join(parts[:end])
                    if paths.get(prefix.casefold(), (prefix, True)) != (prefix, True):
                        raise WorkspaceError("CONFLICTING_PROJECT_PATH")
            return files
    except WorkspaceError:
        raise
    except (binascii.Error, ValueError, OSError, EOFError, RuntimeError, zipfile.BadZipFile, zlib.error) as exc:
        raise WorkspaceError("INVALID_ZIP") from exc


def project_snapshot(body):
    files = body.files if body.files is not None else read_zip(body.zip_base64)
    manifest, names, file_names, total = [], {}, set(), 0
    if not files or not any(file.path.endswith(".py") for file in files):
        raise WorkspaceError("PYTHON_FILE_REQUIRED")
    if len(files) > MAX_FILES:
        raise WorkspaceError("PROJECT_TOO_LARGE", 413)
    for file in sorted(files, key=lambda item: item.path):
        if file.path == PLAN_FILENAME:
            raise WorkspaceError("RESERVED_PROJECT_PLAN")
        parts = check_path(file.path)
        for end in range(1, len(parts) + 1):
            name = "/".join(parts[:end])
            key = name.casefold()
            if names.setdefault(key, name) != name or key in file_names:
                raise WorkspaceError("CONFLICTING_PROJECT_PATH")
        file_names.add(file.path.casefold())
        try:
            data = file.content.encode("utf-8")
        except UnicodeError as exc:
            raise WorkspaceError("INVALID_PROJECT_TEXT") from exc
        if b"\0" in data:
            raise WorkspaceError("INVALID_PROJECT_TEXT")
        total += len(data)
        if len(data) > MAX_FILE_BYTES or total > MAX_PROJECT_BYTES:
            raise WorkspaceError("PROJECT_TOO_LARGE", 413)
        manifest.append({"path": file.path, "sha256": sha256(data).hexdigest(), "content": file.content})
    identity = {"version": 1, "files": [{k: row[k] for k in ("path", "sha256")} for row in manifest]}
    return {"files": manifest, "snapshot_hash": digest(identity)}


def offline_plan(snapshot, body):
    """Check operator-supplied scope and suggest missing evidence without inventing outcomes."""
    paths = set(body.allowed_write_paths)
    python_paths = {file["path"] for file in snapshot["files"] if file["path"].endswith(".py")}
    if len(paths) != len(body.allowed_write_paths) or not paths <= python_paths:
        raise WorkspaceError("INVALID_WRITE_SCOPE")
    entrypoint = body.entrypoint.strip()
    if entrypoint:
        path, separator, function = entrypoint.partition(":")
        if not separator or path not in python_paths or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]{0,63}", function):
            raise WorkspaceError("INVALID_ENTRYPOINT")
    draft = body.model_dump(include=set(PlanDraft.model_fields) - {"revision"})
    draft.update(goal=body.goal.strip(), entrypoint=entrypoint, allowed_write_paths=sorted(paths))
    draft["reference_rules"] = REFERENCE_RULES[body.reference_profile]
    try:
        all_cases = draft["public_cases"] + draft["acceptance_cases"] + draft["adversarial_cases"]
        inputs = {canonical(case["input"]) for case in all_cases}
        if (body.correctness_verification and len(inputs) != len(all_cases)
                or any(len(canonical(case)) > 1024 for case in all_cases)):
            raise WorkspaceError("INVALID_OR_OVERLAPPING_CASES")
        if body.correctness_verification and body.reference_profile != "none":
            for case in all_cases:
                if canonical(reference_result(body.reference_profile, case["input"])) != canonical(case["expected"]):
                    raise WorkspaceError("REFERENCE_EXPECTATION_CONFLICT")
        canonical(draft)
    except WorkspaceError:
        raise
    except (ValueError, RecursionError) as exc:
        raise WorkspaceError("INVALID_PLAN_DATA") from exc
    questions = list(body.questions) + [message for ready, message in (
        (draft["goal"], "预期行为与成功标准是什么？"),
        (paths, "允许修改哪些现有 Python 文件？"),
        (entrypoint, "哪个函数接收 JSON 输入并返回 JSON 结果？"),
        (not body.correctness_verification or body.public_cases, "提供至少一个可供 Executor 查看和复现的公开用例。"),
        (not body.correctness_verification or body.acceptance_cases, "提供至少一个输入不同的独立验收用例及可信期望值。"),
        (not body.correctness_verification or body.acceptance_basis.strip() or body.reference_profile != "none",
         "NEEDS_CONFIRMATION: 请说明独立验收期望值的需求依据及推导过程。"),
    ) if not ready]
    if body.correctness_verification and "NEEDS_CONFIRMATION" in canonical(draft).decode() and not questions:
        questions.append("NEEDS_CONFIRMATION: 请解决草案中标记的不确定规则后重新审核。")
    return {**draft, "source": "OFFLINE_RULES", "questions": questions,
            "steps": draft["implementation"] or ["在允许的文件内提案", "运行公开用例", "独立比较冻结的验收结果"],
            "suggestions": ["覆盖正常行为、边界及错误输入", "为每个用例给出可比较的期望值"]}


def plan_document(plan):
    return canonical({"version": 1, **{key: plan[key] for key in PlanDraft.model_fields
                                      if key != "revision" and key in plan}}) + b"\n"


def import_snapshot(body):
    files = body.files if body.files is not None else read_zip(body.zip_base64)
    documents = [file for file in files if file.path == PLAN_FILENAME]
    source = [file for file in files if file.path != PLAN_FILENAME]
    if not source:
        raise WorkspaceError("PYTHON_FILE_REQUIRED")
    snapshot = project_snapshot(ImportProject(files=source))
    if not documents:
        return snapshot, None
    # A portable document is an untrusted draft. Only this server can freeze
    # the validated plan against the newly imported source snapshot.
    try:
        if len(documents) != 1 or len(documents[0].content.encode("utf-8")) > MAX_PLAN_REQUEST:
            raise ValueError("Invalid plan size")
        data = json.loads(documents[0].content)
        version = data.pop("version", None) if isinstance(data, dict) else None
        if type(version) is not int or version != 1:
            raise ValueError("Unsupported plan version")
        return snapshot, offline_plan(snapshot, PlanDraft(revision=0, **data))
    except (ValueError, TypeError, RecursionError) as exc:
        raise WorkspaceError("INVALID_PROJECT_PLAN") from exc


class WorkspaceStore:
    def __init__(self, path):
        # SQLite sidecars inherit the directory's exposure. Use a dedicated
        # owner-only directory for snapshots and protected acceptance data.
        if path.is_symlink() or path.parent.is_symlink():
            raise ValueError("Workspace storage must not use symlinks")
        parent = path.parent.stat()
        if os.name == "posix" and (parent.st_uid != os.geteuid() or parent.st_mode & 0o077):
            raise ValueError("Workspace storage directory must be private to the service user")
        self.path = path
        with self.transaction() as db:
            db.execute("""CREATE TABLE IF NOT EXISTS projects (
                id TEXT PRIMARY KEY, owner TEXT NOT NULL, snapshot TEXT NOT NULL,
                revision INTEGER NOT NULL, state TEXT NOT NULL, plan TEXT, frozen_hash TEXT)""")
            db.execute("""CREATE TABLE IF NOT EXISTS freezes (
                project_id TEXT NOT NULL, revision INTEGER NOT NULL, hash TEXT NOT NULL,
                spec TEXT NOT NULL, PRIMARY KEY (project_id, revision))""")
            db.execute("""CREATE TABLE IF NOT EXISTS runs (
                id TEXT PRIMARY KEY, project_id TEXT NOT NULL, record TEXT NOT NULL, review TEXT)""")
            db.execute("""CREATE TABLE IF NOT EXISTS run_requests (
                project_id TEXT NOT NULL, key TEXT NOT NULL, fingerprint TEXT NOT NULL, run_id TEXT NOT NULL,
                PRIMARY KEY (project_id, key))""")
            db.execute("""CREATE TABLE IF NOT EXISTS run_events (
                seq INTEGER PRIMARY KEY AUTOINCREMENT, run_id TEXT NOT NULL,
                state TEXT NOT NULL, at TEXT NOT NULL)""")
            db.execute("""CREATE TABLE IF NOT EXISTS retry_links (
                parent_id TEXT PRIMARY KEY, run_id TEXT NOT NULL)""")
            db.execute("""CREATE TABLE IF NOT EXISTS planning_events (
                project_id TEXT NOT NULL, revision INTEGER NOT NULL, event TEXT NOT NULL,
                PRIMARY KEY (project_id, revision))""")
            db.execute("""CREATE TABLE IF NOT EXISTS source_archive (
                project_id TEXT NOT NULL, hash TEXT NOT NULL, snapshot TEXT NOT NULL,
                PRIMARY KEY (project_id, hash))""")
            db.execute("""CREATE TABLE IF NOT EXISTS saved_versions (
                project_id TEXT NOT NULL, revision INTEGER NOT NULL, hash TEXT NOT NULL,
                saved_at TEXT NOT NULL, snapshot TEXT NOT NULL, PRIMARY KEY (project_id, revision))""")

    @contextmanager
    def transaction(self):
        with closing(sqlite3.connect(self.path, timeout=2)) as db, db:
            db.row_factory = sqlite3.Row
            db.execute("BEGIN IMMEDIATE")
            yield db

    def _project(self, db, owner, project_id):
        row = db.execute("SELECT * FROM projects WHERE id=? AND owner=?", (project_id, owner)).fetchone()
        if row is None:
            raise WorkspaceError("WORKSPACE_PROJECT_NOT_FOUND", 404)
        return {"project_id": project_id, **json.loads(row["snapshot"]), "revision": row["revision"],
                "state": row["state"], "plan": json.loads(row["plan"]) if row["plan"] else None,
                "frozen_hash": row["frozen_hash"]}

    def read(self, owner, project_id):
        with self.transaction() as db:
            return self._project(db, owner, project_id)

    def revision(self, owner, project_id):
        # Ordinary chat needs identity only, not the serialized source snapshot.
        with self.transaction() as db:
            row = db.execute('SELECT revision FROM projects WHERE id=? AND owner=?', (project_id, owner)).fetchone()
            if row is None:
                raise WorkspaceError('WORKSPACE_PROJECT_NOT_FOUND', 404)
            return row['revision']

    def projects(self, owner):
        with self.transaction() as db:
            rows = db.execute("""SELECT id AS project_id, revision, state,
                json_extract(plan, '$.goal') AS title, json_extract(snapshot, '$.files[0].path') AS first_file
                FROM projects WHERE owner=? ORDER BY rowid DESC""", (owner,))
            return [dict(row) for row in rows]

    def save_source(self, owner, project_id, body):
        snapshot = project_snapshot(ImportProject(files=body.files))
        folders = set()
        file_paths = {file["path"].casefold() for file in snapshot["files"]}
        for path in body.folders:
            check_path(path, directory=True)
            key = path.casefold()
            if key in folders or any(key == file or key.startswith(file + "/") for file in file_paths):
                raise WorkspaceError("CONFLICTING_PROJECT_PATH")
            folders.add(key)
        snapshot["folders"] = sorted(body.folders)
        with self.transaction() as db:
            project = self._project(db, owner, project_id)
            if project["revision"] != body.revision:
                raise WorkspaceError("STALE_WORKSPACE_REVISION", 409)
            versions = db.execute("SELECT revision FROM saved_versions WHERE project_id=? ORDER BY revision",
                                  (project_id,)).fetchall()
            if len(versions) >= 3:
                if not body.replace_oldest:
                    raise WorkspaceError("WORKSPACE_VERSION_LIMIT", 409)
                db.execute("DELETE FROM saved_versions WHERE project_id=? AND revision=?",
                           (project_id, versions[0]["revision"]))
            # Preserve source bytes referenced by immutable freeze hashes, independently of version slots.
            old_hash = project["snapshot_hash"]
            if db.execute("SELECT 1 FROM freezes WHERE project_id=? AND json_extract(spec, '$.snapshot_hash')=?",
                          (project_id, old_hash)).fetchone():
                archived = {"files": project["files"], "snapshot_hash": old_hash}
                db.execute("INSERT OR IGNORE INTO source_archive VALUES (?, ?, ?)",
                           (project_id, old_hash, canonical(archived).decode()))
            revision = body.revision + 1
            encoded = canonical(snapshot).decode()
            db.execute("INSERT INTO saved_versions VALUES (?, ?, ?, ?, ?)",
                       (project_id, revision, snapshot["snapshot_hash"], datetime.now(timezone.utc).isoformat(), encoded))
            db.execute("UPDATE projects SET snapshot=?, revision=?, state='IMPORTED', plan=NULL, frozen_hash=NULL WHERE id=?",
                       (encoded, revision, project_id))
            return self._project(db, owner, project_id)

    def versions(self, owner, project_id):
        with self.transaction() as db:
            self._project(db, owner, project_id)
            rows = db.execute("SELECT revision, hash, saved_at, snapshot FROM saved_versions WHERE project_id=? ORDER BY revision DESC",
                              (project_id,))
            return [{**dict(row), "snapshot": json.loads(row["snapshot"])} for row in rows]

    def history(self, owner, project_id):
        with self.transaction() as db:
            self._project(db, owner, project_id)
            records = [json.loads(row["record"]) for row in
                       db.execute("SELECT record FROM runs WHERE project_id=?", (project_id,))]
        return sorted(records, key=lambda record: record["created_at"], reverse=True)

    def frozen_project(self, owner, project_id, revision, *, historical=False):
        with self.transaction() as db:
            project = self._project(db, owner, project_id)
            if not historical and (project["revision"] != revision or project["state"] != "FROZEN"):
                raise WorkspaceError("WORKSPACE_FREEZE_REQUIRED", 409)
            row = db.execute("SELECT hash, spec FROM freezes WHERE project_id=? AND revision=?",
                             (project_id, revision)).fetchone()
            if row is None:
                raise WorkspaceError("WORKSPACE_FREEZE_INVALID", 409)
            spec = json.loads(row["spec"])
            if historical and spec["snapshot_hash"] != project["snapshot_hash"]:
                archived = db.execute("SELECT snapshot FROM source_archive WHERE project_id=? AND hash=?",
                                      (project_id, spec["snapshot_hash"])).fetchone()
                if archived:
                    project.update(json.loads(archived["snapshot"]))
            source = project_snapshot(ImportProject(files=[
                {"path": item["path"], "content": item["content"]} for item in project["files"]
            ]))
            if (spec["project_id"] != project_id or spec["owner"] != owner
                    or spec["approved_revision"] != revision - 1
                    or spec["snapshot_hash"] != project["snapshot_hash"]
                    or source["snapshot_hash"] != project["snapshot_hash"]
                    or (not historical and spec["version"] >= 2 and spec.get("policy") !=
                        workspace_policy(spec["plan"].get("adversarial_enabled", False)))
                    or digest(spec) != row["hash"]
                    or (not historical and (spec["plan"] != project["plan"] or row["hash"] != project["frozen_hash"]))):
                raise WorkspaceError("WORKSPACE_FREEZE_INVALID", 409)
            return {**project, "revision": revision, "frozen_hash": row["hash"],
                    "plan": spec["plan"], "policy": spec.get("policy", workspace_policy())}

    def _request_run(self, db, project_id, key, fingerprint, parent=None):
        row = db.execute('SELECT fingerprint,run_id FROM run_requests WHERE project_id=? AND key=?',
                         (project_id, key)).fetchone()
        if row:
            if row['fingerprint'] != fingerprint:
                raise WorkspaceError('WORKSPACE_IDEMPOTENCY_CONFLICT', 409)
            return row['run_id']
        if parent:
            row = db.execute('SELECT runs.id,runs.record FROM retry_links JOIN runs ON runs.id=retry_links.run_id '
                             'WHERE retry_links.parent_id=? AND runs.project_id=?', (parent, project_id)).fetchone()
            if row:
                if json.loads(row['record']).get('request_fingerprint') != fingerprint:
                    raise WorkspaceError('WORKSPACE_RETRY_ALREADY_USED', 409)
                db.execute('INSERT INTO run_requests VALUES(?,?,?,?)', (project_id, key, fingerprint, row['id']))
                return row['id']
        return None

    def request_run(self, owner, project_id, body):
        with self.transaction() as db:
            self._project(db, owner, project_id)
            return self._request_run(db, project_id, body.idempotency_key,
                                     run_fingerprint(body), body.retry_run_id)

    def reconcile_interrupted(self, journal=None):
        with self.transaction() as db:
            for row in db.execute('SELECT id,record FROM runs').fetchall():
                record = json.loads(row['record'])
                if record['state'] not in ('QUEUED', 'RUNNING'):
                    continue
                summary = journal.summary(row['id']) if journal else {'requests': [], 'state': 'SAFE_TO_RETRY'}
                billing = summary['state']
                if not summary['requests'] and record['state'] == 'RUNNING' and not record.get('request_journal_version'):
                    billing = 'UNKNOWN_BILLING'
                record.update(state='ERROR', billing_state=billing, model_requests=summary['requests'],
                              finished_at=datetime.now(timezone.utc).isoformat(),
                              error={'code': 'WORKSPACE_RUN_INTERRUPTED'})
                if record.get('workspace_report'):
                    record['workspace_report'].update(status='INCONCLUSIVE', reason='WORKSPACE_RUN_INTERRUPTED')
                db.execute('UPDATE runs SET record=? WHERE id=?', (canonical(record).decode(), row['id']))
                self._release_unsent_retry(db, record)
                db.execute('INSERT INTO run_events(run_id,state,at) VALUES(?,?,?)',
                           (row['id'], 'INTERRUPTED_' + billing, record['finished_at']))

    def _release_unsent_retry(self, db, record):
        if (record.get('retry_parent') and record.get('billing_state') == 'SAFE_TO_RETRY'
                and (record.get('workspace_report') or {}).get('status') != 'VERIFIED'):
            db.execute('DELETE FROM retry_links WHERE parent_id=? AND run_id=?',
                       (record['retry_parent'], record['run_id']))

    def save_run(self, record):
        data = canonical(record)
        if len(data) > 512 * 1024:
            raise OSError("Workspace report too large")
        project_id, run_id = record["project_id"], record["run_id"]
        with self.transaction() as db:
            if record['state'] == 'QUEUED' and record.get('idempotency_key'):
                existing = self._request_run(db, project_id, record['idempotency_key'],
                                             record['request_fingerprint'], record.get('retry_parent'))
                if existing:
                    return existing
            if record["state"] == "QUEUED":
                # Recheck the revision inside the same transaction that admits the job.
                project = self._project(db, record["owner"], project_id)
                if project["state"] != "FROZEN" or project["frozen_hash"] != record["frozen_hash"]:
                    raise WorkspaceError("WORKSPACE_FREEZE_REQUIRED", 409)
                if db.execute("SELECT count(*) FROM runs WHERE project_id=?", (project_id,)).fetchone()[0] >= MAX_RUNS_PER_PROJECT:
                    raise WorkspaceError("WORKSPACE_RUN_LIMIT", 429)
                parent_id = record.get("retry_parent")
                if parent_id:
                    parent = db.execute("SELECT review FROM runs WHERE id=? AND project_id=?",
                                        (parent_id, project_id)).fetchone()
                    if parent is None or parent["review"] is not None:
                        raise WorkspaceError("WORKSPACE_RETRY_UNAVAILABLE", 409)
                    if db.execute("SELECT 1 FROM retry_links WHERE parent_id=?", (parent_id,)).fetchone():
                        raise WorkspaceError("WORKSPACE_RETRY_ALREADY_USED", 409)
                    db.execute("INSERT INTO retry_links VALUES (?, ?)", (parent_id, run_id))
                db.execute("INSERT INTO runs VALUES (?, ?, ?, NULL)", (run_id, project_id, data.decode()))
                if record.get('idempotency_key'):
                    db.execute('INSERT INTO run_requests VALUES(?,?,?,?)',
                               (project_id, record['idempotency_key'], record['request_fingerprint'], run_id))
            else:
                db.execute("UPDATE runs SET record=? WHERE id=? AND project_id=?",
                           (data.decode(), run_id, project_id))
                if record['state'] in ('COMPLETED', 'ERROR'):
                    self._release_unsent_retry(db, record)
            db.execute('INSERT INTO run_events(run_id,state,at) VALUES(?,?,?)',
                       (run_id, record['state'], datetime.now(timezone.utc).isoformat()))
            return run_id

    def run(self, owner, project_id, run_id, *, decision=None):
        with self.transaction() as db:
            project = self._project(db, owner, project_id)
            row = db.execute("SELECT record, review FROM runs WHERE id=? AND project_id=?",
                             (run_id, project_id)).fetchone()
            if row is None:
                raise WorkspaceError("WORKSPACE_RUN_NOT_FOUND", 404)
            record, review = json.loads(row["record"]), row["review"]
            if decision:
                report = record.get("workspace_report")
                if record["state"] not in ("COMPLETED", "ERROR") or not report or review is not None:
                    raise WorkspaceError("WORKSPACE_REVIEW_UNAVAILABLE", 409)
                if decision == "ACCEPTED" and (record['state'] != 'COMPLETED' or report["status"] != "VERIFIED" or not report["changed_paths"]
                        or project["state"] != "FROZEN" or project["frozen_hash"] != report["frozen_hash"]):
                    raise WorkspaceError("WORKSPACE_VERIFIED_CHANGE_REQUIRED", 409)
                if decision == 'KEPT_UNVERIFIED':
                    if (report['status'] == 'REJECTED' or not report['changed_paths']
                            or project['state'] != 'FROZEN' or project['frozen_hash'] != report['frozen_hash']):
                        raise WorkspaceError('WORKSPACE_CANDIDATE_NOT_RETAINABLE', 409)
                    from .workspace_execution import project_candidate
                    candidate, changed, patch = project_candidate(project, report['replacements'])
                    if (candidate['snapshot_hash'] != report['artifact_hash'] or patch != report['diff']
                            or sorted(changed) != sorted(report['changed_paths'])):
                        raise WorkspaceError('WORKSPACE_EXPORT_IDENTITY_MISMATCH', 409)
                db.execute("UPDATE runs SET review=? WHERE id=?", (decision, run_id))
                review = decision
            record.pop("owner", None)
            retried = db.execute("SELECT 1 FROM retry_links WHERE parent_id=?", (run_id,)).fetchone() is not None
            return {**record, "review": review, "retried": retried}

    def annotate_run(self, owner, project_id, run_id, fields):
        """Only advisory fields may be added; original verdict and review are immutable here."""
        allowed = {'explanation', 'explanation_status', 'explanation_error'}
        if not fields.keys() <= allowed:
            raise WorkspaceError('INVALID_EXPLANATION')
        with self.transaction() as db:
            self._project(db, owner, project_id)
            row = db.execute('SELECT record FROM runs WHERE id=? AND project_id=?', (run_id, project_id)).fetchone()
            if row is None:
                raise WorkspaceError('WORKSPACE_RUN_NOT_FOUND', 404)
            record = json.loads(row['record'])
            if record['state'] not in ('COMPLETED', 'ERROR') or not record.get('workspace_report'):
                raise WorkspaceError('WORKSPACE_REVIEW_UNAVAILABLE', 409)
            record['workspace_report'].update(fields)
            data = canonical(record)
            if len(data) > 512 * 1024:
                raise WorkspaceError('WORKSPACE_REPORT_TOO_LARGE')
            db.execute('UPDATE runs SET record=? WHERE id=?', (data.decode(), run_id))

    def import_project(self, owner, body):
        snapshot, draft = import_snapshot(body)
        project_id = uuid.uuid4().hex
        with self.transaction() as db:
            if db.execute("SELECT count(*) FROM projects").fetchone()[0] >= MAX_PROJECTS:
                raise WorkspaceError("WORKSPACE_PROJECT_LIMIT", 429)
            state = "IMPORTED" if draft is None else "CLARIFYING" if draft["questions"] else "PLAN_READY"
            db.execute("INSERT INTO projects VALUES (?, ?, ?, 0, ?, ?, NULL)",
                       (project_id, owner, canonical(snapshot).decode(), state,
                        canonical(draft).decode() if draft is not None else None))
            return self._project(db, owner, project_id)

    def change(self, owner, project_id, body, action, *, planning=None):
        # A write transaction keeps stale browser approvals from freezing a newer draft.
        with self.transaction() as db:
            project = self._project(db, owner, project_id)
            if project["revision"] != body.revision:
                raise WorkspaceError("STALE_WORKSPACE_REVISION", 409)
            revision = body.revision + 1
            plan, state, frozen_hash = project["plan"], "REJECTED", None
            if action == "plan":
                plan = offline_plan(project, body)
                decision = planning if planning is not None else rule_triage(plan, requested=True)
                plan["planning"] = decision
                if decision["source"] == "VULTR_PLAN":
                    plan["source"] = "VULTR_PLAN"
                if decision.get("implementation") and not plan["implementation"]:
                    plan["implementation"] = decision["implementation"]
                    plan["steps"] = decision["implementation"]
                if decision.get("acceptance_suggestions"):
                    plan["suggestions"].extend(decision["acceptance_suggestions"])
                missing = decision["missing_requirements"]
                if decision["source"] == "VULTR" and missing:
                    plan["questions"].extend(missing)
                if "objective" in missing and not plan["questions"]:
                    plan["questions"].append("预期行为与成功标准是什么？")
                state = ("CLARIFYING" if plan["questions"] or missing or decision["route"] == "CLARIFY"
                         else "PLAN_READY")
            elif project["state"] != "PLAN_READY":
                if action == "freeze" or project["state"] != "CLARIFYING":
                    raise WorkspaceError("WORKSPACE_PLAN_NOT_READY", 409)
            elif action == "freeze":
                # Revalidate legacy drafts at the approval boundary before freezing.
                checked = offline_plan(project, PlanDraft(revision=body.revision, **{
                    key: plan[key] for key in PlanDraft.model_fields if key != "revision" and key in plan}))
                functional = checked['correctness_verification']
                if (checked["questions"] or not checked["goal"]
                        or functional and (not checked['public_cases'] or not checked['acceptance_cases'])
                        or not checked["allowed_write_paths"]
                        or not checked["entrypoint"]):
                    raise WorkspaceError("WORKSPACE_PLAN_NOT_READY", 409)
                if functional and ("NEEDS_CONFIRMATION" in canonical(checked).decode()
                        or not (checked["acceptance_basis"].strip() or checked["reference_profile"] != "none") or not body.confirm_acceptance):
                    raise WorkspaceError("WORKSPACE_ACCEPTANCE_CONFIRMATION_REQUIRED", 409)
                plan["adversarial_enabled"] = body.adversarial_enabled
                route = plan.get("planning", {}).get("route", "PLAN_REQUIRED")
                if route != "DIRECT" and any(
                        not plan.get(field) or any(not value.strip() for value in plan[field])
                        for field in ("implementation", "constraints", "risks")):
                    raise WorkspaceError("WORKSPACE_PLAN_NOT_READY", 409)
                if getattr(body, "approval", "formal") != ("direct" if route == "DIRECT" else "formal"):
                    raise WorkspaceError("WORKSPACE_APPROVAL_ROUTE_MISMATCH", 409)
                rules = rule_triage(plan)
                if route == "DIRECT" and rules["route"] != "DIRECT" and not rules["semantic_eligible"]:
                    raise WorkspaceError("WORKSPACE_APPROVAL_ROUTE_MISMATCH", 409)
                if db.execute("SELECT count(*) FROM freezes WHERE project_id=?", (project_id,)).fetchone()[0] >= MAX_FREEZES:
                    raise WorkspaceError("WORKSPACE_FREEZE_LIMIT", 429)
                state = "FROZEN"
                spec = {"version": 2, "project_id": project_id, "owner": owner,
                        "snapshot_hash": project["snapshot_hash"], "approved_revision": body.revision,
                        "plan": plan, "approval": "direct" if route == "DIRECT" else "formal",
                        "policy": workspace_policy(body.adversarial_enabled)}
                frozen_hash = digest(spec)
                db.execute("INSERT INTO freezes VALUES (?, ?, ?, ?)",
                           (project_id, revision, frozen_hash, canonical(spec).decode()))
            if db.execute("SELECT count(*) FROM planning_events WHERE project_id=?", (project_id,)).fetchone()[0] >= MAX_PLANNING_EVENTS:
                raise WorkspaceError("WORKSPACE_PLANNING_LIMIT", 429)
            decision = plan.get("planning", {}) if plan else {}
            event = {"action": action, "state": state, "plan_hash": digest(plan),
                     "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                     "route": decision.get("route", "PLAN_REQUIRED"),
                     "missing_count": len(decision.get("missing_requirements", []))}
            if action == "plan":
                event.update({key: decision[key] for key in ("source", "fallback_reason",
                             "semantic_elapsed_ms", "inference_usage") if key in decision})
            db.execute("INSERT INTO planning_events VALUES (?, ?, ?)", (project_id, revision, canonical(event).decode()))
            db.execute("UPDATE projects SET revision=?, state=?, plan=?, frozen_hash=? WHERE id=?",
                       (revision, state, canonical(plan).decode(), frozen_hash, project_id))
            return self._project(db, owner, project_id)
