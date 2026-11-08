"""Human retention never certifies a candidate; explanations remain advisory."""
import json
import unittest
from unittest.mock import patch
from tests import test_workspace_execution as fixtures
from trustbound.workspace_explanation import generate_explanation, review_context

PAIR={'en':'Brief public explanation','zh':'简短公开说明'}
class ReviewInteractionTests(unittest.TestCase):
    setUp=fixtures.WorkspaceExecutionTests.setUp
    evidence=fixtures.WorkspaceExecutionTests.evidence
    run_candidate=fixtures.WorkspaceExecutionTests.run_candidate

    def test_inconclusive_changes_can_be_retained_exported_but_not_restored_as_verified(self):
        from dataclasses import replace
        path,report=self.run_candidate(lambda *args:replace(self.evidence(*args),stdout='not JSON'))
        self.assertEqual(report['status'],'INCONCLUSIVE')
        self.assertEqual(self.client.post(path+'/review/ACCEPTED',json={}).status_code,409)
        kept=self.client.post(path+'/review/KEPT_UNVERIFIED',json={})
        self.assertEqual(kept.status_code,200,kept.text)
        self.assertEqual(kept.json()['workspace_report'],report)
        self.assertEqual(kept.json()['review'],'KEPT_UNVERIFIED')
        exported=self.client.get(path+'/export/zip')
        self.assertEqual(exported.status_code,200)
        self.assertIn('unverified',exported.headers['content-disposition'])
        restored=self.client.post(self.project+'/runs',json={'revision':2,'mode':'restore','restore_run_id':report['run_id']})
        self.assertEqual(restored.status_code,409)

    def test_retention_rejects_tampered_candidate(self):
        path,report=self.run_candidate(self.evidence)
        store=self.client.app.state.projects
        with store.transaction() as db:
            row=db.execute('SELECT record FROM runs WHERE id=?',(report['run_id'],)).fetchone()
            record=json.loads(row['record']);record['workspace_report']['replacements']['main.py']='tampered'
            db.execute('UPDATE runs SET record=? WHERE id=?',(json.dumps(record),report['run_id']))
        self.assertEqual(self.client.post(path+'/review/KEPT_UNVERIFIED',json={}).status_code,409)

    def test_review_covers_every_requirement_and_keeps_independent_values_sealed(self):
        _,report=self.run_candidate(self.evidence)
        project={**self.frozen,'plan':{**self.frozen['plan'],'acceptance_cases':[{'input':'SEALED_INPUT','expected':'SEALED_EXPECTED'}]}}
        context=review_context(project,report)
        self.assertNotIn('SEALED_',json.dumps(context))
        payload={'summary':PAIR,'requirements':[{'id':row['id'],'status':'unknown','explanation':PAIR} for row in context['requirements']],
                 'roles':[{'role':role,'description':PAIR,'reason':PAIR} for role in context['roles']]}
        with patch('trustbound.workspace_explanation.VultrClient') as client:
            client.return_value.catalog.return_value={'data':[{'id':'test','architecture':{'output_modalities':['text']}}]}
            client.return_value.complete.return_value=json.dumps(payload)
            result=generate_explanation(project,report,'test')
            self.assertTrue(result['advisory'])
            self.assertEqual(set(result['requirement_texts']),{row['id'] for row in payload['requirements']})
            self.assertNotIn('SEALED_',json.dumps(client.return_value.complete.call_args.args[1]))
            payload['requirements'].pop()
            client.return_value.complete.return_value=json.dumps(payload)
            with self.assertRaises(ValueError):generate_explanation(project,report,'test')

    def test_explanation_failure_does_not_change_verdict_or_hide_changes(self):
        from trustbound.workspace_execution import execute_workspace, StartWorkspaceRun, WorkspaceJob
        from trustbound.inference import InferenceError
        request=StartWorkspaceRun(revision=2,mode='offline',files={'main.py':'after'},authorize_explanation=True)
        with patch('trustbound.workspace_execution.run_worker_request',side_effect=self.evidence),patch('trustbound.workspace_execution.generate_explanation',side_effect=InferenceError('MODEL_QUOTA_EXHAUSTED')):
            report=execute_workspace(WorkspaceJob(self.frozen,request,'ROOTLESS_WORKER'),'a'*32)
        self.assertEqual(report['status'],'VERIFIED')
        self.assertEqual(report['explanation_status'],'UNAVAILABLE')
        self.assertEqual(report['changed_paths'],['main.py'])

    def test_existing_run_explanation_is_cached_without_changing_verdict(self):
        import os
        from unittest.mock import Mock
        from fastapi.testclient import TestClient
        from trustbound.api import create_app
        path,report=self.run_candidate(self.evidence)
        response={'summary':PAIR,'requirements':[],'roles':[], 'artifact_hash':report['artifact_hash'], 'frozen_hash':report['frozen_hash']}
        with patch.dict(os.environ,{'TRUSTBOUND_ENABLE_WORKSPACE_LIVE':'1','VULTR_INFERENCE_API_KEY':'test-placeholder','VULTR_MODEL':'test-model'}),patch('trustbound.api.workspace_transport',return_value='ROOTLESS_WORKER'),patch('trustbound.api.deployment_settings',return_value=(False,'',Mock())):
            with TestClient(create_app(report_directory=None),base_url='http://127.0.0.1',headers=self.client.headers) as live,patch('trustbound.api.generate_explanation',return_value=response) as model:
                self.assertEqual(live.post(path+'/explanation',json={'authorize_model':False}).status_code,422)
                for _ in range(2):
                    updated=live.post(path+'/explanation',json={'authorize_model':True})
                    self.assertEqual(updated.status_code,200,updated.text)
                    self.assertEqual(updated.json()['workspace_report']['status'],report['status'])
                model.assert_called_once()
