<script setup>
import { computed, inject, ref, watch } from 'vue'
import { diffLines } from '../api/adapter.js'
import CodePanel from './CodePanel.vue'
const props = defineProps({ task: Object, report: Object, candidate: String, mode: String, executionMode: String,
  recoveryAttempt: Object, single: Boolean, editable: Boolean, draft: String, versionLabel: String, versionComparison: Boolean })
const emit = defineEmits(['edit'])
const original = computed(() => props.task.original)
const python = computed(() => original.value.path.endsWith('.py'))
const preferences = inject('workbenchPreferences')
const tab = ref('diff')
const hasCandidate = computed(() => !props.single && Boolean(props.report?.diff || props.versionComparison || (props.candidate && props.candidate !== original.value.content)) || props.draft !== undefined)
const showOriginal = computed(() => !hasCandidate.value || preferences?.value.codeView !== 'candidate')
const showCandidate = computed(() => (hasCandidate.value && preferences?.value.codeView !== 'original') || tab.value === 'edit')
watch(() => props.draft, value => { if (value === undefined && tab.value === 'edit' && !props.editable) tab.value = 'diff' })
watch([() => props.report?.run_id, () => original.value.path], () => { tab.value = 'diff' })
const changes = computed(() => diffLines(props.report?.diff || ''))
const added = computed(() => changes.value.filter(line => line.kind === 'added').length)
const removed = computed(() => changes.value.filter(line => line.kind === 'removed').length)
</script>

