"""Prepare or submit ONE Workspace benchmark run; analysis is in a separate module."""
import argparse
import csv
from datetime import datetime, timezone
import hashlib
import re
from urllib.error import HTTPError
import json
import os
from pathlib import Path
import time
import uuid
from urllib.request import Request, build_opener, ProxyHandler

ROOT = Path(__file__).resolve().parents[1]


def main():
    p = argparse.ArgumentParser(__doc__)
    p.add_argument('experiment', choices=list('BCDE'))
    p.add_argument('--manifest', required=True, type=Path)
    p.add_argument('--execute', action='store_true')
    p.add_argument('--allow-paid-inference', action='store_true')
    a = p.parse_args()
    cfg = json.loads(a.manifest.read_text(encoding='utf-8-sig'))
    if cfg['experiment_type'] != a.experiment:
        raise SystemExit('Experiment mismatch')
    if a.experiment == 'F':
        raise SystemExit('BLOCKED: existing scheduler supports one active task')
    body = dict(cfg['request'])
    if a.experiment == 'D' and (body.get('mode') != 'fixture' or body.get('recovery_mode', 'off') != 'off' or body.get('candidate_id') not in ('fixed', 'double_rounding')):
        raise SystemExit('D requires a fixed formally acceptable candidate and recovery OFF')
    if a.experiment == 'C' and cfg.get('file_count') not in (1, 5, 10, 20):
        raise SystemExit('C requires file_count 1/5/10/20')
    if a.experiment == 'E' and (body.get('mode') != 'original' or body.get('adversarial_enabled')):
        raise SystemExit('E uses fixed original source, adversarial OFF')
    if body.get('mode') == 'live' and not body.get('model_id'):
        raise SystemExit('Fill and confirm model_id; no default model is selected by toolkit')
    if not a.execute:
        print(json.dumps({'configuration_only': True, 'manifest': cfg}, indent=2))
        return
    if (body.get('mode') == 'live' or body.get('adversarial_mode') == 'live') and not a.allow_paid_inference:
        raise SystemExit('Live requires --allow-paid-inference')
    if not cfg.get('source_commit') or not cfg.get('source_hash') or (a.experiment != 'D' and not cfg.get('project_id')):
        raise SystemExit('Fill source_commit/source_hash/project_id before execution')
    if not re.fullmatch(r'[0-9a-f]{40}', cfg['source_commit']) or not re.fullmatch(r'[0-9a-f]{64}', cfg['source_hash']):
        raise SystemExit('Expected actual 40-hex release commit and 64-hex source hash')
    run = uuid.uuid4().hex
    out = ROOT / 'benchmarks/results/raw' / run
    out.mkdir(parents=True, exist_ok=False)
    (out / 'manifest.json').write_text(json.dumps(cfg, indent=2), encoding='utf-8')
    headers = {'Content-Type': 'application/json'}
    token = os.environ.get('TRUSTBOUND_WORKSPACE_TOKEN')
    if token:
        headers['Authorization'] = 'Bearer ' + token
    http = build_opener(ProxyHandler({}))
    base = cfg.get('base_url', 'http://127.0.0.1:5173').rstrip('/')
    if not base.startswith(('http://127.0.0.1:', 'http://localhost:')):
        raise SystemExit('Use localhost or SSH tunnel; remote credential transport disabled')
    def request(route, payload=None):
        req = Request(base + route, headers=headers, data=None if payload is None else json.dumps(payload).encode())
        try:
            with http.open(req, timeout=20) as response:
                return json.load(response)
        except HTTPError as error:
            raw = error.read(65536)
            try:
                detail = json.loads(raw).get('detail', {})
                code = detail.get('code') if isinstance(detail, dict) else None
            except (ValueError, AttributeError):
                code = None
            (out / ('http-error-' + str(time.monotonic_ns()) + '.json')).write_text(json.dumps({'http_status': error.code, 'code': code}), encoding='utf-8')
            raise
    started = datetime.now(timezone.utc).isoformat()
    tick = time.monotonic()
    status, failure, result = 'INCOMPLETE', None, None
    try:
        health = request('/api/health')
        (out / 'health.json').write_text(json.dumps(health), encoding='utf-8')
        if health.get('active_run_id') is not None:
            raise ValueError('Service busy; do not bypass admission')
        if a.experiment != 'D':
            project = request('/api/workspace/projects/' + cfg['project_id'])
            (out / 'project.json').write_text(json.dumps(project), encoding='utf-8')
            if project.get('snapshot_hash') != cfg['source_hash'] or project.get('revision') != body.get('revision'):
                raise ValueError('Frozen source hash or revision mismatch')
        route = '/api/runs' if a.experiment == 'D' else '/api/workspace/projects/' + cfg['project_id'] + '/runs'
        if a.experiment != 'D':
            body['idempotency_key'] = run
        accepted = request(route, body)
        (out / 'accepted.json').write_text(json.dumps(accepted), encoding='utf-8')
        while time.monotonic() - tick < cfg.get('poll_deadline_seconds', 300):
            result = request(route + '/' + accepted['run_id'])
            (out / ('poll-' + str(time.monotonic_ns()) + '.json')).write_text(json.dumps(result), encoding='utf-8')
            if result['state'] not in ('QUEUED', 'RUNNING'):
                status = result['state']
                break
            time.sleep(1)
        else:
            status = 'CLIENT_POLL_TIMEOUT'
    except (Exception, KeyboardInterrupt) as error:
        failure = type(error).__name__  # Do not export credentials or arbitrary provider messages.
    finally:
        report = ((result or {}).get('workspace_report') or {}) if a.experiment != 'D' else (result or {})
        if a.experiment == 'D' and status == 'COMPLETED' and (report.get('verification') or {}).get('artifact_hash') != cfg['source_hash']:
            status, failure = 'EVIDENCE_IDENTITY_MISMATCH', 'Fixed candidate hash differs from manifest'
        usage = report.get('inference_usage') or {}
        no_model = body.get('mode') != 'live' and body.get('adversarial_mode', 'off') != 'live'
        known_no_model = no_model and status == 'COMPLETED'
        models = sorted({c['response_model'] for c in usage.get('calls', []) if c.get('response_model')})
        record = dict(experiment_id=cfg['experiment_id'], experiment_type=a.experiment,
                      run_id=run, dataset_version=cfg['dataset_version'], source_commit=cfg['source_commit'],
                      source_hash=cfg['source_hash'], configuration=cfg, actual_model_id=models or None,
                      started_at=started, completed_at=datetime.now(timezone.utc).isoformat(),
                      input_tokens=usage.get('prompt_tokens'), output_tokens=usage.get('completion_tokens'),
                      estimated_cost='0' if known_no_model else usage.get('estimated_usd'), latency_ms=(time.monotonic()-tick)*1000,
                      execution_status=status, verification_status=(report.get('final_decision') or {}).get('status') if a.experiment == 'D' else report.get('status'),
                      security_status=(report.get('security_evidence') or {}).get('status'),
                      evidence_reference=str(out), failure_reason=failure,
                      formal_verification_status=(report.get('verification') or {}).get('status') if a.experiment == 'D' else report.get('formal_status'),
                      model_request_latency_ms=None, phase_timings={'server_started_at': (result or {}).get('started_at'), 'server_finished_at': (result or {}).get('finished_at')}, cpu_peak=None, memory_peak=None, pid_peak=None,
                      evidence_source='LIVE_MODEL_DOCKER' if (body.get('mode') == 'live' or body.get('adversarial_mode') == 'live') else 'OFFLINE_MODEL_DOCKER',
                      report=report)
        (out / 'record.json').write_text(json.dumps(record, indent=2), encoding='utf-8')
        with (out / 'record.csv').open('x', newline='', encoding='utf-8') as stream:
            columns = [k for k in record if k not in ('report', 'configuration')]
            writer = csv.DictWriter(stream, fieldnames=columns, extrasaction='ignore')
            writer.writeheader()
            writer.writerow(record)
        from integrity import seal
        seal(out)
        print(out)
    if status != 'COMPLETED':
        raise SystemExit('Incomplete: server task may still run; inspect accepted.json and service before retry')


if __name__ == '__main__':
    main()

