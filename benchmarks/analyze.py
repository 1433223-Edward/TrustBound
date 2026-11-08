"""Offline statistics and PNG/SVG/HTML, strictly separate from experiment submission."""
import argparse
from collections import Counter
import csv
import html
import json
from pathlib import Path
import statistics
from integrity import verify


def summarize(rows):
    groups={}
    for row in rows:
        cfg=row['configuration']
        # Keep treatment, source snapshot, verification mode and model request separate.
        key=json.dumps([row['experiment_type'],row['evidence_source'],row['actual_model_id'],cfg.get('group'),row['source_commit'],row['source_hash'],cfg.get('dataset_version'),cfg.get('file_count'),cfg.get('request',{}).get('correctness_verification'),cfg.get('request',{}).get('model_id')],sort_keys=True)
        groups.setdefault(key,[]).append(row)
    output=[]
    for key,rs in groups.items():
        done=[r for r in rs if r['execution_status']=='COMPLETED']
        verified=sum(r.get('verification_status')=='VERIFIED' for r in done)
        lat=[r['latency_ms'] for r in done if r.get('latency_ms') is not None]
        costs=[float(r['estimated_cost']) for r in rs if r.get('estimated_cost') is not None]
        count=len(rs)
        output.append(dict(label=key,n=count,completed=len(done),execution_counts=dict(Counter(r['execution_status'] for r in rs)),verification_counts=dict(Counter(str(r.get('verification_status')) for r in rs)),unknown_billing=sum(r.get('estimated_cost') is None for r in rs),missing_models=sum(not r.get('actual_model_id') for r in rs),verified=verified,success=verified/len(done) if done else None,latency=statistics.mean(lat) if lat else None,latency_sd=statistics.stdev(lat) if len(lat)>1 else None,cost=statistics.mean(costs) if len(costs)==count else None,cost_per_verified=sum(costs)/verified if len(costs)==count and verified else None))
    return output


def paired(rows):
    buckets={}
    for row in rows:
        cfg=row['configuration']
        if row['experiment_type'] not in ('D','E') or not cfg.get('pair_id'):continue
        buckets.setdefault((row['experiment_type'],cfg['pair_id']),[]).append(row)
    output=[]
    for (kind,pair_id),rs in buckets.items():
        result=dict(experiment=kind,pair_id=pair_id,status='INVALID_PAIR',reason=None)
        off=[r for r in rs if r['configuration'].get('group')=='off']
        on=[r for r in rs if r['configuration'].get('group')=='on']
        if len(off)!=1 or len(on)!=1:
            result['reason']='Need exactly one OFF and one ON per pair_id'
        else:
            x,y=off[0],on[0]
            def foundation(r):
                cfg=r['configuration']; rep=r.get('report',{});v=rep.get('verification') or {}
                return (r['source_commit'],r['source_hash'],r['dataset_version'],v.get('artifact_hash') if kind=='D' else rep.get('snapshot_hash'),v.get('acceptance_hash') if kind=='D' else rep.get('frozen_hash'),cfg.get('request',{}).get('candidate_id'))
            match=foundation(x)==foundation(y) and all(r['execution_status']=='COMPLETED' for r in (x,y))
            if kind=='D':
                vx=x.get('report',{}).get('verification') or {};vy=y.get('report',{}).get('verification') or {}
                match=match and bool(vx.get('artifact_hash') and vx.get('acceptance_hash')) and vx.get('artifact_hash')==vy.get('artifact_hash')
            if not match:result['reason']='Incomplete or mismatched source/candidate/acceptance evidence'
            else:
                result.update(status='MATCHED',reason='Fixed candidate, no recovery; observations limited to this pair',latency_delta_ms=y['latency_ms']-x['latency_ms'],cost_delta_usd=float(y['estimated_cost'])-float(x['estimated_cost']) if y.get('estimated_cost') is not None and x.get('estimated_cost') is not None else None)
                if kind=='D':
                    adv=y.get('report',{}).get('adversarial_report') or {}
                    execution=adv.get('execution') or {}
                    trustworthy=adv.get('status') == 'COMPLETED' and execution.get('test_hash') == adv.get('driver_hash') and bool(adv.get('driver_hash')) and execution.get('status') == 'EXITED' and execution.get('exit_code') in (0, 1) and all(execution.get(k) is True for k in ('cleanup_confirmed','workspace_unchanged','limits_verified')) and execution.get('artifact_hash')==(y.get('report',{}).get('verification') or {}).get('artifact_hash')
                    challenges=adv.get('challenges',[])
                    result['confirmed_findings']=sum(c.get('status')=='CONFIRMED' for c in challenges) if trustworthy else None
                    result['non_confirmed']=sum(c.get('status')=='NOT_CONFIRMED' for c in challenges) if trustworthy else None
                    result['comparison_valid']=trustworthy and all(r.get('estimated_cost') is not None for r in (x,y)) and bool(y.get('actual_model_id'))
                    result['final_verified_delta']=int(y.get('verification_status')=='VERIFIED')-int(x.get('verification_status')=='VERIFIED')
                    if not result['comparison_valid']:result['reason']='Missing trusted counterexample execution/model/cost; no valid D efficacy comparison'
        output.append(result)
    return output


