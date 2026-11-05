"""Gate D authorization boundaries using explicit synthetic verification evidence."""
from dataclasses import replace
import json
import unittest
from unittest.mock import patch
from scripts.check_gate_d import initial_outcome, ConfirmedChallengeReplay, verify_repair
from trustbound.adversarial_contracts import AdversarialReport, ChallengeValidationResult, AdversarialChallenge
from trustbound.contracts import ExecutionResult
from trustbound.recovery import recovery_eligibility, build_recovery_context
from trustbound.runner import sha256, IMAGE
from trustbound.service import TASK, ROOT


class GateDTests(unittest.TestCase):
    def test_parent_evidence_is_bound_and_context_is_minimal(self):
        initial = initial_outcome()
        trigger, failures, problem = recovery_eligibility(initial)
        self.assertIsNone(problem)
        self.assertEqual(trigger, 'CONFIRMED_ADVERSARIAL')
        self.assertEqual([f['amount'] for f in failures], ['1.23495', '-1.23495'])
        context = build_recovery_context(initial, failures, 0)
        self.assertEqual(context['remaining_recovery_attempts'], 0)
        self.assertEqual(set(context), {'task_id','requirement','candidate','confirmed_failures','remaining_recovery_attempts'})
        self.assertNotIn('calls', context)

    def test_replay_has_no_network_and_does_not_copy_expected_values(self):
        _, failures, _ = recovery_eligibility(initial_outcome())
        adapter = ConfirmedChallengeReplay(failures)
        data = json.loads(adapter.complete(None, None, None))
        self.assertEqual(len(data['challenges']), 2)
        self.assertTrue(all(set(c) == {'amount','requirement_id','reason'} for c in data['challenges']))
        self.assertEqual(adapter.calls, [])
        self.assertEqual(adapter.source, 'TRUSTED_GATE_C_REPLAY')

    @patch('scripts.check_gate_d.run_adversarial')
    @patch('scripts.check_gate_d.verify_patch')
    def test_successful_replay_cannot_replace_fresh_adversarial_review(self, verify, replay):
        code = (ROOT / 'fixtures/billing/fixed.py').read_text()
        artifact = sha256(code.encode())
        verify.return_value.to_dict.return_value = {'status':'VERIFIED','artifact_hash':artifact,'run_id':'unit-formal'}
        row = ChallengeValidationResult(AdversarialChallenge('unit','1.23495','billing-v1.round-half-up','unit'),
            'NOT_CONFIRMED',expected=123,actual=123,actual_type='int')
        e = ExecutionResult('adversarial','unit-container',IMAGE,artifact,'unit-driver','EXITED',0,'','',None,True,True,True)
        replay.return_value = AdversarialReport(TASK.task_id,artifact,'COMPLETED','TRUSTED_GATE_C_REPLAY','unit',{},(row,),e,'unit-driver')
        result = verify_repair({'analysis':'unit','files':{'billing.py':code}}, [])
        self.assertEqual(result['gate_c_replay_report']['status'], 'COMPLETED')
        self.assertEqual(result['adversarial_report']['status'], 'UNAVAILABLE')
        self.assertEqual(result['final_decision']['status'], 'INCONCLUSIVE')
