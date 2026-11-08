<script setup>
import { computed, ref, watch } from 'vue'
import { executionStatus } from '../api/adapter.js'
import StatusBadge from './StatusBadge.vue'
import EvidenceFrame from './EvidenceFrame.vue'
import { evidenceTabs } from '../evidenceTabs.js'
import { t } from '../i18n.js'
import AdversarialPanel from './AdversarialPanel.vue'
import RecoveryPanel from './RecoveryPanel.vue'
const props = defineProps({ report: Object, mode: String, executionMode: String, adversarialReport: Object, finalDecision: Object, recoveryReport: Object, inferenceUsage: Object })
const tab = ref('summary')
const tabs = computed(evidenceTabs)
const overallStatus = computed(() => props.recoveryReport?.final_status || props.finalDecision?.status || props.report?.status)
watch(() => props.report?.run_id, () => { tab.value = props.recoveryReport ? 'recovery' : 'summary' })
const publicRun = computed(() => props.report?.executions.find(e => e.phase === 'public'))
const acceptance = computed(() => props.report?.executions.find(e => e.phase === 'acceptance'))
const cleaned = computed(() => props.report?.executions.length ? props.report.executions.every(e => e.cleanup_confirmed) : null)
const failure = computed(() => acceptance.value?.stderr.match(/AssertionError:[^\n]*/)?.[0] || publicRun.value?.timeout_reason || publicRun.value?.stderr.match(/AssertionError:[^\n]*/)?.[0] || '')
defineExpose({ showEvidence(row) { tab.value = row.tab; document.getElementById('billing-evidence')?.scrollIntoView({ block: 'nearest' }) } })
</script>

