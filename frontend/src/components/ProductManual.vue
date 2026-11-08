<script setup>
import { computed, onMounted } from 'vue'
import chinese from '../../../docs/TRUSTBOUND_PUBLIC_HANDBOOK.md?raw'
import english from '../../../docs/TRUSTBOUND_PUBLIC_HANDBOOK_EN.md?raw'
import { parseManual } from '../manual.js'
import { t } from '../i18n.js'

const blocks = computed(() => parseManual(t(english, chinese)))
const headings = computed(() => blocks.value.filter(block => block.type === 'heading' && block.level === 2))
onMounted(() => {
  const anchor = headings.value.find(block => location.hash === '#' + block.id)
  if (anchor) document.getElementById(anchor.id)?.scrollIntoView()
})
</script>

<template>
  <section class="product-page manual-layout">
    <aside class="manual-index">
      <nav :aria-label="$t('Documentation contents', '文档目录')">
        <span class="eyebrow">{{ $t('ON THIS PAGE', '文档目录') }}</span>
        <a v-for="heading in headings" :key="heading.id" :href="'#' + heading.id">{{ heading.text }}</a>
      </nav>
    </aside>
    <article class="product-manual product-card">
      <span class="eyebrow product-kicker"><i></i>{{ $t('PRODUCT HANDBOOK', '产品手册') }}</span>
      <template v-for="(block, index) in blocks" :key="index">
        <component :is="'h' + block.level" v-if="block.type === 'heading'" :id="block.id">{{ block.text }}</component>
        <pre v-else-if="block.type === 'code'" class="product-code"><code>{{ block.text }}</code></pre>
        <ul v-else-if="block.type === 'list'"><li v-for="(item, i) in block.items" :key="i">{{ item }}</li></ul>
        <blockquote v-else-if="block.type === 'quote'">{{ block.text }}</blockquote>
        <div v-else-if="block.type === 'table'" class="manual-table">
          <table><thead><tr><th v-for="(cell, i) in block.headers" :key="i" scope="col">{{ cell }}</th></tr></thead>
            <tbody><tr v-for="(row, i) in block.rows" :key="i"><td v-for="(cell, j) in row" :key="j">{{ cell }}</td></tr></tbody>
          </table>
        </div>
        <p v-else>{{ block.text }}</p>
      </template>
    </article>
  </section>
</template>
