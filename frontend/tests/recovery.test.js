// Captured Stage 2 records exercise UI contract guards; no fresh Docker claim here.
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { validateRecoveryReport } from '../src/api/adapter.js'
import { createWorkspace } from '../src/state/workspace.js'

const records = JSON.parse(readFileSync(new URL('../../docs/adversarial-integration-results.json', import.meta.url), 'utf8'))
const demo = JSON.parse(readFileSync(new URL('../src/data/demo.json', import.meta.url), 'utf8'))
const stage = id => structuredClone(records.find(r => r.experiment === id).snapshot)

function sampleRecovery() {
  const initial = stage('E2'), last = stage('E1'), id = 'unit-recovery-job'
  const attempts = [initial, last].map((s, index) => ({ ...s, run_id: id, attempt_index: index,
    candidate_hash: s.verification.artifact_hash, previous_candidate_hash: index ? initial.verification.artifact_hash : null,
    recovery_trigger: index ? 'CONFIRMED_ADVERSARIAL' : 'INITIAL', confirmed_failure_evidence: [], model_source: 'OFFLINE_TEST' }))
  return { ...last, run_id: id, recovery_mode: 'offline', recovery_report: {
    run_id: id, max_attempts: 2, current_attempt: 1, validated_attempt_index: 1, status: 'COMPLETED',
    stop_reason: 'VERIFIED', final_status: 'VERIFIED', final_decision: attempts[1].final_decision, attempts } }
}

test('recovery keeps separate initial failure and final version success', () => {
  const data = sampleRecovery(); validateRecoveryReport(data, 'offline')
  assert.equal(data.recovery_report.attempts[0].final_decision.status, 'FAILED')
  assert.notEqual(data.recovery_report.attempts[0].candidate_hash, data.recovery_report.attempts[1].candidate_hash)
})

test('missing history, broken version chain and unbounded attempts are rejected', () => {
  for (const mutate of [s => { s.recovery_report = null },
    s => { s.recovery_report.attempts[1].previous_candidate_hash = 'wrong' },
    s => { s.recovery_report.attempts[1].candidate_hash = 'old-artifact' },
    s => { s.recovery_report.max_attempts = 10 },
    s => { s.recovery_report.validated_attempt_index = 0 },
    s => { s.recovery_report.attempts[1].verification = null }]) {
    const data = sampleRecovery(); mutate(data)
    assert.throws(() => validateRecoveryReport(data, 'offline'))
  }
})

test('failed generation is inconclusive and has no borrowed verification', () => {
  const data = sampleRecovery(), r = data.recovery_report, first = r.attempts[0]
  Object.assign(data, { verification: first.verification, adversarial_report: first.adversarial_report, final_decision: first.final_decision })
  Object.assign(r.attempts[1], { verification: null, adversarial_report: null, candidate_hash: null,
    final_decision: { status: 'INCONCLUSIVE' } })
  Object.assign(r, { final_status: 'INCONCLUSIVE', final_decision: r.attempts[1].final_decision, status: 'STOPPED',
    validated_attempt_index: 0, stop_reason: 'RECOVERY_MODEL_ERROR:INVALID_RESPONSE' })
  validateRecoveryReport(data, 'offline')
  r.attempts[1].final_decision.status = 'VERIFIED'
  assert.throws(() => validateRecoveryReport(data, 'offline'), /borrow/)
})

test('workspace submits explicit offline recovery and resets the single history state', async () => {
  const data = sampleRecovery(); let options
  const ws = createWorkspace({ demo, client: { health: async () => ({}), listTasks: async () => demo.tasks,
    getTask: async () => demo.tasks[0], startRun: async (_task, _signal, value) => { options = value; return data.run_id },
    waitForRun: async (_id, _task, _signal, value) => { value.onUpdate(data); return data } } })
  ws.selectMode('LIVE'); ws.selectScenario('double_rounding'); ws.selectRecoveryMode('offline')
  assert.equal(ws.state.adversarialMode, 'offline')
  await ws.runAgent()
  assert.equal(ws.state.phase, 'READY')
  assert.equal(ws.state.recoveryReport.final_status, 'VERIFIED')
  assert.equal(options.recovery_mode, 'offline'); assert.equal(options.recovery_fixture, 'fixed')
  assert.equal(ws.trace.value.at(-1).state, 'VERIFIED')
  ws.selectRecoveryFixture('exhausted')
  assert.equal(ws.state.recoveryReport, null); assert.equal(ws.state.report, null)
})

test('a newly loaded workspace never restores a previous recovery as running', () => {
  const ws = createWorkspace({ demo, client: {} })
  assert.equal(ws.state.phase, 'IDLE'); assert.equal(ws.state.recoveryMode, 'off')
  assert.equal(ws.state.recoveryReport, null)
})
