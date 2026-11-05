<script setup>
import { computed, ref, watch } from 'vue'
import { executionStatus } from '../api/adapter.js'
import StatusBadge from './StatusBadge.vue'
import AdversarialPanel from './AdversarialPanel.vue'
import RecoveryPanel from './RecoveryPanel.vue'
const props = defineProps({ report: Object, mode: String, executionMode: String, adversarialReport: Object, finalDecision: Object, recoveryReport: Object, inferenceUsage: Object })
const tab = ref('summary')
const overallStatus = computed(() => props.recoveryReport?.final_status || props.finalDecision?.status || props.report?.status)
watch(() => props.report?.run_id, () => { tab.value = props.recoveryReport ? 'recovery' : 'summary' })
const publicRun = computed(() => props.report?.executions.find(e => e.phase === 'public'))
const acceptance = computed(() => props.report?.executions.find(e => e.phase === 'acceptance'))
const cleaned = computed(() => props.report?.executions.length ? props.report.executions.every(e => e.cleanup_confirmed) : null)
const failure = computed(() => acceptance.value?.stderr.match(/AssertionError:[^\n]*/)?.[0] || publicRun.value?.timeout_reason || publicRun.value?.stderr.match(/AssertionError:[^\n]*/)?.[0] || '')
</script>

