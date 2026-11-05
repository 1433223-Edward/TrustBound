"""Gate D: one separately authorized repair, known-case replay, fresh review pending."""
import argparse
import json
import os
from pathlib import Path
import sys
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from trustbound.adversarial import REQUIREMENT_ID, run_adversarial, final_decision
from trustbound.adversarial_contracts import AdversarialReport
from trustbound.inference import VultrClient, TaskInferenceBudget, task_inference_budget
from trustbound.recovery import run_recovery, recovery_eligibility, build_recovery_context
from trustbound.runner import sha256
from trustbound.service import TASK, verify_patch

EVIDENCE = ROOT / 'artifacts/gate-c-0021d4ee71e74a2eb82499da86d5de9a.json'


def initial_outcome():
    proof = json.loads(EVIDENCE.read_text(encoding='utf-8'))
    code = (ROOT / 'fixtures/billing/double_rounding.py').read_bytes().decode('utf-8')
    if sha256(code.encode()) != proof['artifact_hash']:
        raise ValueError('Gate C artifact changed')
    return {'candidate': {'path':'billing.py', 'content':code, 'source':'GATE_C_ARTIFACT'},
            'verification':proof['verification'], 'adversarial_report':proof['adversarial_report'],
            'final_decision':proof['final_decision'], 'proposal':None, 'executor':None,
            'llm_source':'NONE', 'error':None}


class ConfirmedChallengeReplay:
    """Data adapter for the existing validator, never a model or network transport.

    Only confirmed Gate C inputs are replayed. Oracle outputs are recomputed by
    the host; no model request or fresh adversarial discovery is claimed.
    """
    configured, source, timeout, max_attempts = True, 'TRUSTED_GATE_C_REPLAY', 3, 1

    def __init__(self, failures):
        self.failures, self.calls = failures, []

    def catalog(self):
        return {'data':[{'id':'trusted-replay', 'architecture':{'output_modalities':['text']}}]}

    def complete(self, model, messages, max_tokens, **options):
        return json.dumps({'challenges':[{'amount':f['amount'], 'requirement_id':REQUIREMENT_ID,
            'reason':'Replay a confirmed Gate C input'} for f in self.failures]})


def verify_repair(proposal, failures):
    # Controller already enforces JSON/AST; this is the unchanged formal service.
    verification = verify_patch(TASK.task_id, proposal['files']).to_dict()
    code = proposal['files'].get('billing.py', (ROOT / 'fixtures/billing/original.py').read_bytes().decode())
    outcome = {'candidate':{'path':'billing.py','content':code,'source':'LIVE_RECOVERY'},
               'proposal':proposal, 'verification':verification, 'executor':None,
               'llm_source':'VULTR_LIVE_HTTP', 'error':None}
    replay = None
    if verification['status'] == 'VERIFIED':
        replay = run_adversarial(code.encode(), verification['artifact_hash'], ConfirmedChallengeReplay(failures), model_id='trusted-replay')
    outcome['gate_c_replay_report'] = replay.to_dict() if replay else None
    if replay and any(row.status == 'CONFIRMED' for row in replay.challenges):
        adversarial = replay
    else:
        # Passing known inputs never substitutes for a fresh independent review.
        adversarial = AdversarialReport(TASK.task_id, verification['artifact_hash'],
            'UNAVAILABLE' if verification['status'] == 'VERIFIED' else 'SKIPPED', 'NO_LIVE_CALL',
            'FRESH_ADVERSARIAL_REQUIRES_SEPARATE_AUTHORIZATION', {})
    outcome['adversarial_report'] = adversarial.to_dict()
    outcome['final_decision'] = final_decision(verification, adversarial)
    return outcome


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--allow-paid-inference', action='store_true')
    args = parser.parse_args()
    initial = initial_outcome()
    trigger, failures, problem = recovery_eligibility(initial)
    if problem or not failures:
        raise SystemExit('Gate C evidence is not eligible; no model request made.')
    context = build_recovery_context(initial, failures, 0)
    if os.environ.get("VULTR_MODEL") != "deepseek-v4.1-flash-1017":
        raise SystemExit("Configured model differs from authorized model; no request made.")
    client = VultrClient(timeout=60, max_attempts=1, output_limit=4096)
    if not args.allow_paid_inference:
        print(json.dumps({'eligible':True,'trigger':trigger,'confirmed_inputs':[f['amount'] for f in failures],
            'candidate_hash':initial['verification']['artifact_hash'], 'key_configured':client.configured,
            'model':'deepseek-v4.1-flash-1017','max_requests':1,'max_recovery_attempts':1,
            'max_completion_tokens':4096,'reasoning_max_tokens':1024,'timeout_seconds':60,'max_attempts':1,
            'remaining_after_request':context['remaining_recovery_attempts'], 'fresh_adversarial':'NOT_AUTHORIZED'}))
        return
    if not client.configured:
        raise SystemExit('Key unavailable; no model request made.')
    budget = TaskInferenceBudget(max_requests=1, max_output_tokens=4096)
    with task_inference_budget(budget):
        result = run_recovery(initial, lambda proposal: verify_repair(proposal, failures), lambda _:client,
            max_attempts=1, completion_tokens=4096, reasoning_tokens=1024)
    result['inference_usage'] = budget.to_dict()
    result['parent_evidence'] = EVIDENCE.name
    output = ROOT / 'artifacts' / ('gate-d-' + uuid.uuid4().hex + '.json')
    output.write_text(json.dumps(result,indent=2),encoding='utf-8')
    print('Recovery:', result['recovery_report']['final_status'], 'Stop:',result['recovery_report']['stop_reason'])
    print('Report:', output)


if __name__ == '__main__':
    main()
