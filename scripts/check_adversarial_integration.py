"""Real HTTP + Docker Stage 2 experiments; only model transport is deterministic."""
import json
from pathlib import Path
import time
from urllib import request


def main():
    root = Path(__file__).resolve().parents[1]
    base = "http://127.0.0.1:5173/api"

    def http(path, body=None):
        req = request.Request(base + path, data=json.dumps(body).encode() if body is not None else None,
                              headers={"Content-Type": "application/json"})
        with request.build_opener(request.ProxyHandler({})).open(req, timeout=10) as response:
            return json.load(response)

    cases = [
        ("E1", "fixed", "offline", "standard", "COMPLETED", "VERIFIED"),
        ("E1-executor", "fixed", "offline", "standard", "COMPLETED", "VERIFIED"),
        ("E2", "double_rounding", "offline", "standard", "COMPLETED", "FAILED"),
        ("E3", "fixed", "offline", "invalid", "INCOMPLETE", "INCONCLUSIVE"),
        ("E4-timeout", "fixed", "offline", "timeout", "GENERATION_FAILED", "INCONCLUSIVE"),
        ("E4-failure", "fixed", "offline", "failure", "GENERATION_FAILED", "INCONCLUSIVE"),
    ]
    if not http('/health')['modes']['live_executor']['enabled']:
        cases.append(("E4-unavailable", "fixed", "live", "standard", "UNAVAILABLE", "INCONCLUSIVE"))
    records = []
    for experiment, candidate, mode, profile, stage_status, final_status in cases:
        accepted = http('/runs', {"task_id": "billing-rounding-01", "mode": "offline_executor" if experiment == "E1-executor" else "fixture", "candidate_id": candidate,
                                   "adversarial_mode": mode, "adversarial_fixture": profile})
        deadline = time.monotonic() + 120
        while time.monotonic() < deadline:
            snapshot = http('/runs/' + accepted['run_id'])
            assert http('/health')['status'] == 'ok'
            if snapshot['state'] in ('COMPLETED', 'ERROR'):
                break
            time.sleep(0.2)
        else:
            raise AssertionError('Stage 2 experiment exceeded deadline')
        records.append({"experiment": experiment, "snapshot": snapshot})
        output = root / 'artifacts/adversarial-integration-results.json'
        output.write_text(json.dumps(records, indent=2, ensure_ascii=False), encoding='utf-8')
        assert snapshot['state'] == 'COMPLETED', snapshot['error']
        base_report, adversarial, final = snapshot['verification'], snapshot['adversarial_report'], snapshot['final_decision']
        assert base_report['status'] == 'VERIFIED', 'Existing formal acceptance must remain unchanged'
        assert adversarial['status'] == stage_status
        assert final['status'] == final_status
        assert final['formal_report_id'] == base_report['run_id']
        assert adversarial['artifact_hash'] == base_report['artifact_hash']
        for e in [*base_report['executions'], *([adversarial['execution']] if adversarial['execution'] else [])]:
            assert e['cleanup_confirmed'] and e['workspace_unchanged'] and e['limits_verified']
        if experiment in ('E1', 'E1-executor'):
            assert adversarial['confirmed_count'] == 0 and adversarial['valid_count'] == 2
        if experiment == 'E1-executor':
            assert snapshot['executor']['source'] == 'OFFLINE_TEST'
            assert snapshot['proposal'] is not None and adversarial['source'] == 'OFFLINE_TEST'
        if experiment == 'E2':
            confirmed = [row for row in adversarial['challenges'] if row['status'] == 'CONFIRMED']
            assert len(confirmed) == 2
            assert (confirmed[0]['challenge']['amount'], confirmed[0]['expected'], confirmed[0]['actual']) == ('1.00499', 100, 101)
            assert adversarial['execution']['exit_code'] == 1
        if experiment == 'E3':
            assert all(row['status'] == 'INVALID' for row in adversarial['challenges'])
            assert adversarial['execution'] is None
        print(f"{experiment}: formal={base_report['status']}, adversarial={adversarial['status']}, final={final['status']}", flush=True)
    print(f'Evidence: {output}')


if __name__ == '__main__':
    main()
