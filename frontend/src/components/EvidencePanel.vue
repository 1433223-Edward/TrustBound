<script setup>
import { computed, ref, watch } from 'vue'
import { executionStatus } from '../api/adapter.js'
import StatusBadge from './StatusBadge.vue'
const props = defineProps({ report: Object, mode: String })
const tab = ref('summary')
watch(() => props.report?.run_id, () => { tab.value = 'summary' })
const publicRun = computed(() => props.report?.executions.find(e => e.phase === 'public'))
const acceptance = computed(() => props.report?.executions.find(e => e.phase === 'acceptance'))
const cleaned = computed(() => props.report?.executions.length ? props.report.executions.every(e => e.cleanup_confirmed) : null)
const failure = computed(() => acceptance.value?.stderr.match(/AssertionError:[^\n]*/)?.[0] || publicRun.value?.timeout_reason || publicRun.value?.stderr.match(/AssertionError:[^\n]*/)?.[0] || '')
</script>

<template>
  <section class="evidence-panel">
    <div class="evidence-heading"><h2><span aria-hidden="true">▤</span> Evidence Report</h2><div class="evidence-tabs" role="tablist" aria-label="证据视图"><button v-for="item in ['summary', 'diff', 'logs']" :key="item" role="tab" :aria-selected="tab === item" :class="{ selected: tab === item }" @click="tab = item">{{ { summary: 'Overview', diff: 'Raw diff', logs: 'Execution logs' }[item] }}</button></div><StatusBadge v-if="report" :status="report.status" :label="mode === 'DEMO' ? `SAMPLE · ${report.status}` : report.status" /><span v-else class="muted micro">Awaiting evidence</span></div>
    <div v-if="!report" class="empty-state evidence-empty"><span class="empty-symbol small">▤</span><div><h3>No evidence collected</h3><p>回放一份 Sample，或连接真实 API。界面不会凭空生成验收结论。</p></div></div>
    <div v-else class="evidence-body">
      <template v-if="tab === 'summary'">
        <div class="evidence-metrics">
          <div><span class="field-label">PUBLIC TESTS</span><StatusBadge :status="executionStatus(publicRun)" /><small>Exit code <b class="mono">{{ publicRun?.exit_code ?? '—' }}</b></small></div>
          <div><span class="field-label">INDEPENDENT VERIFICATION</span><StatusBadge :status="executionStatus(acceptance)" /><small>{{ acceptance ? 'Protected billing-v1 suite' : '无执行记录 · 未推断为通过' }}</small></div>
          <div><span class="field-label">EXECUTION</span><strong>{{ publicRun?.status === 'TIMED_OUT' ? 'Deadline exceeded' : publicRun ? 'Container exited' : 'Not started' }}</strong><small>{{ publicRun?.timeout_reason || (publicRun ? `Timeout: no · limits ${publicRun.limits_verified ? 'checked' : 'unconfirmed'}` : 'Policy stopped execution') }}</small></div>
          <div><span class="field-label">CLEANUP & INTEGRITY</span><strong :class="{ 'text-good': cleaned, 'text-bad': cleaned === false }">{{ cleaned === null ? 'Not applicable' : cleaned ? 'Containers removed' : 'Cleanup unconfirmed' }}</strong><small>{{ report.executions.length ? `Workspace ${report.executions.every(e => e.workspace_unchanged) ? 'unchanged' : 'changed'}` : 'No sandbox was created' }}</small></div>
        </div>
        <div class="finding" :class="report.status === 'VERIFIED' ? 'finding-good' : 'finding-alert'"><span aria-hidden="true">{{ report.status === 'VERIFIED' ? '✓' : '↳' }}</span><div><strong>{{ report.status === 'VERIFIED' ? 'Declared acceptance checks passed.' : report.status === 'REJECTED' ? 'Request stopped at the permission boundary.' : report.status === 'INCONCLUSIVE' ? 'Evidence is insufficient for a verdict.' : 'The evidence does not support success.' }}</strong><code v-if="failure">{{ failure }}</code><p v-else>{{ report.policy_reason }}</p></div></div>
        <div class="evidence-meta"><span class="mono" :title="report.artifact_hash">SHA-256 {{ report.artifact_hash.slice(0, 16) }}…</span><span>Requested paths: {{ report.changed_paths.join(', ') || 'none' }}</span><span>{{ mode === 'DEMO' ? 'Historical evidence · no live execution' : 'Server-reported evidence' }}</span></div>
        <details class="limitations"><summary>Verification scope & limitations</summary><ul><li v-for="limitation in report.limitations" :key="limitation">{{ limitation }}</li></ul></details>
      </template>
      <pre v-else-if="tab === 'diff'" class="raw-diff">{{ report.diff || 'No code changes recorded.' }}</pre>
      <div v-else class="logs"><p class="micro">原始进程输出；stderr 非空不代表测试失败。日志仅在展开后显示。</p><p v-if="!report.executions.length">No execution logs — request was rejected before sandbox creation.</p><section v-for="execution in report.executions" :key="execution.container_name"><h3>{{ execution.phase === 'public' ? 'Public Tests' : 'Independent Verification' }} <span class="mono muted">exit {{ execution.exit_code ?? 'unknown' }}</span></h3><p v-if="execution.error" class="text-bad">{{ execution.error }}</p><details v-for="stream in ['stdout', 'stderr']" :key="stream"><summary>{{ execution.phase }} · {{ stream }} <span class="muted">{{ execution[stream].length.toLocaleString() }} chars</span></summary><pre>{{ execution[stream] || '(empty)' }}</pre></details></section></div>
    </div>
  </section>
</template>
