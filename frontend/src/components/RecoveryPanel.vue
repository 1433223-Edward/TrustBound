<script setup>
import StatusBadge from './StatusBadge.vue'
import AdversarialPanel from './AdversarialPanel.vue'
defineProps({ report: Object })
</script>

<template>
  <div v-if="!report" class="empty-state"><h3>{{ $t("Recovery not requested", "未请求恢复") }}</h3><p>{{ $t("Select offline recovery for up to two attempts under the same checks.", "选择显式 Offline 恢复；最多两次，验证标准保持不变。") }}</p></div>
  <div v-else class="recovery-view">
    <div class="recovery-header"><h3>{{ $t('Bounded Recovery · Attempt', '有界恢复 · 尝试') }} {{ report.current_attempt }} / {{ report.max_attempts }}</h3><StatusBadge :status="report.final_status || report.status" /></div>
    <p class="micro">{{ report.stop_reason || $t("Backend running · each candidate reruns the complete verification chain.", "Backend running · 每次候选重新执行权限、公开测试、独立验收与对抗验证。") }}</p>
    <p class="micro">{{ $t("Real evidence must match the candidate. Offline / Mock refers to the model response.", "只有绑定候选版本的真实证据可以支持成功。Offline / Mock 指模型响应，不是容器测试结果。") }}</p>
    <p class="micro">{{ $t('The editor shows the last evaluated attempt:', '编辑区显示最后已评估的尝试：') }} {{ report.validated_attempt_index }}. {{ $t('Failed proposals inherit no earlier test results.', '失败提案不继承旧测试结果。') }}</p>
    <details v-for="attempt in report.attempts" :key="attempt.attempt_index" :open="attempt.attempt_index === report.attempts.length - 1" class="attempt">
      <summary>{{ $t('Attempt', '尝试') }} {{ attempt.attempt_index }} · {{ attempt.attempt_index === 0 ? 'Initial candidate' : attempt.model_source === 'OFFLINE_TEST' ? 'OFFLINE / MOCK repair' : 'Vultr repair path' }} · {{ attempt.final_decision?.status || 'Unverified' }}</summary>
      <p class="micro">Trigger: {{ attempt.recovery_trigger }} · Stop: {{ attempt.stop_reason || '—' }}</p>
      <p class="micro mono">Candidate {{ attempt.candidate_hash || 'No candidate produced' }}<br>Previous {{ attempt.previous_candidate_hash || '—' }}</p>
      <div v-for="(failure, index) in attempt.confirmed_failure_evidence" :key="index" class="failure-evidence mono">{{ failure.amount }} → expected {{ failure.expected }} / observed {{ failure.actual }} · {{ failure.error_type }}</div>
      <p class="micro">Formal {{ attempt.verification?.status || 'NOT RUN' }} · Adversarial {{ attempt.adversarial_report?.status || 'NOT RUN' }} · Decision {{ attempt.final_decision?.status || 'Pending' }}</p>
      <details><summary>{{ $t('Candidate diff', '候选差异') }} {{ attempt.attempt_index === 0 ? '(against original)' : '(against previous)' }}</summary><pre>{{ attempt.attempt_index === 0 ? attempt.verification?.diff : attempt.diff_from_previous || '(no valid code change)' }}</pre></details>
      <details v-if="attempt.verification"><summary>{{ $t('Formal sandbox evidence', '正式验收沙盒证据') }}</summary><div v-for="e in attempt.verification.executions" :key="e.container_name"><p class="micro">{{ e.phase }} · {{ e.status }} · exit {{ e.exit_code }} · cleanup {{ e.cleanup_confirmed }} · limits {{ e.limits_verified }} · integrity {{ e.workspace_unchanged }}</p><pre>stdout: {{ e.stdout || '(empty)' }}
stderr: {{ e.stderr || '(empty)' }}</pre></div></details>
      <details v-if="attempt.adversarial_report"><summary>{{ $t('Independent adversarial evidence', '独立对抗证据') }}</summary><AdversarialPanel :report="attempt.adversarial_report" :decision="attempt.final_decision" :formal-status="attempt.verification?.status" /></details>
      <details v-if="attempt.diagnostic_report"><summary>Trusted business diagnostic · real Docker / no LLM</summary><AdversarialPanel :report="attempt.diagnostic_report" :decision="attempt.final_decision" :formal-status="attempt.verification?.status" /></details>
      <details v-if="attempt.model_call_metadata?.length"><summary>Model call metadata · {{ attempt.model_source }}</summary><pre>{{ JSON.stringify(attempt.model_call_metadata, null, 2) }}</pre></details>
    </details>
  </div>
</template>

<style scoped>
.recovery-header{display:flex;justify-content:space-between;gap:12px;flex-wrap:wrap}.recovery-view>p{margin-top:8px}
.attempt{border:1px solid var(--line);border-radius:4px;padding:12px;margin-top:12px;background:#11171a;font-size:11px}
.attempt summary{cursor:pointer;line-height:1.7}.attempt p{margin-top:8px;overflow-wrap:anywhere}.attempt details{margin-top:10px}
.attempt pre{max-height:190px;overflow:auto;white-space:pre-wrap;overflow-wrap:anywhere;font:11px/1.7 var(--mono);background:#101518;padding:10px}
.failure-evidence{color:var(--amber);margin:10px 0;overflow-wrap:anywhere}
</style>
