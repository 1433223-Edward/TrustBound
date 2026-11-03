import { computed, reactive, readonly } from 'vue'
import { traceFor, validateReport } from '../api/adapter.js'

export function createWorkspace({ demo, client, sleep = ms => new Promise(resolve => setTimeout(resolve, ms)) }) {
  const state = reactive({ mode: 'DEMO', tasks: demo.tasks, taskId: demo.tasks[0].spec.task_id,
    scenario: 'public_only', phase: 'IDLE', connection: 'DISCONNECTED', error: '', report: null, proposal: null, candidate: '' })
  let generation = 0
  let controller
  const task = computed(() => state.tasks.find(item => item.spec.task_id === state.taskId))
  const busy = computed(() => state.phase === 'LOADING')
  const trace = computed(() => traceFor(state.report, state.proposal, state.mode))

  function reset() {
    generation++
    controller?.abort()
    Object.assign(state, { phase: 'IDLE', error: '', report: null, proposal: null, candidate: '' })
  }
  function selectTask(id) {
    if (!state.tasks.some(item => item.spec.task_id === id)) throw new Error('Unknown task.')
    reset()
    state.taskId = id
  }
  function selectScenario(id) {
    if (!demo.reports.some(item => item.candidate_id === id)) throw new Error('Unknown sample.')
    reset()
    state.scenario = id
  }
  function selectMode(mode) {
    if (!['DEMO', 'LIVE'].includes(mode)) throw new Error('Unknown mode.')
    reset()
    state.mode = mode
    state.tasks = demo.tasks
    state.taskId = demo.tasks[0].spec.task_id
    state.connection = 'DISCONNECTED'
  }

  async function replay() {
    if (state.mode !== 'DEMO' || busy.value) return
    reset()
    const token = generation
    state.phase = 'LOADING'
    try {
      await sleep(450)
      if (token !== generation) return
      const report = structuredClone(demo.reports.find(item => item.candidate_id === state.scenario && item.task.task_id === state.taskId))
      validateReport(report, state.taskId)
      state.report = report
      state.candidate = demo.candidates[state.scenario] || ''
      state.phase = 'READY'
    } catch (error) {
      if (token === generation) { state.phase = 'ERROR'; state.error = error.message }
    }
  }

  async function runAgent() {
    if (busy.value) return
    reset()
    if (state.mode !== 'LIVE') {
      state.phase = 'ERROR'
      state.error = 'Backend not connected. Run Agent 需要真实 API；请切换 Live API 模式，或使用独立的 Demo Replay。'
      return
    }
    const token = generation
    controller = new AbortController()
    const signal = controller.signal
    state.phase = 'LOADING'
    state.connection = 'CONNECTING'
    try {
      const tasks = await client.listTasks(signal)
      if (token !== generation) return
      if (!tasks.some(item => item.spec.task_id === state.taskId)) throw new Error('Selected task is not offered by backend.')
      state.tasks = tasks
      state.connection = 'CONNECTED'
      const runId = await client.startRun(state.taskId, signal)
      if (token !== generation) return
      const snapshot = await client.waitForRun(runId, state.taskId, signal)
      // Discard stale responses when mode/task changes; this never cancels server work.
      if (token !== generation) return
      validateReport(snapshot.verification, state.taskId)
      state.report = snapshot.verification
      state.proposal = snapshot.proposal
      state.candidate = snapshot.proposal?.files?.['billing.py'] || ''
      state.phase = 'READY'
    } catch (error) {
      if (token === generation) {
        state.phase = 'ERROR'
        state.error = error.message || 'Unknown API error.'
        state.connection = 'UNAVAILABLE'
      }
    }
  }
  return { state: readonly(state), task, busy, trace, selectTask, selectScenario, selectMode, replay, runAgent }
}
