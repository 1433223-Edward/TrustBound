<script setup>
import { computed } from 'vue'
import { tokenize } from '../api/adapter.js'
const props = defineProps({ source: { type: String, default: '' } })
const lines = computed(() => props.source.replace(/\n$/, '').split('\n').map(tokenize))
</script>

<template><div class="code-scroll" tabindex="0" aria-label="只读 Python 代码"><div class="code-line" v-for="(line, index) in lines" :key="index"><span class="line-number" aria-hidden="true">{{ index + 1 }}</span><code><span v-for="(token, tokenIndex) in line" :key="tokenIndex" :class="`syntax-${token.kind}`">{{ token.text }}</span></code></div></div></template>
