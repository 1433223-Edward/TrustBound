"""Offline control checks; no real inference or container claims."""
import json
import unittest
from unittest.mock import Mock, patch
from trustbound.executor import run_executor
from trustbound.inference import VultrClient, DEFAULT_MODEL, InferenceError
from trustbound.service import ROOT

class GateBTests(unittest.TestCase):
    @patch('trustbound.executor.verify_patch')
    def test_one_proposal_skips_smoke_and_reuses_verifier(self, verify):
        code = (ROOT / 'fixtures/billing/fixed.py').read_text()
        transport = Mock(side_effect=[{'data':[{'id':DEFAULT_MODEL,'architecture':{'output_modalities':['text']}}]},
            {'model':DEFAULT_MODEL,'choices':[{'finish_reason':'stop','message':{'content':json.dumps({'analysis':'OFFLINE unit proposal','files':{'billing.py':code}})}}]}])
        verify.return_value.status = 'FAILED'
        verify.return_value.to_dict.return_value = {'status':'FAILED','unit_double':True}
        client = VultrClient('offline-unit', transport=transport, timeout=60, max_attempts=1, output_limit=2048)
        report = run_executor(client, model_id=DEFAULT_MODEL, smoke_check=False, proposal_tokens=2048)
        self.assertEqual(len(client.calls), 1)
        self.assertEqual([r['phase'] for r in report['requests']], ['proposal'])
        self.assertEqual(transport.call_args.args[2]['max_completion_tokens'], 2048)
        self.assertEqual(report['status'], 'FAILED')
        verify.assert_called_once_with('billing-rounding-01', {'billing.py':code})

    def test_default_output_cap_still_blocks_2048(self):
        transport = Mock()
        client = VultrClient('offline-unit', transport=transport)
        with self.assertRaises(InferenceError):
            client.complete({'id':DEFAULT_MODEL}, [], 2048)
        transport.assert_not_called()
