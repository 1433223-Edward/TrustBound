<script setup>
defineProps({ id: String, hash: String, label: String })
</script>

<template>
  <details v-if="id || hash" class="snapshot-identity">
    <summary class="field-label">{{ label }} <code v-if="hash">{{ hash.slice(0, 8) }}</code></summary>
    <p v-if="id" class="micro mono">{{ id }}</p>
    <p v-if="hash" class="micro mono">{{ hash }}</p>
  </details>
</template>
