import { computed, reactive, readonly } from 'vue'
import { traceFor, validateReport, validateAdversarialEnvelope, validateRecoveryReport } from '../api/adapter.js'

export function createWorkspace({ demo, client, sleep = ms => new Promise(resolve => setTimeout(resolve, ms)) }) {
  const state = reactive({ mode: 'DEMO', tasks: demo.tasks, taskId: demo.tasks[0].spec.task_id,
    scenario: 'public_only', executionMode: 'fixture', runState: '', llmSource: 'NONE',
    adversarialMode: 'off', adversarialFixture: 'standard', adversarialReport: null, finalDecision: null,
    recoveryMode: 'off', recoveryFixture: 'fixed', recoveryReport: null, inferenceUsage: null,
    phase: 'IDLE', connection: 'DISCONNECTED', error: '', report: null, proposal: null, candidate: '' })
  let generation = 0
  let controller
  const task = computed(() => state.tasks.find(item => item.spec.task_id === state.taskId))
  const busy = computed(() => state.phase === 'LOADING')
  const trace = computed(() => traceFor(state.report, state.proposal, state.mode, state.executionMode, state.recoveryReport?.final_status ? { ...state.finalDecision, status: state.recoveryReport.final_status, reason: state.recoveryReport.stop_reason } : state.finalDecision))

  function reset() {
    generation++
    controller?.abort()
    Object.assign(state, { phase: 'IDLE', runState: '', llmSource: 'NONE', error: '', report: null, proposal: null, candidate: '', adversarialReport: null, finalDecision: null, recoveryReport: null, inferenceUsage: null })
  }
  function selectTask(id) {
    if (!state.tasks.some(item => item.spec.task_id === id)) throw new Error('Unknown task.')
    reset()
    state.taskId = id
  }
  function selectScenario(id) {
    if (!demo.reports.some(item => item.candidate_id === id) && !(state.mode === 'LIVE' && id === 'double_rounding')) throw new Error('Unknown sample.')
    reset()
    state.scenario = id
  }
  function selectMode(mode) {
    if (!['DEMO', 'LIVE'].includes(mode)) throw new Error('Unknown mode.')
    reset()
    state.mode = mode
    if (mode === 'DEMO' && !demo.reports.some(item => item.candidate_id === state.scenario)) state.scenario = 'public_only'
    state.tasks = demo.tasks
    state.taskId = demo.tasks[0].spec.task_id
    state.connection = 'DISCONNECTED'
  }

  function selectExecutionMode(mode) {
    if (!['fixture', 'offline_executor', 'live_executor'].includes(mode)) throw new Error('Unknown execution mode.')
    reset()
    state.executionMode = mode
  }

  function selectAdversarialMode(mode) {
    if (!['off', 'offline', 'live'].includes(mode)) throw new Error('Unknown adversarial mode.')
    reset()
    state.adversarialMode = mode
    state.adversarialFixture = 'standard'
  }
  function selectAdversarialFixture(profile) {
    if (!['standard', 'invalid', 'timeout', 'failure'].includes(profile)) throw new Error('Unknown adversarial fixture.')
    reset()
    state.adversarialFixture = profile
  }

  function selectRecoveryMode(mode) {
    if (!['off', 'offline', 'live'].includes(mode)) throw new Error('Unknown recovery mode.')
    reset(); state.recoveryMode = mode; state.recoveryFixture = 'fixed'
    if (mode !== 'off' && state.adversarialMode === 'off') state.adversarialMode = 'offline'
  }
  function selectRecoveryFixture(profile) {
    if (!['fixed', 'exhausted', 'unauthorized', 'invalid_json', 'empty', 'failure', 'timeout'].includes(profile)) throw new Error('Unknown recovery fixture.')
    reset(); state.recoveryFixture = profile
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
      state.error = 'Demo Replay 不会启动任务；请切换 Local API 后执行真实 Docker，或使用独立的历史回放。'
      return
    }
    const token = generation
    controller = new AbortController()
    const signal = controller.signal
    state.phase = 'LOADING'
    state.connection = 'CONNECTING'
    try {
      await client.health(signal)
      const tasks = await client.listTasks(signal)
      if (token !== generation) return
      if (!tasks.some(item => item.spec.task_id === state.taskId)) throw new Error('Selected task is not offered by backend.')
      state.tasks = tasks
      state.connection = 'CONNECTED'
      const detail = await client.getTask(state.taskId, signal)
      if (token !== generation) return
      if (detail.spec?.task_id !== state.taskId || typeof detail.original?.content !== 'string') throw new Error('Invalid task details.')
      state.tasks = tasks.map(item => item.spec.task_id === state.taskId ? detail : item)
      const options = { mode: state.executionMode }
      if (state.adversarialMode !== 'off') options.adversarial_mode = state.adversarialMode
      if (state.adversarialMode === 'offline') options.adversarial_fixture = state.adversarialFixture
      if (state.executionMode === 'fixture') options.candidate_id = state.scenario
      if (state.recoveryMode !== 'off') options.recovery_mode = state.recoveryMode
      if (state.recoveryMode === 'offline') options.recovery_fixture = state.recoveryFixture
      const runId = await client.startRun(state.taskId, signal, options)
      if (token !== generation) return
      const snapshot = await client.waitForRun(runId, state.taskId, signal, {
        mode: state.executionMode, candidateId: state.scenario,
        onUpdate: data => { if (token === generation) {
          state.runState = data.state + (state.recoveryMode !== 'off' ? ` · Attempt ${data.current_attempt ?? 0} / 2` : '')
          if (data.inference_usage) state.inferenceUsage = data.inference_usage
          if (data.recovery_report?.run_id === runId) state.recoveryReport = data.recovery_report
        } },
      })
      // Discard stale responses when mode/task changes; this never cancels server work.
      if (token !== generation) return
      validateReport(snapshot.verification, state.taskId)
      validateAdversarialEnvelope(snapshot, state.adversarialMode)
      validateRecoveryReport(snapshot, state.recoveryMode)
      state.recoveryReport = snapshot.recovery_report || null
      state.inferenceUsage = snapshot.inference_usage || null
      state.report = snapshot.verification
      state.adversarialReport = snapshot.adversarial_report || null
      state.finalDecision = snapshot.final_decision || null
      state.proposal = snapshot.proposal
      state.llmSource = snapshot.llm_source || 'NONE'
      state.candidate = snapshot.candidate?.content || snapshot.proposal?.files?.['billing.py'] || ''
      state.phase = 'READY'
    } catch (error) {
      if (token === generation) {
        state.phase = 'ERROR'
        state.error = error.message || 'Unknown API error.'
        state.connection = state.connection === 'CONNECTED' && /^HTTP \d{3}/.test(state.error) ? 'CONNECTED' : 'UNAVAILABLE'
      }
    }
  }
  return { state: readonly(state), task, busy, trace, selectTask, selectScenario, selectMode, selectExecutionMode, selectAdversarialMode, selectAdversarialFixture, selectRecoveryMode, selectRecoveryFixture, replay, runAgent }
}
