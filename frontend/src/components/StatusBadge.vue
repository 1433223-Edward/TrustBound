<script setup>
import { computed } from 'vue'
const props = defineProps({ status: { type: String, default: 'WAITING' }, label: String })
const tone = computed(() => ['VERIFIED', 'PASSED', 'ALLOWED', 'RECORDED', 'CONNECTED'].includes(props.status) ? 'good'
  : ['FAILED', 'ERROR', 'API_FAILED', 'TIMED_OUT', 'UNAVAILABLE'].includes(props.status) ? 'bad'
    : ['REJECTED', 'INCONCLUSIVE', 'DEMO', 'UNKNOWN'].includes(props.status) ? 'warn'
      : ['LOADING', 'CONNECTING', 'RUNNING'].includes(props.status) ? 'active' : 'neutral')
</script>

<template><span class="status-badge" :class="tone"><i aria-hidden="true"></i>{{ label || status.replaceAll('_', ' ') }}</span></template>
