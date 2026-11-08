"""Correctness is optional; scope, sandbox and evidence checks never are."""
from dataclasses import replace
import json
import time
import unittest
from unittest.mock import patch
from fastapi.testclient import TestClient
from tests import test_workspace_execution as fixtures
from tests import test_workspace_parallel as parallel
from trustbound.api import create_app
from trustbound.workspace import digest, run_fingerprint
from trustbound.workspace_execution import StartWorkspaceRun, WorkspaceJob, execute_workspace, workspace_retry_context

class VerificationModeTests(unittest.TestCase):
    setUp=fixtures.WorkspaceExecutionTests.setUp
    evidence=fixtures.WorkspaceExecutionTests.evidence

    def execute(self, worker=None, **updates):
        body={'revision':2,'mode':'offline','files':{'main.py':'after'},'correctness_verification':False,'execution_input':2,**updates}
        with patch('trustbound.workspace_execution.run_worker_request',side_effect=worker or self.evidence) as runner:
            started=self.client.post(self.project+'/runs',json=body)
            self.assertEqual(started.status_code,202,started.text)
            path=self.project+'/runs/'+started.json()['run_id']
            for _ in range(200):
                record=self.client.get(path).json()
                if record['state'] not in ('RUNNING','QUEUED'):break
                time.sleep(.01)
        return path,record,runner.call_args_list

    def test_security_only_executes_once_without_expected_values_or_verified_acceptance(self):
        with patch('trustbound.workspace_execution.reference_result',side_effect=AssertionError('No business oracle')):
            path,record,calls=self.execute()
        report=record['workspace_report']
        self.assertEqual(record['verification_mode'],'SECURITY_ONLY')
        self.assertEqual(report['status'],'EXECUTED_UNVERIFIED')
        self.assertEqual(report['security_evidence']['status'],'CONFIRMED')
        self.assertEqual(report['functional_verification']['status'],'NOT_REQUESTED')
        self.assertEqual(len(calls),1)
        self.assertEqual(calls[0].args[1],'execution')
        self.assertNotIn('expected',report['cases'][0])
        self.assertEqual(self.client.post(path+'/review/ACCEPTED',json={}).status_code,409)
        self.assertEqual(self.client.post(path+'/review/KEPT_UNVERIFIED',json={}).status_code,200)
        self.assertIsNone(workspace_retry_context(self.frozen,record))

    def test_invalid_security_evidence_never_counts_as_safe_execution(self):
        for changes in ({'cleanup_confirmed':False},{'limits_verified':False},{'workspace_unchanged':False},
                        {'artifact_hash':'wrong'},{'test_hash':'wrong'},{'image':'wrong'},{'phase':'public'}):
            with self.subTest(changes=changes):
                _,record,_=self.execute(lambda *args:replace(self.evidence(*args),**changes))
                self.assertEqual(record['workspace_report']['status'],'INCONCLUSIVE')
                self.assertEqual(record['workspace_report']['security_evidence']['status'],'INCONCLUSIVE')

    def test_scope_and_runtime_failure_remain_enforced(self):
        _,denied,calls=self.execute(files={'protected.py':'x'})
        self.assertEqual(denied['workspace_report']['status'],'REJECTED')
        self.assertEqual(calls,[])
        _,failed,_=self.execute(lambda *args:replace(self.evidence(*args),exit_code=1))
        self.assertEqual(failed['workspace_report']['status'],'EXECUTION_FAILED')
        self.assertIsNone(workspace_retry_context(self.frozen,failed))

    def test_security_plan_needs_no_oracle_but_cannot_enable_functional_mode_without_reapproval(self):
        planned=self.client.post(self.project+'/plan',json={**self.plan,'revision':2,'correctness_verification':False,
            'public_cases':[],'acceptance_cases':[],'acceptance_basis':''}).json()
        self.assertEqual(planned['state'],'PLAN_READY')
        frozen=self.client.post(self.project+'/freeze',json={'revision':planned['revision']})
        self.assertEqual(frozen.status_code,200,frozen.text)
        revision=frozen.json()['revision']
        self.assertEqual(self.client.post(self.project+'/runs',json={'revision':revision,'mode':'original'}).status_code,409)
        _,record,_=self.execute(revision=revision)
        self.assertEqual(record['workspace_report']['status'],'EXECUTED_UNVERIFIED')

    def test_mode_defaults_and_idempotency_match_legacy_full_verification(self):
        request=StartWorkspaceRun(revision=2,mode='original')
        self.assertTrue(request.correctness_verification)
        legacy=request.model_dump(exclude={'idempotency_key','correctness_verification','execution_input'})
        self.assertEqual(run_fingerprint(request),digest(legacy))
        with self.assertRaises(ValueError):
            StartWorkspaceRun(revision=2,mode='live',authorize_source=True,correctness_verification=False,retry_run_id='a'*32)

    def test_adversarial_analysis_is_independent_but_its_suggestions_are_not_confirmed(self):
        fixture=parallel.ParallelWorkspaceTests()
        fixture.setUp()
        request=StartWorkspaceRun(revision=2,mode='live',authorize_source=True,adversarial_enabled=True,
                                  correctness_verification=False,execution_input=fixture.input)
        with patch('trustbound.workspace_execution._live_replacements',return_value=fixture.fixed), \
             patch('trustbound.workspace_execution.generate_challenges',return_value=fixture.proposals()) as adversary, \
             patch('trustbound.workspace_execution.run_worker_request',side_effect=fixture.observe) as runner:
            report=execute_workspace(WorkspaceJob(fixture.project,request,'ROOTLESS_WORKER'),'f'*32)
        adversary.assert_called_once()
        runner.assert_called_once()
        self.assertEqual(report['status'],'EXECUTED_UNVERIFIED')
        self.assertEqual(report['adversarial_report']['challenges'][0]['status'],'VALID')
        self.assertEqual(report['adversarial_report']['verification_status'],'NOT_RUN_FUNCTIONAL_VERIFICATION_DISABLED')

    def test_real_docker_runs_the_same_restricted_driver_without_functional_cases(self):
        with patch('trustbound.api.workspace_transport',return_value='LOCAL_DOCKER'):
            app=create_app(report_directory=None)
        with TestClient(app,base_url='http://127.0.0.1',headers=self.client.headers) as client:
            imported=client.post(self.base,json={'files':[{'path':'main.py','content':'def solve(value):\n    return {"echo": value}\n'}]}).json()
            route=self.base+'/'+imported['project_id']
            draft=client.post(route+'/plan',json={**self.plan,'revision':0,'correctness_verification':False,
                'public_cases':[],'acceptance_cases':[],'acceptance_basis':''}).json()
            frozen=client.post(route+'/freeze',json={'revision':draft['revision']})
            self.assertEqual(frozen.status_code,200,frozen.text)
            started=client.post(route+'/runs',json={'revision':frozen.json()['revision'],'mode':'original',
                'correctness_verification':False,'execution_input':7})
            self.assertEqual(started.status_code,202,started.text)
            for _ in range(400):
                record=client.get(route+'/runs/'+started.json()['run_id']).json()
                if record['state'] not in ('RUNNING','QUEUED'):break
                time.sleep(.05)
            report=record['workspace_report']
            self.assertEqual(report['status'],'EXECUTED_UNVERIFIED',report)
            self.assertEqual(report['security_evidence']['status'],'CONFIRMED')
            self.assertEqual(len(report['cases']),1)
            evidence=report['cases'][0]['execution']
            self.assertTrue(all(evidence[key] for key in ('cleanup_confirmed','limits_verified','workspace_unchanged')))
            self.assertEqual(json.loads(evidence['stdout']),{'echo':7})
            self.assertEqual(report['functional_verification']['status'],'NOT_REQUESTED')
