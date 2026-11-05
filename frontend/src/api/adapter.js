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

export function traceFor(report, proposal, mode = 'DEMO', executionMode = 'fixture', finalDecision = null) {
  const publicRun = report?.executions.find(e => e.phase === 'public')
  const acceptance = report?.executions.find(e => e.phase === 'acceptance')
  const policyDenied = report?.status === 'REJECTED' && !report.executions.length
  return [
    { name: 'Agent Proposal', state: proposal ? 'RECORDED' : report ? 'NOT_RECORDED' : 'WAITING',
      detail: proposal ? proposal.analysis : mode === 'DEMO' ? '固定回放不含 LLM 提案记录。'
        : executionMode === 'fixture' ? '固定候选 · 无模型调用；Docker 将真实执行。'
          : report ? '后端未提供模型提案记录。' : '等待后端提案；浏览器不直接调用 LLM。' },
    { name: 'Permission Check', state: report ? policyDenied ? 'REJECTED' : report.executions.length ? 'ALLOWED' : 'UNKNOWN' : 'WAITING',
      detail: report?.policy_reason || 'Only billing.py may be changed.' },
    { name: 'Sandbox Execution', state: publicRun ? publicRun.status : report ? 'NOT_RUN' : 'WAITING',
      detail: publicRun ? `${publicRun.limits_verified ? 'Limits checked' : 'Limits unconfirmed'} · ${publicRun.cleanup_confirmed ? 'Container removed' : 'Cleanup unconfirmed'}` : 'Isolated Linux container · no network.' },
    { name: 'Public Tests', state: report ? executionStatus(publicRun) : 'WAITING',
      detail: publicRun ? `Exit ${publicRun.exit_code ?? 'unknown'}${publicRun.timeout_reason ? ' · ' + publicRun.timeout_reason : ''}` : 'Declared public test suite.' },
    { name: 'Independent Verification', state: report ? executionStatus(acceptance) : 'WAITING',
      detail: acceptance ? `Fresh container · exit ${acceptance.exit_code ?? 'unknown'}` : report ? '未运行；不能推断为通过。' : 'Protected billing-v1 acceptance.' },
    { name: 'Final Decision', state: finalDecision?.status || report?.status || 'WAITING',
      detail: finalDecision?.reason || (report ? '结论来自 VerificationReport，不来自模型声明。' : 'Evidence first. Decision second.') },
  ]
}

export function validateAdversarialEnvelope(snapshot, requested = 'off') {
  const base = snapshot.verification, report = snapshot.adversarial_report, decision = snapshot.final_decision
  if (requested !== 'off' && (!report || !decision)) throw new Error('Missing requested adversarial evidence.')
  if (!decision && !report) return
  if (!decision || decision.formal_report_id !== base.run_id || decision.artifact_hash !== base.artifact_hash ||
      decision.formal_status !== base.status || !FINAL_STATUSES.includes(decision.status)) throw new Error('Final decision identity mismatch.')
  if (!report) {
    if (decision.status !== base.status) throw new Error('Unexplained final verdict change.')
    return
  }
  if (report.artifact_hash !== base.artifact_hash || report.task_id !== base.task.task_id ||
      !Array.isArray(report.challenges) || report.challenges.length > 4 ||
      !['COMPLETED', 'INCOMPLETE', 'GENERATION_FAILED', 'UNAVAILABLE', 'SKIPPED'].includes(report.status)) throw new Error('Invalid adversarial report.')
  const confirmed = report.challenges.filter(row => row.status === 'CONFIRMED').length
  if (confirmed !== report.confirmed_count) throw new Error('Counterexample count mismatch.')
  const valid = report.challenges.filter(row => row.status !== 'INVALID')
  if (valid.length !== report.valid_count || report.challenges.some(row =>
      !['INVALID', 'INCONCLUSIVE', 'CONFIRMED', 'NOT_CONFIRMED'].includes(row.status) ||
      !row.challenge || typeof row.challenge.amount !== 'string' ||
      (row.status !== 'INVALID' && !Number.isSafeInteger(row.expected)))) {
    throw new Error('Invalid challenge data or count.')
  }
  if (report.source === 'OFFLINE_TEST' && requested === 'live') throw new Error('Offline evidence cannot represent a live model call.')
  if (report.status === 'COMPLETED' || confirmed) {
    const e = report.execution
    if (!valid.length || valid.some(row => !['CONFIRMED', 'NOT_CONFIRMED'].includes(row.status) || !row.actual_type || row.actual === null) ||
        !e || report.status !== 'COMPLETED' || e.phase !== 'adversarial' || e.status !== 'EXITED' ||
        e.exit_code !== (confirmed ? 1 : 0) || !e.cleanup_confirmed || !e.workspace_unchanged ||
        !e.limits_verified || e.error || e.artifact_hash !== base.artifact_hash || e.test_hash !== report.driver_hash) {
      throw new Error('Counterexample lacks matching complete sandbox evidence.')
    }
  }
  const expected = base.status !== 'VERIFIED' ? base.status : confirmed ? 'FAILED'
    : report.status === 'COMPLETED' ? 'VERIFIED' : 'INCONCLUSIVE'
  if (decision.status !== expected) throw new Error('Final verdict contradicts adversarial evidence.')
}

export function validateRecoveryReport(snapshot, requested = 'off') {
  const report = snapshot.recovery_report
  if (!report) {
    if (requested !== 'off') throw new Error('Missing requested recovery history.')
    return
  }
  if (report.run_id !== snapshot.run_id || report.max_attempts !== 2 ||
      !Array.isArray(report.attempts) || report.attempts.length < 1 || report.attempts.length > 3 ||
      !FINAL_STATUSES.includes(report.final_status) || !report.stop_reason ||
      !['COMPLETED', 'STOPPED'].includes(report.status)) throw new Error('Invalid bounded recovery report.')
  let validated
  for (const [index, attempt] of report.attempts.entries()) {
    if (attempt.run_id !== snapshot.run_id || attempt.attempt_index !== index ||
        attempt.previous_candidate_hash !== (index ? report.attempts[index - 1].candidate_hash : null)) {
      throw new Error('Recovery attempt chain mismatch.')
    }
    if (attempt.verification) {
      validateReport(attempt.verification, snapshot.task_id)
      if (attempt.candidate_hash !== attempt.verification.artifact_hash) throw new Error('Recovery candidate/evidence mismatch.')
      validateAdversarialEnvelope(attempt, snapshot.adversarial_mode || 'offline')
      validated = attempt
    } else if (attempt.adversarial_report || attempt.final_decision?.status === 'VERIFIED') {
      throw new Error('Unverified attempt cannot borrow successful evidence.')
    }
  }
  const last = report.attempts.at(-1)
  if (!validated || report.validated_attempt_index !== validated.attempt_index ||
      snapshot.verification.run_id !== validated.verification.run_id ||
      report.current_attempt !== last.attempt_index || report.final_status !== last.final_decision?.status ||
      report.final_status !== report.final_decision?.status ||
      (report.final_status === 'VERIFIED' && (last !== validated || report.stop_reason !== 'VERIFIED' ||
        last.adversarial_report?.status !== 'COMPLETED'))) throw new Error('Recovery final decision does not match its last attempt.')
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
