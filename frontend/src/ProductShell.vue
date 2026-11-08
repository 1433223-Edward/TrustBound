<script setup>
import { computed, onMounted, onUnmounted, provide, ref, watch } from 'vue'
import BillingWorkbench from './App.vue'
import ProjectWorkspace from './components/ProjectWorkspace.vue'
import ProductManual from './components/ProductManual.vue'
import ProductSettings from './components/ProductSettings.vue'
import ProductHome from './components/ProductHome.vue'
import { language, t } from './i18n.js'

const pages = {
  home: ['Home', '首页'], demo: ['Demo Replay', '演示回放'], workspace: ['Agent Workspace', '工作区'],
  documentation: ['Documentation', '文档'], settings: ['Settings', '设置'],
}
const defaults = { theme: 'dark', language: 'en', density: 'comfortable', wrap: false, codeView: 'both', semanticTriage: true, planSummary: true, correctnessVerification: false, challenges: false, recovery: false, execution: 'ask', model: '', start: 'home' }
const storageKey = 'trustbound-interface-v1'
function readPreferences() {
  let legacyExecution = 'ask'
  try {
    if (JSON.parse(localStorage.getItem('trustbound-workspace-permissions'))?.execution === 'deny') legacyExecution = 'deny'
  } catch { /* Keep the default when the legacy value cannot be read. */ }
  try {
    const saved = JSON.parse(localStorage.getItem(storageKey)) ?? {}
    return {
      theme: saved.theme === 'light' ? 'light' : defaults.theme,
      language: saved.language === 'zh-CN' ? 'zh-CN' : defaults.language,
      density: saved.density === 'compact' ? 'compact' : defaults.density,
      wrap: saved.wrap === true,
      codeView: ['original', 'candidate'].includes(saved.codeView) ? saved.codeView : 'both',
      semanticTriage: saved.semanticTriage !== false,
      planSummary: saved.planSummary !== false,
      challenges: saved.challenges === true,
      correctnessVerification: saved.correctnessVerification === true,
      recovery: saved.recovery === true,
      execution: ['ask', 'deny'].includes(saved.execution) ? saved.execution : legacyExecution,
      model: typeof saved.model === 'string' ? saved.model : '', 
      start: ['home', 'demo', 'workspace', 'documentation'].includes(saved.start) ? saved.start : defaults.start,
    }
  } catch { return { ...defaults } }
}
const preferences = ref(readPreferences())
provide("workbenchPreferences", preferences)
const persistenceError = ref(false)
const readPage = () => {
  const key = location.hash.slice(1).split('/')[0]
  return Object.hasOwn(pages, key) ? key : preferences.value.start
}
const page = ref(readPage())
const workspaceCopy = ref(null)
const shellClasses = computed(() => [preferences.value.theme, preferences.value.density,
  { 'wrap-code': preferences.value.wrap }])

function navigate() {
  const next = readPage()
  if (page.value !== next) {
    page.value = next
    window.scrollTo(0, 0)
  }
}
function openWorkspaceCopy(copy) {
  workspaceCopy.value = copy
  location.hash = 'workspace'
}
onMounted(() => window.addEventListener('hashchange', navigate))
onUnmounted(() => window.removeEventListener('hashchange', navigate))
watch(preferences, value => {
  try { localStorage.setItem(storageKey, JSON.stringify(value)); persistenceError.value = false }
  catch { persistenceError.value = true }
}, { deep: true })
watch(() => preferences.value.language, value => {
  language.value = value
  document.documentElement.lang = value
}, { immediate: true, flush: 'sync' })
</script>

<template>
  <div class="product-shell" :class="shellClasses">
    <header class="product-header">
      <a href="#home" class="product-brand"><svg viewBox="0 0 24 24" fill="none" aria-hidden="true"><path d="m12 2 8 4v6c0 4-4 8-8 10-4-2-8-6-8-10V6l8-4Z" stroke="currentColor" stroke-width="1.6"/><path d="m8 12 3 3 5-6" stroke="currentColor" stroke-width="1.6"/></svg>TrustBound</a>
      <nav :aria-label="t('Main navigation', '主导航')">
        <a v-for="(label, id) in pages" :key="id" :href="'#' + id"
          :aria-current="page === id ? 'page' : undefined">{{ t(...label) }}</a>
      </nav>
    </header>
    <main>
      <ProductHome v-if="page === 'home'" />
      <div v-show="page === 'demo'"><BillingWorkbench @edit-copy="openWorkspaceCopy" /></div>
      <KeepAlive><ProjectWorkspace v-if="page === 'workspace'" :source-copy="workspaceCopy" @copy-opened="workspaceCopy = null" /></KeepAlive>
      <ProductManual v-if="page === 'documentation'" />
      <ProductSettings v-if="page === 'settings'" v-model="preferences" :persistence-error="persistenceError" />
    </main>
  </div>
</template>
