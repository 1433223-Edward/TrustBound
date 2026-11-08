"""Offline analysis checks only: no app imports, requests, Docker, or model calls."""
import json
from pathlib import Path
import tempfile
import unittest
from analyze import summarize, paired
from integrity import seal, verify


class AnalysisTests(unittest.TestCase):
    def row(self,**changes):
        r=dict(experiment_type='B',evidence_source='LIVE_MODEL_DOCKER',actual_model_id=['test-model'],configuration={'group':'baseline','request':{}},source_commit='a'*40,source_hash='b'*64,dataset_version='test',execution_status='COMPLETED',verification_status='VERIFIED',latency_ms=10,estimated_cost=None)
        r.update(changes);return r

    def test_unknown_cost_not_zero_and_failed_task_retained(self):
        s=summarize([self.row(),self.row(execution_status='CLIENT_POLL_TIMEOUT')])[0]
        self.assertIsNone(s['cost']);self.assertIsNone(s['cost_per_verified'])
        self.assertEqual(s['n'],2);self.assertEqual(s['completed'],1)
        self.assertEqual(s['execution_counts']['CLIENT_POLL_TIMEOUT'],1)

    def test_cost_includes_failed_attempts(self):
        s=summarize([self.row(estimated_cost='1'),self.row(estimated_cost='2',execution_status='ERROR')])[0]
        self.assertEqual(s['cost_per_verified'],3)

    def test_security_only_not_verified(self):
        s=summarize([self.row(verification_status='EXECUTED_UNVERIFIED')])[0]
        self.assertEqual(s['success'],0)

    def test_unpaired_not_comparison(self):
        r=self.row(experiment_type='D');r['configuration'].update(pair_id='pair',group='on')
        self.assertEqual(paired([r])[0]['status'],'INVALID_PAIR')

    def test_hash_tampering_detected(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent) as tmp:
            path=Path(tmp)/'raw.json';path.write_text('{}');seal(tmp);verify(tmp)
            path.write_text('{"changed":true}')
            with self.assertRaises(ValueError):verify(tmp)


if __name__=='__main__':unittest.main()

