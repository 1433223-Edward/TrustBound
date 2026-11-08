import { t } from './i18n.js'

// Deterministic summaries are control-layer statements, never model quotations.
export function agentNarration({ run, billing } = {}) {
  const rows = []
  const add = (role, text, status, tab = 'summary', runId, attempt) => rows.push({ role, text, status, tab, runId, attempt })
  const verdict = status => status === 'EXECUTED_UNVERIFIED'
    ? t('Code ran under the approved sandbox controls. Functional correctness was not verified; review or retain it as an unverified draft.', '代码已按批准的沙箱限制执行，未验证功能正确性。你可以审核并保留为未验证草稿。')
    : status === 'EXECUTION_FAILED' ? t('The bounded execution did not complete successfully. No functional verification was performed.', '受限执行未成功完成，未进行功能验证。')
    : status === 'VERIFIED'
    ? t('All required checks for this candidate passed. Review the evidence before accepting the changes.', '该候选的必要检查已通过，请查看证据后决定是否接受修改。')
    : status === 'FAILED' ? t('Verified checks found a mismatch. The candidate has not passed; inspect the failed case before deciding on a repair.', '已核验的测试发现结果不符，候选未通过。请查看失败用例，再决定是否修复。')
      : status === 'REJECTED' ? t('The proposal was rejected. It has not been approved for use.', '提案已被拒绝，不能作为已批准的结果使用。')
        : t('The evidence is incomplete. No successful verification is claimed; inspect the report before retrying.', '证据尚不完整，未宣称验证成功。请查看报告后决定是否重试。')
  if (billing) {
    const append = (report, adversarial, role = 'executor', attempt) => {
      if (report) {
        add(role, t('A candidate record is available. Its proposed scope and test results are ready to inspect.', '已有候选记录，可检查其修改范围和测试结果。'), 'RECORDED', 'diff', report.run_id, attempt)
        for (const execution of report.executions ?? []) {
          const intact = execution.status === 'EXITED' && execution.cleanup_confirmed && execution.workspace_unchanged && execution.limits_verified && !execution.error
          add('verifier', execution.phase === 'acceptance'
            ? t('The independent acceptance run finished. ', '独立验收运行已结束。') + (intact && execution.exit_code === 0 ? t('It passed with intact sandbox evidence.', '验收通过，沙箱证据完整。') : t('It did not pass with complete success evidence; inspect the report.', '未取得完整的通过证据，请查看报告。'))
            : t('The public test run finished. ', '公开测试运行已结束。') + (intact && execution.exit_code === 0 ? t('It passed with intact sandbox evidence.', '测试通过，沙箱证据完整。') : t('It did not pass with complete success evidence; inspect the report.', '未取得完整的通过证据，请查看报告。')),
          intact && execution.exit_code === 0 ? 'PASSED' : 'INCONCLUSIVE', 'logs', report.run_id, attempt)
        }
      }
      if (adversarial) {
        const confirmed = (adversarial.challenges ?? []).filter(row => row.status === 'CONFIRMED').length
        add('adversarial', confirmed ? t(`Verifier confirmed ${confirmed} counterexample(s). The candidate still has a demonstrated problem.`, `验证器确认了 ${confirmed} 个反例，候选仍有已证实的问题。`)
          : adversarial.status === 'COMPLETED' ? t('The recorded adversarial checks completed. No counterexample was confirmed in this bounded run.', '记录中的对抗检查已完成，本次有限检查未确认反例。')
            : t('Adversarial analysis has no complete result yet. Do not treat it as passed.', '对抗分析尚无完整结果，不能视为通过。'), adversarial.status, 'adversarial', report?.run_id, attempt)
      }
    }
    if (billing.recovery?.attempts?.length) {
      for (const attempt of billing.recovery.attempts) {
        if (attempt.attempt_index > 0) add('recovery', t('A repair attempt was started from confirmed failure evidence. Its result requires fresh verification.', '已依据可信失败证据启动修复尝试，结果仍须重新验收。'), 'RECORDED', 'recovery', attempt.verification?.run_id, attempt.attempt_index)
        append(attempt.verification, attempt.adversarial_report, attempt.attempt_index > 0 ? 'recovery' : 'executor', attempt.attempt_index)
      }
    } else append(billing.report, billing.adversarial)
    const status = billing.recovery?.final_status ?? billing.decision?.status ?? billing.report?.status
    if (status) add('verifier', verdict(status), status, billing.recovery ? 'recovery' : 'summary', billing.report?.run_id)
    return rows
  }
  const report = run?.workspace_report
  if (!report) {
    if (run?.state) add('system', t('The execution request is recorded. Waiting for execution evidence.', '执行请求已记录，正在等待执行证据。'), run.state, 'summary', run.run_id)
    return rows
  }
  const events = {
    'Candidate generation': () => t('A model request is generating a candidate proposal. No file change has been accepted yet.', '已发起模型请求生成候选提案，尚未接受任何文件修改。'),
    'Independent analysis': () => t('An independent model request is exploring boundary inputs under the approved task rules.', '已发起独立模型请求，按批准的任务规则探索边界输入。'),
    'Proposal received': () => t('The model returned a proposal. The host must still validate it and verify the candidate.', '已收到模型提议，宿主仍需校验提议并验证候选。'),
    'Generation failed': () => t('The model request failed. This stage has no successful result; inspect the evidence for the reason.', '模型请求失败，本阶段没有成功结果；请查看证据中的原因。'),
    'Base acceptance': () => t('The candidate passed scope validation. Starting the approved cases in restricted sandboxes.', '候选已通过修改范围校验，开始在受限沙箱中运行批准的用例。'),
    'Security execution': () => t('Running the authorized input in the restricted sandbox. Business expectations will not be compared.', '正在受限沙箱中运行授权输入，不比较业务期望值。'),
    'Generated challenge verification': () => t('The base checks passed. A generated boundary input is now being checked against trusted expectations.', '基础检查已通过，正在用可信预期核验新生成的边界输入。'),
  }
  for (const event of report.agent_events ?? []) {
    if (events[event.stage]) add(event.role, events[event.stage](), event.status, event.role === 'adversarial' ? 'adversarial' : event.role === 'recovery' ? 'recovery' : 'logs', run.run_id)
  }
  for (const [phase, label] of [['public', t('public', '公开测试')], ['acceptance', t('independent acceptance', '独立验收')], ['adversarial', t('adversarial', '对抗测试')]]) {
    const cases = (report.cases ?? []).filter(row => row.phase === phase)
    if (!cases.length) continue
    const matched = cases.filter(row => row.status === 'MATCHED').length
    const failed = cases.filter(row => row.status === 'MISMATCH').length
    const incomplete = cases.length - matched - failed
    add('verifier', t(`Recorded ${cases.length} ${label} case(s): ${matched} matched, ${failed} mismatched, ${incomplete} incomplete.`, `已记录 ${cases.length} 项${label}：${matched} 项匹配、${failed} 项不符、${incomplete} 项证据未完成。`), failed ? 'FAILED' : incomplete ? 'INCONCLUSIVE' : 'PASSED', phase === 'adversarial' ? 'adversarial' : 'logs', run.run_id)
  }
  for (const row of report.adversarial_report?.challenges ?? []) {
    if (row.status === 'NEEDS_CONFIRMATION') add('adversarial', t('A suggested boundary input needs a business rule from you. It is not a verified counterexample.', '一个建议的边界输入需要你确认业务规则，目前不是已验证反例。'), row.status, 'adversarial', run.run_id)
    if (row.status === 'CONFIRMED') add('verifier', t('A generated counterexample was confirmed against the trusted reference. Review it before authorizing a repair.', '生成的反例已通过可信参考规则确认，请查看后决定是否授权修复。'), row.status, 'adversarial', run.run_id)
  }
  if (report.retried_from) add('recovery', t('This repair uses the previous candidate and a confirmed failure. The frozen acceptance criteria still apply.', '本次修复使用上一候选和已确认失败，仍须满足冻结的验收条件。'), 'RECORDED', 'recovery', run.run_id)
  if (['COMPLETED', 'ERROR'].includes(run.state)) add('verifier', verdict(run.state === 'ERROR' ? 'INCONCLUSIVE' : report.status), run.state === 'ERROR' ? 'INCONCLUSIVE' : report.status, 'summary', run.run_id)
  if (run.review === 'REJECTED') add('system', t('The candidate was discarded. Its evidence remains available and the base snapshot is unchanged.', '候选已丢弃，证据仍保留，基础快照未改变。'), 'RECORDED', 'diff', run.run_id)
  return rows
}

