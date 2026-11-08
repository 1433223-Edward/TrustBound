<script setup>
defineProps({ tabs: { type: Array, default: () => [] } })
const tab = defineModel({ type: String, default: 'summary' })
</script>

<template>
  <section class="evidence-panel">
    <header class="evidence-heading">
      <h2><span aria-hidden="true">▤</span> {{ $t('Evidence Report', '证据报告') }}</h2>
      <div v-if="tabs.length" class="evidence-tabs" role="tablist" :aria-label="$t('Evidence view', '证据视图')">
        <button v-for="item in tabs" :key="item.id" type="button" role="tab" :aria-selected="tab === item.id"
          :class="{ selected: tab === item.id }" @click="tab = item.id">{{ item.label }}</button>
      </div>
      <slot name="status" />
    </header>
    <slot />
  </section>
</template>
