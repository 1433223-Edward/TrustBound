"""Gate C only: one independent live challenge generation; no recovery or answers."""
import argparse
import json
from pathlib import Path
import sys
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from trustbound.adversarial import build_context, build_messages, run_adversarial, final_decision
from trustbound.inference import VultrClient, TaskInferenceBudget, task_inference_budget
from trustbound.runner import sha256
from trustbound.service import TASK, run_task

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--allow-paid-inference', action='store_true')
parser.add_argument('--retest', action='store_true')
args = parser.parse_args()
output_tokens = 4096 if args.retest else 2048
code = (ROOT / 'fixtures/billing/double_rounding.py').read_bytes()
artifact = sha256(code)
client = VultrClient(timeout=60, max_attempts=1, output_limit=output_tokens)
messages = build_messages(build_context(code, artifact), compact=args.retest)
# Guard against accidental reuse of the previous answer-bearing template.
assert '1.00499' not in json.dumps(messages)
if not args.allow_paid_inference:
    print(json.dumps({'key_configured':client.configured, 'model':'deepseek-v4.1-flash-1017',
        'max_completion_tokens':output_tokens, 'max_requests':1, 'timeout_seconds':60, 'max_attempts':1,
        'max_challenges':3 if args.retest else 4, 'reasoning_max_tokens':1024 if args.retest else None, 'response_format':'json_schema' if args.retest else 'json_object', 'known_answer_in_context':False, 'artifact_hash':artifact, 'recovery':False}))
    raise SystemExit(0)
if not client.configured:
    raise SystemExit('Key unavailable; no inference requested.')
output = ROOT / 'artifacts' / ('gate-c-' + uuid.uuid4().hex + '.json')
verification = run_task(TASK.task_id, 'double_rounding').to_dict()
result = {'gate':'C', 'retest':args.retest, 'verification':verification, 'artifact_hash':artifact}
output.write_text(json.dumps(result,indent=2),encoding='utf-8')
if verification['status'] != 'VERIFIED' or verification['artifact_hash'] != artifact:
    raise SystemExit('Formal acceptance or artifact check failed; no inference requested.')
budget = TaskInferenceBudget(max_requests=1, max_output_tokens=output_tokens)
with task_inference_budget(budget):
    report = run_adversarial(code, artifact, client, model_id='deepseek-v4.1-flash-1017', completion_tokens=output_tokens, compact=args.retest)
result.update(adversarial_report=report.to_dict(), final_decision=final_decision(verification,report),
              inference_usage=budget.to_dict())
output.write_text(json.dumps(result,indent=2),encoding='utf-8')
print('Adversarial stage:', report.status, 'Final:', result['final_decision']['status'])
print('Report:', output)
