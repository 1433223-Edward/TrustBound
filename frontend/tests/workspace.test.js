import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { createWorkspace } from '../src/state/workspace.js'
import { createApiClient } from '../src/api/client.js'
import { diffLines, traceFor, validateReport } from '../src/api/adapter.js'

const demo = JSON.parse(readFileSync(new URL('../src/data/demo.json', import.meta.url), 'utf8'))
const taskId = demo.tasks[0].spec.task_id
const sample = id => structuredClone(demo.reports.find(r => r.candidate_id === id))
const immediate = async () => {}
const forbiddenClient = { listTasks() { throw new Error('Demo must not contact an API') } }
const make = (options = {}) => createWorkspace({ demo: structuredClone(demo), client: forbiddenClient, sleep: immediate, ...options })
const jsonResponse = (body, status = 200, type = 'application/json') => ({ ok: status >= 200 && status < 300, status,
  headers: { get: () => type }, json: async () => body })
const snapshot = report => ({ run_id: report.run_id, task_id: taskId, source: 'LIVE', state: 'COMPLETED', proposal: null, verification: report })

test('all five real reports conform to the consumed contract', () => {
  for (const report of demo.reports) assert.equal(validateReport(report, taskId), report)
})
test('false success keeps public pass distinct from independent failure', () => {
  const trace = traceFor(sample('public_only'), null)
  assert.equal(trace[0].state, 'NOT_RECORDED')
  assert.equal(trace[3].state, 'PASSED')
  assert.equal(trace[4].state, 'FAILED')
  assert.equal(trace[5].state, 'FAILED')
})
test('policy denial never invents sandbox or acceptance evidence', () => {
  const trace = traceFor(sample('unauthorized'), null)
  assert.equal(trace[1].state, 'REJECTED')
  assert.equal(trace[2].state, 'NOT_RUN')
  assert.equal(trace[4].state, 'NOT_RUN')
})
test('timeout retains real termination rather than showing a test pass', () => {
  const trace = traceFor(sample('timeout'), null)
  assert.equal(trace[2].state, 'TIMED_OUT')
  assert.equal(trace[3].state, 'TIMED_OUT')
})
test('contradictory VERIFIED reports are rejected', () => {
  for (const alter of [r => { r.executions[0].cleanup_confirmed = false },
    r => { r.executions.pop() }, r => { r.executions[0].artifact_hash = 'other' },
    r => { r.executions[1].test_hash = 'other' }]) {
    const report = sample('fixed'); alter(report)
    assert.throws(() => validateReport(report, taskId), /Contradictory/)
  }
})
test('missing report fields or wrong task are rejected', () => {
  assert.throws(() => validateReport(sample('fixed'), 'wrong-task'))
  const report = sample('fixed'); delete report.artifact_hash
  assert.throws(() => validateReport(report, taskId))
})
test('diff metadata is not counted as changed source', () => {
  const lines = diffLines(sample('fixed').diff)
  assert.equal(lines.filter(line => line.kind === 'added').length, 3)
  assert.equal(lines.filter(line => line.kind === 'removed').length, 3)
  assert.equal(lines[0].kind, 'meta')
})
test('fresh workspace starts idle without patch, result, or persistent run', () => {
  const ws = make()
  assert.equal(ws.state.mode, 'DEMO'); assert.equal(ws.state.phase, 'IDLE')
  assert.equal(ws.state.report, null); assert.equal(ws.state.candidate, '')
})
test('sample loading is explicit and does not call the backend', async () => {
  let resolve
  const ws = make({ sleep: () => new Promise(r => { resolve = r }) })
  const loading = ws.replay()
  assert.equal(ws.busy.value, true); assert.equal(ws.state.report, null)
  resolve(); await loading
  assert.equal(ws.state.phase, 'READY'); assert.equal(ws.state.report.status, 'FAILED')
  assert.equal(ws.state.proposal, null)
})
test('scenario change clears prior code, evidence, and errors', async () => {
  const ws = make(); await ws.replay(); ws.selectScenario('fixed')
  assert.equal(ws.state.report, null); assert.equal(ws.state.candidate, '')
  await ws.replay(); assert.equal(ws.state.report.status, 'VERIFIED')
})
test('mode change discards a late replay result', async () => {
  let resolve
  const ws = make({ sleep: () => new Promise(r => { resolve = r }) })
  const loading = ws.replay(); ws.selectMode('LIVE'); resolve(); await loading
  assert.equal(ws.state.mode, 'LIVE'); assert.equal(ws.state.phase, 'IDLE')
  assert.equal(ws.state.report, null)
})
test('task changes synchronously update metadata and clear results', async () => {
  const data = structuredClone(demo)
  data.tasks.push({ ...structuredClone(data.tasks[0]), title: 'Unit-test task only',
    spec: { ...data.tasks[0].spec, task_id: 'test-task' }, original: { path: 'other.py', content: 'test-only' } })
  const ws = make({ demo: data }); await ws.replay(); ws.selectTask('test-task')
  assert.equal(ws.task.value.original.content, 'test-only'); assert.equal(ws.state.report, null)
})
test('Run Agent in demo mode does not pretend to execute', async () => {
  const ws = make(); await ws.runAgent()
  assert.equal(ws.state.phase, 'ERROR'); assert.match(ws.state.error, /Backend not connected/)
  assert.equal(ws.state.report, null)
})
test('live API failure does not fall back to sample success', async () => {
  const ws = make({ client: { listTasks: async () => { throw new Error('HTTP 503') } } })
  ws.selectMode('LIVE'); await ws.runAgent()
  assert.equal(ws.state.phase, 'ERROR'); assert.equal(ws.state.report, null)
  assert.equal(ws.state.connection, 'UNAVAILABLE')
})
test('live final verdict is supplied by matching verification, not request success', async () => {
  const report = sample('public_only')
  const ws = make({ client: { listTasks: async () => demo.tasks, startRun: async () => report.run_id,
    waitForRun: async () => snapshot(report) } })
  ws.selectMode('LIVE'); await ws.runAgent()
  assert.equal(ws.state.phase, 'READY'); assert.equal(ws.state.report.status, 'FAILED')
})
test('switching mode ignores an outstanding live response', async () => {
  let resolve
  const ws = make({ client: { listTasks: () => new Promise(r => { resolve = r }) } })
  ws.selectMode('LIVE'); const run = ws.runAgent(); ws.selectMode('DEMO')
  resolve(demo.tasks); await run
  assert.equal(ws.state.phase, 'IDLE'); assert.equal(ws.state.report, null)
})
test('200 HTML SPA fallback is not a connected backend', async () => {
  const client = createApiClient({ fetcher: async () => jsonResponse({}, 200, 'text/html') })
  await assert.rejects(client.listTasks(), /not connected/)
})
test('HTTP errors are visible', async () => {
  const client = createApiClient({ fetcher: async () => jsonResponse({}, 500) })
  await assert.rejects(client.listTasks(), /HTTP 500/)
})
test('invalid JSON is rejected instead of interpreted as success', async () => {
  const client = createApiClient({ fetcher: async () => ({ ...jsonResponse({}), json: async () => { throw new Error('Invalid JSON') } }) })
  await assert.rejects(client.listTasks(), /Invalid JSON/)
})
test('POST accepts only task ID, stays same-origin, and is not retried', async () => {
  const calls = []
  const client = createApiClient({ fetcher: async (url, options) => {
    calls.push([url, options]); return jsonResponse({}, 503)
  } })
  await assert.rejects(client.startRun(taskId), /503/)
  assert.equal(calls.length, 1); assert.equal(calls[0][0], '/api/runs')
  assert.deepEqual(JSON.parse(calls[0][1].body), { task_id: taskId })
})
test('request timeout aborts transport and reports unknown server state', async () => {
  const client = createApiClient({ requestTimeout: 5, fetcher: async (_url, { signal }) =>
    new Promise((_resolve, reject) => signal.addEventListener('abort', () => reject(new Error('Aborted')))) })
  await assert.rejects(client.listTasks(), /超时或停止/)
})
test('polling waits for matching completed evidence', async () => {
  const report = sample('fixed'); let count = 0
  const client = createApiClient({ sleep: immediate, fetcher: async () => jsonResponse(++count === 1
    ? { ...snapshot(report), state: 'RUNNING', verification: null } : snapshot(report)) })
  const result = await client.waitForRun(report.run_id, taskId)
  assert.equal(result.verification.status, 'VERIFIED'); assert.equal(count, 2)
})
test('mismatched run identity cannot supply evidence', async () => {
  const report = sample('fixed')
  const client = createApiClient({ fetcher: async () => jsonResponse(snapshot(report)) })
  await assert.rejects(client.waitForRun('different-id', taskId), /mismatch/)
})
test('completed response requires matching verification task ID', async () => {
  const report = sample('fixed'); const data = snapshot(report); data.verification.task.task_id = 'wrong'
  const client = createApiClient({ fetcher: async () => jsonResponse(data) })
  await assert.rejects(client.waitForRun(data.run_id, taskId), /matching verification/)
})
test('server job IDs may differ from the existing verifier-generated report ID', async () => {
  const report = sample('fixed'); const data = { ...snapshot(report), run_id: 'server-job-id' }
  const client = createApiClient({ fetcher: async () => jsonResponse(data) })
  const result = await client.waitForRun('server-job-id', taskId)
  assert.equal(result.verification.run_id, report.run_id)
})
test('live proposal empty state never claims a fixed sample was generated', () => {
  assert.match(traceFor(null, null, 'LIVE')[0].detail, /等待后端/)
})
test('inconclusive evidence retains its verdict without inventing a pass', () => {
  const report = sample('original'); report.status = 'INCONCLUSIVE'
  report.executions[0].status = 'ERROR'; report.executions[0].exit_code = null
  assert.equal(validateReport(report, taskId).status, 'INCONCLUSIVE')
  assert.equal(traceFor(report, null)[3].state, 'ERROR')
})
test('polling deadline produces no fabricated verdict', async () => {
  let time = 0
  const report = sample('fixed')
  const client = createApiClient({ now: () => time, runTimeout: 10, sleep: async () => { time += 20 },
    fetcher: async () => jsonResponse({ ...snapshot(report), state: 'RUNNING' }) })
  await assert.rejects(client.waitForRun(report.run_id, taskId), /状态未知/)
})