def main():
    p=argparse.ArgumentParser(__doc__)
    p.add_argument('--raw',type=Path,default=Path('benchmarks/results/raw'))
    p.add_argument('--out',type=Path,required=True)
    p.add_argument('--experiment',choices=list('BCDE'))
    a=p.parse_args();rows=[];seen=set()
    for path in a.raw.glob('*/record.json'):
        verify(path.parent)
        r=json.loads(path.read_text(encoding='utf-8-sig'))
        required=('experiment_id','run_id','experiment_type','dataset_version','source_commit','source_hash','actual_model_id','configuration','started_at','completed_at','input_tokens','output_tokens','estimated_cost','latency_ms','execution_status','verification_status','security_status','evidence_reference','failure_reason')
        if any(k not in r for k in required):raise ValueError(f'{path}: missing required fields')
        if r['run_id'] in seen:raise ValueError('duplicate run_id')
        seen.add(r['run_id'])
        if r['evidence_source'] not in ('LIVE_MODEL_DOCKER','OFFLINE_MODEL_DOCKER'):raise ValueError('Replay/synthetic evidence rejected')
        if a.experiment and r['experiment_type']!=a.experiment:continue
        rows.append(r)
    if not rows:raise SystemExit('No raw observations; no charts generated')
    a.out.mkdir(parents=True,exist_ok=False)
    columns=[k for k in rows[0] if k not in ('report','configuration')]
    with (a.out/'summary.csv').open('x',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=columns,extrasaction='ignore');w.writeheader();w.writerows(rows)
    summaries=summarize(rows);pairs=paired(rows)
    (a.out/'statistics.json').write_text(json.dumps(summaries,indent=2),encoding='utf-8')
    (a.out/'pairs.json').write_text(json.dumps(pairs,indent=2),encoding='utf-8')
    try:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
    except ImportError:raise SystemExit('CSV/JSON saved; PNG/SVG/HTML require optional matplotlib (not installed automatically)')
    images=[]
    eligible_pairs=[r for r in pairs if r['status']=='MATCHED' and (r['experiment']=='E' or r.get('comparison_valid'))]
    if eligible_pairs:
        fig,ax=plt.subplots(figsize=(10,5))
        ax.bar(range(len(eligible_pairs)),[r['latency_delta_ms'] for r in eligible_pairs])
        ax.set_xticks(range(len(eligible_pairs)),[r['experiment']+':'+r['pair_id'] for r in eligible_pairs],rotation=25)
        ax.set(xlabel='Validated fixed-source pair',ylabel='ON minus OFF client ms',title='Paired observed overhead; exploratory v2')
        fig.tight_layout()
        for ext in ('png','svg'):fig.savefig(a.out/('paired-overhead.'+ext))
        plt.close(fig);images.append('paired-overhead.svg')
    for metric,unit in [('success','VERIFIED / completed'),('latency','client total ms'),('cost','mean estimated USD/task'),('cost_per_verified','estimated USD / VERIFIED')]:
        valid=[s for s in summaries if s[metric] is not None]
        if not valid:continue
        fig,ax=plt.subplots(figsize=(12,7));ax.bar(range(len(valid)),[s[metric] for s in valid],yerr=[s['latency_sd'] or 0 for s in valid] if metric=='latency' else None)
        ax.set_xticks(range(len(valid)),[f'group {i+1}; n={s["n"]}' for i,s in enumerate(valid)])
        ax.set(xlabel='Stratified group (see statistics.json)',ylabel=unit,title=metric+' — exploratory / v2')
        fig.text(.01,.01,'Source: '+str(a.raw)+'; latency errors=sample SD; no population inference',fontsize=8)
        fig.tight_layout(rect=(0,.04,1,1))
        for ext in ('png','svg'):fig.savefig(a.out/(metric+'.'+ext),dpi=150)
        plt.close(fig);images.append(metric+'.svg')
    # Individual C points preserve failures; they are not treated as successful scale capacity.
    scale=[r for r in rows if r['experiment_type']=='C' and r['configuration'].get('file_count') is not None]
    for field,unit in [('latency_ms','client ms'),('input_tokens','tokens'),('estimated_cost','estimated USD'),('verified_outcome','VERIFIED=1, other observed terminal=0'),('security_outcome','CONFIRMED security=1, other=0')]:
        for r in scale:
            if r['execution_status']=='COMPLETED':
                r['verified_outcome']=int(r.get('verification_status')=='VERIFIED')
                if r.get('security_status') is not None:r['security_outcome']=int(r['security_status']=='CONFIRMED')
        valid=[r for r in scale if r.get(field) is not None]
        if not valid:continue
        fig,ax=plt.subplots();ax.scatter([r['configuration']['file_count'] for r in valid],[float(r[field]) for r in valid]);ax.set(xlabel='Source files',ylabel=unit,title=f'Scale vs {field}; n={len(valid)}; exploratory v2')
        for ext in ('png','svg'):fig.savefig(a.out/(f'scale-{field}.'+ext),bbox_inches='tight')
        plt.close(fig);images.append(f'scale-{field}.svg')
    valid=[s for s in summaries if s['cost'] is not None and s['success'] is not None]
    if valid:
        fig,ax=plt.subplots();ax.scatter([s['cost'] for s in valid],[s['success'] for s in valid]);ax.set(xlabel='Mean estimated USD/task',ylabel='VERIFIED/completed',title='Cost vs success; exploratory v2')
        for i,s in enumerate(valid):ax.annotate(f'group {i+1} n={s["n"]}',(s['cost'],s['success']))
        for ext in ('png','svg'):fig.savefig(a.out/('cost-success.'+ext),bbox_inches='tight')
        plt.close(fig);images.append('cost-success.svg')
    page='<html><meta charset="utf-8"><title>TrustBound Benchmark v2</title><h1>Observed results — exploratory</h1><p>Source: '+html.escape(str(a.raw))+'</p><p>Missing data remain unknown. See statistics.json and pairs.json for denominators and valid comparisons.</p>'+''.join('<img style="max-width:100%" src="'+name+'">' for name in images)+'<pre>'+html.escape(json.dumps(summaries,indent=2))+'</pre></html>'
    (a.out/'index.html').write_text(page,encoding='utf-8')
    (a.out/'BENCHMARK_REPORT.md').write_text('# Benchmark v2\n\nExploratory observations only. See index.html, summary.csv, statistics.json and pairs.json. F deferred. TTFR and uninstrumented resource peaks unavailable.\n',encoding='utf-8')
    print(a.out/'index.html')


if __name__=='__main__':main()
