"""Final independent review of the Gate D artifact; no further recovery."""
import argparse
from copy import deepcopy
import json
from pathlib import Path
import sys
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from trustbound.adversarial import build_context, build_messages, reference_cents, run_adversarial, final_decision
from trustbound.inference import VultrClient, TaskInferenceBudget, task_inference_budget
from trustbound.recovery import formal_evidence_problem, intact_execution, complete_success
from trustbound.runner import sha256

PARENT = ROOT / 'artifacts/gate-d-31e9eb19bc60432fac260d96b6a092aa.json'
ARTIFACT = '69226f0e9244d6dfedde7d8c2a9a5f3a1e5091b1f569ebe5053bc9817d088eb8'


def validate_parent(parent):
    """Accept only the recovered version with intact formal and replay observations."""
    attempt = deepcopy(parent['recovery_report']['attempts'][-1])
    code = attempt['candidate']['content'].encode('utf-8')
    if attempt['verification']['status'] != 'VERIFIED' or attempt['candidate_hash'] != ARTIFACT or sha256(code) != ARTIFACT or formal_evidence_problem(attempt):
        raise ValueError('Candidate/formal evidence mismatch')
    replay = attempt['gate_c_replay_report']
    e = replay['execution']
    if (replay['artifact_hash'] != ARTIFACT or replay['status'] != 'COMPLETED'
            or not intact_execution(e, ARTIFACT) or e['exit_code'] != 0
            or e['phase'] != 'adversarial' or e['test_hash'] != replay['driver_hash']):
        raise ValueError('Replay evidence incomplete')
    observed = json.loads(e['stdout'])['results']
    valid = [row for row in replay['challenges'] if row['status'] != 'INVALID']
    if not valid or len(observed) != len(valid):
        raise ValueError('No matching replay observations')
    for row, actual in zip(valid, observed):
        c = row['challenge']
        if (row['status'] != 'NOT_CONFIRMED' or row['actual_type'] != 'int'
                or type(row['actual']) is not int or row['actual'] != row['expected']
                or row['expected'] != reference_cents(c['amount'])
                or actual != {'id':c['challenge_id'], 'amount':c['amount'], 'actual':row['actual'], 'actual_type':'int'}):
            raise ValueError('Replay observations contradict reference')
    return attempt, code


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--allow-paid-inference', action='store_true')
    args = parser.parse_args()
    attempt, code = validate_parent(json.loads(PARENT.read_text(encoding='utf-8')))
    context = build_context(code, ARTIFACT)
    messages = build_messages(context, compact=True)
    # Only the allowlisted context reaches the model; history/replay stay host-side.
    for row in attempt['gate_c_replay_report']['challenges']:
        assert row['challenge']['amount'] not in json.dumps(messages)
    client = VultrClient(timeout=60, max_attempts=1, output_limit=4096)
    if not args.allow_paid_inference:
        print(json.dumps({'candidate_hash':ARTIFACT, 'formal_and_replay_intact':True,
            'key_configured':client.configured, 'model':'deepseek-v4.1-flash-1017',
            'max_requests':1, 'max_completion_tokens':4096, 'reasoning_max_tokens':1024,
            'max_challenges':3, 'max_attempts':1, 'timeout_seconds':60, 'recovery':False,
            'context_fields':list(context)}))
        return
    if not client.configured:
        raise SystemExit('Key unavailable; no model request made.')
    budget = TaskInferenceBudget(max_requests=1, max_output_tokens=4096)
    with task_inference_budget(budget):
        report = run_adversarial(code, ARTIFACT, client, model_id='deepseek-v4.1-flash-1017',
                                 completion_tokens=4096, compact=True)
    decision = final_decision(attempt['verification'], report)
    checked = {**attempt, 'adversarial_report':report.to_dict(), 'final_decision':decision}
    if decision['status'] == 'VERIFIED' and not complete_success(checked):
        decision = {**decision, 'status':'INCONCLUSIVE', 'reason':'INCOMPLETE_FINAL_EVIDENCE'}
    result = {'gate':'D_FINAL', 'parent_report':PARENT.name, 'candidate_hash':ARTIFACT,
        'verification':attempt['verification'], 'gate_c_replay_report':attempt['gate_c_replay_report'],
        'adversarial_report':report.to_dict(), 'final_decision':decision, 'inference_usage':budget.to_dict(),
        'stop_reason':decision['status'] if report.status == 'COMPLETED' else report.reason}
    output = ROOT / 'artifacts' / ('gate-d-final-' + uuid.uuid4().hex + '.json')
    output.write_text(json.dumps(result,indent=2),encoding='utf-8')
    print('Final:', decision['status'], 'Report:', output)


if __name__ == '__main__':
    main()
