<script setup>
import { computed } from 'vue'
import StatusBadge from './StatusBadge.vue'
import { t, traceText } from '../i18n.js'
const props = defineProps({ stages: Array, mode: String, report: Object, adversarial: Object, recovery: Object })
const timeline = computed(() => {
  const rows = props.stages.slice(0, -1)
  if (props.adversarial) rows.push({ name: t('Adversarial Testing', '对抗测试'), state: props.adversarial.status, detail: props.adversarial.reason })
  if (props.recovery?.attempts?.length > 1) rows.push({ name: t('Recovery', '恢复'), state: props.recovery.final_status || props.recovery.status,
    detail: t('Replacement attempts have separate evidence.', '每轮修复保留独立证据。') })
  return [...rows, ...props.stages.slice(-1)]
})
</script>

<template>
  <aside class="trace-panel">
    <div class="section-heading"><span class="eyebrow">{{ $t('EXECUTION TRACE', '执行记录') }}</span><span class="muted">↳</span></div>
    <p class="trace-caption">{{ mode === 'DEMO' ? $t('Historical snapshot · recorded events', '历史快照 · 已记录事件') : $t('Based on backend run records', '根据后端记录呈现') }}</p>
    <ol class="trace-list">
      <li v-for="(stage, index) in timeline" :key="index">
        <span class="trace-number mono">{{ String(index + 1).padStart(2, '0') }}</span>
        <div class="trace-step"><h3>{{ traceText(stage.name) }}</h3><StatusBadge :status="stage.state" /><p>{{ traceText(stage.detail) }}</p></div>
      </li>
    </ol>
    <div v-if="report" class="trace-record"><span class="field-label">{{ $t('RECORDED RUN', '已记录运行') }}</span><code>{{ report.run_id.slice(0, 16) }}</code></div>
  </aside>
</template>
