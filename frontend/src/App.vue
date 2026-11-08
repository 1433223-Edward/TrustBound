<script setup>
import { statusText, t } from './i18n.js'
import { computed, nextTick, ref, watch } from 'vue'
import demo from './data/demo.json'
import { createApiClient } from './api/client.js'
import { createWorkspace } from './state/workspace.js'
import StatusBadge from './components/StatusBadge.vue'
import WorkbenchBrand from './components/WorkbenchBrand.vue'
import TaskPanel from './components/TaskPanel.vue'
import CodeWorkspace from './components/CodeWorkspace.vue'
import WorkspaceChat from './components/WorkspaceChat.vue'
import AgentActivity from './components/AgentActivity.vue'
import EvidencePanel from './components/EvidencePanel.vue'
import CustomTaskPanel from './components/CustomTaskPanel.vue'

const client = createApiClient()
const emit = defineEmits(['edit-copy'])
const workspace = createWorkspace({ demo, client })
const { state, task, busy } = workspace
const customEnabled = ref(false)
const liveAvailable = ref(false)
const privateApi = ref(false)
const copyAvailable = ref(false)
const selectedFile = ref(task.value.original.path)
const selectedAttempt = ref(null)
const evidencePanel = ref(null)
async function viewEvidence(row) {
  selectedAttempt.value = row.attempt ?? null
  await nextTick()
  evidencePanel.value?.showEvidence(row)
}
const files = computed(() => [task.value.original, demo.publicTests].filter(Boolean))
const file = computed(() => files.value.find(item => item.path === selectedFile.value) ?? task.value.original)
const activeAttempt = computed(() => {
  const recovery = state.recoveryReport
  return recovery?.attempts?.[selectedAttempt.value ?? recovery.validated_attempt_index]
})
const isCandidateFile = computed(() => file.value.path === task.value.original.path)
const displayedReport = computed(() => isCandidateFile.value ? (activeAttempt.value ? activeAttempt.value.verification : state.report) : null)
const billingCandidate = computed(() => activeAttempt.value ? activeAttempt.value.candidate?.content || '' : state.candidate)
const displayedCandidate = computed(() => isCandidateFile.value ? billingCandidate.value : '')
watch(() => state.report?.run_id, () => { selectedAttempt.value = null })
const developerRequested = import.meta.env.DEV || new URLSearchParams(location.search).get('developer') === '1'
const developerTools = computed(() => privateApi.value && developerRequested)
watch(() => state.mode, async (mode, _, onCleanup) => {
  customEnabled.value = false
  liveAvailable.value = false
  privateApi.value = false
  const controller = new AbortController()
  onCleanup(() => controller.abort())
  try {
    const health = await client.health(controller.signal)
    if (!controller.signal.aborted) {
      copyAvailable.value = health.workspace?.enabled === true && health.public_demo === false
      if (mode !== 'LIVE') return
      privateApi.value = health.public_demo === false
      liveAvailable.value = privateApi.value && health.modes?.live_executor?.enabled === true
      customEnabled.value = developerTools.value && health.custom_task?.enabled === true
      if (!privateApi.value && !busy.value) {
        if (state.executionMode === 'live_executor') workspace.selectExecutionMode('fixture')
        if (state.adversarialMode === 'live' || state.adversarialFixture !== 'standard') workspace.selectAdversarialMode('off')
        if (state.recoveryMode !== 'off') workspace.selectRecoveryMode('off')
      }
    }
  } catch { /* Billing retains its own API status and controls. */ }
}, { immediate: true })
function editCopy() {
  emit('edit-copy', {
    files: files.value.map(item => ({ path: item.path,
      content: item.path === task.value.original.path ? billingCandidate.value || task.value.original.content : item.content })),
    plan: {
      goal: 'Convert decimal amounts to cents. Round to the nearest cent with half cents away from zero.',
      entrypoint: 'billing.py:to_cents', allowed_write_paths: ['billing.py'],
      public_cases: [{ input: '1.239', expected: 124 }, { input: '1.23', expected: 123 }],
      acceptance_cases: [{ input: '1.005', expected: 101 }, { input: '-1.005', expected: -101 }],
    },
  })
}
function playCase(id) {
  if (busy.value) return
  workspace.selectScenario(id)
  return workspace.replay()
}

function selectCase(id) {
  workspace.selectScenario(id)
  if (!developerTools.value) workspace.selectAdversarialMode(id === 'double_rounding' ? 'offline' : 'off')
}

function selectExperience(mode) {
  workspace.selectExecutionMode(mode)
  if (!developerTools.value) workspace.selectAdversarialMode(mode === 'fixture' && state.scenario === 'double_rounding' ? 'offline' : 'off')
}
const activity = computed(() => busy.value ? state.mode === 'DEMO' ? t("Loading sample", "正在加载历史记录") : (state.runState ? statusText(state.runState) : t("Connecting to API", "正在连接 API"))
  : state.phase === 'ERROR' ? t("Request error", "请求错误") : state.report ? state.mode === 'DEMO' ? t("Sample loaded", "已加载历史记录") : statusText(state.recoveryReport?.final_status || state.finalDecision?.status || state.report.status) : t("Ready", "就绪"))
</script>

