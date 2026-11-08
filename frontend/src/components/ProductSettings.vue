<script setup>
import { onMounted, onUnmounted, ref } from 'vue'
import { createApiClient } from '../api/client.js'

const preferences = defineModel({ required: true })
defineProps({ persistenceError: Boolean })
const health = ref(null)
const group = ref('appearance')
const checked = ref(false)
const controller = new AbortController()
onMounted(async () => {
  try { health.value = await createApiClient().health(controller.signal) }
  catch { /* The interface preferences are available without a backend. */ }
  finally { checked.value = true }
})
onUnmounted(() => controller.abort())
</script>

<template>
  <section class="product-page settings-page">
    <header class="page-heading"><span class="eyebrow product-kicker"><i></i>{{ $t('PREFERENCES', '偏好设置') }}</span><h1>{{ $t('Settings', '设置') }}</h1>
      <p>{{ $t('Personalize your interface and inspect deployment limits.', '调整界面偏好，查看部署限制。') }}</p></header>
    <p v-if="persistenceError" role="alert" class="product-notice">{{ $t('Browser storage is unavailable. Changes apply to this page only.', '浏览器存储不可用，本次偏好仅在当前页面有效。') }}</p>
    <div class="settings-layout">
      <nav class="settings-nav" :aria-label="$t('Settings categories', '设置分类')">
        <button v-for="([id, name], index) in [['appearance', $t('Appearance', '外观')], ['workspace', $t('Workspace', '工作区')], ['agent', $t('Agent workflow', 'Agent 工作方式')], ['execution', $t('System limits', '系统限制')]]" :key="id" type="button"
          :aria-pressed="group === id" :class="{ selected: group === id }" @click="group = id"><span class="mono">0{{ index + 1 }}</span>{{ name }}</button>
      </nav>
      <div class="settings-content product-card">
        <section v-if="group === 'appearance'">
          <h2>{{ $t('Appearance & language', '外观与语言') }}</h2>
          <p>{{ $t('Your preferences are saved in this browser.', '偏好保存在当前浏览器。') }}</p>
          <div class="setting-row"><div><strong>{{ $t('Language', '界面语言') }}</strong><small>{{ $t('Applies across the product.', '适用于整个产品界面。') }}</small></div>
            <div class="settings-segments" role="group" :aria-label="$t('Language', '语言')">
              <button type="button" :aria-pressed="preferences.language === 'en'" @click="preferences.language = 'en'">English</button>
              <button type="button" :aria-pressed="preferences.language === 'zh-CN'" @click="preferences.language = 'zh-CN'">简体中文</button>
            </div>
          </div>
          <div class="setting-row"><div><strong>{{ $t('Theme', '主题') }}</strong><small>{{ $t('Choose a light or dark surface.', '选择浅色或深色界面。') }}</small></div>
            <div class="settings-segments" role="group" :aria-label="$t('Theme', '主题')">
              <button type="button" :aria-pressed="preferences.theme === 'light'" @click="preferences.theme = 'light'">☼ {{ $t('Light', '浅色') }}</button>
              <button type="button" :aria-pressed="preferences.theme === 'dark'" @click="preferences.theme = 'dark'">◐ {{ $t('Dark', '深色') }}</button>
            </div>
          </div>
          <label class="setting-row"><span>{{ $t('Display density', '显示密度') }}</span><select v-model="preferences.density"><option value="comfortable">{{ $t('Comfortable', '舒适') }}</option><option value="compact">{{ $t('Compact', '紧凑') }}</option></select></label>
        </section>
        <section v-else-if="group === 'workspace'">
          <h2>{{ $t('Workspace preferences', '工作区偏好') }}</h2>
          <label class="setting-row"><span>{{ $t('Code View Preferences', '代码视图偏好') }}</span>
            <select v-model="preferences.codeView"><option value="original">{{ $t('Original', '原始代码') }}</option><option value="candidate">{{ $t('Candidate', '候选修改') }}</option><option value="both">{{ $t('Both', '并排显示') }}</option></select>
          </label>
          <label class="setting-row"><span>{{ $t('Default page', '默认入口') }}</span><select v-model="preferences.start">
            <option value="home">{{ $t('Home', '首页') }}</option><option value="demo">{{ $t('Demo Replay', '演示回放') }}</option>
            <option value="workspace">{{ $t('Agent Workspace', '工作区') }}</option><option value="documentation">{{ $t('Documentation', '文档') }}</option>
          </select></label>
          <label class="setting-row"><span>{{ $t('Wrap code in Workspace and Documentation', '工作区及手册代码自动换行') }}</span><input v-model="preferences.wrap" type="checkbox"></label>
        </section>
        <section v-else-if="group === 'agent'">
          <h2>{{ $t('Agent workflow', 'Agent 工作方式') }}</h2>
          <label class="setting-row correctness-setting"><div><strong>{{ $t('Code Correctness Verification', '代码正确性验证') }}</strong><small>{{ $t('For new Workspace runs. Off executes one approved input without business tests; permissions, isolation, limits, cleanup and evidence checks remain mandatory. Adversarial analysis is configured separately. Fixed Billing evaluations and system regression tests are unaffected.', '适用于新的 Workspace 运行。关闭后仅运行一份授权输入，不做业务测试；权限、隔离、资源限制、清理及证据检查仍强制执行。对抗分析单独配置，Billing 固定评测与系统回归不受影响。') }}</small></div><input type="checkbox" v-model="preferences.correctnessVerification"></label>
          <label class="setting-row"><div><strong>{{ $t('Sandbox permission', '沙盒权限') }}</strong><small>{{ $t('Applies to Workspace runs and retries.', '适用于工作区运行与重试。') }}</small></div><select v-model="preferences.execution">
            <option value="ask">{{ $t('Ask before execution', '执行前询问') }}</option>
            <option value="deny">{{ $t('Deny execution', '禁止执行') }}</option>
          </select></label>
          <label class="setting-row"><div><strong>{{ $t('Optional Vultr triage', '可选 Vultr 分流') }}</strong><small>{{ $t('Local rules, clarification and approval always apply.', '本地规则、必要澄清和批准始终生效。') }}</small></div><input type="checkbox" v-model="preferences.semanticTriage"></label>
          <label class="setting-row"><div><strong>{{ $t('Plan summary', '计划摘要') }}</strong><small>{{ $t('Show the summary in Plan Review.', '在计划审核中展示摘要。') }}</small></div><input type="checkbox" v-model="preferences.planSummary"></label>
          <label class="setting-row"><div><strong>{{ $t('Adversarial Agent', '独立对抗 Agent') }}</strong><small>{{ $t('Live runs start independent analysis after plan approval. Switching on requires approval of the model budget. Off makes no adversarial model call.', '批准计划后，Live 运行自动启动独立分析。开启需批准模型预算。关闭后不发起对抗模型调用。') }}</small></div><input type="checkbox" v-model="preferences.challenges"></label>
          <label class="setting-row"><div><strong>{{ $t('Offer Retry Fix', '显示重试修复') }}</strong><small>{{ $t('Available retries require authorization. Automatic recovery is unavailable in Workspace.', '可用的重试仍需授权。Workspace 暂不支持自动恢复。') }}</small></div><input type="checkbox" v-model="preferences.recovery"></label>
          <div v-if="health?.workspace?.live_enabled" class="setting-row"><div><strong>{{ $t('Model preference', '模型偏好') }}</strong><small>{{ $t('Choose an available model in Workspace chat. Your choice is remembered.', '在工作区对话中选择可用模型，选择会被记住。') }}</small></div><span>{{ preferences.model || '—' }}</span></div>
        </section>
        <section v-else>
          <h2>{{ $t('Execution & access', '执行与访问') }}</h2>
          <p>{{ $t('Deployment settings are read-only here. Reviewer access is managed by the host.', '此处仅展示部署设置。评委访问权限由部署端管理。') }}</p>
          <p v-if="!checked" role="status">{{ $t('Checking the backend…', '正在读取后端状态…') }}</p><p v-else-if="!health">{{ $t('Backend status unavailable.', '后端状态不可用。') }}</p>
          <dl v-else class="product-facts">
            <dt>{{ $t('Execution modes', '执行模式') }}</dt><dd>{{ Object.entries(health.modes).filter(([, mode]) => mode.enabled).map(([name]) => name).join(' · ') }}</dd>
            <dt>{{ $t('Concurrent tasks', '最大并发任务') }}</dt><dd>{{ health.max_concurrent_runs }}</dd>
            <dt>{{ $t('Persistent quota', '持久化配额') }}</dt><dd>{{ health.persistent_quota ? $t('Enabled', '已启用') : $t('Disabled', '未启用') }}</dd>
            <dt>{{ $t('Project Workspace', '项目工作区') }}</dt><dd>{{ health.workspace?.enabled ? $t('Private access enabled', '已启用私有访问') : $t('Disabled', '未启用') }}</dd>
          </dl>
        </section>
      </div>
    </div>
  </section>
</template>
