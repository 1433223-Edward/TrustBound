<script setup>
import { computed, inject, onMounted, onUnmounted, ref, watch } from 'vue'
import { createApiClient } from '../api/client.js'
import { language, message, planText, t } from '../i18n.js'
import AgentActivity from './AgentActivity.vue'
import demo from '../data/demo.json'
import ProjectFileTree from './ProjectFileTree.vue'
import SnapshotIdentity from './SnapshotIdentity.vue'
import EvidenceFrame from './EvidenceFrame.vue'
import StatusBadge from './StatusBadge.vue'
import WorkbenchBrand from './WorkbenchBrand.vue'
import WorkspaceRunPanel from './WorkspaceRunPanel.vue'
import WorkspaceChat from './WorkspaceChat.vue'
import ProjectPlanDialog from './ProjectPlanDialog.vue'
import CodeWorkspace from './CodeWorkspace.vue'
import { importableProjectFile } from '../fileTree.js'
import { workspaceRoute } from '../workspaceConversation.js'

const client = createApiClient()
const props = defineProps({ sourceCopy: Object })
const emit = defineEmits(['copy-opened'])
const controller = new AbortController()
const enabled = ref(null)
const capabilities = ref({})
const sampleFiles = ref(null)
const token = ref('')
const project = ref(null)
const projectId = ref('')
const selected = ref('')
const goal = ref('')
const entrypoint = ref('')
const referenceProfile = ref('none')
const paths = ref([])
const publicCases = ref('[]')
const acceptanceCases = ref('[]')
const adversarialCases = ref('[]')
const implementation = ref('')
const constraints = ref('')
const risks = ref('')
const dirty = ref(false)
const busy = ref(false)
const error = ref('')
const zipPicker = ref(null)
const folderPicker = ref(null)
const model = ref('')
const models = ref(null)
const preferences = inject('workbenchPreferences')
const edits = ref(null)
const folders = ref([])
const historyTab = ref('')
const runs = ref([])
const versions = ref([])
const historicalRun = ref(null)
const viewedVersion = ref(null)
const saveState = ref('')
const recentKey = 'trustbound-workspace-last-v1'
let autosaveTimer
const draftKey = id => 'trustbound-workspace-draft-v1:' + id
const sourceDirty = computed(() => edits.value !== null || Object.keys(drafts.value).length > 0)
const viewingHistory = computed(() => Boolean(historicalRun.value || viewedVersion.value))
const reportRun = computed(() => historicalRun.value ?? run.value)
const workingFiles = () => sourceFiles.value.map(file => ({ path: file.path, content: drafts.value[file.path] ?? file.content }))

const planSource = ref('')
const directory = ref('')
const planPath = 'TRUSTBOUND_PLAN.json'
const drafts = ref({})
const run = ref(null)
const planOpen = ref(false)
const acceptanceBasis = ref('')
const questions = ref('')
const confirmAcceptance = ref(false)
const quickMode = ref(false)
const executionRequested = ref(false)
const messages = ref([])
const runCommand = ref(null)
const runPanel = ref(null)
const settings = computed(() => ({ execution: preferences.value.execution, correctnessVerification: preferences.value.correctnessVerification !== false }))
watch(model, value => { if (preferences) preferences.value.model = value })
const needsToken = computed(() => capabilities.value.access !== 'local')
const developerTools = computed(() => capabilities.value.access === 'local' &&
  (import.meta.env.DEV || new URLSearchParams(location.search).get('developer') === '1'))
const sourceFiles = computed(() => edits.value ?? project.value?.files ?? [])
const displayFiles = computed(() => project.value?.plan
  ? [...sourceFiles.value, { path: planPath, content: planSource.value || JSON.stringify(project.value.plan, null, 2) }]
  : sourceFiles.value)
const visibleFiles = computed(() => {
  if (historicalRun.value) return historicalRun.value.historical_source?.files ?? []
  if (!viewedVersion.value) return displayFiles.value
  return [...displayFiles.value, ...viewedVersion.value.snapshot.files.filter(file =>
    !displayFiles.value.some(current => current.path === file.path)).map(file => ({ path: file.path, content: '' }))]
})
const currentFile = computed(() => visibleFiles.value.find(file => file.path === selected.value))
const originalFile = computed(() => historicalRun.value ? currentFile.value : viewedVersion.value ? { ...currentFile.value, content: drafts.value[selected.value] ?? currentFile.value?.content } : project.value?.files.find(file => file.path === selected.value) ?? currentFile.value)
const editorDraft = computed(() => {
  if (viewingHistory.value) return undefined
  if (Object.hasOwn(drafts.value, selected.value)) return drafts.value[selected.value]
  return currentFile.value?.content !== originalFile.value?.content ? currentFile.value?.content : undefined
})
const displayedChanges = computed(() => [...new Set([...changed.value, ...Object.keys(drafts.value),
  ...sourceFiles.value.filter(file => !project.value?.files.some(old => old.path === file.path)).map(file => file.path)])])
const editable = computed(() => Boolean(currentFile.value && selected.value !== planPath && !busy.value && !viewingHistory.value))
const manualFiles = computed(() => Object.fromEntries(Object.entries(drafts.value)
  .filter(([path]) => project.value?.plan?.allowed_write_paths.includes(path))))
const sourceChangesBlockRun = sourceDirty
const changed = computed(() => run.value?.review === 'REJECTED' ? [] : run.value?.workspace_report?.changed_paths ?? [])
const currentDiff = computed(() => {
  if (!historicalRun.value && (run.value?.review === 'REJECTED' || sourceDirty.value) || viewedVersion.value) return ''
  const patch = reportRun.value?.workspace_report?.diff ?? ''
  const files = patch.split(/(?=^--- a\/.+\r?\n\+\+\+ b\/.+\r?\n@@ )/m)
  return files.find(part => part.startsWith(`--- a/${selected.value}\n`)) ?? ''
})
const comparison = computed(() => currentDiff.value ? {
  run_id: reportRun.value.workspace_report.run_id, diff: currentDiff.value,
} : null)
const canApprove = computed(() => project.value?.state === 'PLAN_READY' && !dirty.value &&
  (project.value.plan?.correctness_verification ?? true) === settings.value.correctnessVerification)
const planning = computed(() => project.value?.plan?.planning)
const missing = computed(() => planning.value?.missing_requirements ?? [])
const directReview = computed(() => planning.value?.route === 'DIRECT' && project.value.state === 'PLAN_READY')
const clarify = computed(() => project.value?.state === 'CLARIFYING')
const idPattern = /^[a-f0-9]{32}$/

onMounted(async () => {
  try {
    capabilities.value = (await client.health(controller.signal)).workspace ?? {}
    enabled.value = capabilities.value.enabled === true
    if (enabled.value && !needsToken.value) {
      let id
      try { id = localStorage.getItem(recentKey) } catch { /* Storage is optional for opening projects. */ }
      if (idPattern.test(id ?? '')) {
        try { open(await request('/' + id)) } catch { /* The preview database may have changed. */ }
      }
    }
  }
  catch (failure) { enabled.value = false; error.value = failure }
})
onMounted(() => {
  window.addEventListener('pagehide', flushDraft)
  window.addEventListener('keydown', saveShortcut)
})
onUnmounted(() => {
  flushDraft()
  window.removeEventListener('pagehide', flushDraft)
  window.removeEventListener('keydown', saveShortcut)
  controller.abort()
})

