"""Offline final-review parent/version checks; no model or container execution."""
import json
import unittest
from scripts.check_gate_d_final import PARENT, ARTIFACT, validate_parent
from trustbound.adversarial import build_context, build_messages


class GateDFinalTests(unittest.TestCase):
    def parent(self):
        return json.loads(PARENT.read_text(encoding='utf-8'))

    def test_actual_parent_evidence_is_bound(self):
        attempt, code = validate_parent(self.parent())
        self.assertEqual(attempt['candidate_hash'], ARTIFACT)
        payload = json.dumps(build_messages(build_context(code, ARTIFACT), compact=True))
        for value in ['1.23495', '-1.23495', 'confirmed_failures', 'remaining_recovery_attempts']:
            self.assertNotIn(value, payload)

    def test_old_version_and_unconfirmed_replay_cannot_pass_preflight(self):
        for key in ['hash', 'cleanup', 'observation']:
            parent = self.parent()
            attempt = parent['recovery_report']['attempts'][-1]
            if key == 'hash':
                attempt['candidate_hash'] = attempt['previous_candidate_hash']
            elif key == 'cleanup':
                attempt['gate_c_replay_report']['execution']['cleanup_confirmed'] = False
            else:
                attempt['gate_c_replay_report']['challenges'][0]['actual'] = 124
            with self.assertRaises(ValueError):
                validate_parent(parent)