<template>
  <section class="evidence-panel">
    <div class="evidence-heading"><h2><span aria-hidden="true">▤</span> Evidence Report</h2><div class="evidence-tabs" role="tablist" aria-label="证据视图"><button v-for="item in ['summary', 'diff', 'logs', 'adversarial', 'recovery']" :key="item" role="tab" :aria-selected="tab === item" :class="{ selected: tab === item }" @click="tab = item">{{ { summary: 'Overview', diff: 'Raw diff', logs: 'Execution logs', adversarial: 'Adversarial', recovery: 'Recovery' }[item] }}</button></div><StatusBadge v-if="report" :status="overallStatus" :label="mode === 'DEMO' ? `SAMPLE · ${overallStatus}` : `${executionMode === 'fixture' ? 'DOCKER' : executionMode === 'offline_executor' ? 'MOCK LLM' : 'VULTR'} · ${overallStatus}`" /><span v-else class="muted micro">Awaiting evidence</span></div>
    <details v-if="inferenceUsage" style="padding:10px 20px;font-size:11px;max-height:180px;overflow:auto">
      <summary>Inference usage · Live {{ inferenceUsage.live_request_count }} / Offline {{ inferenceUsage.offline_request_count }} · requests {{ inferenceUsage.request_count }} / {{ inferenceUsage.max_requests }}</summary>
      <p>Live input {{ inferenceUsage.prompt_tokens ?? 'unknown' }} · output {{ inferenceUsage.completion_tokens ?? 'unknown' }} · estimated USD {{ inferenceUsage.estimated_usd ?? 'unknown' }} · {{ inferenceUsage.billing_status }}</p>
      <p>Reserved output tokens {{ inferenceUsage.reserved_output_tokens }} / {{ inferenceUsage.max_output_tokens }} · Estimates are not actual invoices.</p>
      <p v-for="(call, index) in inferenceUsage.calls" :key="index">{{ call.source }} · {{ call.model }} · {{ call.status }} · output limit {{ call.max_completion_tokens }} · estimated USD {{ call.estimated_usd ?? 'unknown' }}</p>
    </details>
    <div v-if="!report && !recoveryReport" class="empty-state evidence-empty"><span class="empty-symbol small">▤</span><div><h3>No evidence collected</h3><p>回放一份 Sample，或连接真实 API。界面不会凭空生成验收结论。</p></div></div>
    <div v-else-if="!report" class="evidence-body"><RecoveryPanel :report="recoveryReport" /></div>
    <div v-else class="evidence-body">
      <template v-if="tab === 'summary'">
        <p v-if="recoveryReport" class="micro">Last evaluated attempt {{ recoveryReport.validated_attempt_index }} · Recovery {{ recoveryReport.final_status }} · {{ recoveryReport.stop_reason }}</p>
        <p v-if="adversarialReport" class="micro">Formal {{ report.status }} · Adversarial {{ adversarialReport.status }} · Overall {{ overallStatus }} — 下面四项为正式验收记录；反例证据见 Adversarial。</p>
        <div class="evidence-metrics">
          <div><span class="field-label">PUBLIC TESTS</span><StatusBadge :status="executionStatus(publicRun)" /><small>Exit code <b class="mono">{{ publicRun?.exit_code ?? '—' }}</b></small></div>
          <div><span class="field-label">INDEPENDENT VERIFICATION</span><StatusBadge :status="executionStatus(acceptance)" /><small>{{ acceptance ? 'Protected billing-v1 suite' : '无执行记录 · 未推断为通过' }}</small></div>
          <div><span class="field-label">EXECUTION</span><strong>{{ publicRun?.status === 'TIMED_OUT' ? 'Deadline exceeded' : publicRun ? 'Container exited' : 'Not started' }}</strong><small>{{ publicRun?.timeout_reason || (publicRun ? `Timeout: no · limits ${publicRun.limits_verified ? 'checked' : 'unconfirmed'}` : 'Policy stopped execution') }}</small></div>
          <div><span class="field-label">CLEANUP & INTEGRITY</span><strong :class="{ 'text-good': cleaned, 'text-bad': cleaned === false }">{{ cleaned === null ? 'Not applicable' : cleaned ? 'Containers removed' : 'Cleanup unconfirmed' }}</strong><small>{{ report.executions.length ? `Workspace ${report.executions.every(e => e.workspace_unchanged) ? 'unchanged' : 'changed'}` : 'No sandbox was created' }}</small></div>
        </div>
        <div class="finding" :class="overallStatus === 'VERIFIED' ? 'finding-good' : 'finding-alert'"><span aria-hidden="true">{{ overallStatus === 'VERIFIED' ? '✓' : '↳' }}</span><div><strong>{{ overallStatus === 'VERIFIED' ? 'Declared acceptance checks passed.' : overallStatus === 'REJECTED' ? 'Request stopped at the permission boundary.' : overallStatus === 'INCONCLUSIVE' ? 'Evidence is insufficient for a verdict.' : 'The evidence does not support success.' }}</strong><code v-if="failure">{{ failure }}</code><p v-else>{{ recoveryReport?.stop_reason || finalDecision?.reason || report.policy_reason }}</p></div></div>
        <div class="evidence-meta"><span class="mono" :title="report.artifact_hash">SHA-256 {{ report.artifact_hash.slice(0, 16) }}…</span><span>Requested paths: {{ report.changed_paths.join(', ') || 'none' }}</span><span>{{ mode === 'DEMO' ? 'Historical evidence · no live execution' : 'Server-reported evidence' }}</span></div>
        <details class="limitations"><summary>Verification scope & limitations</summary><ul><li v-for="limitation in report.limitations" :key="limitation">{{ limitation }}</li></ul></details>
      </template>
      <pre v-else-if="tab === 'diff'" class="raw-diff">{{ report.diff || 'No code changes recorded.' }}</pre>
      <RecoveryPanel v-else-if="tab === 'recovery'" :report="recoveryReport" />
      <AdversarialPanel v-else-if="tab === 'adversarial'" :report="adversarialReport" :decision="finalDecision" :formal-status="report.status" />
      <div v-else class="logs"><p class="micro">原始进程输出；stderr 非空不代表测试失败。日志仅在展开后显示。</p><p v-if="!report.executions.length">No execution logs — request was rejected before sandbox creation.</p><section v-for="execution in report.executions" :key="execution.container_name"><h3>{{ execution.phase === 'public' ? 'Public Tests' : 'Independent Verification' }} <span class="mono muted">exit {{ execution.exit_code ?? 'unknown' }}</span></h3><p v-if="execution.error" class="text-bad">{{ execution.error }}</p><details v-for="stream in ['stdout', 'stderr']" :key="stream"><summary>{{ execution.phase }} · {{ stream }} <span class="muted">{{ execution[stream].length.toLocaleString() }} chars</span></summary><pre>{{ execution[stream] || '(empty)' }}</pre></details></section></div>
    </div>
  </section>
</template>
