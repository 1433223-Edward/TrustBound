<script setup>
import StatusBadge from './StatusBadge.vue'
defineProps({ stages: Array, mode: String, report: Object })
</script>

<template><aside class="trace-panel"><div class="section-heading"><span class="eyebrow">EXECUTION TRACE</span><span class="muted">↳</span></div><p class="trace-caption">{{ mode === 'DEMO' ? 'Historical snapshot · 非实时事件流' : '根据后端最终记录呈现' }}</p><ol class="trace-list"><li v-for="(stage, index) in stages" :key="stage.name"><span class="trace-number mono">{{ String(index + 1).padStart(2, '0') }}</span><div class="trace-step"><h3>{{ stage.name }}</h3><StatusBadge :status="stage.state" /><p>{{ stage.detail }}</p></div></li></ol><div v-if="report" class="trace-record"><span class="field-label">RECORDED RUN</span><code>{{ report.run_id.slice(0, 16) }}</code><span class="micro">{{ mode === 'DEMO' ? '源自本地真实历史报告' : '来自已连接 API' }}</span></div></aside></template>
