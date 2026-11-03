<script setup>
import { computed, ref, watch } from 'vue'
import { diffLines } from '../api/adapter.js'
import CodePanel from './CodePanel.vue'
const props = defineProps({ task: Object, report: Object, candidate: String, mode: String })
const tab = ref('diff')
watch(() => props.report?.run_id, () => { tab.value = 'diff' })
const changes = computed(() => diffLines(props.report?.diff || ''))
const added = computed(() => changes.value.filter(line => line.kind === 'added').length)
const removed = computed(() => changes.value.filter(line => line.kind === 'removed').length)
</script>

<template>
  <main class="code-workspace">
    <div class="workspace-heading"><div><span class="eyebrow">CODE WORKSPACE</span><span class="breadcrumb">fixtures / billing / <b>billing.py</b></span></div><span class="read-only"><span aria-hidden="true">⌑</span> Read-only</span></div>
    <div class="code-panes">
      <section class="code-pane"><div class="pane-heading"><h2><span class="pane-dot original"></span>Original Code</h2><span class="mono muted">Python</span></div><div class="file-tab"><span class="python-small">py</span>{{ task.original.path }}<span class="muted">original</span></div><CodePanel :source="task.original.content" /><div class="pane-footer">原始样例 · 不会写入宿主项目</div></section>
      <section class="code-pane proposed"><div class="pane-heading"><h2><span class="pane-dot proposed-dot"></span>Proposed Changes</h2><span v-if="report?.diff" class="diff-count mono"><em>+{{ added }}</em><b>−{{ removed }}</b></span></div>
        <div class="file-tab"><span class="python-small">py</span>billing.py<div class="segmented mini"><button :class="{ selected: tab === 'diff' }" @click="tab = 'diff'">Diff</button><button :class="{ selected: tab === 'after' }" @click="tab = 'after'">After</button></div></div>
        <div v-if="!report" class="empty-state proposal-empty"><div class="empty-symbol" aria-hidden="true">＋</div><h3>No proposal yet</h3><p>{{ mode === 'DEMO' ? '回放后查看固定候选及差异。' : '执行后查看候选修改与差异。' }}</p><span class="micro">{{ mode === 'DEMO' ? 'Demo Replay 只加载固定候选。' : '仅后端可调用模型并独立验收。' }}</span></div>
        <div v-else-if="tab === 'diff' && report.diff" class="diff-scroll" tabindex="0" aria-label="候选代码差异"><div v-for="(line, index) in changes" :key="index" class="diff-line" :class="line.kind"><span class="diff-gutter">{{ line.kind === 'added' ? '+' : line.kind === 'removed' ? '−' : ' ' }}</span><code>{{ ['added', 'removed'].includes(line.kind) ? line.text.slice(1) : line.text }}</code></div></div>
        <div v-else-if="tab === 'diff'" class="empty-state"><h3>No code changes</h3><p>该记录未包含代码差异。</p></div>
        <CodePanel v-else-if="candidate" :source="candidate" />
        <div v-else class="empty-state"><h3>Source not recorded</h3><p>记录只有 Diff，没有候选全文。</p></div>
        <div class="pane-footer"><span v-if="mode === 'DEMO'">{{ report ? '固定 Fixture · 非 LLM 生成' : '等待显式历史回放' }}</span><span v-else>模型建议不等于验证成功</span></div>
      </section>
    </div>
  </main>
</template>
