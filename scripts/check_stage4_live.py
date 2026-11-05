"""Explicitly approved live experiments; never substitutes fixtures for model output."""
import argparse
import json
import os
from pathlib import Path
import sys
import uuid
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from trustbound.inference import VultrClient, select_model, TaskInferenceBudget, task_inference_budget
from trustbound.web_tasks import execute_web_run, live_availability

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--phase', choices=['smoke', 'e2e'], default='smoke')
parser.add_argument('--allow-paid-inference', action='store_true')
args = parser.parse_args()
if not args.allow_paid_inference:
    print(json.dumps(live_availability()))
    raise SystemExit('Configuration only; explicit paid-request approval flag required.')
if args.phase != 'smoke' and not live_availability()['enabled']:
    raise SystemExit('Live configuration unavailable; no inference requested.')
output = ROOT / 'artifacts' / ('stage4-live-' + uuid.uuid4().hex + '.json')
if args.phase == 'smoke':
    budget = TaskInferenceBudget(max_requests=1, max_output_tokens=512)
    client = VultrClient(timeout=30, max_attempts=1)
    result = {'source': client.source, 'success': False, 'requested_model': 'deepseek-v4.1-flash-1017'}
    try:
        with task_inference_budget(budget):
            model = select_model(client.catalog(), 'deepseek-v4.1-flash-1017')
            text = client.complete(model, [{'role':'user','content':'Return only this JSON object: {"status":"READY"}'}],512,json_mode=True)
            from trustbound.executor import unique_object
            value = json.loads(text, object_pairs_hook=unique_object)
            result['json_valid'] = True
            result['ready_matches'] = value == {"status": "READY"}
            result['success'] = result['ready_matches']
            if not result['success']:
                result['error'] = 'UNEXPECTED_SMOKE_JSON'
            result['source'] = client.source
    except Exception as error:
        result['error'] = type(error).__name__ + ':' + str(error) if type(error).__name__ == 'InferenceError' else 'LIVE_TEST_ERROR'
    finally:
        result['inference_usage'] = budget.to_dict()
        output.write_text(json.dumps(result,indent=2),encoding='utf-8')
else:
    if os.environ.get('TRUSTBOUND_ENABLE_RECOVERY_LIVE') != '1':
        raise SystemExit('Separate live recovery opt-in required.')
    result = execute_web_run('billing-rounding-01','live_executor',None,'live',recovery_mode='live')
    output.write_text(json.dumps(result,indent=2),encoding='utf-8')
print(output)
