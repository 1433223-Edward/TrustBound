"""Single operator entry point. No arguments opens a menu; nothing runs automatically."""
import argparse
from datetime import datetime, timezone
import importlib.util
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parent


def invoke(filename,arguments):
    return subprocess.call([sys.executable,str(ROOT/filename),*arguments])


def main():
    p=argparse.ArgumentParser(__doc__)
    p.add_argument('action',nargs='?',choices=['prepare','A','B','C','D','E','check','analyze'])
    p.add_argument('--manifest',type=Path)
    p.add_argument('--execute',action='store_true')
    p.add_argument('--allow-paid-inference',action='store_true')
    p.add_argument('--out',type=Path)
    p.add_argument('--raw',type=Path,default=ROOT/'results/raw')
    p.add_argument('--report',type=Path,nargs='+')
    a=p.parse_args()
    if a.action is None:
        print('TrustBound frozen toolkit: prepare | A | B | C | D | E | check | analyze. F deferred.')
        action=input('Choose action (Enter exits): ').strip()
        if not action:return
        # The menu asks for an explicit execution decision; it never launches all experiments.
        arguments=[action]
        if action in 'BCDE' and len(action)==1:
            default=ROOT/'configs'/('D-off.json' if action=='D' else 'E-on.json' if action=='E' else action+'.json')
            arguments+=['--manifest',input('Manifest path (Enter uses '+str(default)+'): ').strip() or str(default)]
            if input('Submit ONE real task? type EXECUTE: ').strip()=='EXECUTE':
                arguments+=['--execute']
                if input('Permit paid inference if configured? type PAID: ').strip()=='PAID':arguments+=['--allow-paid-inference']
        return subprocess.call([sys.executable,str(Path(__file__).resolve()),*arguments])
    out=a.out or ROOT/'results/processed'/datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    if a.action=='prepare':
        return invoke('prepare_scale.py',['--out',str(a.out or ROOT/'datasets/generated-v2')])
    if a.action in ('B','C','D','E'):
        if not a.manifest:p.error('--manifest required')
        flags=['--execute'] if a.execute else []
        if a.allow_paid_inference:flags+=['--allow-paid-inference']
        return invoke('run_workspace.py',[a.action,'--manifest',str(a.manifest),*flags])
    if a.action=='A':
        if a.execute:
            raise SystemExit('A is VM operator-only: follow security/BENCHMARK_RUNBOOK.md; this launcher never starts local attack probes.')
        if not a.report:
            print((ROOT/'security/BENCHMARK_RUNBOOK.md').read_text(encoding='utf-8-sig'));return
        return invoke('security/analyze.py',[*[str(x) for x in a.report],'--out',str(out)])
    if a.action=='check':
        from integrity import verify
        directories=list(a.raw.glob('*/record.json'))
        if not directories:raise SystemExit('No raw records found')
        for path in directories:verify(path.parent);print('OK',path.parent)
        return
    if a.action=='analyze':return invoke('analyze.py',['--raw',str(a.raw),'--out',str(out)])


if __name__=='__main__':sys.exit(main())