function flushDraft() {
  clearTimeout(autosaveTimer)
  if (!project.value || !sourceDirty.value) return
  try {
    // Store only working source and layout. Tokens, model messages and approved plans stay out of the draft.
    localStorage.setItem(draftKey(project.value.project_id), JSON.stringify({
      base: project.value.snapshot_hash, files: workingFiles(), folders: folders.value,
    }))
    saveState.value = 'autosaved'
  } catch { saveState.value = 'failed' }
}

watch([drafts, edits, folders], () => {
  clearTimeout(autosaveTimer)
  if (!project.value || !sourceDirty.value) return
  saveState.value = 'unsaved'
  autosaveTimer = setTimeout(flushDraft, 450)
}, { deep: true })

function saveShortcut(event) {
  if (location.hash.split('/')[0] !== '#workspace' || !(event.ctrlKey || event.metaKey) ||
      event.key.toLowerCase() !== 's' || !project.value || planOpen.value) return
  event.preventDefault()
  if (!viewingHistory.value && sourceDirty.value) void saveSnapshot()
}

function restoreDraft(snapshot) {
  try {
    localStorage.setItem(recentKey, snapshot.project_id)
    const draft = JSON.parse(localStorage.getItem(draftKey(snapshot.project_id)))
    if (draft?.base === snapshot.snapshot_hash && Array.isArray(draft.files)) {
      edits.value = draft.files
      folders.value = Array.isArray(draft.folders) ? draft.folders : []
      saveState.value = 'autosaved'
    }
  } catch { saveState.value = 'failed' }
}

function loadHistory(kind) {
  historyTab.value = kind
  return operate(async () => {
    const data = await request('/' + project.value.project_id + '/' + kind)
    if (kind === 'runs') runs.value = data
    else versions.value = data
  })
}

function viewRun(item) {
  return operate(async () => {
    historicalRun.value = await request('/' + project.value.project_id + '/runs/' + item.run_id + '?source=true')
    viewedVersion.value = null
    const files = historicalRun.value.historical_source?.files ?? []
    const changedPath = historicalRun.value.workspace_report?.changed_paths?.[0]
    if (changedPath || !files.some(file => file.path === selected.value)) selected.value = changedPath ?? files[0]?.path ?? ''
  })
}

function returnToCurrent() {
  historicalRun.value = null
  viewedVersion.value = null
  if (!displayFiles.value.some(file => file.path === selected.value)) selected.value = displayFiles.value[0]?.path ?? ''
}

function restoreVersion(version) {
  if (sourceDirty.value && !window.confirm(t('Replace the current draft with this saved version?', '用这个已保存版本替换当前草稿？'))) return
  edits.value = version.snapshot.files.map(({ path, content }) => ({ path, content }))
  drafts.value = {}
  folders.value = version.snapshot.folders ?? []
  returnToCurrent()
  flushDraft()
}


function createProject() {
  return operate(async () => open(await request('', {
    files: [{ path: 'main.py', content: 'def solve(value):\n    raise NotImplementedError()\n' }],
  })))
}

async function operate(action) {
  if (busy.value) return
  if (needsToken.value && !token.value.trim()) { error.value = { code: 'WORKSPACE_AUTH_REQUIRED' }; return }
  busy.value = true
  error.value = ''
  try { await action() }
  catch (failure) { error.value = failure }
  finally { busy.value = false }
}

function request(path, body) {
  return client.workspaceProject(path, token.value.trim(), body, controller.signal)
}

function open(snapshot) {
  const switching = project.value?.project_id !== snapshot.project_id
  if (switching) {
    flushDraft()
    historyTab.value = ''
    runs.value = []
    versions.value = []
    historicalRun.value = null
    viewedVersion.value = null
    saveState.value = ''
    sampleFiles.value = snapshot.offline_files ?? null
    drafts.value = {}
    edits.value = null
    folders.value = snapshot.folders ?? []
    directory.value = ''
    messages.value = []
    runCommand.value = null
    planOpen.value = false
    executionRequested.value = false
  }
  if (project.value?.frozen_hash !== snapshot.frozen_hash) run.value = null
  planSource.value = ''
  project.value = snapshot
  projectId.value = snapshot.project_id
  if (switching) restoreDraft(snapshot)
  if (!displayFiles.value.some(file => file.path === selected.value)) selected.value = displayFiles.value[0]?.path ?? ''
  quickMode.value = snapshot.plan?.quick_mode ?? false
  goal.value = snapshot.plan?.goal ?? ''
  entrypoint.value = snapshot.plan?.entrypoint ?? ''
  referenceProfile.value = snapshot.plan?.reference_profile ?? 'none'
  paths.value = snapshot.plan?.allowed_write_paths ?? []
  publicCases.value = JSON.stringify(snapshot.plan?.public_cases ?? [], null, 2)
  acceptanceCases.value = JSON.stringify(snapshot.plan?.acceptance_cases ?? [], null, 2)
  adversarialCases.value = JSON.stringify(snapshot.plan?.adversarial_cases ?? [], null, 2)
  implementation.value = (snapshot.plan?.implementation ?? []).join('\n')
  constraints.value = (snapshot.plan?.constraints ?? []).join('\n')
  risks.value = (snapshot.plan?.risks ?? []).join('\n')
  acceptanceBasis.value = snapshot.plan?.acceptance_basis ?? ''
  questions.value = (snapshot.plan?.questions ?? []).join('\n')
  confirmAcceptance.value = false
  dirty.value = false
}

function loadSample(name) {
  return operate(async () => {
    if (name !== 'billing') return open(await request('/samples/' + name, {}))
    const original = demo.tasks[0].original
    const imported = await request('', { files: [original, demo.publicTests] })
    open(await request('/' + imported.project_id + '/plan', { revision: imported.revision,
      goal: 'Round decimal amounts to the nearest cent, half away from zero.',
      entrypoint: 'billing.py:to_cents', allowed_write_paths: ['billing.py'],
      public_cases: [{ input: '1.239', expected: 124 }],
      implementation: ['Inspect cents conversion', 'Apply Decimal ROUND_HALF_UP', 'Check positive and negative ties'],
      constraints: ['Only modify the selected Python file; no external services'],
      risks: ['Binary floating point may change tie rounding'],
      acceptance_basis: 'Decimal rounding with ROUND_HALF_UP: 1.005 -> 101 cents; -1.005 -> -101 cents.',
      acceptance_cases: [{ input: '1.005', expected: 101 }, { input: '-1.005', expected: -101 }],
    }))
    sampleFiles.value = { 'billing.py': demo.candidates.fixed }
  })
}

function confirmLeave() {
  flushDraft()
  if (sourceDirty.value && saveState.value === 'failed') {
    return window.confirm(t('Autosave failed. Leave and lose the unsaved source edits?', '自动保存失败。仍要离开并丢弃未保存的源码修改吗？'))
  }
  return !dirty.value || window.confirm(t('Leave and discard unsaved plan edits? Your source draft is separate.', '离开并丢弃未提交的计划编辑？源码草稿单独保存。'))
}

function backToProjects() {
  if (!confirmLeave()) return
  project.value = null
  try { localStorage.removeItem(recentKey) } catch { /* The project remains available by ID. */ }
  planOpen.value = false
  edits.value = null
  drafts.value = {}
  dirty.value = false
}

