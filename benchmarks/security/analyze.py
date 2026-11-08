"""Offline A1-A5 report aggregation. Never imports the application or runs probes."""
import argparse
import csv
import hashlib
import json
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument('reports', nargs='+', type=Path)
    parser.add_argument('--out', required=True, type=Path)
    args = parser.parse_args()
    records, seen = [], set()
    for path in args.reports:
        raw = path.read_bytes()
        report = json.loads(raw)
        if report.get('suite') != 'trustbound-security-a1-a5' or report.get('source') != 'REAL_ROOTLESS_DOCKER':
            raise ValueError(f'{path}: expected original Rootless attack-suite report; offline/replay rejected')
        key = report['run_id']
        if key in seen:
            raise ValueError(f'Duplicate run_id: {key}')
        seen.add(key)
        indexed = {(r['case_id'], r['layer']): r for r in report['results']}
        for case in ('A1', 'A2', 'A3', 'A4', 'A5'):
            row = indexed.get((case, 'SANDBOX_RUNTIME'), {})
            execution = row.get('execution', {})
            status = row.get('status', 'MISSING')
            if status not in ('PASS', 'FAIL', 'INCONCLUSIVE', 'MISSING'):
                raise ValueError(f'{path}: invalid status')
            if status == 'PASS' and not all(execution.get(k) is True for k in ('limits_verified', 'cleanup_confirmed', 'workspace_unchanged')):
                raise ValueError(f'{path}: PASS lacks execution evidence')
            records.append(dict(run_id=key, case=case, status=status,
                                cleanup=execution.get('cleanup_confirmed'),
                                source_commit=report.get('release_commit'),
                                timestamp=report.get('timestamp_utc'),
                                evidence=str(path), sha256=hashlib.sha256(raw).hexdigest()))
    args.out.mkdir(parents=True, exist_ok=False)
    with (args.out / 'records.csv').open('x', newline='', encoding='utf-8') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(records[0]))
        writer.writeheader()
        writer.writerows(records)
    summary = []
    for case in ('A1', 'A2', 'A3', 'A4', 'A5'):
        rows = [r for r in records if r['case'] == case]
        passed = sum(r['status'] == 'PASS' for r in rows)
        failed = sum(r['status'] == 'FAIL' for r in rows)
        summary.append(dict(case=case, planned=len(rows), passed=passed, failed=failed,
                            unknown=len(rows)-passed-failed,
                            containment_rate=passed/(passed+failed) if passed+failed else None))
    (args.out / 'summary.json').write_text(json.dumps(summary, indent=2), encoding='utf-8')
    # SVG is dependency-free; no simulated observations or interpolated missing data.
    cells = []
    for i, row in enumerate(summary):
        value = row['containment_rate']
        label = 'N/A' if value is None else f'{value:.1%}'
        cells.append(f'<text x="20" y="{80+i*55}">{row["case"]}: {label}; n={row["passed"]+row["failed"]}, unknown={row["unknown"]} (exploratory)</text>')
    svg = '<svg xmlns="http://www.w3.org/2000/svg" width="850" height="420"><rect width="100%" height="100%" fill="white"/><g font-family="sans-serif" font-size="18"><text x="20" y="30">Security containment / A1-A5 / REAL_ROOTLESS_DOCKER / v1</text>' + ''.join(cells) + '<text x="20" y="390">Source: records.csv; rates exclude unknown; no control-group claim</text></g></svg>'
    (args.out / 'security.svg').write_text(svg, encoding='utf-8')
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import numpy as np
    values = np.array([[r['containment_rate'] if r['containment_rate'] is not None else np.nan for r in summary]])
    fig, ax = plt.subplots(figsize=(10, 4))
    ax.imshow(np.ma.masked_invalid(values), vmin=0, vmax=1, cmap='RdYlGn', aspect='auto')
    ax.set_xticks(range(5), [r['case'] for r in summary])
    ax.set_yticks([0], ['Runtime containment'])
    ax.set(xlabel='Existing attack case', ylabel='PASS / (PASS + FAIL)', title='Security observed containment — exploratory v2')
    for i, r in enumerate(summary):
        ax.text(i, 0, f"n={r['passed']+r['failed']} unknown={r['unknown']}", ha='center', fontsize=8)
    fig.text(.01, .01, 'Source: records.csv; A1/A2 Process, A3 Secret, A4/A5 Resource; cleanup recorded separately', fontsize=8)
    fig.tight_layout(rect=(0,.07,1,1))
    fig.savefig(args.out/'security.png', dpi=150)
    fig.savefig(args.out/'security-heatmap.svg')
    plt.close(fig)
    (args.out/'index.html').write_text('<html><meta charset="utf-8"><h1>Security observed evidence</h1><img src="security-heatmap.svg"><p>Exploratory; missing cases are not passes. See records.csv and summary.json.</p></html>', encoding='utf-8')


if __name__ == '__main__':
    main()