// Stable cards replace states in first-seen role order; the report keeps full history.
export function agentCards(input) {
  const cards = new Map()
  for (const row of agentNarration(input)) {
    const key = `${input.run?.run_id ?? 'billing'}:current:${row.role}`
    const previous = cards.get(key)
    const facts = previous?.facts ?? []
    if (row.role === 'verifier' && row.tab === 'logs' && /^(Recorded|已记录)/.test(row.text)) facts.push(row.text)
    cards.set(key, { ...row, key, facts, source: 'SYSTEM' })
  }
  const report = input.run?.workspace_report
  const explanation = report?.explanation
  const local = pair => pair ? t(pair.en, pair.zh) : ''
  for (const event of report?.agent_events ?? []) {
    if (!event.explanation || event.explanation_source !== 'MODEL') continue
    const key = `${input.run.run_id}:current:${event.role}`
    const card = cards.get(key)
    if (card) Object.assign(card, { model: event.model, source: 'MODEL',
      modelDescription: local(event.explanation.description), reason: local(event.explanation.reason) })
  }
  if (explanation?.artifact_hash === report?.artifact_hash && explanation?.frozen_hash === report?.frozen_hash) {
    for (const row of explanation?.roles ?? []) {
      const card = cards.get(`${input.run.run_id}:current:${row.role}`)
      if (card) Object.assign(card, { model: explanation.model, source: 'MODEL',
        modelDescription: local(row.description), reason: local(row.reason) })
    }
  }
  return [...cards.values()]
}