<template>
  <EvidenceFrame id="billing-evidence" v-model="tab" :tabs="tabs">
    <template #status>
      <StatusBadge v-if="report" :status="overallStatus" :label="mode === 'DEMO' ? `SAMPLE · ${$status(overallStatus)}` : `${executionMode === 'fixture' ? 'DOCKER' : executionMode === 'offline_executor' ? 'MOCK LLM' : 'VULTR'} · ${$status(overallStatus)}`" />
      <span v-else class="muted micro">{{ $t('Awaiting evidence', '等待证据') }}</span>
    </template>
    <details v-if="inferenceUsage" style="padding:10px 20px;font-size:11px;max-height:180px;overflow:auto">
      <summary>{{ $t('Inference usage · Live', '推理用量 · 实时') }} {{ inferenceUsage.live_request_count }} / {{ $t('Offline', '离线') }} {{ inferenceUsage.offline_request_count }} · {{ $t('Requests', '请求') }} {{ inferenceUsage.request_count }} / {{ inferenceUsage.max_requests }}</summary>
      <p>{{ $t('Live input', '实时输入') }} {{ inferenceUsage.prompt_tokens ?? 'unknown' }} · {{ $t('Output', '输出') }} {{ inferenceUsage.completion_tokens ?? 'unknown' }} · {{ $t('Estimated USD', '估算 USD') }} {{ inferenceUsage.estimated_usd ?? 'unknown' }} · {{ inferenceUsage.billing_status }}</p>
      <p>{{ $t('Reserved output tokens', '预留输出 Tokens') }} {{ inferenceUsage.reserved_output_tokens }} / {{ inferenceUsage.max_output_tokens }} · {{ $t('Provider invoice may differ.', '以实际账单为准。') }}</p>
      <p v-for="(call, index) in inferenceUsage.calls" :key="index">{{ call.source }} · {{ call.model }} · {{ call.status }} · output limit {{ call.max_completion_tokens }} · estimated USD {{ call.estimated_usd ?? 'unknown' }}</p>
    </details>
    <div v-if="!report && !recoveryReport" class="empty-state evidence-empty"><span class="empty-symbol small">▤</span><div><h3>{{ $t("No evidence collected", "暂无证据") }}</h3><p>{{ $t("Replay a sample or connect to the API to collect evidence.", "回放一份 Sample，或连接真实 API。界面不会凭空生成验收结论。") }}</p></div></div>
    <div v-else-if="!report" class="evidence-body"><RecoveryPanel :report="recoveryReport" /></div>
    <div v-else class="evidence-body">
      <template v-if="tab === 'summary'">
        <p v-if="recoveryReport" class="micro">Last evaluated attempt {{ recoveryReport.validated_attempt_index }} · Recovery {{ recoveryReport.final_status }} · {{ recoveryReport.stop_reason }}</p>
        <p v-if="adversarialReport" class="micro">Formal {{ report.status }} · Adversarial {{ adversarialReport.status }} · Overall {{ overallStatus }} — {{ $t('See Adversarial for counterexamples.', '查看「对抗」了解反例。') }}</p>
        <div class="evidence-metrics">
          <div><span class="field-label">{{ $t("PUBLIC TESTS", "公开测试") }}</span><StatusBadge :status="executionStatus(publicRun)" /><small>{{ $t('Exit code', '退出码') }} <b class="mono">{{ publicRun?.exit_code ?? '—' }}</b></small></div>
          <div><span class="field-label">{{ $t("INDEPENDENT VERIFICATION", "独立验收") }}</span><StatusBadge :status="executionStatus(acceptance)" /><small>{{ acceptance ? $t("Protected billing-v1 suite", "受保护的 billing-v1 用例") : $t("No execution record · no passing verdict", "无执行记录 · 未推断为通过") }}</small></div>
          <div><span class="field-label">{{ $t("EXECUTION", "执行") }}</span><strong>{{ publicRun?.status === 'TIMED_OUT' ? $t("Deadline exceeded", "超时") : publicRun ? $t("Container exited", "容器已退出") : $t("Not started", "未启动") }}</strong><small>{{ publicRun?.timeout_reason || (publicRun ? `Timeout: no · limits ${publicRun.limits_verified ? 'checked' : 'unconfirmed'}` : $t("Policy stopped execution", "策略阻止执行")) }}</small></div>
          <div><span class="field-label">{{ $t("CLEANUP & INTEGRITY", "清理与完整性") }}</span><strong :class="{ 'text-good': cleaned, 'text-bad': cleaned === false }">{{ cleaned === null ? $t("Not applicable", "不适用") : cleaned ? $t("Containers removed", "容器已清理") : $t("Cleanup unconfirmed", "清理未确认") }}</strong><small>{{ report.executions.length ? `Workspace ${report.executions.every(e => e.workspace_unchanged) ? 'unchanged' : 'changed'}` : $t("No sandbox was created", "未创建沙盒") }}</small></div>
        </div>
        <div class="finding" :class="overallStatus === 'VERIFIED' ? 'finding-good' : 'finding-alert'"><span aria-hidden="true">{{ overallStatus === 'VERIFIED' ? '✓' : '↳' }}</span><div><strong>{{ overallStatus === 'VERIFIED' ? $t("Declared acceptance checks passed.", "通过声明的验收范围。") : overallStatus === 'REJECTED' ? $t("Request stopped at the permission boundary.", "请求已在权限边界停止。") : overallStatus === 'INCONCLUSIVE' ? $t("Evidence is insufficient for a verdict.", "证据不足以作出通过裁决。") : $t("The evidence does not support success.", "证据不支持通过。") }}</strong><code v-if="failure">{{ failure }}</code><p v-else>{{ recoveryReport?.stop_reason || finalDecision?.reason || report.policy_reason }}</p></div></div>
        <div class="evidence-meta"><span class="mono" :title="report.artifact_hash">SHA-256 {{ report.artifact_hash.slice(0, 16) }}…</span><span>{{ $t('Requested paths', '请求修改路径') }}: {{ report.changed_paths.join(', ') || 'none' }}</span><span>{{ mode === 'DEMO' ? $t("Historical evidence · no live execution", "历史证据 · 无实时执行") : $t("Server-reported evidence", "后端报告证据") }}</span></div>
        <details class="limitations"><summary>{{ $t("Verification scope & limitations", "验收范围与局限") }}</summary><ul><li v-for="limitation in report.limitations" :key="limitation">{{ limitation }}</li></ul></details>
      </template>
      <pre v-else-if="tab === 'diff'" class="raw-diff">{{ report.diff || $t("No code changes recorded.", "未记录代码修改。") }}</pre>
      <RecoveryPanel v-else-if="tab === 'recovery'" :report="recoveryReport" />
      <AdversarialPanel v-else-if="tab === 'adversarial'" :report="adversarialReport" :decision="finalDecision" :formal-status="report.status" />
      <div v-else class="logs"><p class="micro">{{ $t("Raw process logs. Stderr can contain messages even when checks pass.", "原始进程输出；stderr 非空不代表测试失败。日志仅在展开后显示。") }}</p><p v-if="!report.executions.length">{{ $t("No execution logs — request was rejected before sandbox creation.", "请求在创建沙盒前被拒绝，没有执行日志。") }}</p><section v-for="execution in report.executions" :key="execution.container_name"><h3>{{ execution.phase === 'public' ? $t("Public Tests", "公开测试") : $t("Independent Verification", "独立验收") }} <span class="mono muted">exit {{ execution.exit_code ?? 'unknown' }}</span></h3><p v-if="execution.error" class="text-bad">{{ execution.error }}</p><details v-for="stream in ['stdout', 'stderr']" :key="stream"><summary>{{ execution.phase }} · {{ stream }} <span class="muted">{{ execution[stream].length.toLocaleString() }} chars</span></summary><pre>{{ execution[stream] || '(empty)' }}</pre></details></section></div>
    </div>
  </EvidenceFrame>
</template>