function mutateFiles(action, row, destination) {
  if (busy.value) return false
  const target = row?.path ?? ''
  const contains = path => path === target || path.startsWith(target + '/')
  if (action === 'delete') {
    if (!target || target === planPath || !window.confirm(t('Delete from the working copy, including unsaved edits here?', '从工作副本删除（含其中的未保存编辑）？') + ' ' + target)) return
    edits.value = sourceFiles.value.filter(file => !contains(file.path))
    drafts.value = Object.fromEntries(Object.entries(drafts.value).filter(([path]) => !contains(path)))
    folders.value = folders.value.filter(path => !contains(path))
    if (contains(selected.value)) selected.value = edits.value[0]?.path ?? ''
    directory.value = ''
    return true
  }
  if (!destination || destination.toLowerCase() === planPath.toLowerCase()) return false
  const occupied = [...sourceFiles.value.map(file => file.path), ...folders.value]
  if (!/^[A-Za-z0-9_.-]+(?:\/[A-Za-z0-9_.-]+)*$/.test(destination) ||
      destination.split('/').some(part => part === '.' || part === '..') ||
      occupied.some(path => path.toLowerCase() === destination.toLowerCase() || path.toLowerCase().startsWith(destination.toLowerCase() + '/')) ||
      sourceFiles.value.some(file => destination.toLowerCase().startsWith(file.path.toLowerCase() + '/')) ||
      (action === 'rename' && (!target || target === planPath || destination.startsWith(target + '/')))) {
    error.value = t('Choose a new valid project-relative path.', '请选择有效且未被占用的项目相对路径。')
    return false
  }
  if ((action === 'file' || (action === 'rename' && !row?.directory)) && !/\.(py|txt|md)$/.test(destination)) {
    error.value = t('Use a .py, .txt or .md file.', '文件类型须为 .py、.txt 或 .md。')
    return false
  }
  if (action === 'folder') {
    folders.value = [...folders.value, destination]
    directory.value = destination
    edits.value ??= sourceFiles.value.slice()
  } else if (action === 'file') {
    edits.value = [...sourceFiles.value, { path: destination, content: '' }]
    selected.value = destination
    directory.value = ''
  } else {
    const renamed = path => contains(path) ? destination + path.slice(target.length) : path
    edits.value = sourceFiles.value.map(file => ({ ...file, path: renamed(file.path) }))
    folders.value = folders.value.map(renamed)
    selected.value = renamed(selected.value)
    directory.value = directory.value ? destination : ''
  }
  const nextDrafts = {}
  for (const file of sourceFiles.value) {
    const previous = action === 'rename' && (file.path === destination || file.path.startsWith(destination + '/'))
      ? target + file.path.slice(destination.length) : file.path
    if (Object.hasOwn(drafts.value, previous)) nextDrafts[file.path] = drafts.value[previous]
  }
  drafts.value = nextDrafts
  return true
}

function saveSnapshot() {
  return operate(async () => {
    if (!sourceDirty.value || viewingHistory.value) return
    const id = project.value.project_id
    const route = '/' + id + '/versions'
    const body = { revision: project.value.revision, files: workingFiles(), folders: folders.value }
    saveState.value = 'saving'
    try {
      const slots = await request(route)
      if (slots.length >= 3 && !window.confirm(t('Replace the oldest manual version? Run evidence is kept.', '覆盖最早的手动版本？运行证据仍会保留。'))) {
        flushDraft()
        return
      }
      const snapshot = await request(route, { ...body, replace_oldest: slots.length >= 3 })
      edits.value = null
      drafts.value = {}
      sampleFiles.value = null
      open(snapshot)
      saveState.value = 'saved'
      try { localStorage.removeItem(draftKey(id)) } catch { /* An older draft cannot match changed source. */ }
      if (historyTab.value === 'versions') versions.value = await request(route)
      say(t('Source saved as a new revision. Approve a new plan before running.', '源码已保存为新修订。运行前请重新批准计划。'), 'system')
    } catch (failure) { saveState.value = 'failed'; throw failure }
  })
}

function selectFile(path) {
  directory.value = ''
  selected.value = path
  if (!viewingHistory.value && path === planPath && project.value.frozen_hash) {
    void operate(async () => {
      const blob = await client.workspaceProject('/' + project.value.project_id + '/plan-document/' + project.value.revision,
        token.value.trim(), undefined, controller.signal, true)
      planSource.value = await blob.text()
    })
  }
}

function loadModels() {
  return operate(async () => {
    models.value = (await request('/models')).models
    model.value = models.value.includes(preferences?.value.model) ? preferences.value.model : models.value[0] ?? ''
  })
}

function say(text, role = 'agent', modelId) {
  messages.value.push({ role, text, model: modelId, source: 'CONTROL_EVENT' })
}

function showRun(value) {
  const report = value?.workspace_report
  if (!viewingHistory.value && report?.changed_paths.length && report.run_id !== run.value?.workspace_report?.run_id
      && !report.changed_paths.includes(selected.value)) {
    selected.value = report.changed_paths[0]
  }
  if (value?.review === 'REJECTED') {
    for (const path of report.changed_paths) {
      if (drafts.value[path] === report.replacements[path]) delete drafts.value[path]
    }
  }
  run.value = value
}

function editDraft(content) {
  if (content === currentFile.value.content) delete drafts.value[selected.value]
  else drafts.value[selected.value] = content
}

function retainDraft(files) {
  if (viewingHistory.value || sourceDirty.value) return
  edits.value = project.value.files.map(file => ({ ...file, content: files[file.path] ?? file.content }))
  drafts.value = {}
  flushDraft()
  say(t('Retained changes loaded into the editing draft. Save a new source revision and approve its checks before executing.', '保留的改动已载入编辑草稿。运行前请保存新源码修订，并重新批准验收条件。'), 'system')
}

watch([() => props.sourceCopy, enabled, token], ([copy, ready, credential]) => {
  if (!copy || !ready || (needsToken.value && !credential.trim())) return
  if (!confirmLeave()) { emit('copy-opened'); return }
  void operate(async () => {
    const imported = await request('', { files: copy.files })
    open(imported)
    emit('copy-opened')
    open(await request(`/${imported.project_id}/plan`, { ...copy.plan, revision: imported.revision }))
    say(t('Editable copy opened. Edit the candidate in the code pane, then review the plan before running.',
      '已打开独立副本。可以在代码区编辑候选，运行前请审核计划。'))
  })
}, { immediate: true })

function send(text) {
  if (busy.value) return
  messages.value.push({ role: 'user', text })
  const intent = workspaceRoute(text, quickMode.value)
  if (intent.kind === 'quick') {
    return quickReply(text)
  }
  if (intent.kind === 'greeting') {
    say(t('Hello. Describe the change you want, or ask to inspect the imported files.', '你好。描述希望修改的内容，或让我查看已导入的文件。'))
    return
  }
  if (intent.kind === 'question') {
    say(t('The current project is ' + project.value.files.map(file => file.path).join(', ') +
      '. Use /files to inspect it, or describe a concrete change. No execution was started.',
      '当前项目包含 ' + project.value.files.map(file => file.path).join('、') +
      '。输入 /files 可查看文件，或描述具体修改目标。当前尚未启动执行。'))
    return
  }
  if (intent.kind === 'files') {
    messages.value.push({ role: 'agent', permission: 'files', text: t(
      'Allow listing file names from the imported snapshot?', '允许列出已导入快照的文件名吗？') })
    return
  }
  if (intent.kind === 'plan') {
    executionRequested.value = false
    planOpen.value = true
    return
  }
  if (intent.kind === 'run' || intent.kind === 'restore') {
    executionRequested.value = true
    if (project.value.state !== 'FROZEN' || dirty.value) {
      say(t('Approve the current plan before running checks or restoring a candidate.', '执行或回退前，请先确认当前计划。'))
      if (goal.value.trim()) void change('triage')
      else if (!quickMode.value) planOpen.value = true
      else say(t('Describe the change first. Scope and trusted checks are required before execution.', '请先描述修改目标。执行前需要明确范围和可信验收条件。'), 'system')
    } else {
      executionRequested.value = false
      runCommand.value = intent
    }
    return
  }
  prepareChange(intent.goal)
}

