"""Persistent, fail-closed task and model admission for the single-VM deployment."""
import argparse
from contextlib import closing, contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from functools import cached_property
import os
from pathlib import Path
import re
import sqlite3
import time


class AdmissionError(Exception):
    def __init__(self, code, retry_after=None):
        super().__init__(code)
        self.code = code
        self.retry_after = retry_after


@dataclass(frozen=True)
class Admission:
    database: Path
    max_runs: int = 40
    min_run_seconds: int = 5
    max_model_calls: int = 0
    max_output_tokens: int = 0

    @cached_property
    def journal(self):
        from .model_journal import ModelJournal
        return ModelJournal(self.database)

    def _reserve(self, *, outputs=None, now=None, run_id=None):
        now = int(time.time()) if now is None else now
        try:
            # mode=rw is intentional: deletion must never silently reset a campaign.
            with closing(sqlite3.connect(self.database.as_uri() + "?mode=rw", uri=True, timeout=0.2)) as db, db:
                db.execute("BEGIN IMMEDIATE")
                if run_id is not None:
                    db.execute("CREATE TABLE IF NOT EXISTS run_admissions (run_id TEXT PRIMARY KEY, reserved_at INTEGER NOT NULL)")
                    if db.execute("SELECT 1 FROM run_admissions WHERE run_id=?", (run_id,)).fetchone():
                        return
                row = db.execute("SELECT runs, calls, tokens, last_run FROM budget WHERE id = 1").fetchone()
                if row is None or any(type(value) is not int or value < 0 for value in row):
                    raise sqlite3.DatabaseError("Invalid quota ledger")
                runs, calls, tokens, last_run = row
                if outputs is None:
                    if runs >= self.max_runs:
                        raise AdmissionError("RUN_QUOTA_EXHAUSTED")
                    wait = self.min_run_seconds - (now - last_run)
                    if wait > 0:
                        raise AdmissionError("RUN_RATE_LIMITED", wait)
                    db.execute("UPDATE budget SET runs = ?, last_run = ? WHERE id = 1", (runs + 1, now))
                    if run_id is not None:
                        db.execute("INSERT INTO run_admissions VALUES (?, ?)", (run_id, now))
                else:
                    if calls >= self.max_model_calls or tokens + outputs > self.max_output_tokens:
                        raise AdmissionError("MODEL_QUOTA_EXHAUSTED")
                    db.execute("UPDATE budget SET calls = ?, tokens = ? WHERE id = 1", (calls + 1, tokens + outputs))
        except (sqlite3.Error, OSError, ValueError):
            raise AdmissionError("QUOTA_STORE_UNAVAILABLE") from None

    def reserve_run(self, run_id=None):
        self._reserve(run_id=run_id)

    def reserve_model(self, outputs):
        if type(outputs) is not int or not 1 <= outputs <= 4096:
            raise AdmissionError("INVALID_MODEL_RESERVATION")
        self._reserve(outputs=outputs)


def initialize(database):
    """Create a new campaign explicitly; never replace an existing ledger."""
    path = Path(database)
    if not path.is_absolute():
        raise ValueError("Quota database path must be absolute")
    fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    os.close(fd)
    with closing(sqlite3.connect(path)) as db, db:
        db.execute("CREATE TABLE budget (id INTEGER PRIMARY KEY CHECK (id = 1),"
                   " runs INTEGER NOT NULL, calls INTEGER NOT NULL, tokens INTEGER NOT NULL,"
                   " last_run INTEGER NOT NULL)")
        db.execute("INSERT INTO budget VALUES (1, 0, 0, 0, 0)")


def _limit(name, default, minimum, maximum):
    value = int(os.environ.get(name, default))
    if not minimum <= value <= maximum:
        raise ValueError(f"Invalid deployment limit: {name}")
    return value


def deployment_settings():
    public = os.environ.get("TRUSTBOUND_PUBLIC_DEMO") == "1"
    domain = os.environ.get("TRUSTBOUND_PUBLIC_DOMAIN", "")
    database = os.environ.get("TRUSTBOUND_QUOTA_DB", "")
    if public:
        if (not re.fullmatch(r"(?=.{1,253}$)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z][a-z0-9-]{0,62}", domain)
                or not database or not os.environ.get("TRUSTBOUND_RUNNER_SOCKET")
                or any(os.environ.get(name) == "1" for name in
                       ("TRUSTBOUND_ENABLE_LIVE", "TRUSTBOUND_ENABLE_RECOVERY_LIVE", "TRUSTBOUND_ENABLE_CUSTOM_TASK"))):
            raise ValueError("Public demo requires a domain, quota ledger, isolated Runner, and offline-only settings")
    if not database:
        if os.environ.get("TRUSTBOUND_RUNNER_SOCKET") and os.environ.get("TRUSTBOUND_ENABLE_LIVE") == "1":
            raise ValueError("Deployed Live inference requires a persistent quota ledger")
        return public, domain, None
    path = Path(database)
    if not path.is_absolute():
        raise ValueError("Quota database path must be absolute")
    return public, domain, Admission(
        path,
        _limit("TRUSTBOUND_MAX_RUNS", 40, 1, 10_000),
        _limit("TRUSTBOUND_MIN_RUN_SECONDS", 5, 1 if public else 0, 3600),
        _limit("TRUSTBOUND_MAX_MODEL_CALLS", 0, 0, 100),
        _limit("TRUSTBOUND_MAX_OUTPUT_TOKENS", 0, 0, 200_000),
    )


_MODEL_ADMISSION = ContextVar("trustbound_model_admission", default=None)
_MODEL_REQUEST = ContextVar("trustbound_model_request", default=None)


@contextmanager
def model_request_identity(run_id, role):
    admission = _MODEL_ADMISSION.get()
    if not isinstance(admission, Admission):
        yield
        return
    from .model_journal import JournalError
    from .inference import InferenceError
    try:
        request_id = admission.journal.create(run_id, role)
    except JournalError as error:
        raise InferenceError(str(error)) from None
    token = _MODEL_REQUEST.set((admission, request_id))
    try:
        yield
    finally:
        _MODEL_REQUEST.reset(token)
        admission.journal.fail_unsent(request_id)


def model_request_transition(state, metadata=None):
    identity = _MODEL_REQUEST.get()
    if identity:
        identity[0].journal.mark(identity[1], state, metadata)


@contextmanager
def inference_admission(admission):
    token = _MODEL_ADMISSION.set(admission)
    try:
        yield
    finally:
        _MODEL_ADMISSION.reset(token)


def reserve_live_attempt(outputs):
    admission = _MODEL_ADMISSION.get()
    identity = _MODEL_REQUEST.get()
    if identity:
        admission.journal.reserve(identity[1], outputs, admission.max_model_calls, admission.max_output_tokens)
    elif admission is not None:
        admission.reserve_model(outputs)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("init",))
    parser.add_argument("database", type=Path)
    args = parser.parse_args()
    try:
        initialize(args.database)
    except (ValueError, OSError, sqlite3.Error):
        parser.exit(1, "Quota initialization failed. An existing ledger will not be overwritten.\n")
    print("Quota ledger initialized.")


if __name__ == "__main__":
    main()
