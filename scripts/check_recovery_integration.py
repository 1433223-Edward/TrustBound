"""Real local HTTP/Docker recovery experiments; all model responses are explicitly offline."""
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

    cases = [("R1", "double_rounding", "fixed", "standard", "VERIFIED", "VERIFIED", 2),
             ("R1-business", "original", "fixed", "standard", "VERIFIED", "VERIFIED", 2),
             ("R2", "double_rounding", "exhausted", "standard", "FAILED", "RECOVERY_LIMIT_REACHED", 3),
             ("R3", "double_rounding", "unauthorized", "standard", "REJECTED", "FORMAL_REJECTED", 2),
             ("R4", "fixed", "fixed", "invalid", "INCONCLUSIVE", "EVIDENCE_INCONCLUSIVE", 1),
             ("R5-json", "double_rounding", "invalid_json", "standard", "INCONCLUSIVE", "INVALID_RECOVERY_PROPOSAL:INVALID_JSON", 2),
             ("R5-empty", "double_rounding", "empty", "standard", "INCONCLUSIVE", "RECOVERY_MODEL_ERROR:INVALID_RESPONSE", 2),
             ("R5-failure", "double_rounding", "failure", "standard", "INCONCLUSIVE", "RECOVERY_MODEL_ERROR:API_FAILURE_BILLING_UNKNOWN", 2),
             ("R5-timeout", "double_rounding", "timeout", "standard", "INCONCLUSIVE", "RECOVERY_MODEL_ERROR:TIMEOUT_BILLING_UNKNOWN", 2),
             ("R-stop-timeout", "timeout", "fixed", "standard", "FAILED", "UNSAFE_OR_INCOMPLETE_EXECUTION", 1)]
    records = []
    for label, candidate, profile, adversary, status, stop, count in cases:
        accepted = http('/runs', {"task_id": "billing-rounding-01", "mode": "fixture", "candidate_id": candidate,
            "adversarial_mode": "offline", "adversarial_fixture": adversary,
            "recovery_mode": "offline", "recovery_fixture": profile})
        deadline = time.monotonic() + 180
        seen_attempts = set()
        while time.monotonic() < deadline:
            s = http('/runs/' + accepted['run_id'])
            assert http('/health')['status'] == 'ok'
            seen_attempts.add(s.get('current_attempt'))
            if s['state'] in ('COMPLETED', 'ERROR'):
                break
            time.sleep(.2)
        else:
            raise AssertionError('Recovery deadline exceeded')
        records.append({"experiment": label, "observed_attempts": sorted(x for x in seen_attempts if x is not None), "snapshot": s})
        output = root / 'artifacts/recovery-integration-results.json'
        output.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding='utf-8')
        assert s['state'] == 'COMPLETED', s.get('error')
        r = s['recovery_report']
        assert r['run_id'] == s['run_id'] and r['max_attempts'] == 2
        assert (r['final_status'], r['stop_reason'], len(r['attempts'])) == (status, stop, count), r
        for i, attempt in enumerate(r['attempts']):
            assert attempt['attempt_index'] == i and attempt['run_id'] == s['run_id']
            assert attempt['previous_candidate_hash'] == (r['attempts'][i - 1]['candidate_hash'] if i else None)
            if not attempt['verification']:
                assert attempt['adversarial_report'] is None and attempt['final_decision']['status'] != 'VERIFIED'
                continue
            evidence = attempt['verification']['executions'][:]
            for key in ('adversarial_report', 'diagnostic_report'):
                if attempt.get(key) and attempt[key].get('execution'):
                    evidence.append(attempt[key]['execution'])
            for e in evidence:
                assert e['artifact_hash'] == attempt['candidate_hash']
                assert e['cleanup_confirmed'] and e['workspace_unchanged'] and e['limits_verified']
        if label.startswith('R1'):
            first, last = r['attempts']
            assert first['final_decision']['status'] == 'FAILED' and last['final_decision']['status'] == 'VERIFIED'
            assert first['candidate_hash'] != last['candidate_hash']
            assert [e['phase'] for e in last['verification']['executions']] == ['public', 'acceptance']
            assert last['adversarial_report']['status'] == 'COMPLETED' and last['adversarial_report']['confirmed_count'] == 0
        if label == 'R2':
            assert len({a['candidate_hash'] for a in r['attempts']}) == 3
        if label == 'R3':
            assert r['attempts'][-1]['verification']['executions'] == []
        print(f"{label}: attempts={count}, final={status}, stop={stop}", flush=True)
    print(f'Evidence: {output}')


if __name__ == '__main__':
    main()
