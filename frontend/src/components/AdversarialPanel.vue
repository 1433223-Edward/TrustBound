<script setup>
import StatusBadge from './StatusBadge.vue'
defineProps({ report: Object, decision: Object, formalStatus: String })
</script>

<template>
  <div class="adversarial-view">
    <div v-if="!report" class="empty-state">
      <h3>Adversarial verification not requested</h3>
      <p>在 Local API 中选择独立对抗验证。历史 Demo 不含这一阶段，不能补造证据。</p>
    </div>
    <template v-else>
      <div class="adversarial-header">
        <div><h3>Independent adversarial verification</h3><p class="micro">{{ report.source === 'OFFLINE_TEST' ? 'OFFLINE · 只模拟模型响应，合法反例真实执行 Docker。' : report.source === 'NO_LIVE_CALL' ? '未调用模型；本阶段没有完成验证。' : 'Vultr HTTP · 独立消息上下文' }}</p></div>
        <StatusBadge :status="report.status" />
      </div>
      <div class="adversarial-counts mono">Generated {{ report.generated_count ?? '—' }} · Valid {{ report.valid_count }} · Confirmed {{ report.confirmed_count }}<span>Formal {{ formalStatus }} → Overall {{ decision?.status }}</span></div>
      <p class="micro">{{ report.reason }}</p>
      <p class="micro" v-if="decision">{{ decision.reason }}</p>
      <div v-for="row in report.challenges" :key="row.challenge.challenge_id" class="challenge-row">
        <div class="challenge-top"><code>{{ row.challenge.amount || '(missing input)' }}</code><StatusBadge :status="row.status" /></div>
        <p>{{ row.challenge.reason }}</p><p class="micro">{{ row.challenge.requirement_id }} · {{ row.reason }}</p>
        <div v-if="row.status !== 'INVALID'" class="challenge-values mono"><span>Expected: {{ row.expected }}</span><span>Observed: {{ row.actual ?? 'not observed' }}{{ row.actual_type ? ` (${row.actual_type})` : '' }}</span></div>
      </div>
      <details v-if="report.execution" class="adversarial-evidence">
        <summary>Actual sandbox evidence · exit {{ report.execution.exit_code ?? 'unknown' }} · cleanup {{ report.execution.cleanup_confirmed }}</summary>
        <p class="micro mono">Artifact {{ report.artifact_hash }}<br>Driver {{ report.driver_hash }}</p>
        <p class="micro">{{ report.execution.status }} · limits {{ report.execution.limits_verified }} · workspace unchanged {{ report.execution.workspace_unchanged }}</p>
        <pre>stdout: {{ report.execution.stdout || '(empty)' }}
stderr: {{ report.execution.stderr || '(empty)' }}</pre>
      </details>
      <p class="micro">{{ decision?.scope }} · 无反例不等于绝对正确；模型文字不是执行证据。</p>
    </template>
  </div>
</template>

<style scoped>
.adversarial-header,.challenge-top,.adversarial-counts,.challenge-values{display:flex;align-items:center;justify-content:space-between;gap:12px;flex-wrap:wrap}
.adversarial-header{margin-bottom:12px}.adversarial-header h3{margin-bottom:5px}
.adversarial-counts{font-size:11px;padding:10px 0;color:#b6c7d1}.adversarial-counts span{color:var(--amber)}
.challenge-row{margin:12px 0;border:1px solid var(--line);border-radius:4px;padding:12px;background:#11171a}
.challenge-row p{font-size:11px;line-height:1.7;margin-top:6px;overflow-wrap:anywhere}
.challenge-values{justify-content:flex-start;font-size:11px;margin-top:9px;gap:24px}
.adversarial-evidence{font-size:11px;margin:14px 0}.adversarial-evidence p{margin-top:9px;overflow-wrap:anywhere}
.adversarial-evidence pre{max-height:170px;overflow:auto;white-space:pre-wrap;overflow-wrap:anywhere;font:11px/1.7 var(--mono);padding:10px;background:#101518}
</style>
