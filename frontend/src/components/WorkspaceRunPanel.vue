<script setup>
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import { createApiClient } from '../api/client.js'
import StatusBadge from './StatusBadge.vue'
import EvidenceFrame from './EvidenceFrame.vue'
import { evidenceTabs } from '../evidenceTabs.js'
import { message, t } from '../i18n.js'

const props = defineProps({ project: Object, token: String, capabilities: Object, sampleFiles: Object,
  dirty: Boolean, model: String, settings: Object, command: Object, developerTools: Boolean, manualFiles: Object, offerRecovery: Boolean, adversarialEnabled: Boolean, historyRecord: Object, viewingVersion: Boolean, sourceDirty: Boolean })
const emit = defineEmits(['record', 'note', 'retain-draft', 'reviewed'])
const client = createApiClient()
const controller = new AbortController()
onUnmounted(() => controller.abort())
const mode = ref('offline')
const originalOnly = ref(false)
const pending = ref(null)
const permissionCard = ref(null)
const pendingRetry = ref(null)
const explanationPermission = ref(false)
const explaining = ref(false)
const executionInput = ref('null')
const replacements = ref({})
const busy = ref(false)
const error = ref('')
const runId = ref('')
const record = ref(null)
const displayRecord = computed(() => props.historyRecord ?? record.value)
const report = computed(() => displayRecord.value?.workspace_report)
const historyMode = computed(() => Boolean(props.historyRecord || props.viewingVersion))
const evidenceRunId = computed(() => props.historyRecord?.run_id ?? runId.value)
const tab = ref('summary')
function showEvidence(row) {
  if (row.runId && row.runId !== evidenceRunId.value) return
  tab.value = row.tab
  document.getElementById('workspace-evidence')?.scrollIntoView({ block: 'nearest' })
}
defineExpose({ showEvidence })
const tabs = computed(evidenceTabs)
const projectRoute = computed(() => '/' + props.project.project_id + '/runs')
const runRoute = computed(() => projectRoute.value + '/' + runId.value)
const sourceLabel = computed(() => ({ ORIGINAL: t('Original source', '原始源码'), OFFLINE: t('Offline candidate', '离线候选'),
  LIVE: t('Live Vultr', '真实 Vultr'), RETRY: t('Live recovery', '真实模型恢复'),
  RESTORE: t('Manual restore', '人工回退') })[report.value?.source])
const observed = computed(() => report.value?.cases.filter(item => Object.hasOwn(item, 'actual')) ?? [])
const challenges = computed(() => report.value?.cases.filter(item => item.phase === 'adversarial') ?? [])
const matched = computed(() => observed.value.filter(item => item.status === 'MATCHED').length)
const containers = computed(() => report.value?.cases.filter(item => item.execution.container_name) ?? [])
const duration = computed(() => {
  const elapsed = Date.parse(displayRecord.value?.finished_at) - Date.parse(displayRecord.value?.started_at)
  return Number.isFinite(elapsed) && elapsed >= 0 ? (elapsed / 1000).toFixed(1) : null
})
watch(record, value => emit('record', value))
watch(pending, async value => {
  if (!value) return
  await nextTick()
  permissionCard.value?.scrollIntoView({ block: 'nearest' })
})
watch(() => report.value?.run_id, () => { tab.value = 'summary' })
watch(() => props.model, value => { mode.value = value && props.capabilities.live_enabled ? 'live' : 'offline' }, { immediate: true })
watch(historyMode, value => { if (value) pending.value = null })
watch(() => props.dirty, value => { if (value) pending.value = null })
watch(() => props.settings.execution, value => { if (value === 'deny') pending.value = null })
watch(() => props.settings.correctnessVerification, () => { pending.value = null })
watch(() => props.project.frozen_hash, () => { executionInput.value = JSON.stringify(props.project.plan?.public_cases?.[0]?.input ?? null, null, 2) }, { immediate: true })
watch(() => props.command, value => {
  if (value?.kind === 'run') requestRun()
  if (value?.kind === 'restore') requestRun({ restore: value.id })
})

function request(path, body, download = false) {
  return client.workspaceProject(path, props.token.trim(), body, controller.signal, download)
}

async function operate(action) {
  if (busy.value) return
  busy.value = true
  error.value = ''
  try { await action() }
  catch (failure) { if (!controller.signal.aborted) error.value = failure }
  finally { busy.value = false }
}