<template>
  <section class="code-workspace">
    <div class="workspace-heading"><div><span class="eyebrow">{{ $t("CODE WORKSPACE", "代码工作区") }}</span><span class="breadcrumb">{{ mode === 'WORKSPACE' ? $t('Project', '项目') : 'fixtures / billing' }} / <b>{{ original.path }}</b></span></div><button v-if="editable" class="primary-button" type="button" @click="tab = tab === 'edit' ? 'after' : 'edit'">{{ tab === 'edit' ? $t('View code', '查看代码') : $t('Edit file', '编辑文件') }}</button><span class="read-only"><span aria-hidden="true">⌑</span> {{ $t("Read-only", "只读") }}</span></div>
    <div class="code-panes" :class="{ 'single-file': !(showOriginal && showCandidate) }">
      <section v-if="showOriginal" class="code-pane"><div class="pane-heading"><h2><span class="pane-dot original"></span>{{ $t("Original Code", "原始代码") }}</h2><span class="mono muted">{{ python ? 'Python' : $t('Text', '文本') }}</span></div><div class="file-tab"><span class="python-small">{{ python ? 'py' : '≡' }}</span>{{ original.path }}<span class="muted">{{ versionLabel && mode === "WORKSPACE" ? $t("Source", "源码") : $t("Original", "原始") }}</span></div><CodePanel :source="original.content" :plain="!python" :json="original.path.endsWith('.json')" /><div class="pane-footer">{{ mode === 'WORKSPACE' ? $t('Original snapshot', '原始快照') : $t('Original fixture · read-only host project', '原始样例 · 不会写入宿主项目') }}</div></section>
      <section v-if="showCandidate" class="code-pane proposed"><div class="pane-heading"><h2><span class="pane-dot proposed-dot"></span>{{ versionLabel && !report ? $t("Saved version", "已保存版本") : $t("Candidate Changes", "候选修改") }}</h2><span v-if="report?.diff" class="diff-count mono"><em>+{{ added }}</em><b>−{{ removed }}</b></span></div>
        <div class="file-tab"><span class="python-small">{{ python ? 'py' : '≡' }}</span>{{ original.path }}<span v-if="versionLabel" class="muted mono" :title="versionLabel">{{ versionLabel.slice(0, 12) }}</span><div class="segmented mini"><button :class="{ selected: tab === 'diff' }" @click="tab = 'diff'">{{ $t("Diff", "差异") }}</button><button :class="{ selected: tab === 'after' }" @click="tab = 'after'">{{ $t("After", "修改后") }}</button><button v-if="editable" :class="{ selected: tab === 'edit' }" @click="tab = 'edit'">{{ $t('Edit copy', '编辑副本') }}</button></div></div>
        <textarea v-if="editable && tab === 'edit'" class="candidate-editor mono" spellcheck="false"
          :aria-label="$t('Editable candidate copy', '可编辑候选副本')" :value="draft ?? original.content"
          maxlength="4096" @input="emit('edit', $event.target.value)"></textarea>
        <div v-else-if="!report && draft === undefined && !candidate && !versionComparison" class="empty-state proposal-empty"><div class="empty-symbol" aria-hidden="true">＋</div><h3>{{ $t("No proposal yet", "暂无候选") }}</h3><p>{{ mode === 'DEMO' ? $t("Replay a record to inspect the candidate and diff.", "回放后查看固定候选及差异。") : $t("Run the task to inspect the candidate and diff.", "执行后查看候选修改与差异。") }}</p><span class="micro">{{ mode === 'DEMO' ? $t("Demo Replay loads a fixed candidate.", "Demo Replay 只加载固定候选。") : $t("Inference and independent verification run through the backend.", "仅后端可调用模型并独立验收。") }}</span></div>
        <div v-else-if="tab === 'diff' && draft === undefined && report?.diff" class="diff-scroll" tabindex="0" :aria-label="$t('Candidate diff', '候选代码差异')"><div v-for="(line, index) in changes" :key="index" class="diff-line" :class="line.kind"><span class="diff-gutter">{{ line.kind === 'added' ? '+' : line.kind === 'removed' ? '−' : ' ' }}</span><code>{{ ['added', 'removed'].includes(line.kind) ? line.text.slice(1) : line.text }}</code></div></div>
        <div v-else-if="tab === 'diff' && draft === undefined && !candidate && !versionComparison" class="empty-state"><h3>{{ $t("No code changes", "无代码修改") }}</h3><p>{{ $t("This record contains no diff.", "该记录未包含代码差异。") }}</p></div>
        <CodePanel v-else-if="draft !== undefined || candidate || versionComparison" :source="draft ?? candidate" :plain="!python" />
        <div v-else class="empty-state"><h3>{{ $t("Source not recorded", "未记录候选源码") }}</h3><p>{{ $t("Only the diff was recorded.", "记录只有 Diff，没有候选全文。") }}</p></div>
        <div class="pane-footer"><span v-if="tab === 'edit' && editable">{{ $t('Local draft · verified only after an authorized run', '本地草稿 · 授权运行后验收') }}</span><span v-else-if="mode === 'WORKSPACE'">{{ report ? $t('Candidate from the execution report', '执行报告中的候选') : $t('Awaiting a candidate', '等待候选') }}</span><span v-else-if="mode === 'DEMO'">{{ report ? $t("Fixed fixture · no model generation", "固定 Fixture · 非 LLM 生成") : $t("Awaiting replay", "等待显式历史回放") }}</span><span v-else-if="recoveryAttempt?.attempt_index > 0">Attempt {{ recoveryAttempt.attempt_index }} · {{ recoveryAttempt.model_source === 'OFFLINE_TEST' ? $t("Offline / mock repair", "Offline / Mock 恢复提案") : $t("Vultr repair", "Vultr 恢复提案") }} · {{ $t('Real container verification', '真实容器验证') }}</span><span v-else>{{ executionMode === 'fixture' ? $t("Fixed candidate · real execution", "固定候选 · 本次真实执行；非模型生成") : executionMode === 'offline_executor' ? $t("Simulated proposal · real container checks", "模拟模型提案 · 真实容器验收") : $t("The verifier decides from evidence", "模型建议不等于验证成功") }}</span></div>
      </section>
    </div>
  </section>
</template>
