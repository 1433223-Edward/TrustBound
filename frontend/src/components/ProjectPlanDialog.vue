<script setup>
import { onMounted, ref, useId, watch } from 'vue'

const open = defineModel({ type: Boolean, required: true })
defineProps({ title: { type: String, required: true } })
const dialog = ref(null)
const titleId = useId()
function sync() {
  if (open.value && !dialog.value.open) dialog.value.showModal()
  if (!open.value && dialog.value.open) dialog.value.close()
}
onMounted(sync)
watch(open, sync, { flush: 'post' })
</script>

<template>
  <dialog ref="dialog" class="project-plan-dialog" :aria-labelledby="titleId" @close="open = false">
    <header class="project-plan-header">
      <div><span class="eyebrow">{{ $t('WORKSPACE / PLAN', '工作区 / 计划') }}</span><h2 :id="titleId">{{ title }}</h2></div>
      <button class="product-button subtle" type="button" @click="open = false">{{ $t('Close', '关闭') }}</button>
    </header>
    <slot />
  </dialog>
</template>
