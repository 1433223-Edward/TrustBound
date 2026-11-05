"""Offline API payload/diagnostic checks; no provider call or reasoning text logging."""
import json
import unittest
from unittest.mock import Mock
from trustbound.inference import VultrClient, InferenceError
from trustbound.adversarial import compact_schema, build_context, build_messages
from trustbound.runner import sha256
from trustbound.service import ROOT


class GateCRetestTests(unittest.TestCase):
    def test_payload_and_numeric_diagnostics_without_private_reasoning(self):
        transport = Mock(return_value={'model': 'unit-model', 'usage': {'prompt_tokens': 20,
            'completion_tokens': 4096, 'total_tokens': 4116,
            'completion_tokens_details': {'reasoning_tokens': 1024}},
            'choices': [{'finish_reason': 'length', 'message': {'content': '{', 'reasoning': 'PRIVATE_REASONING_MARKER'}}]})
        client = VultrClient('offline-unit', transport=transport, timeout=60, max_attempts=1, output_limit=4096)
        model = {'id':'unit-model','reasoning':{'supports_max_tokens': True},'supported_parameters':['structured_outputs']}
        with self.assertRaises(InferenceError):
            client.complete(model, [], 4096, json_mode=True, reasoning_tokens=1024, response_schema=compact_schema())
        payload = transport.call_args.args[2]
        self.assertEqual(payload['reasoning'], {'max_tokens':1024})
        self.assertTrue(payload['response_format']['json_schema']['strict'])
        self.assertEqual(transport.call_count, 1)
        self.assertEqual(client.calls[0]['reasoning_tokens'], 1024)
        self.assertEqual(client.calls[0]['content_chars'], 1)
        self.assertNotIn('PRIVATE_REASONING_MARKER', json.dumps(client.calls))

    def test_unsupported_reasoning_budget_never_sends_request(self):
        transport = Mock()
        client = VultrClient('offline-unit', transport=transport, output_limit=4096)
        with self.assertRaisesRegex(InferenceError, 'UNSUPPORTED_REASONING_BUDGET'):
            client.complete({'id':'unit-model'}, [], 4096, reasoning_tokens=1024)
        transport.assert_not_called()

    def test_compact_context_excludes_known_answers_and_schema_caps_generation(self):
        code = (ROOT / 'fixtures/billing/double_rounding.py').read_bytes()
        messages = build_messages(build_context(code, sha256(code)), compact=True)
        self.assertNotIn('1.00499', json.dumps(messages))
        schema = compact_schema()['properties']['challenges']
        self.assertEqual(schema['maxItems'], 3)
        self.assertNotIn('expected', schema['items']['properties'])
