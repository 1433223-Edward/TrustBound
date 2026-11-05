<script setup>
import { computed, ref, watch } from 'vue'
import demo from './data/demo.json'
import { createApiClient } from './api/client.js'
import { createWorkspace } from './state/workspace.js'
import StatusBadge from './components/StatusBadge.vue'
import TaskPanel from './components/TaskPanel.vue'
import CodeWorkspace from './components/CodeWorkspace.vue'
import ExecutionTrace from './components/ExecutionTrace.vue'
import EvidencePanel from './components/EvidencePanel.vue'
import CustomTaskPanel from './components/CustomTaskPanel.vue'

const client = createApiClient()
const workspace = createWorkspace({ demo, client })
const { state, task, busy, trace } = workspace
const customEnabled = ref(false)
watch(() => state.mode, async (mode, _, onCleanup) => {
  customEnabled.value = false
  if (mode !== 'LIVE') return
  const controller = new AbortController()
  onCleanup(() => controller.abort())
  try {
    const health = await client.health(controller.signal)
    if (!controller.signal.aborted) customEnabled.value = health.custom_task?.enabled === true
  } catch { /* Billing retains its own API status and controls. */ }
})
const activity = computed(() => busy.value ? state.mode === 'DEMO' ? 'Loading sample' : (state.runState || 'Connecting to API')
  : state.phase === 'ERROR' ? 'Request error' : state.report ? state.mode === 'DEMO' ? 'Sample loaded' : (state.recoveryReport?.final_status || state.finalDecision?.status || state.report.status) : 'Ready')
</script>

<template>
  <div class="app-shell">
    <header class="topbar"><a class="brand" href="/" aria-label="TrustBound 工作区"><svg viewBox="0 0 32 36" fill="none" aria-hidden="true"><path d="M16 2 29 8v11c0 7-8 12-13 15C11 31 3 26 3 19V8L16 2Z" stroke="currentColor" stroke-width="2"/><path d="m10 18 4 4 8-9" stroke="currentColor" stroke-width="2.2"/></svg><strong>TrustBound</strong><span class="brand-tag">WORKSPACE</span></a><div class="top-task"><span class="muted">/</span>{{ task.title }}<StatusBadge :status="state.report ? (state.recoveryReport?.final_status || state.finalDecision?.status || state.report.status) : state.phase" :label="activity" /></div><div class="top-actions"><span class="connection"><i :class="{ online: state.connection === 'CONNECTED' }"></i>{{ state.connection === 'CONNECTED' ? 'API connected' : state.connection === 'CONNECTING' ? 'Connecting…' : 'Backend not connected' }}</span><button class="run-button" :disabled="busy" @click="workspace.runAgent"><span :class="{ spinner: busy && state.mode === 'LIVE' }">{{ busy && state.mode === 'LIVE' ? '' : '▷' }}</span>Run Agent</button></div></header>
    <div class="mode-bar"><div class="segmented mode-switch" role="group" aria-label="数据模式"><button :aria-pressed="state.mode === 'DEMO'" :class="{ selected: state.mode === 'DEMO' }" @click="workspace.selectMode('DEMO')">Demo Replay</button><button :aria-pressed="state.mode === 'LIVE'" :class="{ selected: state.mode === 'LIVE' }" @click="workspace.selectMode('LIVE')">Local API</button></div><p v-if="state.mode === 'DEMO'"><span class="sample-label">SAMPLE</span>真实历史报告回放 · 固定候选 · 不调用 LLM，不执行容器</p><p v-else><span class="live-label">LOCAL API</span>{{ state.executionMode === 'fixture' ? '固定候选 · 真实 Docker · Executor 无模型调用' : state.executionMode === 'offline_executor' ? '模拟模型响应 · 真实 Executor / Docker / 验收' : 'Vultr 实时推理 · 仅后端持有凭据' }}<span v-if="state.adversarialMode !== 'off'"> · Adversary {{ state.adversarialMode === 'offline' ? 'OFFLINE 模拟提议' : 'Vultr 独立模型（待实际请求）' }}</span><span v-if="state.recoveryMode !== 'off'"> · Recovery {{ state.recoveryMode === 'offline' ? 'OFFLINE / MOCK' : 'Vultr（需单独授权）' }}</span></p><span class="version mono">LOCAL / v0.1</span></div>
    <div v-if="state.error" class="error-banner" role="alert"><strong>Request not completed</strong><span>{{ state.error }}</span></div>
    <div class="workspace-grid" :aria-busy="busy">
      <TaskPanel :task="task" :tasks="state.tasks" :mode="state.mode" :scenario="state.scenario" :execution-mode="state.executionMode" :adversarial-mode="state.adversarialMode" :adversarial-fixture="state.adversarialFixture" :recovery-mode="state.recoveryMode" :recovery-fixture="state.recoveryFixture" :busy="busy" @task="workspace.selectTask" @scenario="workspace.selectScenario" @execution-mode="workspace.selectExecutionMode" @adversarial-mode="workspace.selectAdversarialMode" @adversarial-fixture="workspace.selectAdversarialFixture" @recovery-mode="workspace.selectRecoveryMode" @recovery-fixture="workspace.selectRecoveryFixture" @replay="workspace.replay" @run="workspace.runAgent" />
      <CodeWorkspace :recovery-attempt="state.recoveryReport?.attempts?.[state.recoveryReport.validated_attempt_index]" :task="task" :report="state.report" :candidate="state.candidate" :execution-mode="state.executionMode" :mode="state.mode" />
      <ExecutionTrace :stages="trace" :mode="state.mode" :report="state.report" />
      <EvidencePanel :inference-usage="state.inferenceUsage" :recovery-report="state.recoveryReport" :adversarial-report="state.adversarialReport" :final-decision="state.finalDecision" :execution-mode="state.executionMode" :report="state.report" :mode="state.mode" />
    </div>
    <CustomTaskPanel v-if="customEnabled" :client="client" />
    <footer class="statusbar"><span><span class="status-light"></span>Trusted control · isolated execution</span><span aria-live="polite">{{ activity }}{{ state.mode === 'DEMO' ? ' · Sample mode' : ' · ' + state.executionMode }}</span><span class="mono">Python fixture <span class="footer-divider">/</span> billing-v1</span></footer>
  </div>
</template>
