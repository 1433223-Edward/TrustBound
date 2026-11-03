export const FINAL_STATUSES = ['VERIFIED', 'FAILED', 'REJECTED', 'INCONCLUSIVE']

export function validateReport(report, taskId) {
  if (!report || !FINAL_STATUSES.includes(report.status) || !report.run_id ||
      typeof report.artifact_hash !== 'string' || typeof report.acceptance_hash !== 'string' ||
      report.task?.task_id !== taskId || !Array.isArray(report.executions) ||
      typeof report.diff !== 'string' || typeof report.policy_reason !== 'string' ||
      !Array.isArray(report.changed_paths) || !Array.isArray(report.limitations)) {
    throw new Error('Invalid verification report: missing fields or task mismatch.')
  }
  for (const execution of report.executions) {
    if (!['public', 'acceptance'].includes(execution.phase) ||
        !['EXITED', 'TIMED_OUT', 'ERROR'].includes(execution.status) ||
        !(execution.exit_code === null || Number.isInteger(execution.exit_code)) ||
        typeof execution.stdout !== 'string' || typeof execution.stderr !== 'string' ||
        ['cleanup_confirmed', 'workspace_unchanged', 'limits_verified'].some(key => typeof execution[key] !== 'boolean')) {
      throw new Error('Invalid execution evidence.')
    }
  }
  // A transport success is never sufficient evidence for a VERIFIED result.
  if (report.status === 'VERIFIED' && (report.executions.length !== 2 ||
      !['public', 'acceptance'].every(phase => report.executions.some(e => e.phase === phase)) ||
      report.executions.some(e => !executionPassed(e) || e.artifact_hash !== report.artifact_hash) ||
      report.executions.find(e => e.phase === 'acceptance')?.test_hash !== report.acceptance_hash)) {
    throw new Error('Contradictory VERIFIED report: successful, matching evidence is required.')
  }
  return report
}

export function executionPassed(e) {
  return e.status === 'EXITED' && e.exit_code === 0 && e.cleanup_confirmed &&
    e.workspace_unchanged && e.limits_verified && !e.error
}

export function executionStatus(e) {
  if (!e) return 'NOT_RUN'
  if (e.status === 'TIMED_OUT') return 'TIMED_OUT'
  if (e.status === 'ERROR') return 'ERROR'
  return e.exit_code === 0 ? 'PASSED' : 'FAILED'
}

export function traceFor(report, proposal, mode = 'DEMO') {
  const publicRun = report?.executions.find(e => e.phase === 'public')
  const acceptance = report?.executions.find(e => e.phase === 'acceptance')
  const policyDenied = report?.status === 'REJECTED' && !report.executions.length
  return [
    { name: 'Agent Proposal', state: proposal ? 'RECORDED' : report ? 'NOT_RECORDED' : 'WAITING',
      detail: proposal ? proposal.analysis : mode === 'DEMO' ? '固定回放不含 LLM 提案记录。' : report ? '后端未提供模型提案记录。' : '等待后端提案；浏览器不直接调用 LLM。' },
    { name: 'Permission Check', state: report ? policyDenied ? 'REJECTED' : report.executions.length ? 'ALLOWED' : 'UNKNOWN' : 'WAITING',
      detail: report?.policy_reason || 'Only billing.py may be changed.' },
    { name: 'Sandbox Execution', state: publicRun ? publicRun.status : report ? 'NOT_RUN' : 'WAITING',
      detail: publicRun ? `${publicRun.limits_verified ? 'Limits checked' : 'Limits unconfirmed'} · ${publicRun.cleanup_confirmed ? 'Container removed' : 'Cleanup unconfirmed'}` : 'Isolated Linux container · no network.' },
    { name: 'Public Tests', state: report ? executionStatus(publicRun) : 'WAITING',
      detail: publicRun ? `Exit ${publicRun.exit_code ?? 'unknown'}${publicRun.timeout_reason ? ' · ' + publicRun.timeout_reason : ''}` : 'Declared public test suite.' },
    { name: 'Independent Verification', state: report ? executionStatus(acceptance) : 'WAITING',
      detail: acceptance ? `Fresh container · exit ${acceptance.exit_code ?? 'unknown'}` : report ? '未运行；不能推断为通过。' : 'Protected billing-v1 acceptance.' },
    { name: 'Final Decision', state: report?.status || 'WAITING',
      detail: report ? '结论来自 VerificationReport，不来自模型声明。' : 'Evidence first. Decision second.' },
  ]
}

export function diffLines(diff) {
  return diff.split('\n').filter((line, index, lines) => index < lines.length - 1 || line).map((text) => ({
    text,
    kind: text.startsWith('+++') || text.startsWith('---') || text.startsWith('@@') ? 'meta'
      : text.startsWith('+') ? 'added' : text.startsWith('-') ? 'removed' : 'context',
  }))
}

export function tokenize(line) {
  const pattern = /(""".*?"""|"[^"\n]*"|'[^'\n]*'|#[^\n]*|\b(?:from|import|def|return|while|pass|as|True|False|None)\b|\b\d+(?:\.\d+)?\b)/g
  return line.split(pattern).filter(Boolean).map(text => ({ text,
    kind: /^["']/.test(text) ? 'string' : text.startsWith('#') ? 'comment'
      : /^\d/.test(text) ? 'number' : /^(from|import|def|return|while|pass|as|True|False|None)$/.test(text) ? 'keyword' : 'plain',
  }))
}
