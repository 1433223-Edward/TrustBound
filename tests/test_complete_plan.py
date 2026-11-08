"""Plan generation and approval regressions; never call a paid model."""
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from trustbound.inference import InferenceError
from trustbound.planning import generate_plan
from trustbound.workspace import FreezeRequest, ImportProject, PlanDraft, WorkspaceError, WorkspaceStore


class CompletePlanTests(unittest.TestCase):
    def setUp(self):
        self.temp = self.enterContext(TemporaryDirectory())
        self.store = WorkspaceStore(Path(self.temp) / 'state.sqlite3')
        self.project = self.store.import_project('user', ImportProject(files=[
            {'path': 'main.py', 'content': 'def solve(x): return x * 2'}]))
        self.payload = PlanDraft(revision=0, goal='Return double the input',
            allowed_write_paths=['main.py'], entrypoint='main.py:solve',
            public_cases=[{'input': 2, 'expected': 4}],
            acceptance_cases=[{'input': 3, 'expected': 6}],
            implementation=['Update solve to multiply by two'], constraints=['Only main.py'],
            risks=['Check zero and negative inputs'],
            acceptance_basis='Explicit multiplication requirement: independently compute 3 * 2 = 6.').model_dump()

    def save(self, payload):
        return self.store.change('user', self.project['project_id'], PlanDraft(**payload), 'plan')

    def freeze(self, revision, confirm=True):
        return self.store.change('user', self.project['project_id'],
            FreezeRequest(revision=revision, confirm_acceptance=confirm), 'freeze')

    def test_generation_preserves_every_field_and_rejects_silent_defaults(self):
        with patch('trustbound.planning.VultrClient') as client:
            client.return_value.catalog.return_value = {'data': [{'id': 'test',
                'architecture': {'output_modalities': ['text']}}]}
            client.return_value.complete.return_value = json.dumps(self.payload)
            draft, _ = generate_plan(self.project, self.payload['goal'], 'test')
            self.assertEqual(draft.model_dump(), self.payload)
            for field in ('implementation', 'constraints', 'risks', 'acceptance_basis', 'questions', 'public_cases'):
                incomplete = dict(self.payload)
                del incomplete[field]
                client.return_value.complete.return_value = json.dumps(incomplete)
                with self.subTest(field=field), self.assertRaises(InferenceError):
                    generate_plan(self.project, self.payload['goal'], 'test')

    def test_questions_edits_approval_and_immutable_snapshot(self):
        pending = self.save({**self.payload, 'questions': ['NEEDS_CONFIRMATION: should negatives double?']})
        self.assertEqual(pending['state'], 'CLARIFYING')
        with self.assertRaises(WorkspaceError):
            self.freeze(1)
        ready = self.save({**self.payload, 'revision': 1, 'implementation': ['User edited step']})
        self.assertEqual(ready['plan']['implementation'], ['User edited step'])
        with self.assertRaises(WorkspaceError):
            self.freeze(2, False)
        frozen = self.freeze(2)
        self.assertEqual(frozen['state'], 'FROZEN')
        self.save({**self.payload, 'revision': 3, 'goal': 'New goal'})
        with self.store.transaction() as db:
            spec = json.loads(db.execute('SELECT spec FROM freezes').fetchone()[0])
        self.assertEqual(spec['plan']['implementation'], ['User edited step'])
        self.assertEqual(spec['snapshot_hash'], self.project['snapshot_hash'])

    def test_unknown_basis_and_invalid_cases_block_approval(self):
        for basis in ('', 'NEEDS_CONFIRMATION: rounding rule?'):
            ready = self.save({**self.payload, 'revision': self.store.read('user', self.project['project_id'])['revision'],
                               'acceptance_basis': basis})
            with self.assertRaises(WorkspaceError):
                self.freeze(ready['revision'])
        with self.assertRaises(WorkspaceError):
            self.save({**self.payload, 'revision': ready['revision'], 'acceptance_cases': self.payload['public_cases']})

    def test_twenty_files_and_twenty_one_rejected(self):
        files = [{'path': f'm{i}.py', 'content': 'x=1'} for i in range(20)]
        self.store.import_project('user', ImportProject(files=files))
        with self.assertRaises(WorkspaceError):
            self.store.import_project('user', ImportProject(files=files + [{'path': 'extra.py', 'content': 'x=1'}]))