function toggleFile(path, enabled) {
  if (enabled) replacements.value[path] = props.project.files.find(file => file.path === path).content
  else delete replacements.value[path]
}

async function poll() {
  if (!/^[a-f0-9]{32}$/.test(runId.value)) throw new Error(t('Use a 32-character run ID.', '运行 ID 格式不正确。'))
  for (let attempt = 0; attempt < 300 && !controller.signal.aborted; attempt++) {
    record.value = await request(runRoute.value)
    if (!['QUEUED', 'RUNNING'].includes(record.value.state)) return
    await new Promise(resolve => setTimeout(resolve, 1000))
  }
  if (!controller.signal.aborted) throw new Error(t('Wait timed out. Reopen the run using its ID.', '等待超时。保留运行 ID 并重新查看结果。'))
}

function requestRun({ restore, retry } = {}) {
  if (historyMode.value || !props.capabilities.execution || props.dirty || busy.value || pending.value) return
  if (props.settings.execution === 'deny') {
    emit('note', t('Workspace settings deny sandbox execution.', 'Workspace 设置禁止沙盒执行。'))
    return
  }
  const manual = props.manualFiles ?? {}
  const offlineFiles = originalOnly.value ? {} : Object.keys(manual).length
    ? manual : Object.keys(replacements.value).length ? replacements.value : props.sampleFiles ?? {}
  const selectedMode = restore ? 'restore' : retry || mode.value === 'live' ? 'live'
    : Object.keys(offlineFiles).length ? 'offline' : 'original'
  if (selectedMode === 'live' && !props.model) {
    emit('note', t('Select a model in Agent Chat first.', '请先在 Agent 对话中选择模型。'))
    return
  }
  const body = { revision: props.project.revision, mode: selectedMode }
  body.correctness_verification = props.settings.correctnessVerification !== false
  if (!body.correctness_verification) {
    try { body.execution_input = JSON.parse(executionInput.value) }
    catch { error.value = t('Enter valid JSON execution input.', '请输入有效 JSON 执行输入。'); return }
  }
  if (props.capabilities.live_enabled) {
    body.authorize_explanation = true
    if (props.model) body.model_id = props.model
  }
  if (selectedMode === 'offline') body.files = { ...offlineFiles }
  if (selectedMode === 'live') Object.assign(body, { authorize_source: true, model_id: props.model })
  if (restore) body.restore_run_id = restore
  if (selectedMode === 'live' && props.adversarialEnabled) {
    if (!props.project.plan.adversarial_enabled) {
      emit('note', t('Approve the plan with Adversarial Agent enabled before running.', '请先在启用独立对抗 Agent 的情况下重新批准计划。'))
      return
    }
    body.adversarial_enabled = true
  }
  if (retry) {
    body.retry_run_id = retry
    pendingRetry.value = record.value?.retry
  }
  const fingerprint = JSON.stringify(body)
  const storageKey = 'trustbound-pending-run:' + props.project.project_id
  let saved
  try { saved = JSON.parse(sessionStorage.getItem(storageKey)) } catch { /* Optional browser persistence. */ }
  body.idempotency_key = saved?.fingerprint === fingerprint ? saved.key : crypto.randomUUID()
  pending.value = body
}

function denyRun() {
  pending.value = null
  emit('note', t('Permission denied. No task was submitted.', '权限请求已拒绝，未提交任务。'))
}

function start() {
  if (!pending.value || props.dirty || props.settings.execution === 'deny') return
  const body = pending.value
  pending.value = null
  return operate(async () => {
    record.value = null
    const storageKey = 'trustbound-pending-run:' + props.project.project_id
    const { idempotency_key: key, ...requestBody } = body
    try { sessionStorage.setItem(storageKey, JSON.stringify({ key, fingerprint: JSON.stringify(requestBody) })) } catch { /* In-memory pending still retains the key. */ }
    let started
    try {
      started = await request(projectRoute.value, body)
    } catch (error) {
      pending.value = body
      throw error
    }
    try { sessionStorage.removeItem(storageKey) } catch { /* Optional browser persistence. */ }
    runId.value = started.run_id
    record.value = started
    emit('note', t(`Sandbox run submitted: ${runId.value}`, `已提交沙盒运行：${runId.value}`))
    await poll()
    if (report.value) emit('note', t(`Final report: ${report.value.status}`, `最终报告：${report.value.status}`))
  })
}

