"""Render only archived historical evidence. No application, HTTP, Docker or model imports."""
from pathlib import Path
from datetime import datetime, timezone, timedelta
import csv
import hashlib
import html
import json
import os
import sys

BATCH = Path(__file__).resolve().parent
ROOT = BATCH.parents[3]
OUT = BATCH / 'historical-analysis'
HISTORY = BATCH / 'historical-raw'


def write_csv(path, rows):
    if not rows:
        return
    with path.open('x', encoding='utf-8-sig', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main():
    OUT.mkdir(exist_ok=False)
    HISTORY.mkdir(exist_ok=False)
    archived = []
    for name in ('environment-smoke.json', 'day1-results.json'):
        source = ROOT / 'docs' / name
        raw = source.read_bytes()
        (HISTORY / name).write_bytes(raw)
        archived.append(dict(source=str(source.relative_to(ROOT)), archive=str((HISTORY/name).relative_to(BATCH)), sha256=hashlib.sha256(raw).hexdigest(), classification='HISTORICAL_LOCAL_DOCKER_RECORD', origin_verified_by_new_execution=False))
    smoke = json.loads((HISTORY/'environment-smoke.json').read_bytes())
    reports = json.loads((HISTORY/'day1-results.json').read_bytes())
    execution_rows = []
    for name in ('normal', 'timeout'):
        e=smoke[name]; state=e['state']
        execution_rows.append(dict(source='docs/environment-smoke.json',source_class='HISTORICAL_LOCAL_DOCKER_RECORD',run_id=None,container_name=e['container_name'],case=name,phase='smoke',execution_status='TIMED_OUT' if e['timed_out'] else 'EXITED',exit_code=state.get('ExitCode'),cleanup_confirmed=e.get('cleanup_confirmed'),limits_verified=None,workspace_unchanged=None,started_at=state.get('StartedAt'),finished_at=state.get('FinishedAt'),actual_model_id=None,cost=None))
    task_rows=[]
    for r in reports:
        task_rows.append(dict(source='docs/day1-results.json',source_class='HISTORICAL_LOCAL_DOCKER_RECORD',run_id=r['run_id'],candidate=r['candidate_id'],verification_status=r['status'],artifact_hash=r['artifact_hash'],acceptance_hash=r['acceptance_hash'],container_count=len(r['executions']),actual_model_id=None,cost=None))
        for e in r['executions']:
            execution_rows.append(dict(source='docs/day1-results.json',source_class='HISTORICAL_LOCAL_DOCKER_RECORD',run_id=r['run_id'],container_name=e['container_name'],case=r['candidate_id'],phase=e['phase'],execution_status=e['status'],exit_code=e.get('exit_code'),cleanup_confirmed=e.get('cleanup_confirmed'),limits_verified=e.get('limits_verified'),workspace_unchanged=e.get('workspace_unchanged'),started_at=None,finished_at=None,actual_model_id=None,cost=None))
    names=[r['container_name'] for r in execution_rows]
    if len(names)!=len(set(names)):
        raise ValueError('Duplicate historical container identity; stop to avoid double counting')
    write_csv(OUT/'historical-executions.csv', execution_rows)
    write_csv(OUT/'historical-tasks.csv', task_rows)
    coverage=[
        dict(dimension='Process Isolation',scenario='Read-only root and non-root smoke',status='INCONCLUSIVE',evidence='docs/environment-smoke.json#/normal',observation=smoke['normal']['stdout'],gap='Historical local observation only; no Rootless A1 runtime report; mount/process boundaries incomplete'),
        dict(dimension='Process Isolation',scenario='A1 unauthorized permission gate',status='INCONCLUSIVE',evidence='docs/day1-results.json#candidate_id=unauthorized',observation=next(r['status'] for r in reports if r['candidate_id']=='unauthorized'),gap='Policy-layer rejection is not container filesystem isolation evidence'),
        dict(dimension='Process Isolation',scenario='A2 network isolation',status='INCONCLUSIVE',evidence='docs/environment-smoke.json#/normal',observation='NetworkMode='+str(smoke['normal']['limits']['NetworkMode'])+'; '+smoke['normal']['stdout'].split('interfaces:')[-1].splitlines()[0],gap='lo/inspect observed historically; no dedicated A2 route probe report'),
        dict(dimension='Secret Hygiene',scenario='A3 synthetic secret / Web-Runner isolation',status='NOT_TESTED',evidence=None,observation=None,gap='No original Rootless A3 observations; no fresh secret test performed'),
        dict(dimension='Resource Limits',scenario='A4 host execution timeout',status='INCONCLUSIVE',evidence='docs/environment-smoke.json#/timeout; docs/day1-results.json#candidate_id=timeout',observation='Historical timeout/137 and cleanup records',gap='Bounded historical timeout evidence; no Rootless A4 probe report'),
        dict(dimension='Resource Limits',scenario='A5 cgroup OOM termination',status='NOT_TESTED',evidence=None,observation=None,gap='Memory configuration is not OOM enforcement evidence'),
        dict(dimension='Resource Limits',scenario='CPU and PID enforcement under load',status='NOT_TESTED',evidence='docs/environment-smoke.json#/normal/limits',observation='Configured NanoCpus='+str(smoke['normal']['limits']['NanoCpus'])+'; PidsLimit='+str(smoke['normal']['limits']['PidsLimit']),gap='Inspect only; no runtime CPU/PID trigger test'),
        dict(dimension='Lifecycle Discipline',scenario='Normal / failed / timed-out cleanup',status='INCONCLUSIVE',evidence='historical-executions.csv',observation=str(sum(r['cleanup_confirmed'] is True for r in execution_rows))+'/'+str(len(execution_rows))+' historical cleanup confirmations',gap='Historical bounded executions only; not systematic lifecycle proof'),
        dict(dimension='Lifecycle Discipline',scenario='Orphan recovery / long-run leaks',status='NOT_TESTED',evidence=None,observation=None,gap='No real fault-injection or sustained resource telemetry report')]
    write_csv(OUT/'security-coverage.csv',coverage)
    clean=sum(r['cleanup_confirmed'] is True for r in execution_rows)
    timed=sum(r['execution_status']=='TIMED_OUT' for r in execution_rows)
    summary=dict(dataset='historical-security-audit-v1',evidence_class='HISTORICAL_LOCAL_DOCKER_RECORD',new_docker_executions=0,new_model_requests=0,historical_task_count=len(task_rows),historical_container_count=len(execution_rows),historical_timed_out_count=timed,historical_cleanup_confirmed=clean,historical_cleanup_observed_denominator=len(execution_rows),rootless_a1_a5_complete_reports_found=0,containment_rate=None,false_rejection_rate=None,secret_exposure_rate=None,resource_enforcement_rate=None,limitations='No dedicated Rootless suite report; different tasks/phases are not independent repetitions. No universal security conclusions.',sources=archived,coverage=coverage)
    (OUT/'statistics.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
    # Use the already-installed plotting library in this interpreter; no installation.
    os.environ['MPLCONFIGDIR']=str(BATCH/'plot-cache')
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.colors import ListedColormap
    images=[]
    fig,ax=plt.subplots(figsize=(13,7))
    vals=[[1 if row['status']=='INCONCLUSIVE' else 0] for row in coverage]
    ax.imshow(vals,aspect='auto',cmap=ListedColormap(['#d6d6d6','#f0b35d']),vmin=0,vmax=1)
    ax.set_yticks(range(len(coverage)),[row['dimension']+' / '+row['scenario'] for row in coverage],fontsize=9)
    ax.set_xticks([0],['Evidence scope'])
    for i,row in enumerate(coverage):ax.text(0,i,row['status'],ha='center',va='center',fontsize=9)
    ax.set_title('Historical security coverage — no new attack runs / v1')
    fig.text(.01,.01,'Source: archived docs/environment-smoke.json + docs/day1-results.json; orange=partial historical evidence, gray=not tested; no PASS implied',fontsize=8)
    fig.tight_layout(rect=(0,.05,1,1))
    for ext in ('png','svg'):fig.savefig(OUT/('security-coverage.'+ext),dpi=150)
    plt.close(fig);images.append('security-coverage.svg')
    fig,ax=plt.subplots(figsize=(10,5))
    categories=['EXITED','TIMED_OUT','ERROR']
    counts=[sum(r['execution_status']==s for r in execution_rows) for s in categories]
    ax.bar(categories,counts,color=['#739ac4','#e0a354','#b25d5d'])
    ax.set(xlabel='Recorded container execution state (not security verdict)',ylabel='Historical containers',title=f'Historical Docker execution records; n={len(execution_rows)} / v1')
    for i,n in enumerate(counts):ax.text(i,n,str(n),ha='center',va='bottom')
    fig.text(.01,.01,'Source: historical-executions.csv; no new runs, no Demo Replay or synthetic observations',fontsize=8)
    fig.tight_layout(rect=(0,.05,1,1))
    for ext in ('png','svg'):fig.savefig(OUT/('historical-execution-status.'+ext),dpi=150)
    plt.close(fig);images.append('historical-execution-status.svg')
    decisions=json.loads((BATCH/'execution-decisions.json').read_text(encoding='utf-8'))
    write_csv(BATCH/'execution-decisions.csv',[dict(experiment=r['experiment'],status=r['status'],submitted=r['submitted'],run_id=r['run_id'],actual_cost=r['actual_cost'],new_model_requests=r['model_requests'],missing='; '.join(r['missing'])) for r in decisions])
    page='<html lang="zh"><meta charset="utf-8"><title>TrustBound 有限批次报告</title><style>body{font:16px sans-serif;max-width:1200px;margin:30px auto;padding:20px}img{max-width:100%}pre{white-space:pre-wrap}</style><h1>有限批次报告：未提交新实验</h1><p>prepare完成；现有Benchmark原始目录为空。D-OFF/E-OFF/E-ON配置缺失，服务健康接口访问被权限拒绝，因此跳过。B/C/D-ON未获固定付费批次授权。A未启动攻击。</p><h2>历史Docker证据（不是本轮实验）</h2><p>以下图表仅来自存档历史报告，不包含Demo Replay或合成结果。所有安全维度为INCONCLUSIVE或NOT_TESTED。</p>'+''.join('<img src="'+name+'">' for name in images)+'<h2>历史统计与来源</h2><pre>'+html.escape(json.dumps(summary,ensure_ascii=False,indent=2))+'</pre><h2>运行/授权缺口</h2><pre>'+html.escape(json.dumps(decisions,ensure_ascii=False,indent=2))+'</pre></html>'
    (OUT/'index.html').write_text(page,encoding='utf-8')
    print(json.dumps(dict(output=str(OUT),historical_tasks=len(task_rows),historical_containers=len(execution_rows),historical_cleanup=clean,new_experiments=0,plotting_interpreter=sys.executable),indent=2))


if __name__=='__main__':main()
