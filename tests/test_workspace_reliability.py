"""Durable recovery boundaries using real SQLite, simulated transport and Runner."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from dataclasses import replace
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
from tempfile import TemporaryDirectory
import time
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient
from trustbound.admission import Admission, initialize, inference_admission, model_request_identity
from trustbound.api import create_app
from trustbound.inference import InferenceError, VultrClient
from trustbound.model_journal import JournalError
from trustbound.workspace import WorkspaceStore
from trustbound.workspace_execution import StartWorkspaceRun, WorkspaceJob
from tests import test_workspace_execution as fixtures


class JournalTests(unittest.TestCase):
    def setUp(self):
        self.directory = self.enterContext(TemporaryDirectory())
        self.path = Path(self.directory) / 'quota.sqlite'
        initialize(self.path)
        self.admission = Admission(self.path, min_run_seconds=0, max_model_calls=4, max_output_tokens=16384)

    def counters(self):
        with closing(sqlite3.connect(self.path)) as db:
            return db.execute('SELECT calls,tokens FROM budget').fetchone()

    def test_actual_process_exit_before_and_after_dispatch(self):
        for run_id, stage in [('before', 'RESERVED'), ('after', 'SENT')]:
            script = "from pathlib import Path; import os; from trustbound.admission import Admission; a=Admission(Path(" + repr(str(self.path)) + "),max_model_calls=4,max_output_tokens=16384); j=a.journal; r=j.create(" + repr(run_id) + ",'executor'); j.reserve(r,1024,4,16384); " + ("j.mark(r,'SENT'); " if stage == 'SENT' else '') + 'os._exit(7)'
            self.assertEqual(subprocess.run([sys.executable, '-B', '-c', script], capture_output=True).returncode, 7)
            self.admission.journal.reconcile()
            summary = self.admission.journal.summary(run_id)
            self.assertEqual(summary['state'], 'SAFE_TO_RETRY' if stage == 'RESERVED' else 'UNKNOWN_BILLING')
            self.assertEqual(self.counters(), (0, 0) if stage == 'RESERVED' else (1, 1024))
        self.admission.journal.reconcile()
        self.assertEqual(self.counters(), (1, 1024))

    def test_timeout_is_durable_and_identity_cannot_be_dispatched_again(self):
        attempts = []
        def transport(*args):
            attempts.append(args[0])
            raise TimeoutError()
        client = VultrClient('unit-placeholder', transport=transport, max_attempts=1)
        client.source = 'VULTR_LIVE_HTTP'
        with inference_admission(self.admission):
            with self.assertRaises(InferenceError), model_request_identity('run', 'executor'):
                client.complete({'id':'unit'}, [{'role':'user','content':'hello'}], 1024)
            with self.assertRaises(InferenceError), model_request_identity('run', 'executor'):
                client.complete({'id':'unit'}, [], 1024)
        self.assertEqual(attempts, ['POST'])
        self.assertEqual(self.admission.journal.summary('run')['state'], 'UNKNOWN_BILLING')
        self.assertEqual(self.counters(), (1, 1024))

    def test_response_and_final_verdict_are_recorded_without_hidden_reasoning(self):
        def transport(*args):
            return {'id':'provider-response','model':'unit','usage':{'completion_tokens':3}, 'choices':[{'finish_reason':'stop','message':{'content':'hello', 'reasoning':'PRIVATE_REASONING'}}]}
        client = VultrClient('unit-placeholder', transport=transport, max_attempts=1)
        client.source = 'VULTR_LIVE_HTTP'
        with inference_admission(self.admission), model_request_identity('success', 'executor'):
            self.assertEqual(client.complete({'id':'unit'}, [], 1024), 'hello')
        self.admission.journal.finalize('success', 'VERIFIED')
        summary = self.admission.journal.summary('success')
        self.assertEqual(summary['requests'][0]['state'], 'FINALIZED')
        self.assertNotIn('PRIVATE_REASONING', json.dumps(summary))
        with self.admission.journal.transaction() as db:
            states=[row[0] for row in db.execute('SELECT state FROM model_request_events ORDER BY seq')]
        self.assertEqual(states, ['CREATED','RESERVED','SENT','RESPONSE_RECEIVED','RESPONSE_RECEIVED','FINALIZED'])

    def test_parallel_roles_share_the_persistent_cap(self):
        quota = Admission(self.path, max_model_calls=1, max_output_tokens=1024)
        sent = []
        def work(role):
            def transport(*args):
                sent.append(role)
                return {'model':'unit','choices':[{'finish_reason':'stop','message':{'content':'hello'}}]}
            client = VultrClient('unit-placeholder', transport=transport, max_attempts=1)
            client.source = 'VULTR_LIVE_HTTP'
            try:
                with inference_admission(quota), model_request_identity('parallel', role):
                    return client.complete({'id':'unit'}, [], 1024)
            except InferenceError as error:
                return str(error)
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(work, ['executor', 'adversarial']))
        self.assertEqual(sorted(results), ['MODEL_QUOTA_EXHAUSTED', 'hello'])
        self.assertEqual(len(sent), 1)
        self.assertEqual(self.counters(), (1, 1024))


class WorkspaceReliabilityTests(unittest.TestCase):
    setUp = fixtures.WorkspaceExecutionTests.setUp
    evidence = fixtures.WorkspaceExecutionTests.evidence
    run_candidate = fixtures.WorkspaceExecutionTests.run_candidate

    def quota(self):
        path = self.client.app.state.projects.path.parent / 'quota.sqlite'
        initialize(path)
        return Admission(path, min_run_seconds=0, max_model_calls=4, max_output_tokens=16384)

    def test_concurrent_same_key_claims_one_task_and_one_run_reservation(self):
        manager = self.client.app.state.runs
        manager.admission = quota = self.quota()
        request = StartWorkspaceRun(revision=2,mode='original',idempotency_key='same-key-00000000')
        job = WorkspaceJob({**self.frozen,'owner':'private-operator'}, request, 'ROOTLESS_WORKER')
        with patch.object(manager.pool,'submit') as submit:
            with ThreadPoolExecutor(max_workers=8) as pool:
                identifiers = list(pool.map(lambda _: manager.submit(job), range(16)))
        self.assertEqual(len(set(identifiers)),1)
        submit.assert_called_once()
        with closing(sqlite3.connect(quota.database)) as db:
            self.assertEqual(db.execute('SELECT runs FROM budget').fetchone()[0],1)
        conflict=self.client.post(self.project+'/runs',json={'revision':2,'mode':'offline','files':{'main.py':'x'},'idempotency_key':request.idempotency_key})
        self.assertEqual(conflict.status_code,409)

    def test_startup_persists_interruption_and_preserves_history(self):
        store=self.client.app.state.projects
        for number,state in [(1,'QUEUED'),(2,'RUNNING')]:
            record={'run_id':str(number)*32,'project_id':self.frozen['project_id'],'owner':'private-operator',
                    'frozen_hash':self.frozen['frozen_hash'],'state':'QUEUED','created_at':'now','revision':2}
            store.save_run(record)
            if state=='RUNNING':
                store.save_run({**record,'state':state})
        with patch('trustbound.api.workspace_transport',return_value='ROOTLESS_WORKER'):
            with TestClient(create_app(report_directory=None),base_url='http://127.0.0.1',headers=self.client.headers) as restarted:
                for number in (1,2):
                    record=restarted.get(self.project+'/runs/'+str(number)*32).json()
                    self.assertEqual(record['state'],'ERROR')
        with store.transaction() as db:
            records=[json.loads(row[0]) for row in db.execute('SELECT record FROM runs')]
            self.assertTrue(all(row['state']=='ERROR' for row in records))
            self.assertEqual({row['billing_state'] for row in records},{'SAFE_TO_RETRY','UNKNOWN_BILLING'})
            self.assertEqual(db.execute('SELECT count(*) FROM freezes').fetchone()[0],1)

    def test_presend_failure_unlocks_parent_but_timeout_keeps_it_locked(self):
        _,parent=self.run_candidate(lambda *args:replace(self.evidence(*args),stdout='5'))
        quota=self.quota()
        with patch.dict(os.environ,{'TRUSTBOUND_ENABLE_WORKSPACE_LIVE':'1','TRUSTBOUND_ENABLE_RECOVERY_LIVE':'1','VULTR_INFERENCE_API_KEY':'unit-placeholder','VULTR_MODEL':'test-model'}), patch('trustbound.api.workspace_transport',return_value='ROOTLESS_WORKER'), patch('trustbound.api.deployment_settings',return_value=(False,'',quota)):
            with TestClient(create_app(report_directory=None),base_url='http://127.0.0.1',headers=self.client.headers) as live:
                body={'revision':2,'mode':'live','authorize_source':True,'retry_run_id':parent['run_id'],'idempotency_key':'first-key-00000000'}
                def wait(reply):
                    self.assertEqual(reply.status_code,202,reply.text)
                    route=self.project+'/runs/'+reply.json()['run_id']
                    for _ in range(100):
                        record=live.get(route).json()
                        if record['state'] not in ('RUNNING','QUEUED'): return record
                        time.sleep(.01)
                    self.fail('run did not finish')
                with patch('trustbound.workspace_execution._live_replacements',side_effect=InferenceError('CATALOG_UNAVAILABLE')):
                    before=wait(live.post(self.project+'/runs',json=body))
                self.assertEqual(before['billing_state'],'SAFE_TO_RETRY')
                self.assertFalse(live.get(self.project+'/runs/'+parent['run_id']).json()['retried'])
                def timeout(*args):
                    def transport(*args): raise TimeoutError()
                    client=VultrClient('unit-placeholder',transport=transport,max_attempts=1)
                    client.source='VULTR_LIVE_HTTP'
                    return client.complete({'id':'unit'},[],1024)
                body['idempotency_key']='second-key-0000000'
                with patch('trustbound.workspace_execution._live_replacements',side_effect=timeout) as model:
                    after=wait(live.post(self.project+'/runs',json=body))
                    duplicate=live.post(self.project+'/runs',json=body)
                    self.assertEqual(duplicate.json()['run_id'],after['run_id'])
                    model.assert_called_once()
                self.assertEqual(after['billing_state'],'UNKNOWN_BILLING')
                self.assertTrue(live.get(self.project+'/runs/'+parent['run_id']).json()['retried'])
                self.assertNotIn('retry',after)
