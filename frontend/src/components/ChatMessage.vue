<script setup>
import StatusBadge from './StatusBadge.vue'
defineProps({ role: String, label: String, model: String, status: String, source: String })
</script>
<template>
  <article class="chat-message agent-bubble" :class="role">
    <header class="agent-bubble-heading">
      <strong>{{ label }}<span v-if="model" class="muted"> · {{ model }}</span></strong>
      <StatusBadge v-if="status" :status="status" />
    </header>
    <small v-if="source" class="muted">{{ source }}</small>
    <slot />
  </article>
</template>