onMounted(() => {
  if (props.project.state !== 'FROZEN') return
  void operate(async () => {
    const history = await request(projectRoute.value)
    const latest = history.find(item => item.frozen_hash === props.project.frozen_hash)
    if (latest) {
      runId.value = latest.run_id
      await poll()
    }
  })
})

function review(decision) {
  return operate(async () => {
    const reviewed = await request(projectRoute.value + '/' + evidenceRunId.value + '/review/' + decision, {})
    if (props.historyRecord) emit('reviewed', { ...props.historyRecord, ...reviewed })
    else record.value = reviewed
    if (decision === 'KEPT_UNVERIFIED') emit('note', t('Changes retained by human decision, without verification approval. You can export them or load an editing draft.', '已人工确认保留修改，但未标记为验收通过。可导出，或载入编辑草稿。'))
    if (decision === 'REJECTED') emit('note', t('Unaccepted changes discarded. The original snapshot is active in the editor.',
      '已丢弃未接受修改，编辑区已恢复显示原始快照。'))
  })
}

function explainExistingRun() {
  explanationPermission.value = false
  return operate(async () => {
    explaining.value = true
    try {
      const updated = await request(projectRoute.value + '/' + evidenceRunId.value + '/explanation', {
        authorize_model: true, ...(props.model ? { model_id: props.model } : {}),
      })
      if (props.historyRecord) emit('reviewed', { ...props.historyRecord, ...updated })
      else record.value = updated
    } finally { explaining.value = false }
  })
}

function download(kind) {
  return operate(async () => {
    const id = evidenceRunId.value
    const blob = await request(projectRoute.value + '/' + id + '/export/' + kind, undefined, true)
    const url = URL.createObjectURL(blob)
    const anchor = document.createElement('a')
    anchor.href = url
    anchor.download = `trustbound-${displayRecord.value.review === 'KEPT_UNVERIFIED' ? 'unverified-' : ''}${id}.${kind}`
    anchor.click()
    setTimeout(() => URL.revokeObjectURL(url), 1000)
  })
}
</script>

