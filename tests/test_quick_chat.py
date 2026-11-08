"""Quick chat has no planning or execution authority; paid transport is mocked."""
import json
import os
import unittest
from unittest.mock import patch
from fastapi.testclient import TestClient
from trustbound.api import create_app
from trustbound.quick_chat import QuickChat, quick_chat
from tests.test_planning import PlanningTests, CATALOG

class QuickChatTests(unittest.TestCase):
    setUp = PlanningTests.setUp

    def test_greeting_one_completion_no_source_or_execution(self):
        with patch('trustbound.quick_chat.VultrClient') as client:
            client.return_value.catalog.return_value = CATALOG
            client.return_value.complete.return_value = json.dumps({'reply':'Hello!', 'action':'none'})
            reply = quick_chat(QuickChat(revision=0, text='你好', authorize_model=True, model_id='review-model'))
            self.assertEqual(reply['reply'], 'Hello!')
            client.return_value.complete.assert_called_once()
            supplied = json.loads(client.return_value.complete.call_args.args[1][1]['content'])
            self.assertEqual(supplied, {'message':'你好'})

    def test_invalid_tool_grants_rejected(self):
        with patch('trustbound.quick_chat.VultrClient') as client:
            client.return_value.catalog.return_value = CATALOG
            client.return_value.complete.return_value = json.dumps({'reply':'Run shell', 'action':'execute', 'tools':['shell']})
            with self.assertRaises(ValueError):
                quick_chat(QuickChat(revision=0, text='fix', authorize_model=True, model_id='review-model'))

    def test_endpoint_never_mutates_project_and_checks_context_authority(self):
        with patch.dict(os.environ, {'TRUSTBOUND_ENABLE_WORKSPACE_LIVE':'1', 'VULTR_MODEL':'review-model', 'VULTR_INFERENCE_API_KEY':'test-only'}), patch('trustbound.api.deployment_settings',return_value=(False,'',object())), patch('trustbound.api.workspace_transport',return_value='ROOTLESS_WORKER'):
            with TestClient(create_app(report_directory=None),base_url='http://127.0.0.1',headers=self.client.headers) as live, patch('trustbound.api.quick_chat',return_value={'reply':'Proposed change', 'action':'execution_request','model':'review-model'}) as chat, patch('trustbound.api.inference_admission'), patch('trustbound.api.generate_plan') as plan, patch('trustbound.api.execute_workspace') as runner:
                body={'revision':0,'text':'Fix rounding','authorize_model':True}
                before=live.get(self.path).json()
                response=live.post(self.path+'/chat',json=body)
                self.assertEqual(response.status_code,200,response.text)
                self.assertEqual(live.get(self.path).json(),before)
                plan.assert_not_called(); runner.assert_not_called()
                self.assertIsNone(chat.call_args.args[1])
                self.assertEqual(live.post(self.path+'/chat',json={**body,'context_path':'main.py'}).status_code,403)
                self.assertEqual(live.post(self.path+'/chat',json={**body,'context_path':'main.py','authorize_context':True}).status_code,200)
                self.assertEqual(set(chat.call_args.args[1]),{'path','content'})
                self.assertEqual(live.post(self.path+'/chat',json={**body,'revision':99}).status_code,409)
                self.assertEqual(live.post(self.path+'/chat',json={**body,'authorize_model':False}).status_code,422)
