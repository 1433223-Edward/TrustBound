<script setup>
import { computed } from 'vue'
import demo from './data/demo.json'
import { createApiClient } from './api/client.js'
import { createWorkspace } from './state/workspace.js'
import StatusBadge from './components/StatusBadge.vue'
import TaskPanel from './components/TaskPanel.vue'
import CodeWorkspace from './components/CodeWorkspace.vue'
import ExecutionTrace from './components/ExecutionTrace.vue'
import EvidencePanel from './components/EvidencePanel.vue'

const workspace = createWorkspace({ demo, client: createApiClient() })
const { state, task, busy, trace } = workspace
const activity = computed(() => busy.value ? state.mode === 'DEMO' ? 'Loading sample' : 'Waiting for API'
  : state.phase === 'ERROR' ? 'Request error' : state.report ? state.mode === 'DEMO' ? 'Sample loaded' : state.report.status : 'Ready')
</script>

<template>
  <div class="app-shell">
    <header class="topbar"><a class="brand" href="/" aria-label="TrustBound 工作区"><svg viewBox="0 0 32 36" fill="none" aria-hidden="true"><path d="M16 2 29 8v11c0 7-8 12-13 15C11 31 3 26 3 19V8L16 2Z" stroke="currentColor" stroke-width="2"/><path d="m10 18 4 4 8-9" stroke="currentColor" stroke-width="2.2"/></svg><strong>TrustBound</strong><span class="brand-tag">WORKSPACE</span></a><div class="top-task"><span class="muted">/</span>{{ task.title }}<StatusBadge :status="state.phase" :label="activity" /></div><div class="top-actions"><span class="connection"><i :class="{ online: state.connection === 'CONNECTED' }"></i>{{ state.connection === 'CONNECTED' ? 'API connected' : state.connection === 'CONNECTING' ? 'Connecting…' : 'Backend not connected' }}</span><button class="run-button" :disabled="busy" @click="workspace.runAgent"><span :class="{ spinner: busy && state.mode === 'LIVE' }">{{ busy && state.mode === 'LIVE' ? '' : '▷' }}</span>Run Agent</button></div></header>
    <div class="mode-bar"><div class="segmented mode-switch" role="group" aria-label="数据模式"><button :aria-pressed="state.mode === 'DEMO'" :class="{ selected: state.mode === 'DEMO' }" @click="workspace.selectMode('DEMO')">Demo Replay</button><button :aria-pressed="state.mode === 'LIVE'" :class="{ selected: state.mode === 'LIVE' }" @click="workspace.selectMode('LIVE')">Live API</button></div><p v-if="state.mode === 'DEMO'"><span class="sample-label">SAMPLE</span>真实历史报告回放 · 固定候选 · 不调用 LLM，不执行容器</p><p v-else><span class="live-label">LIVE API</span>仅连接同源 FastAPI · 当前仓库尚无 Web API</p><span class="version mono">LOCAL / v0.1</span></div>
    <div v-if="state.error" class="error-banner" role="alert"><strong>Request not completed</strong><span>{{ state.error }}</span></div>
    <div class="workspace-grid" :aria-busy="busy">
      <TaskPanel :task="task" :tasks="state.tasks" :mode="state.mode" :scenario="state.scenario" :busy="busy" @task="workspace.selectTask" @scenario="workspace.selectScenario" @replay="workspace.replay" @run="workspace.runAgent" />
      <CodeWorkspace :task="task" :report="state.report" :candidate="state.candidate" :mode="state.mode" />
      <ExecutionTrace :stages="trace" :mode="state.mode" :report="state.report" />
      <EvidencePanel :report="state.report" :mode="state.mode" />
    </div>
    <footer class="statusbar"><span><span class="status-light"></span>Trusted control · isolated execution</span><span aria-live="polite">{{ activity }}{{ state.mode === 'DEMO' ? ' · Sample mode' : ' · Live API mode' }}</span><span class="mono">Python fixture <span class="footer-divider">/</span> billing-v1</span></footer>
  </div>
</template>