<template>
  <div class="app-shell">
    <header class="topbar"><WorkbenchBrand /><div class="top-task"><span class="muted">/</span>{{ task.title }}<StatusBadge :status="state.report ? (state.recoveryReport?.final_status || state.finalDecision?.status || state.report.status) : state.phase" :label="activity" /></div><div class="top-actions"><span class="connection"><i :class="{ online: state.connection === 'CONNECTED' }"></i>{{ state.connection === 'CONNECTED' ? $t("API connected", "API 已连接") : state.connection === 'CONNECTING' ? $t("Connecting…", "连接中…") : $t("Backend not connected", "后端未连接") }}</span><button class="run-button" :disabled="busy" @click="state.mode === 'DEMO' ? workspace.replay() : workspace.runAgent()"><span :class="{ spinner: busy && state.mode === 'LIVE' }">{{ busy && state.mode === 'LIVE' ? '' : '▷' }}</span>{{ state.mode === 'DEMO' ? $t('Replay case', '回放案例') : $t('Run Agent', '运行 Agent') }}</button></div></header>
    <div class="mode-bar"><div class="segmented mode-switch" role="group" :aria-label="$t('Data mode', '数据模式')"><button :aria-pressed="state.mode === 'DEMO'" :class="{ selected: state.mode === 'DEMO' }" @click="workspace.selectMode('DEMO')">{{ $t("Demo Replay", "演示回放") }}</button><button :aria-pressed="state.mode === 'LIVE'" :class="{ selected: state.mode === 'LIVE' }" @click="workspace.selectMode('LIVE')">{{ $t("Local API", "本地 API") }}</button></div><p v-if="state.mode === 'DEMO'"><span class="sample-label">SAMPLE</span>{{ $t("Recorded report · fixed candidate · no new inference or container", "真实历史报告回放 · 固定候选 · 不调用 LLM，不执行容器") }}</p><p v-else><span class="live-label">LOCAL API</span>{{ state.executionMode === 'fixture' ? $t("Fixed candidate · real Docker · no inference", "固定候选 · 真实 Docker · Executor 无模型调用") : state.executionMode === 'offline_executor' ? $t("Simulated proposal · real Executor, Docker and verification", "模拟模型响应 · 真实 Executor / Docker / 验收") : $t("Live Vultr inference · backend-held credentials", "Vultr 实时推理 · 仅后端持有凭据") }}<span v-if="state.adversarialMode !== 'off'"> · Adversary {{ state.adversarialMode === 'offline' ? $t("Offline simulated proposal", "OFFLINE 模拟提议") : $t("Independent Vultr model · pending request", "Vultr 独立模型（待实际请求）") }}</span><span v-if="state.recoveryMode !== 'off'"> · Recovery {{ state.recoveryMode === 'offline' ? 'OFFLINE / MOCK' : $t("Vultr · separate authorization", "Vultr（需单独授权）") }}</span></p><span class="version mono">LOCAL / v0.1</span></div>
    <div v-if="state.error" class="error-banner" role="alert"><strong>{{ $t("Request not completed", "请求未完成") }}</strong><span>{{ $message(state.error) }}</span></div>
    <div class="workspace-grid" :aria-busy="busy">
      <TaskPanel :task="task" :mode="state.mode" :scenario="state.scenario" :execution-mode="state.executionMode"
        :adversarial-mode="state.adversarialMode" :adversarial-fixture="state.adversarialFixture"
        :recovery-mode="state.recoveryMode" :recovery-fixture="state.recoveryFixture" :busy="busy"
        :developer-tools="developerTools" :live-available="liveAvailable" :files="files" :selected-file="selectedFile"
        :record="activeAttempt?.verification ?? state.report" :copy-available="copyAvailable" :recovery-report="state.recoveryReport"
        :selected-attempt="activeAttempt?.attempt_index" @select-file="selectedFile = $event"
        @select-attempt="selectedAttempt = $event" @edit-copy="editCopy" @scenario="selectCase"
        @execution-mode="selectExperience" @adversarial-mode="workspace.selectAdversarialMode"
        @adversarial-fixture="workspace.selectAdversarialFixture" @recovery-mode="workspace.selectRecoveryMode"
        @recovery-fixture="workspace.selectRecoveryFixture" @replay-case="playCase" @run="workspace.runAgent" />
      <CodeWorkspace :recovery-attempt="activeAttempt" :task="{ original: file }" :report="displayedReport"
        :candidate="displayedCandidate" :single="!isCandidateFile" :execution-mode="state.executionMode" :mode="state.mode" />
      <aside class="trace-panel project-chat-panel"><WorkspaceChat read-only><template #activity><AgentActivity inline @evidence="viewEvidence" :billing="{ report: state.report, adversarial: state.adversarialReport,
        recovery: state.recoveryReport, decision: state.finalDecision, proposal: state.proposal,
        mode: state.mode, executionMode: state.executionMode }" /></template></WorkspaceChat></aside>
      <EvidencePanel ref="evidencePanel" :inference-usage="state.inferenceUsage" :recovery-report="state.recoveryReport" :adversarial-report="state.adversarialReport" :final-decision="state.finalDecision" :execution-mode="state.executionMode" :report="state.report" :mode="state.mode" />
    </div>
    <CustomTaskPanel v-if="customEnabled" :client="client" />
    <footer class="statusbar"><span><span class="status-light"></span>{{ $t("Trusted control · isolated execution", "可信控制 · 隔离执行") }}</span><span aria-live="polite">{{ activity }}{{ state.mode === 'DEMO' ? ' · ' + $t('Sample mode', '回放模式') : ' · ' + state.executionMode }}</span><span class="mono">Python fixture <span class="footer-divider">/</span> billing-v1</span></footer>
  </div>
</template>
