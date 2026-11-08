<script setup>
import { ref } from 'vue'
import ChatMessage from './ChatMessage.vue'

defineProps({ messages: { type: Array, default: () => [] }, busy: Boolean, readOnly: Boolean, quickMode: Boolean })
const emit = defineEmits(['send', 'files', 'deny-files', 'quick-mode', 'action', 'deny-action'])
const input = ref('')

function submit() {
  const text = input.value.trim()
  if (!text) return
  emit('send', text)
  input.value = ''
}
</script>

<template>
  <section class="workspace-chat">
    <div class="section-heading"><span class="eyebrow">{{ $t('Agent Chat', 'Agent 对话') }}</span><span class="muted">↳</span></div>
    <slot name="model" />
    <div class="chat-messages" role="log" :aria-label="$t('Agent conversation', 'Agent 交互')">
      <p v-if="!readOnly && !messages.length" class="chat-message agent">{{ $t('Describe the change you want. Use /files to inspect the snapshot or /run to use an approved plan.', '描述希望修改的内容。用 /files 查看快照文件，或用 /run 执行已批准的计划。') }}</p>
      <ChatMessage v-for="(item, index) in messages" :key="index" :role="item.role"
        :model="item.model" :source="item.source === 'CONTROL_EVENT' || (item.role !== 'user' && !item.model) ? $t('Local control', '本地控制层') : item.model ? $t('Model reply · not execution evidence', '模型回复 · 非执行证据') : undefined"
        :label="item.role === 'user' ? $t('You', '你') : item.role === 'system' ? $t('Workspace', '工作区') : item.model && item.source !== 'CONTROL_EVENT' ? $t('Assistant', '助手') : $t('Executor', '执行 Agent')">
        <p>{{ item.text }}</p>
        <div v-if="item.permission === 'files'" class="product-actions">
          <button type="button" class="product-button primary" @click="emit('files', index)">{{ $t('Allow listing', '允许列出') }}</button>
          <button type="button" class="product-button" @click="emit('deny-files', index)">{{ $t('Deny', '拒绝') }}</button>
        </div>
        <div v-if="['context', 'prepare'].includes(item.permission)" class="product-actions">
          <p>{{ item.permission === 'context' ? $t('Only the selected saved file will be sent to the model.', '仅将选中的已保存文件发送给模型。') : $t('Prepare scope and trusted checks first. This does not authorize execution.', '先准备修改范围和可信验收条件，此操作不授权执行。') }}</p>
          <button class="product-button primary" type="button" :disabled="busy" @click="emit('action', index)">{{ item.permission === 'context' ? $t('Allow selected file', '允许读取当前文件') : $t('Prepare execution requirements', '准备执行条件') }}</button>
          <button class="product-button" type="button" :disabled="busy" @click="emit('deny-action', index)">{{ $t('Deny', '拒绝') }}</button>
        </div>
      </ChatMessage>
      <slot name="activity" />
      <slot />
    </div>
    <form v-if="!readOnly" class="chat-compose" @submit.prevent="submit">
      <label class="visually-hidden" for="workspace-message">{{ $t('Message', '消息') }}</label>
      <label class="quick-mode-toggle"><input type="checkbox" :checked="quickMode" :disabled="busy"
        @change="emit('quick-mode', $event.target.checked)">{{ $t('Quick Mode', '快捷模式') }}
        <small>{{ $t('Direct model chat, without automatic plan review. Execution still requires approval.', '直接与模型聊天，不自动弹出计划审核；执行仍需授权。') }}</small></label>
      <textarea id="workspace-message" v-model="input" rows="2" maxlength="1200" :placeholder="$t('Describe the goal or type /run…', '描述目标，或输入 /run…')"></textarea>
      <button class="primary-button" type="submit" :disabled="busy || !input.trim()">{{ $t('Send', '发送') }} ↑</button>
    </form>
  </section>
</template>