function prepareChange(text) {
  executionRequested.value = false
  const intent = { goal: text }
  goal.value = clarify.value && !missing.value.includes('objective')
    ? `${goal.value}\n${intent.goal}` : intent.goal
  dirty.value = true
  if (!entrypoint.value) {
    const entries = project.value.files.flatMap(file => {
      const entry = /^def (solve|quote)\(/m.exec(file.content)
      return file.path.endsWith('.py') && entry ? [{ path: file.path, name: entry[1] }] : []
    })
    if (entries.length === 1) {
      entrypoint.value = `${entries[0].path}:${entries[0].name}`
      paths.value = [entries[0].path]
    }
  }
  void change('triage')
}

function quickReply(text, contextPath) {
  return operate(async () => {
    const reply = await request('/' + project.value.project_id + '/chat', {
      revision: project.value.revision, text, authorize_model: true,
      model_id: model.value || undefined, language: language.value === 'zh-CN' ? 'zh' : 'en',
      ...(contextPath ? { context_path: contextPath, authorize_context: true } : {}),
    })
    messages.value.push({ role: 'agent', text: reply.reply, model: reply.model,
      permission: reply.action === 'read_context' ? 'context' : reply.action === 'execution_request' ? 'prepare' : null,
      requestText: text, contextPath: selected.value, source: reply.source })
  })
}

function resolveAction(index, allowed) {
  const item = messages.value[index]
  const permission = item.permission
  item.permission = null
  if (!allowed) { say(t('Permission denied. No action was started.', '权限已拒绝，未启动操作。'), 'system'); return }
  if (permission === 'context') {
    if (sourceDirty.value) { say(t('Save the selected source before sharing it.', '发送源码前请先保存。'), 'system'); return }
    return quickReply(item.requestText, item.contextPath)
  }
  // This prepares bounded execution requirements, never a model-granted permission.
  if (permission === 'prepare') prepareChange(item.requestText)
}

function resolveFiles(index, allowed) {
  messages.value[index].permission = null
  say(allowed ? project.value.files.map(file => file.path).join('\n') : t('File listing denied.', '已拒绝列出文件。'))
}

function generateWithAI() {
  return operate(async () => {
    if (sourceDirty.value) throw new Error(t('Save source edits before generating a plan.', '生成计划前请先保存源码编辑。'))
    if (!model.value || !goal.value.trim()) throw new Error(t('Select a Vultr model and enter a goal first.', '请先选择 Vultr 模型并输入目标。'))
    const snapshot = await request('/' + project.value.project_id + '/generate-plan', {
      revision: project.value.revision, goal: goal.value, model_id: model.value, authorize_model: true, correctness_verification: settings.value.correctnessVerification,
    })
    open(snapshot)
    planOpen.value = true
    say(t('Vultr drafted a plan. Review its scope and proposed expected results before approval.',
      'Vultr 已生成计划草案，请审核修改范围及建议的期望结果，再决定是否批准。'), 'agent',
      snapshot.plan?.planning?.inference_usage?.calls?.find(call => call.response_model)?.response_model)
  })
}

function updateQuickMode(value) {
  quickMode.value = value
  say(value ? t('Quick chat enabled. Messages go directly to the model; source access and execution need separate approval.',
    '已开启快捷聊天。消息直接交给模型，源码读取和执行仍需单独授权。') :
    t('Quick Mode disabled. Task triage and plan review apply to new tasks.', '已关闭快捷模式，新任务恢复分流及计划审核。'), 'system')
}

function downloadPlan() {
  return operate(async () => {
    const blob = await client.workspaceProject(`/${project.value.project_id}/plan-document/${project.value.revision}`,
      token.value.trim(), undefined, controller.signal, true)
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = 'TRUSTBOUND_PLAN.json'
    link.click()
    setTimeout(() => URL.revokeObjectURL(url), 1000)
  })
}

function loadProject() {
  return operate(async () => {
    if (!confirmLeave()) return
  const id = projectId.value.trim()
    if (!idPattern.test(id)) throw new Error(t('Use a 32-character project ID.', '项目 ID 应为 32 位小写十六进制字符。'))
    open(await request(`/${id}`))
  })
}

function importProject(event, isZip) {
  const selectedFiles = Array.from(event.target.files)
  const files = isZip ? selectedFiles : selectedFiles.filter(importableProjectFile)
  if (!confirmLeave()) { event.target.value = ''; return }
  event.target.value = ''
  if (!files.length) { error.value = t('Choose a folder containing Python files.', 'Choose a folder containing Python files.'); return }
  return operate(async () => {
    if (isZip) {
      if (files[0].size > 65536) throw new Error(t('ZIP limit: 64 KiB.', 'ZIP 最大 64 KiB。'))
      const bytes = new Uint8Array(await files[0].arrayBuffer())
      let binary = ''
      for (const byte of bytes) binary += String.fromCharCode(byte)
      open(await request('', { zip_base64: btoa(binary) }))
    } else {
      if (files.filter(file => file.name !== 'TRUSTBOUND_PLAN.json').length > 20 || files.some(file => file.size > (file.name === 'TRUSTBOUND_PLAN.json' ? 16384 : 4096))) {
        throw new Error(t('Import up to 20 files, 4 KiB each and 24 KiB total.', '最多 20 个文件，单文件 4 KiB，总大小 24 KiB。'))
      }
      const utf8 = new TextDecoder('utf-8', { fatal: true, ignoreBOM: true })
      const rows = await Promise.all(files.map(async file => ({
        path: file.webkitRelativePath.split('/').slice(1).join('/') || file.name,
        content: utf8.decode(await file.arrayBuffer()),
      })))
      open(await request('', { files: rows }))
    }
  })
}

function change(action, options = {}) {
  return operate(async () => {
    const { project_id: id, revision } = project.value
    if (sourceDirty.value) throw new Error(t("Save the source snapshot first.", "请先保存源码快照。"))
    const body = { revision }
    if (action === 'plan' || action === 'triage') {
      try {
        const lines = value => value.split('\n').map(line => line.trim()).filter(Boolean)
        Object.assign(body, { correctness_verification: settings.value.correctnessVerification, reference_profile: referenceProfile.value, quick_mode: quickMode.value, goal: goal.value, entrypoint: entrypoint.value, allowed_write_paths: paths.value,
          public_cases: JSON.parse(publicCases.value), acceptance_cases: JSON.parse(acceptanceCases.value),
          adversarial_cases: preferences?.value.challenges === false ? [] : JSON.parse(adversarialCases.value), implementation: lines(implementation.value),
          constraints: lines(constraints.value), risks: lines(risks.value),
          acceptance_basis: acceptanceBasis.value, questions: lines(questions.value), ...options })
      } catch {
        throw new Error(t('Enter valid JSON for the case lists.', '请为用例列表输入有效 JSON。'))
      }
    }
    if (action === 'triage' && !preferences?.value.semanticTriage) body.authorize_model = false
    if (action === 'freeze') {
      body.confirm_acceptance = confirmAcceptance.value
      body.approval = planning.value?.route === 'DIRECT' ? 'direct' : 'formal'
      body.adversarial_enabled = preferences?.value.challenges !== false
    }
    open(await request(`/${id}/${action}`, body))
    if (action === 'triage') {
      const route = planning.value.route
      planOpen.value = !quickMode.value && executionRequested.value && route === 'PLAN_REQUIRED'
      executionRequested.value = false
      say({
        DIRECT: t('This task qualifies for quick approval. Check the scope and cases below.', '此任务可快速确认，请核对下方范围与用例。'),
        CLARIFY: t('I need the details shown below before deciding how to proceed.', '请补充下方缺失条件，再重新分流。'),
        PLAN_REQUIRED: t('Review the formal plan before allowing execution.', '此任务需要先审核正式计划，再授权执行。'),
      }[route])
    }
    if (action === 'freeze') {
      planOpen.value = false
      say(t('Plan approved and saved as TRUSTBOUND_PLAN.json in the managed project. Use /run to request execution.',
        '计划已确认并保存为托管项目根目录的 TRUSTBOUND_PLAN.json。输入 /run 申请执行。'))
    }
  })
}
</script>

<template>
  <section class="app-shell unified-workbench">
    <header class="topbar">
      <WorkbenchBrand />
      <div class="top-task"><span class="muted">/</span>{{ $t('Agent Workspace', 'Agent 工作区') }}
        <StatusBadge :status="(viewingHistory || !sourceDirty ? reportRun?.workspace_report?.status : null) ?? project?.state ?? 'WAITING'" />
      </div>
      <div v-if="enabled" class="top-actions">
        <span v-if="project && saveState" class="muted micro" role="status">{{ { unsaved: $t('Unsaved', '未保存'),
          saving: $t('Saving…', '保存中…'), saved: $t('Saved version', '已保存版本'),
          autosaved: $t('Autosaved draft', '已自动保存草稿'), failed: $t('Save failed', '保存失败') }[saveState] }}</span>
        <button v-if="project" class="primary-button" type="button" :disabled="busy || !sourceDirty || viewingHistory" @click="saveSnapshot">{{ $t('Save', '保存') }}</button>
        <button v-if="project" class="primary-button" type="button" :disabled="busy || ['QUEUED', 'RUNNING'].includes(run?.state)" @click="backToProjects">{{ $t("Back to Projects", "返回项目选择") }}</button>
        <button v-if="project" class="primary-button" type="button" :disabled="busy" @click="planOpen = true">{{ $t('Edit project plan', '修改计划书') }}</button>
        <button class="run-button" type="button" :disabled="busy" @click="zipPicker.click()">＋ {{ $t('Import ZIP', '导入 ZIP') }}</button>
        <button class="primary-button" type="button" :disabled="busy" @click="folderPicker.click()">{{ $t('Open folder', '打开文件夹') }}</button>
      </div>
    </header>
    <p v-if="error" role="alert" class="error-banner">{{ message(error) }}</p>
    <p v-if="enabled === null" role="status" class="product-notice">{{ $t('Connecting to the backend…', '正在连接后端…') }}</p>
    <div v-else-if="!enabled" class="workspace-launch product-card">
      <span class="capability-icon" aria-hidden="true">⌑</span>
      <h2>{{ $t('Private access required', '需要私有访问') }}</h2>
      <p>{{ $t('This deployment has not enabled project imports. You can still explore the recorded Billing demo.', '此部署未启用项目导入。仍可体验 Billing 历史演示。') }}</p>
      <a class="product-button primary" href="#demo">{{ $t('Open Demo Replay', '打开演示回放') }} ↗</a>
    </div>
    <template v-else>
      <input ref="zipPicker" type="file" accept=".zip" hidden @change="importProject($event, true)">
      <input ref="folderPicker" type="file" webkitdirectory="" directory="" multiple hidden @change="importProject($event, false)">
      <div class="mode-bar workspace-mode-bar"><p><span class="live-label">{{ $t('PRIVATE WORKSPACE', '私有工作区') }}</span>{{ $t('Describe a task in chat, then authorize sandbox execution.', '在聊天中描述任务，再授权沙盒执行。') }}</p>
      <details class="access-bar" :open="needsToken && !token">
        <summary><span aria-hidden="true">{{ needsToken ? '⌑' : '↶' }}</span>
          {{ needsToken ? $t('Private access', '私有访问') : $t('Open an existing project', '打开已有项目') }}
          <span v-if="needsToken" class="muted">{{ $t('Token and existing project', '令牌与已有项目') }}</span></summary>
        <fieldset class="product-form" :disabled="busy">
          <label v-if="needsToken">{{ $t('Access token', '访问令牌') }} <input v-model="token" type="password" autocomplete="off" spellcheck="false"></label>
          <label>{{ $t('Existing project ID', '已有项目 ID') }} <input v-model="projectId" spellcheck="false"></label>
          <button class="product-button" type="button" @click="loadProject">{{ $t('Open snapshot', '打开快照') }}</button>
        </fieldset>
      </details></div>
      <p v-if="busy" role="status" class="workspace-progress"><span class="spinner" aria-hidden="true"></span>{{ $t('Working…', '正在处理…') }}</p>
      <div v-if="!project" class="workspace-launch product-card">
        <div class="launch-main">
          <div class="launch-icon" aria-hidden="true">▱</div>
          <div><h2>{{ $t('Start with a project', '从一个项目开始') }}</h2>
            <p>{{ $t('Choose a small Python project or explore a prepared sample with a reproducible plan.', '选择小型 Python 项目，或体验带有可复现计划的样例。') }}</p>
            <div class="product-actions">
              <button class="product-button primary" type="button" :disabled="busy" @click="folderPicker.click()">{{ $t('Open project folder', '打开项目文件夹') }} →</button>
              <button class="product-button" type="button" :disabled="busy" @click="zipPicker.click()">{{ $t('Import ZIP', '导入 ZIP') }}</button>
            </div>
            <small class="muted">{{ $t('Up to 20 files · 4 KiB each · 24 KiB total', '最多 20 个文件 · 单文件 4 KiB · 总计 24 KiB') }}</small>
          </div>
        </div>
        <button class="primary-button" type="button" :disabled="busy" @click="createProject">{{ $t("New Python project", "新建 Python 项目") }}</button>
        <div class="sample-grid">
          <button class="sample-tile" type="button" :disabled="busy" @click="loadSample('billing')"><span class="sample-mark">01</span><strong>Billing Rounding</strong><small>{{ $t("Import sample project", "导入样例项目") }}</small><span aria-hidden="true">→</span></button>
          <button class="sample-tile" type="button" :disabled="busy" @click="loadSample('inventory')"><span class="sample-mark">02</span><strong>Inventory Reconciliation</strong><small>{{ $t('Import sample project', '导入样例项目') }}</small><span aria-hidden="true">→</span></button>
          <button class="sample-tile" type="button" :disabled="busy" @click="loadSample('logs')"><span class="sample-mark">03</span><strong>Application Log Summary</strong><small>{{ $t('Import sample project', '导入样例项目') }}</small><span aria-hidden="true">→</span></button>
        </div>
      </div>
      <div v-if="project" class="workspace-grid" :aria-busy="busy">
        <aside class="task-panel">
          <div class="task-scroll">
            <ProjectFileTree :files="visibleFiles" :folders="historicalRun ? [] : folders" :selected="selected" :changed="displayedChanges" :directory="directory" :mutate="viewingHistory ? undefined : mutateFiles" :disabled="busy" :protected-path="planPath"
              @select="selectFile" @directory="directory = $event" />
            <div class="file-actions" :aria-label="$t('Working copy actions', '工作副本操作')">

              <small v-if="edits || Object.keys(drafts).length" class="muted">{{ $t('Working draft · approve again after saving', '工作草稿 · 保存后须重新批准') }}</small>
            </div>
            <div class="file-actions history-actions">
              <button class="primary-button" type="button" :aria-pressed="historyTab === 'runs'" @click="loadHistory('runs')">{{ $t('Run History', '运行历史') }}</button>
              <button class="primary-button" type="button" :aria-pressed="historyTab === 'versions'" @click="loadHistory('versions')">{{ $t('Version History', '文件版本') }}</button>
            </div>
            <section v-if="historyTab" class="workspace-history">
              <div class="file-actions">
                <button v-if="viewingHistory" class="primary-button" type="button" @click="returnToCurrent">{{ $t('Back to current', '返回当前工作区') }}</button>
                <button class="primary-button" type="button" :disabled="busy" @click="loadHistory(historyTab)">{{ $t('Refresh', '刷新') }}</button>
              </div>
              <template v-if="historyTab === 'runs'">
                <button v-for="item in runs" :key="item.run_id" type="button" class="history-row"
                  :aria-pressed="historicalRun?.run_id === item.run_id" :disabled="busy" @click="viewRun(item)">
                  <strong>{{ item.title }}</strong><StatusBadge :status="item.status || item.state" />
                  <time :datetime="item.created_at">{{ new Date(item.created_at).toLocaleString() }}</time>
                  <code>{{ item.run_id }}</code><small v-if="item.summary">{{ message(item.summary) }}</small>
                </button>
                <p v-if="!runs.length" class="muted micro">{{ $t('No runs yet.', '暂无运行。') }}</p>
              </template>
              <template v-else>
                <div v-for="version in versions" :key="version.revision" class="history-version">
                  <button type="button" class="history-row" :aria-pressed="viewedVersion?.revision === version.revision"
                    @click="historicalRun = null; viewedVersion = version">
                    <strong>r{{ version.revision }} · {{ version.hash.slice(0, 12) }}</strong>
                    <time :datetime="version.saved_at">{{ new Date(version.saved_at).toLocaleString() }}</time>
                  </button>
                  <button class="primary-button" type="button" :disabled="busy" @click="restoreVersion(version)">{{ $t('Restore as draft', '恢复为草稿') }}</button>
                </div>
                <p v-if="!versions.length" class="muted micro">{{ $t('No manual versions yet.', '暂无手动版本。') }}</p>
              </template>
            </section>
            <SnapshotIdentity :id="project.project_id" :hash="historicalRun?.historical_source?.snapshot_hash ?? viewedVersion?.hash ?? project.snapshot_hash" :label="$t('Project snapshot', '项目快照')" />
            <div class="file-actions">
              
            </div>

          </div>
        </aside>
        <CodeWorkspace v-if="currentFile" :key="selected" :task="{ original: originalFile }" :report="comparison"
          :candidate="viewedVersion?.snapshot.files.find(file => file.path === selected)?.content ?? (historicalRun || !sourceDirty ? reportRun?.workspace_report?.replacements[selected] : undefined)"
          :single="!comparison && !viewedVersion && !historicalRun && editorDraft === undefined" :editable="editable"
          :draft="editorDraft" :version-comparison="!!viewedVersion" :version-label="viewedVersion ? 'r' + viewedVersion.revision : historicalRun ? historicalRun.run_id : undefined" mode="WORKSPACE" @edit="editDraft" />
        <aside class="trace-panel project-chat-panel">
          <WorkspaceChat :messages="viewingHistory ? [] : messages" :read-only="viewingHistory" :busy="busy" :quick-mode="quickMode" @quick-mode="updateQuickMode" @send="send"
            @action="resolveAction($event, true)" @deny-action="resolveAction($event, false)" @files="resolveFiles($event, true)" @deny-files="resolveFiles($event, false)">
            <template #model>
              <div v-if="!viewingHistory && capabilities.live_enabled" class="chat-model">
                <button v-if="models === null" class="primary-button" type="button" :disabled="busy" @click="loadModels">{{ $t('Check available Vultr models', '查询可用 Vultr 模型') }}</button>
                <label v-else class="field-label">{{ $t('Model', '模型') }} <select v-model="model">
                  <option value="">{{ $t('Offline', '离线') }}</option>
                  <option v-for="id in models" :key="id">{{ id }}</option>
                </select></label>
              </div>
            </template>
            <template #activity>
              <p class="chat-stage micro" role="status">{{ busy ? (quickMode ? $t('Waiting for reply…', '等待回复…') : $t('Planning…', '规划中…')) : run?.state === 'RUNNING' ? $t('Executing · awaiting evidence', '执行中 · 等待证据') : reportRun?.workspace_report ? $t('Completed', '已完成') : project?.state === 'FROZEN' ? $t('Approved · ready to execute', '已批准 · 可以执行') : $t('Awaiting task approval', '等待任务批准') }}</p>
              <AgentActivity :project="project" :run="viewingHistory ? historicalRun : run" inline @evidence="runPanel?.showEvidence($event)" /></template>
            <template v-if="!viewingHistory">
            <div v-if="project.state === 'PLAN_READY' && !directReview" class="chat-message">
              <button class="primary-button" type="button" @click="planOpen = true">{{ $t('Review project plan', '审核项目计划书') }}</button>
            </div>
            <form v-if="clarify" class="chat-message triage-card" @submit.prevent="change('triage')" @input="dirty = true">
              <strong>{{ $t('CLARIFY · Missing details', 'CLARIFY · 补充条件') }}</strong>
              <ul><li v-for="item in project.plan.questions" :key="item">{{ planText(item) }}</li></ul>
              <label v-if="missing.includes('objective')">{{ $t('Expected behavior', '预期行为') }} <textarea v-model="goal" rows="2" maxlength="1200"></textarea></label>
              <label v-if="missing.includes('entrypoint')">{{ $t('Entry function', '入口函数') }} <input v-model="entrypoint" placeholder="main.py:solve"></label>
              <div v-if="missing.includes('scope')">{{ $t('Allowed files', '允许修改的文件') }}
                <label v-for="file in project.files.filter(file => file.path.endsWith('.py'))" :key="file.path">
                  <input v-model="paths" type="checkbox" :value="file.path"> {{ file.path }}
                </label>
              </div>
              <label v-if="missing.includes('public_cases')">{{ $t('Public cases (JSON)', '公开用例（JSON）') }} <textarea v-model="publicCases" rows="3" class="mono"></textarea></label>
              <label v-if="missing.includes('acceptance_cases')">{{ $t('Independent cases (JSON)', '独立验收用例（JSON）') }} <textarea v-model="acceptanceCases" rows="3" class="mono"></textarea></label>
              <label>{{ $t('Trusted expectation basis', '可信预期依据') }} <textarea v-model="acceptanceBasis" rows="2" maxlength="1200"></textarea></label>
              <label>{{ $t('Unresolved questions (clear after resolving)', '待确认问题（解决后清除）') }} <textarea v-model="questions" rows="2"></textarea></label>
              <p v-if="missing.includes('public_cases') || missing.includes('acceptance_cases')"><code>[{"input": 1, "expected": 2}]</code></p>
              <p v-if="planning.source === 'VULTR'">{{ $t('Answer the question in chat to reevaluate the goal.', '在聊天里回答问题，系统会重新判断目标。') }}</p>
              <button class="product-button" type="submit" :disabled="busy">{{ $t('Check again', '重新分流') }}</button>
            </form>
            <section v-if="directReview" class="chat-message triage-card">
              <strong>{{ $t('DIRECT · Quick approval', 'DIRECT · 快速确认') }}</strong>
              <p>{{ project.plan.goal }}</p>
              <p>{{ preferences?.challenges !== false ? $t('Live execution includes one independent adversarial request. Up to two model requests per run.', '真实执行包含一次独立对抗请求。每次运行最多两次模型请求。') : $t('Independent adversarial model is off.', '独立对抗模型已关闭。') }}</p>
              <p v-if="project.plan.reference_rules" class="micro">{{ project.plan.reference_rules }}</p>
              <p>{{ project.plan.allowed_write_paths.join(', ') }} · {{ project.plan.entrypoint }}</p>
              <details><summary>{{ $t('Inspect exact acceptance cases', '核对具体用例') }}</summary>
                <pre class="product-code">{{ JSON.stringify({ public: project.plan.public_cases, acceptance: project.plan.acceptance_cases, challenges: project.plan.adversarial_cases }, null, 2) }}</pre>
              </details>
              <div class="product-actions">
                <label><input v-model="confirmAcceptance" type="checkbox">{{ settings.correctnessVerification ? $t('I reviewed independent expectations and their basis.', '我已审核独立验收预期及其依据。') : $t('I reviewed the execution scope and sandbox permission.', '我已审核执行范围和沙箱权限。') }}</label>
                <p>{{ project.plan.acceptance_basis || project.plan.reference_rules }}</p>
                <button class="product-button primary" type="button" :disabled="busy || !canApprove || !confirmAcceptance" @click="change('freeze')">{{ $t('Approve scope', '确认范围') }}</button>
                <button class="product-button" type="button" :disabled="busy" @click="change('triage', { request_formal: true })">{{ $t('Request formal plan', '改用正式计划') }}</button>
              </div>
            </section>
            <section v-if="preferences?.semanticTriage && planning?.semantic_eligible && capabilities.live_enabled && !dirty && !project.frozen_hash" class="chat-message triage-card">
              <strong>{{ $t('Optional semantic review', '可选语义判断') }}</strong>
              <p>{{ $t('Send the goal and project paths to Vultr for one classification request, up to 1024 output tokens.', '授权把目标和项目路径发给 Vultr，进行一次分流判断，最多 1024 输出 Tokens。') }}</p>
              <details><summary>{{ $t('Review disclosed data', '查看发送范围') }}</summary>
                <p>{{ project.plan.goal }}</p>
              <p>{{ preferences?.challenges !== false ? $t('Live execution includes one independent adversarial request. Up to two model requests per run.', '真实执行包含一次独立对抗请求。每次运行最多两次模型请求。') : $t('Independent adversarial model is off.', '独立对抗模型已关闭。') }}</p>
              <p v-if="project.plan.reference_rules" class="micro">{{ project.plan.reference_rules }}</p><p>{{ project.plan.entrypoint }}</p>
                <ul><li v-for="file in project.files" :key="file.path">{{ file.path }}</li></ul>
              </details>
              <button class="product-button" type="button" :disabled="busy" @click="change('triage', { authorize_model: true })">{{ $t('Authorize Vultr classification', '授权 Vultr 分流') }}</button>
            </section>
            </template>
            <div id="workspace-chat-controls"></div>
          </WorkspaceChat>
        </aside>
        <WorkspaceRunPanel ref="runPanel" @retain-draft="retainDraft" @reviewed="historicalRun = $event" v-if="project.state === 'FROZEN' || historicalRun" :key="project.frozen_hash ?? project.project_id"
          :project="project" :token="token" :capabilities="capabilities" :sample-files="sampleFiles" :dirty="dirty || sourceChangesBlockRun"
          :model="model" :settings="settings" :command="runCommand" :developer-tools="developerTools"
          :history-record="historicalRun" :viewing-version="!!viewedVersion" :source-dirty="sourceDirty" :manual-files="manualFiles" :adversarial-enabled="preferences?.challenges !== false" :offer-recovery="preferences?.recovery !== false" @record="showRun" @note="say($event, 'system')" />
        <EvidenceFrame v-else>
          <template #status><span class="muted micro">{{ $t('Awaiting evidence', '等待证据') }}</span></template>
          <div class="empty-state evidence-empty"><span class="empty-symbol small">▤</span><div>
            <h3>{{ $t('No evidence collected', '暂无证据') }}</h3>
            <p>{{ $t('Approve the task and authorize a run to collect evidence.', '确认任务并授权执行后收集证据。') }}</p>
          </div></div>
        </EvidenceFrame>
      </div>
      <ProjectPlanDialog v-if="project" v-model="planOpen" :title="$t('Project plan', '项目计划书')">
          <form class="workspace-plan" @submit.prevent="change('plan')" @input="dirty = true">
            <p v-if="(project.plan?.correctness_verification ?? true) !== settings.correctnessVerification" class="product-notice">{{ $t('Update the plan to apply the selected verification mode before approval.', '批准前请更新计划，以应用所选验证模式。') }}</p>
            <div class="panel-label">{{ $t('Plan & approval', '计划与确认') }} <span class="product-chip">r{{ project.revision }}</span></div>
            <fieldset class="product-form plan-fields" :disabled="busy">
              <div class="plan-ai-actions">
                <p>{{ preferences?.challenges !== false ? $t('Adversarial Agent ON. Approval allows parallel Executor and independent adversarial analysis during Live runs, within host quotas. At most two 4096-token generations per run.', '对抗 Agent 已开启。批准后，Live 运行将在宿主额度内并行进行执行提案与独立对抗分析，每次运行最多两次 4096 Token 生成。') : $t('Adversarial Agent OFF. Runner protections remain required.', '对抗 Agent 已关闭，Runner 安全限制仍强制生效。') }}</p>
                <p v-if="error" class="product-notice" role="alert">{{ message(error) }}</p>
                <button class="primary-button" type="button" :disabled="busy || !capabilities.live_enabled || !model || !goal.trim() || sourceDirty" @click="generateWithAI">{{ $t('Generate with AI', 'AI 生成计划书') }}</button>
                <p class="muted micro">{{ $t('Uses the selected model and source files. One paid request, up to 4096 output tokens. Proposed tests require your review.', '使用已选模型及源码。一次付费请求，最多 4096 输出 Token。建议用例需要你审核。') }}</p>
                <p v-if="!model" class="muted micro">{{ $t('Choose a model in Agent Chat before generating.', '请先在 Agent 对话中选择模型。') }}</p>
              </div>
              <p v-if="!settings.correctnessVerification" class="product-notice">{{ $t('Functional verification is off. Approve scope and entrypoint; business cases and expected values are optional.', '功能验证已关闭。请批准修改范围和入口；业务用例及期望值为可选项。') }}</p>
              <label>{{ $t('Development goal', '开发目标') }} <textarea v-model="goal" required maxlength="1200" rows="3" :placeholder="$t('Describe the behavior you want…', '描述你希望实现的行为…')"></textarea></label>
              <details class="plan-criteria" open>
                <summary>{{ $t('Scope & acceptance criteria', '修改范围与验收条件') }}</summary>
                <label>{{ $t('Trusted reference profile', '可信参考规则') }}
                  <select v-model="referenceProfile">
                    <option value="none">{{ $t('No registered reference · new behavior requires confirmation', '无注册参考规则 · 新行为需人工确认') }}</option>
                    <option value="inventory">Inventory reconciliation v1</option><option value="logs">Application log summary v1</option>
                  </select>
                </label>
                <p v-if="project.plan?.reference_rules" class="micro">{{ project.plan.reference_rules }}</p>
                <label>{{ $t('Entry function', '入口函数') }} <input v-model="entrypoint" placeholder="main.py:solve" spellcheck="false"></label>
                <div class="file-scope">{{ $t('Allowed files', '允许修改的文件') }}
                  <label v-for="file in project.files.filter(file => file.path.endsWith('.py'))" :key="file.path">
                    <input v-model="paths" type="checkbox" :value="file.path"> {{ file.path }}
                  </label>
                </div>
                <p class="muted">{{ $t('Use JSON cases with input and expected fields. Keep public and independent inputs distinct.', '用例使用含 input 和 expected 的 JSON，两组输入应不同。') }}</p>
                <label>{{ $t('Public cases', '公开用例') }} <textarea v-model="publicCases" class="mono" rows="3" spellcheck="false"></textarea></label>
                <label>{{ $t('Independent acceptance', '独立验收') }} <textarea v-model="acceptanceCases" class="mono" rows="3" spellcheck="false"></textarea></label>
                <label v-if="preferences?.challenges">{{ $t('Independent challenge cases (optional)', '独立挑战用例（可选）') }} <textarea v-model="adversarialCases" class="mono" rows="3" spellcheck="false"></textarea></label>
                <p class="muted">{{ $t('Provide distinct input and trusted expected output for each challenge. The candidate sees only the input.', '为每个挑战提供不同的输入和可信期望值。候选只收到输入。') }}</p>
                <label>{{ $t('Basis for independent expectations', '独立验收预期依据') }} <textarea v-model="acceptanceBasis" rows="3" maxlength="1200"></textarea></label>
                <label>{{ $t('Open questions (one per line; clear after resolving)', '待确认问题（每行一项，解决后清除）') }} <textarea v-model="questions" rows="3"></textarea></label>
                <label><input v-model="confirmAcceptance" type="checkbox" @input.stop>{{ settings.correctnessVerification ? $t('I reviewed the independent expected values and their basis.', '我已审核独立验收期望值及其依据。') : $t('I reviewed the execution scope and sandbox permission.', '我已审核执行范围和沙箱权限。') }}</label>
              </details>
              <details class="plan-criteria" open>
                <summary>{{ $t('Implementation, constraints & risks', '实施步骤、约束与风险') }}</summary>
                <label>{{ $t('Implementation steps, one per line', '实施步骤，每行一项') }} <textarea v-model="implementation" rows="3" maxlength="1200"></textarea></label>
                <label>{{ $t('Task constraints, one per line', '任务约束，每行一项') }} <textarea v-model="constraints" rows="2" maxlength="1200"></textarea></label>
                <label>{{ $t('Risks, one per line', '风险，每行一项') }} <textarea v-model="risks" rows="2" maxlength="1200"></textarea></label>
                <p class="muted">{{ $t('Sandbox limits and host protections are enforced separately.', '沙盒限制及宿主安全策略由控制层单独执行。') }}</p>
              </details>
              <div class="product-actions">
                <button class="product-button" type="button" @click="planOpen = false">{{ $t("Cancel", "取消") }}</button>
                <button class="product-button" :class="{ primary: !canApprove }" type="submit">{{ project.plan ? $t('Update plan', '更新计划') : $t('Draft offline plan', '生成离线计划') }}</button>
                <button v-if="project.plan && !project.frozen_hash" class="product-button" type="button" @click="change('triage', { request_formal: true })">{{ $t('Regenerate formal draft', '重新生成正式草案') }}</button>
                <button v-if="project.state === 'FROZEN' && !dirty" class="product-button" type="button" @click="downloadPlan">{{ $t('Download plan file', '下载计划书') }}</button>
                <button v-if="canApprove && !directReview" class="product-button primary" type="button" :disabled="!confirmAcceptance" @click="change('freeze')">{{ $t('Approve & freeze', '确认并冻结') }}</button>
                <button v-if="['CLARIFYING', 'PLAN_READY'].includes(project.state)" class="product-button subtle" type="button" @click="change('reject')">{{ $t('Reject plan', '拒绝计划') }}</button>
              </div>
            </fieldset>
            <div v-if="dirty || project.plan" class="plan-review">
              <p v-if="dirty" class="muted">{{ $t('Unsaved changes. Update the plan before approving.', '有未提交的修改，请先更新计划。') }}</p>
              <template v-if="project.plan">
                <p class="muted">{{ planning?.route ?? 'PLAN_REQUIRED' }} · {{ planning?.source === 'VULTR' ? 'Vultr' : $t('Local rules', '本地规则') }} · {{ $status(project.state) }}</p>
                <ul v-if="planning?.risk_flags.length"><li v-for="risk in planning.risk_flags" :key="risk">{{ $status(risk) }}</li></ul>
                <p v-if="planning?.fallback_reason">{{ $t('Semantic review was unavailable. Formal approval remains required.', '语义判断未完成，仍需正式计划批准。') }}</p>
                <p v-if="planning?.inference_usage?.live_request_count">{{ $t('Vultr requests', 'Vultr 请求') }} {{ planning.inference_usage.live_request_count }} · {{ $t('Output tokens', '输出 Tokens') }} {{ planning.inference_usage.completion_tokens ?? '—' }}</p>
                <template v-if="project.plan.questions.length"><strong>{{ $t('Open questions', '待答问题') }}</strong><ul><li v-for="item in project.plan.questions" :key="item">{{ planText(item) }}</li></ul></template>
                <ol v-else-if="preferences?.planSummary"><li v-for="step in project.plan.steps" :key="step">{{ planText(step) }}</li></ol>
                <p v-if="preferences?.planSummary" class="muted">{{ project.plan.suggestions.map(planText).join(' · ') }}</p>
              </template>
            </div>
          </form>
      </ProjectPlanDialog>
    </template>
    <footer class="statusbar"><span><span class="status-light"></span>{{ $t('Trusted control · isolated execution', '可信控制 · 隔离执行') }}</span>
      <span class="mono">{{ project?.snapshot_hash?.slice(0, 12) || $t('No project open', '尚未打开项目') }}</span></footer>
  </section>
</template>
