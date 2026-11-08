<script setup>
import { computed } from 'vue'
import { tokenize } from '../api/adapter.js'
const props = defineProps({ source: { type: String, default: '' }, plain: Boolean, json: Boolean })
function jsonTokens(line) {
  return line.split(/("(?:\\.|[^"\\])*"|\b(?:true|false|null)\b|-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?)/g)
    .map((text, index) => ({ text, kind: index % 2 === 0 ? 'plain' : text.startsWith('"') ? 'string' : 'number' }))
}
const lines = computed(() => props.source.replace(/\n$/, '').split('\n')
  .map(line => props.json ? jsonTokens(line) : props.plain ? [{ kind: 'plain', text: line }] : tokenize(line)))
</script>

<template><div class="code-scroll" tabindex="0" :aria-label="$t('Read-only source', '只读源码')"><div class="code-line" v-for="(line, index) in lines" :key="index"><span class="line-number" aria-hidden="true">{{ index + 1 }}</span><code><span v-for="(token, tokenIndex) in line" :key="tokenIndex" :class="`syntax-${token.kind}`">{{ token.text }}</span></code></div></div></template>
