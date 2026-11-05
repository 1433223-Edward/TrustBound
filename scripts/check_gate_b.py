"""Gate B only: one live Executor proposal, existing verifier, no adversary/recovery."""
import argparse
import json
from pathlib import Path
import sys
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from trustbound.inference import VultrClient, TaskInferenceBudget, task_inference_budget
from trustbound.executor import run_executor

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--allow-paid-inference', action='store_true')
args = parser.parse_args()
client = VultrClient(timeout=60, max_attempts=1, output_limit=2048)
if not args.allow_paid_inference:
    print(json.dumps({'key_configured': client.configured, 'model': 'deepseek-v4.1-flash-1017',
        'max_completion_tokens': 2048, 'max_generation_requests': 1, 'request_timeout_seconds': 60,
        'smoke_check': False, 'adversarial': False, 'recovery': False}))
    raise SystemExit(0)
budget = TaskInferenceBudget(max_requests=1, max_output_tokens=2048)
with task_inference_budget(budget):
    # Reuse all schema, AST, permission and Docker checks; omit the extra smoke call.
    result = run_executor(client, model_id='deepseek-v4.1-flash-1017', smoke_check=False, proposal_tokens=2048)
result['inference_usage'] = budget.to_dict()
result['gate'] = 'B'
output = ROOT / 'artifacts' / ('gate-b-' + uuid.uuid4().hex + '.json')
output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
print('Executor status:', result['status'])
print('Report:', output)
