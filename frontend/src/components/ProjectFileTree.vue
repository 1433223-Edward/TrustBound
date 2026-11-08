<script setup>
import { computed, nextTick, ref, watch } from 'vue'
import { fileTreeRows } from '../fileTree.js'

const props = defineProps({
  files: { type: Array, required: true }, selected: String, folders: Array, directory: String,
  changed: { type: Array, default: () => [] }, mutate: Function, canFork: Boolean,
  disabled: Boolean, protectedPath: String,
})
const emit = defineEmits(['select', 'directory', 'fork'])
const collapsed = ref([])
const menu = ref(null)
const edit = ref(null)
const name = ref('')
const input = ref(null)
const menuPanel = ref(null)
const allRows = computed(() => fileTreeRows(props.files.map(file => file.path), props.folders))
const rows = computed(() => allRows.value.filter(row => !collapsed.value.some(path => row.path.startsWith(path + '/'))))
const selectedRow = computed(() => allRows.value.find(row => row.path === (props.directory || props.selected)))
const labels = {
  file: ['New file', '新建文件'], folder: ['New folder', '新建文件夹'],
  rename: ['Rename', '重命名'], delete: ['Delete', '删除'],
}
const canManage = computed(() => !!props.mutate || props.canFork)
const editorOrder = computed(() => {
  if (!edit.value?.row) return 1
  const index = rows.value.findIndex(row => row.path === edit.value.row.path)
  return (index + 1) * 2 + 1
})

watch(() => props.disabled, value => { if (value) menu.value = null })
function toggle(path) {
  collapsed.value = collapsed.value.includes(path) ? collapsed.value.filter(item => item !== path) : [...collapsed.value, path]
  emit('directory', path)
}

function context(event, row) {
  if (!canManage.value || props.disabled) return
  event.preventDefault()
  const bounds = event.currentTarget.getBoundingClientRect()
  menu.value = { row, x: Math.max(4, Math.min(event.clientX || bounds.left, window.innerWidth - 224)),
    y: Math.max(4, Math.min(event.clientY || bounds.bottom, window.innerHeight - 178)) }
  nextTick(() => menuPanel.value?.querySelector('button:not(:disabled)')?.focus())
}

async function act(action, row) {
  menu.value = null
  if (!props.mutate) { if (props.canFork) emit('fork', row?.path); return }
  if (action === 'delete') { props.mutate(action, row); return }
  const parent = row?.directory && action !== 'rename' ? row.path : row?.path.split('/').slice(0, -1).join('/') || ''
  if (parent) collapsed.value = collapsed.value.filter(path => path !== parent)
  edit.value = { action, row, parent }
  name.value = action === 'rename' ? row.name : ''
  await nextTick()
  input.value?.focus()
  input.value?.select()
}

function submit() {
  const value = name.value.trim()
  if (!value) { edit.value = null; return }
  const { action, row, parent } = edit.value
  if (action === 'rename' && value === row.name) { edit.value = null; return }
  if (!input.value.checkValidity()) { input.value.reportValidity(); return }
  const destination = parent ? parent + '/' + value : value
  if (props.mutate(action, row, destination)) edit.value = null
}

function closeMenu(event) {
  if (!event.currentTarget.contains(event.relatedTarget)) menu.value = null
}
</script>

<template>
  <nav class="project-file-tree" :aria-label="$t('Project files', '项目文件')" @focusout="closeMenu" @keydown.esc="menu = null">
    <div class="section-heading explorer-heading" @contextmenu="context($event, null)">
      <span class="eyebrow">{{ $t('FILE EXPLORER', '文件浏览器') }}</span>
      <div v-if="canManage" class="explorer-tools">
        <button v-if="mutate" v-for="(symbol, action) in { file: '+▤', folder: '+▱' }" :key="action"
          type="button" :title="$t(...labels[action])" :aria-label="$t(...labels[action])" :disabled="disabled"
          @click="act(action, selectedRow)">{{ symbol }}</button>
        <button v-else type="button" :title="$t('Open editable copy', '打开可编辑副本')"
          :aria-label="$t('Open editable copy', '打开可编辑副本')" :disabled="disabled" @click="emit('fork', selected)">↗</button>
      </div>
      <span v-else class="mono muted">{{ files.length }}</span>
    </div>
    <template v-for="(row, index) in rows" :key="(row.directory ? 'dir:' : 'file:') + row.path">
      <button class="tree-row" type="button" :class="{ selected: (directory || selected) === row.path, 'tree-directory': row.directory }"
        :style="{ '--depth': row.depth, order: (index + 1) * 2 }" :aria-expanded="row.directory ? !collapsed.includes(row.path) : undefined"
        :aria-pressed="row.directory ? undefined : selected === row.path" :title="row.path"
        @contextmenu="context($event, row)" @keydown.shift.f10="context($event, row)"
        @click="menu = null; row.directory ? toggle(row.path) : emit('select', row.path)">
        <svg class="tree-chevron" :class="{ expanded: row.directory && !collapsed.includes(row.path), invisible: !row.directory }"
          viewBox="0 0 16 16" fill="none" aria-hidden="true"><path d="m6 3 5 5-5 5" /></svg>
        <svg class="tree-entry-icon" viewBox="0 0 20 20" fill="none" aria-hidden="true">
          <path v-if="row.directory" d="M2 5h6l2 2h8v10H2z" />
          <path v-else d="M5 2h7l4 4v12H5zM12 2v5h4M8 11h5m-5 3h5" />
        </svg>
        <span class="tree-name">{{ row.name }}</span><span v-if="changed.includes(row.path)" class="tree-change" :aria-label="$t('Modified', '已修改')">M</span>
      </button>
    </template>
    <div v-if="menu" ref="menuPanel" class="explorer-menu" :style="{ left: menu.x + 'px', top: menu.y + 'px' }"
      :aria-label="$t('File actions', '文件操作')">
      <small v-if="menu.row" class="mono">{{ menu.row.path }}</small>
      <button v-if="!mutate" type="button" @click="act('file', menu.row)">{{ $t('Open editable copy', '打开可编辑副本') }}</button>
      <template v-else>
        <button v-for="action in ['file', 'folder', 'rename', 'delete']" :key="action" type="button"
          :disabled="['rename', 'delete'].includes(action) && (!menu.row || menu.row.path === protectedPath)"
          @click="act(action, menu.row)">{{ $t(...labels[action]) }}</button>
      </template>
    </div>
    <form v-if="edit" class="tree-row explorer-editor" :style="{ '--depth': edit.parent ? edit.parent.split('/').length : 0, order: editorOrder }"
      @submit.prevent="submit" @keydown.esc.stop.prevent="edit = null">
      <input ref="input" v-model="name" required maxlength="80" pattern="[A-Za-z0-9_.\-]+"
        :aria-label="$t(...labels[edit.action])" :placeholder="$t(...labels[edit.action])">
      <button type="submit" :aria-label="$t('Confirm name', '确认名称')">✓</button>
      <button type="button" :aria-label="$t('Cancel', '取消')" @click="edit = null">×</button>
    </form>
  </nav>
</template>
