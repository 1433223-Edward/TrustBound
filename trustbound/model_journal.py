"""Durable Workspace model dispatch journal in the existing quota database.

SENT is committed before entering transport. A crash across that boundary is
deliberately ambiguous; this journal cannot guarantee provider exactly-once.
"""
from contextlib import closing, contextmanager
from datetime import datetime, timezone
import json
import sqlite3


class JournalError(RuntimeError):
    pass


class ModelJournal:
    def __init__(self, database):
        self.database = database
        with self.transaction() as db:
            db.execute("""CREATE TABLE IF NOT EXISTS model_requests (
                id TEXT PRIMARY KEY, run_id TEXT NOT NULL, role TEXT NOT NULL,
                state TEXT NOT NULL, tokens INTEGER NOT NULL DEFAULT 0,
                reserved INTEGER NOT NULL DEFAULT 0, metadata TEXT NOT NULL DEFAULT '{}')""")
            db.execute("""CREATE TABLE IF NOT EXISTS model_request_events (
                seq INTEGER PRIMARY KEY AUTOINCREMENT, request_id TEXT NOT NULL,
                state TEXT NOT NULL, at TEXT NOT NULL, metadata TEXT NOT NULL)""")

    @contextmanager
    def transaction(self):
        try:
            with closing(sqlite3.connect(self.database.as_uri() + '?mode=rw', uri=True, timeout=2)) as db, db:
                db.row_factory = sqlite3.Row
                db.execute('BEGIN IMMEDIATE')
                yield db
        except (sqlite3.Error, OSError, ValueError):
            raise JournalError('MODEL_JOURNAL_UNAVAILABLE') from None

    def _transition(self, db, request_id, state, metadata=None):
        encoded = json.dumps(metadata or {}, ensure_ascii=False, allow_nan=False)
        db.execute('UPDATE model_requests SET state=?, metadata=? WHERE id=?', (state, encoded, request_id))
        db.execute('INSERT INTO model_request_events(request_id,state,at,metadata) VALUES(?,?,?,?)',
                   (request_id, state, datetime.now(timezone.utc).isoformat(), encoded))

    def create(self, run_id, role):
        request_id = run_id + ':' + role
        with self.transaction() as db:
            if db.execute('SELECT 1 FROM model_requests WHERE id=?', (request_id,)).fetchone():
                raise JournalError('MODEL_REQUEST_ALREADY_RECORDED')
            db.execute('INSERT INTO model_requests(id,run_id,role,state) VALUES(?,?,?,?)',
                       (request_id, run_id, role, 'CREATED'))
            self._transition(db, request_id, 'CREATED')
        return request_id

    def reserve(self, request_id, outputs, max_calls, max_tokens):
        with self.transaction() as db:
            request = db.execute('SELECT state FROM model_requests WHERE id=?', (request_id,)).fetchone()
            if not request or request['state'] != 'CREATED':
                raise JournalError('MODEL_REQUEST_ALREADY_RECORDED')
            quota = db.execute('SELECT calls,tokens FROM budget WHERE id=1').fetchone()
            if not quota or any(type(value) is not int or value < 0 for value in quota):
                raise JournalError('QUOTA_STORE_UNAVAILABLE')
            if quota['calls'] >= max_calls or quota['tokens'] + outputs > max_tokens:
                raise JournalError('MODEL_QUOTA_EXHAUSTED')
            # The request reservation and global counters commit in one transaction.
            db.execute('UPDATE budget SET calls=calls+1,tokens=tokens+? WHERE id=1', (outputs,))
            db.execute('UPDATE model_requests SET tokens=?,reserved=1 WHERE id=?', (outputs, request_id))
            self._transition(db, request_id, 'RESERVED')

    def mark(self, request_id, state, metadata=None):
        allowed = {'SENT': {'RESERVED'}, 'RESPONSE_RECEIVED': {'SENT', 'RESPONSE_RECEIVED'},
                   'UNKNOWN_BILLING': {'SENT'}}
        with self.transaction() as db:
            row = db.execute('SELECT state FROM model_requests WHERE id=?', (request_id,)).fetchone()
            if not row or row['state'] not in allowed.get(state, set()):
                raise JournalError('INVALID_MODEL_REQUEST_TRANSITION')
            self._transition(db, request_id, state, metadata)

    def _unsent(self, db, row):
        if row['reserved']:
            db.execute('UPDATE budget SET calls=calls-1,tokens=tokens-? WHERE id=1 AND calls>=1 AND tokens>=?',
                       (row['tokens'], row['tokens']))
            if db.execute('SELECT changes()').fetchone()[0] != 1:
                raise JournalError('QUOTA_STORE_UNAVAILABLE')
            db.execute('UPDATE model_requests SET reserved=0 WHERE id=?', (row['id'],))
        self._transition(db, row['id'], 'PRE_SEND_FAILED')

    def fail_unsent(self, request_id):
        with self.transaction() as db:
            row = db.execute('SELECT * FROM model_requests WHERE id=?', (request_id,)).fetchone()
            if row and row['state'] in ('CREATED', 'RESERVED'):
                self._unsent(db, row)

    def reconcile(self):
        # Called once on singleton service startup, before accepting new work.
        with self.transaction() as db:
            for row in db.execute("SELECT * FROM model_requests WHERE state IN ('CREATED','RESERVED','SENT')").fetchall():
                if row['state'] == 'SENT':
                    self._transition(db, row['id'], 'UNKNOWN_BILLING', {'reason': 'PROCESS_INTERRUPTED'})
                else:
                    self._unsent(db, row)

    def summary(self, run_id):
        with self.transaction() as db:
            requests = [dict(row) for row in db.execute('SELECT id,role,state,tokens,metadata FROM model_requests WHERE run_id=?', (run_id,))]
        states = {row['state'] for row in requests}
        state = ('UNKNOWN_BILLING' if states & {'SENT', 'UNKNOWN_BILLING'} else
                 'RESULT_RECEIVED' if states & {'RESPONSE_RECEIVED', 'FINALIZED'} else 'SAFE_TO_RETRY')
        return {'state': state, 'requests': requests}

    def finalize(self, run_id, verdict):
        with self.transaction() as db:
            for row in db.execute("SELECT * FROM model_requests WHERE run_id=? AND state='RESPONSE_RECEIVED'", (run_id,)).fetchall():
                metadata = json.loads(row['metadata'])
                self._transition(db, row['id'], 'FINALIZED', {**metadata, 'verdict': verdict})