<template>
  <EvidenceFrame id="workspace-evidence" v-model="tab" :tabs="tabs">
    <template #status>
      <StatusBadge v-if="report" :status="['QUEUED', 'RUNNING'].includes(displayRecord.state) ? displayRecord.state : report.status" :label="`${sourceLabel} · ${$status(['QUEUED', 'RUNNING'].includes(displayRecord.state) ? displayRecord.state : report.status)}`" />
      <StatusBadge v-else-if="displayRecord" :status="displayRecord.error?.code === 'WORKSPACE_RUN_INTERRUPTED' ? 'INCONCLUSIVE' : displayRecord.state" />
      <span v-else class="muted micro">{{ $t('Awaiting evidence', '等待证据') }}</span>
    </template>
    <Teleport defer to="#workspace-chat-controls">
    <div v-show="!historyMode && project.state === 'FROZEN'">
    <p v-if="!capabilities.execution" class="product-notice">{{ $t('This backend has no Workspace runner configured.', '当前后端未配置 Workspace Runner。') }}</p>
    <template v-else>
      <p v-if="dirty">{{ $t('Save and approve your edits before running the new plan.', '请先保存并确认新计划，再运行。') }}</p>
      <fieldset class="product-form plan-fields chat-run-options" :disabled="busy || dirty || !!pending">
        <label v-if="developerTools">{{ $t('Execution experience', '执行体验') }} <select v-model="mode">
          <option value="offline">{{ $t('Offline / Fixture', '离线 / 样例') }}</option>
          <option v-if="capabilities.live_enabled" value="live">{{ $t('Live Agent', '实时 Agent') }}</option>
        </select></label>
        <p v-if="mode === 'offline'" class="micro">{{ sampleFiles && !originalOnly ? $t('Runs the reviewed sample in Docker without model inference.', '在 Docker 中运行已审阅样例，无模型推理。') : $t('Runs the project in Docker without model inference.', '在 Docker 中运行项目，无模型推理。') }}</p>
        <p v-else class="micro">{{ $t('Uses Vultr to propose a candidate and Docker to verify it.', 'Vultr 提出候选，Docker 执行验收。') }}</p>
        <label v-if="settings.correctnessVerification === false">{{ $t('Execution input (JSON, no expected result)', '执行输入（JSON，不设业务期望值）') }}<textarea v-model="executionInput" rows="3" class="mono"></textarea></label>
        <details v-if="mode === 'offline' && developerTools"><summary>{{ $t('Developer options', '开发者选项') }}</summary>
          <label><input v-model="originalOnly" type="checkbox"> {{ $t('Run original snapshot only', '仅运行原始快照') }}</label>
          <div v-if="sampleFiles"><button class="primary-button" type="button" @click="replacements = { ...sampleFiles }">{{ $t('Load reviewed offline patch', '载入已审阅的离线补丁') }}</button></div>
          <div v-for="path in project.plan?.allowed_write_paths ?? []" :key="path">
            <label><input type="checkbox" :checked="Object.hasOwn(replacements, path)" @change="toggleFile(path, $event.target.checked)"> {{ $t('Edit', '修改') }} {{ path }}</label>
            <textarea v-if="Object.hasOwn(replacements, path)" v-model="replacements[path]" class="mono" rows="9" maxlength="4096" :aria-label="$t('Candidate', '候选') + ' ' + path" spellcheck="false"></textarea>
          </div>
        </details>
        <div><button class="primary-button" type="button" @click="requestRun()">{{ $t('Request sandbox run', '申请沙盒运行') }} →</button></div>
      </fieldset>
      <div v-if="pending" ref="permissionCard" class="chat-message permission-request">
        <p v-if="pending.correctness_verification === false">{{ $t('Security-only execution. Functional tests and business acceptance will not run; success will not be VERIFIED.', '仅安全执行：不运行功能测试或业务验收，执行成功也不会标为 VERIFIED。') }}</p>
        <pre v-if="pending.correctness_verification === false" class="product-code">{{ JSON.stringify(pending.execution_input, null, 2) }}</pre>
        <p v-if="pending.authorize_explanation">{{ $t('Also authorize one advisory model review of the frozen requirements, diff and check summaries (up to 4096 output tokens). Independent test inputs and expected values remain sealed.', '同时授权一次模型概览：对照冻结需求、差异和检查摘要说明完成情况，最多 4096 输出 Token；独立测试输入及期望值不发送。') }}</p>
        <strong>{{ $t('Permission request', '权限请求') }}</strong>
        <p>{{ $t('Run the selected candidate in a temporary sandbox under the approved plan?', '允许按已批准计划在临时沙盒运行选定候选吗？') }}</p>
        <p>{{ $t('Candidate', '候选') }}: {{ pending.mode }} · r{{ pending.revision }}</p>
        <p v-if="pending.files">{{ $t('Proposed files', '候选文件') }}: {{ Object.keys(pending.files).join(', ') }}</p>
        <p v-if="pending.restore_run_id" class="mono digest">{{ $t('Restore from', '回退来源') }} {{ pending.restore_run_id }}</p>
        <template v-if="pending.retry_run_id">
          <p>{{ $t('Retry fix from confirmed failure', '根据已确认失败重试修复') }} · {{ pendingRetry?.attempt }} / 2</p>
          <p>{{ $t('This retry also sends the following verified case and the previous candidate.', '本次重试还会发送以下已验证用例及上一轮候选。') }}</p>
          <pre class="product-code">{{ JSON.stringify(pendingRetry?.failure, null, 2) }}</pre>
        </template>
        <template v-if="pending.mode === 'live'">
          <p>{{ pending.model_id }} · {{ pending.adversarial_enabled ? $t('Execution: two independent parallel generations, up to 8192 output tokens.', '执行阶段：两次独立并行生成，最多 8192 输出 Tokens。') : $t('One Vultr generation, up to 4096 output tokens.', '一次 Vultr 生成，最多 4096 输出 Tokens。') }}</p>
          <p>{{ $t('Send the listed files, goal, scope, entry point, approved steps and constraints, and public cases. Independent inputs and answers stay with the verifier.', '发送所列文件、目标、修改范围、入口、已批准的步骤与约束，以及公开用例。独立输入与答案留在验收层。') }}</p>
          <ul><li v-for="file in project.files" :key="file.path">{{ file.path }}</li></ul>
        </template>
        <div class="product-actions">
          <button class="primary-button" type="button" @click="start">{{ $t('Allow and run', '允许并执行') }}</button>
          <button class="primary-button" type="button" @click="denyRun">{{ $t('Deny', '拒绝') }}</button>
        </div>
      </div>
    </template>
    </div>
    </Teleport>
    <div class="evidence-body">
    <p v-if="historyRecord" class="muted">{{ $t('Historical run · read-only', '历史运行 · 只读') }}</p>
    <p v-else-if="sourceDirty && report" class="muted">{{ $t('Previous snapshot evidence · draft is unverified', '上一快照的证据 · 草稿未验收') }}</p>
    <p v-if="historyRecord && ['QUEUED', 'RUNNING'].includes(historyRecord.state)" class="muted">{{ $t('Run is still active. Select it again in Run History to update.', '运行仍在执行。请在运行历史中再次选择该记录刷新。') }}</p>
    <p v-if="busy" role="status" class="workspace-progress">{{ $t('Working…', '正在处理…') }} {{ evidenceRunId }} <span v-if="record">{{ $status(record.state) }}</span></p>
    <p v-if="error || displayRecord?.error" role="alert" class="product-notice">{{ message(error || displayRecord.error) }}</p>
    <article v-if="report" class="workspace-report">
      <template v-if="tab === 'summary'">
      <div v-if="capabilities.live_enabled && ['COMPLETED', 'ERROR'].includes(displayRecord.state) && !report.explanation" class="product-actions">
        <button class="product-button" type="button" :disabled="busy" @click="explanationPermission = true">{{ $t('Explain this result against the plan', '生成本次结果的计划对照说明') }}</button>
      </div>
      <div v-if="explanationPermission" class="chat-message permission-request">
        <p>{{ $t('Send this frozen plan, diff excerpt and redacted check summaries to the configured Vultr model for one overview request, up to 4096 output tokens? Independent inputs and expectations stay sealed. This will not rerun code.', '允许将本次冻结计划、差异片段和脱敏检查摘要发送给已配置的 Vultr 模型，生成一次概览（最多 4096 输出 Token）吗？独立输入和期望值不发送，也不重新执行代码。') }}</p>
        <button class="product-button primary" type="button" :disabled="busy" @click="explainExistingRun">{{ $t('Authorize explanation', '授权生成说明') }}</button>
        <button class="product-button" type="button" @click="explanationPermission = false">{{ $t('Cancel', '取消') }}</button>
      </div>
      <p v-if="explaining">{{ $t('Reviewing the frozen requirements and recorded results…', '正在对照冻结需求与已有结果生成说明…') }}</p>
      <div v-if="!historyMode || (historyRecord && report.frozen_hash === project.frozen_hash)" class="product-actions">
        <button v-if="displayRecord.state === 'COMPLETED' && report.status === 'VERIFIED' && report.changed_paths.length && !displayRecord.review && report.frozen_hash === project.frozen_hash" class="primary-button" type="button" :disabled="busy || dirty" @click="review('ACCEPTED')">{{ $t('Accept changes', '接受修改') }}</button>
        <button v-if="['COMPLETED', 'ERROR'].includes(displayRecord.state) && report.status !== 'REJECTED' && (report.status !== 'VERIFIED' || displayRecord.state === 'ERROR') && report.changed_paths.length && !displayRecord.review && report.frozen_hash === project.frozen_hash" class="primary-button" type="button" :disabled="busy" @click="review('KEPT_UNVERIFIED')">{{ $t('Confirm retention (unverified)', '人工确认保留（未验证）') }}</button>
        <button v-if="offerRecovery && settings.correctnessVerification !== false && displayRecord.retry && !displayRecord.review && report.frozen_hash === project.frozen_hash"
          class="primary-button" type="button" :disabled="busy || dirty || !!pending" @click="requestRun({ retry: report.run_id })">{{ $t('Retry Fix', '重试修复') }}</button>
        <button v-if="!displayRecord.review && report.changed_paths.length" class="primary-button" type="button" :disabled="busy || !!pending" @click="review('REJECTED')">{{ $t('Discard changes', '丢弃未接受修改') }}</button>
        <template v-if="['ACCEPTED', 'KEPT_UNVERIFIED'].includes(displayRecord.review)">
          <p v-if="displayRecord.review === 'KEPT_UNVERIFIED'">{{ $t('Retained by you; this candidate is still unverified.', '你已确认保留，该候选仍未通过可信验收。') }}</p>
          <button class="product-button" type="button" :disabled="busy || dirty || sourceDirty" @click="emit('retain-draft', report.replacements)">{{ $t('Load changes into editing draft', '将改动载入编辑草稿') }}</button>
          <button v-if="developerTools && displayRecord.review === 'ACCEPTED'" class="primary-button" type="button" :disabled="busy || dirty || report.frozen_hash !== project.frozen_hash" @click="requestRun({ restore: report.run_id })">{{ $t('Reverify accepted candidate', '复验已接受候选') }}</button>
          <button class="primary-button" type="button" :disabled="busy" @click="download('patch')">{{ $t('Export patch', '导出 Patch') }}</button>
          <button class="primary-button" type="button" :disabled="busy" @click="download('zip')">{{ $t('Export ZIP', '导出 ZIP') }}</button>
        </template>
      </div>
      <div v-else-if="historyRecord && displayRecord.review === 'ACCEPTED'" class="product-actions">
        <button class="primary-button" type="button" :disabled="busy" @click="download('patch')">{{ $t('Export patch', '导出 Patch') }}</button>
        <button class="primary-button" type="button" :disabled="busy" @click="download('zip')">{{ $t('Export ZIP', '导出 ZIP') }}</button>
      </div>
      <div class="evidence-metrics">
        <div v-if="observed.length"><small>{{ $t('Matched / observed', '匹配 / 已观察') }}</small><strong>{{ matched }} / {{ observed.length }}</strong></div>
        <div v-if="duration"><small>{{ $t('Run duration', '运行耗时') }}</small><strong>{{ duration }} s</strong></div>
        <div v-if="containers.length"><small>{{ $t('Limits verified', '已验证资源限制') }}</small><strong>{{ containers.filter(item => item.execution.limits_verified).length }} / {{ containers.length }}</strong></div>
      </div>
      <div class="finding" :class="report.status === 'VERIFIED' ? 'finding-good' : 'finding-alert'">
        <span aria-hidden="true">{{ report.status === 'VERIFIED' ? '✓' : '↳' }}</span>
        <div><strong>{{ message(report.reason) }}</strong><p>{{ $t('VERIFIED applies only to the approved acceptance scope.', 'VERIFIED 仅表示通过已确认的验收范围。') }}</p></div>
        <StatusBadge v-if="displayRecord.review" :status="displayRecord.review" />
      </div>
      <section v-if="report.explanation" class="requirement-assessment">
        <h3>{{ $t('Model assessment against the approved plan', '模型对照已批准计划的说明') }}</h3>
        <small>{{ report.explanation.model }} · {{ $t('Advisory explanation, not a verification verdict', '模型参考说明，不替代可信裁决') }}</small>
        <p>{{ $t(report.explanation.summary.en, report.explanation.summary.zh) }}</p>
        <p v-if="report.explanation.inference_usage" class="micro">{{ $t('Additional overview requests', '额外概览请求') }} {{ report.explanation.inference_usage.live_request_count }} · {{ $t('Output tokens', '输出 Tokens') }} {{ report.explanation.inference_usage.completion_tokens ?? '—' }}</p>
        <ul><li v-for="item in report.explanation.requirements" :key="item.id">
          <strong>{{ item.status === 'met' ? $t('Model assesses met', '模型判断已满足') : item.status === 'unmet' ? $t('Not met', '未满足') : $t('Unconfirmed', '尚未确认') }}</strong>
          · {{ report.explanation.requirement_texts[item.id] }}
          <p>{{ $t(item.explanation.en, item.explanation.zh) }}</p>
        </li></ul>
      </section>
      <p v-else-if="report.explanation_status === 'RUNNING'">{{ $t('The model is reviewing the requirements against the recorded result.', '模型正在对照需求解释本次记录的结果。') }}</p>
      <p v-else-if="report.explanation_status === 'UNAVAILABLE'" class="muted">{{ $t('Model explanation was unavailable. The evidence and your review choices remain available.', '模型说明未完成；证据及人工处理按钮仍可使用。') }} {{ report.explanation_error }}</p>
      <section class="verification-evidence">
        <h3>{{ $t('Security Evidence', '安全执行证据') }}</h3>
        <p>{{ $status(report.security_evidence?.status ?? 'NOT_RECORDED') }} · {{ $t('Permission scope, sandbox isolation, resource limits, cleanup and execution identity.', '修改权限、沙箱隔离、资源限制、清理与执行身份绑定。') }}</p>
        <h3>{{ $t('Functional Verification Evidence', '功能验证证据') }}</h3>
        <p v-if="report.verification_mode === 'SECURITY_ONLY'">{{ $t('Not requested. Code execution does not establish business correctness.', '未启用。代码执行不代表业务正确性已获验证。') }}</p>
        <p v-else>{{ $status(report.functional_verification?.status ?? report.status) }} · {{ $t('Public tests and frozen independent acceptance.', '公开测试及冻结的独立验收。') }}</p>
        <small>{{ $t('Verification mode', '验证模式') }}: {{ report.verification_mode ?? 'FUNCTIONAL' }}</small>
      </section>
      <p v-if="!report.cases.some(item => item.phase === 'adversarial')" class="muted">{{ $t("No adversarial checks were executed.", "未执行对抗检查。") }}</p>
      <p v-if="report.quick_mode" class="muted">{{ $t('Quick Mode was used. Required approval and sandbox checks still applied.', '本次使用快捷模式，仍执行必要批准及沙盒检查。') }}</p>
      <details><summary>{{ $t('Original run JSON', '原始运行 JSON') }}</summary><pre class="product-code">{{ JSON.stringify(displayRecord, null, 2) }}</pre></details>
      <p v-if="report.planning_route" class="muted">{{ $t('Planning route', '分流路径') }} · {{ report.planning_route }}</p>
      <details><summary>{{ $t('Evidence identity', '证据标识') }}</summary><p class="mono digest">{{ $t('Run', '运行') }} {{ evidenceRunId }}<br>{{ $t('Frozen plan', '冻结计划') }} {{ report.frozen_hash }}<br v-if="report.artifact_hash"><template v-if="report.artifact_hash">{{ $t('Candidate', '候选') }} {{ report.artifact_hash }}</template></p></details>
      <p v-if="report.inference_usage">{{ $t('Vultr generations', 'Vultr 生成') }} {{ report.inference_usage.live_request_count }} · {{ $t('Input', '输入') }} {{ report.inference_usage.prompt_tokens ?? '—' }} · {{ $t('Output', '输出') }} {{ report.inference_usage.completion_tokens ?? '—' }} · {{ $t('Estimated USD', '估算 USD') }} {{ report.inference_usage.estimated_usd ?? '—' }}</p>
      <p v-if="report.restored_from" class="mono digest">{{ $t('Restored and reverified from', '回退并重新验证自') }} {{ report.restored_from }}</p>
      <p v-if="report.retried_from" class="mono digest">{{ $t('Retry attempt', '重试次数') }} {{ report.retry_attempt }} / 2 · {{ report.retried_from }}</p>
      </template>
      <pre v-else-if="tab === 'diff'" class="raw-diff">{{ report.diff || $t('No code changes recorded.', '未记录代码修改。') }}</pre>
      <section v-else-if="tab === 'adversarial'" class="workspace-adversarial">
        <p v-if="report.verification_mode === 'SECURITY_ONLY'" class="product-notice">{{ $t('Analysis is independent of correctness verification. Suggestions in this run were not executed as functional challenges and are not confirmed counterexamples.', '对抗分析独立配置。本次未执行功能挑战，建议不属于已确认反例。') }}</p>
        <h3>{{ $t('Adversarial Verification', '对抗验证') }}</h3>
        <p v-if="report.adversarial_enabled">{{ $t('Independent Vultr analysis was authorized for this run.', '本次运行已授权独立 Vultr 对抗分析。') }}</p>
        <p v-else>{{ $t('Independent adversarial inference was not requested.', '本次未请求独立对抗推理。') }}</p>
        <template v-if="report.adversarial_enabled">
          <StatusBadge :status="report.adversarial_report?.verification_status || report.adversarial_report?.status" />
          <p>{{ report.adversarial_report?.reason || report.adversarial_report?.scope }}</p>
          <p v-if="report.adversarial_report?.inference_usage">{{ $t('Actual model requests', '实际模型请求') }} {{ report.adversarial_report.inference_usage.live_request_count }} · {{ $t('Estimated USD', '估算 USD') }} {{ report.adversarial_report.inference_usage.estimated_usd ?? '—' }}</p>
          <details v-for="row in report.adversarial_report?.challenges ?? []" :key="row.challenge_id" class="case-evidence">
            <summary>{{ row.challenge_id }} · {{ $status(row.status) }}</summary>
            <p>{{ row.reason }} {{ row.validation_reason }}</p>
            <p v-if="row.status === 'NEEDS_CONFIRMATION'">{{ $t('Review this suggestion and update the plan before accepting new business behavior.', '请审核该建议，更新并重新批准计划后才能接受新的业务要求。') }}</p>
            <pre class="product-code">{{ JSON.stringify(row, null, 2) }}</pre>
          </details>
          <details><summary>{{ $t('Original adversarial evidence', '原始对抗证据') }}</summary><pre class="product-code">{{ JSON.stringify(report.adversarial_report, null, 2) }}</pre></details>
        </template>
        <p v-if="!report.adversarial_enabled">{{ $t('Any listed checks came from the approved plan, not a new model proposal.', '下列检查来自已批准计划，而非新的模型提议。') }}</p>
        <p v-if="!challenges.length">{{ $t('No challenge was executed in this run. Check the plan and the run stop reason.', '本次没有执行挑战，请核对计划与运行停止原因。') }}</p>
        <details v-for="item in challenges" :key="item.index" class="case-evidence">
          <summary>{{ $t('Challenge', '挑战') }} {{ item.index }} · {{ $status(item.status) }}</summary>
          <pre class="product-code">{{ JSON.stringify(item, null, 2) }}</pre>
        </details>
      </section>
      <section v-else-if="tab === 'recovery'" class="workspace-recovery">
        <h3>{{ report.retried_from ? $t('Agent repair attempt', 'Agent 修复尝试') : $t('Recovery state', '恢复状态') }}</h3>
        <p v-if="report.retried_from">{{ $t('A repair was proposed from confirmed failure evidence and verified again.', '根据已确认失败证据提出修复，并重新执行验收。') }}</p>
        <p v-else>{{ $t('No Agent Recovery was executed in this run.', '本次运行未执行 Agent Recovery。') }}</p>
        <pre v-if="report.retried_from" class="product-code">{{ JSON.stringify({
          parent_run: report.retried_from, attempt: report.retry_attempt, confirmed_failure: report.retry_evidence,
          candidate_hash: report.artifact_hash, status: report.status,
        }, null, 2) }}</pre>
        <p v-if="report.restored_from">{{ $t('The saved candidate was explicitly restored and verified again.', '已显式回退保存的候选并重新验收。') }} {{ report.restored_from }}</p>
        <p>{{ $t('Reconnecting to a run does not start another model request.', '重新连接运行记录不会发起新的模型请求。') }}</p>
      </section>
      <div v-else-if="tab === 'logs'" class="logs">
        <p v-if="!report.cases.length" class="micro">{{ $t('No sandbox execution was recorded.', '没有沙盒执行记录。') }}</p>
      <details v-for="item in report.cases" :key="item.phase + item.index" class="case-evidence">
        <summary>{{ item.phase === 'execution' ? $t('Security-only execution', '仅安全执行') : item.phase === 'public' ? $t('Public test', '公开测试') : item.phase === 'adversarial' ? $t('Independent challenge', '独立挑战') : $t('Independent acceptance', '独立验收') }} {{ item.index }} <StatusBadge :status="item.status" /></summary>
        <p>{{ $t('Container', '容器') }} {{ item.execution.container_name || '—' }} · {{ $status(item.execution.status) }} · {{ $t('Exit', '退出码') }} {{ item.execution.exit_code ?? '—' }} · {{ item.execution.cleanup_confirmed ? $t('Cleanup confirmed', '已确认清理') : $t('Cleanup unconfirmed', '未确认清理') }} · {{ item.execution.limits_verified ? $t('Limits verified', '已验证限制') : $t('Limits unverified', '未验证限制') }}</p>
        <pre class="product-code">{{ JSON.stringify({ input: item.input, expected: item.expected, actual: item.actual }, null, 2) }}</pre>
        <p v-if="item.execution.error || item.execution.timeout_reason">{{ item.execution.error || item.execution.timeout_reason }}</p>
        <details v-if="item.execution.stdout || item.execution.stderr"><summary>{{ $t('Raw process logs', '原始进程日志') }}</summary>
          <pre class="product-code">stdout: {{ item.execution.stdout || '—' }}
stderr: {{ item.execution.stderr || '—' }}</pre>
        </details>
      </details>
      </div>
    </article>
    <div v-else class="empty-state evidence-empty">
      <span class="empty-symbol small">▤</span><div><h3>{{ $t('No evidence collected', '暂无证据') }}</h3>
        <p>{{ $t('Authorize a run in Agent Chat to collect evidence.', '在 Agent 对话中授权运行后收集证据。') }}</p></div>
    </div>
    </div>
  </EvidenceFrame>
</template>
