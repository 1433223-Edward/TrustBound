<script setup>
import { computed } from 'vue'
import { t } from '../i18n.js'
import { agentCards } from '../agentNarration.js'
import StatusBadge from './StatusBadge.vue'
import ChatMessage from './ChatMessage.vue'
const props = defineProps({ project: Object, run: Object, billing: Object, inline: Boolean })
const emit = defineEmits(['evidence'])
const labels = { executor: ['Executor', '执行 Agent'], adversarial: ['Adversarial', '对抗 Agent'],
  recovery: ['Recovery', '恢复 Agent'], verifier: ['Verifier', '验证器'], system: ['Workspace', '工作区'] }
const entries = computed(() => agentCards(props))
const stage = computed(() => entries.value.at(-1)?.status ?? props.project?.state ?? 'WAITING')
</script>
<template>
  <component :is="inline ? 'div' : 'details'" :class="inline ? 'inline-activity' : 'activity-panel'">
    <summary v-if="!inline" class="panel-label"><span>{{ $t('Agent Activity', 'Agent 活动') }}</span><StatusBadge :status="stage" /></summary>
    <p v-if="billing?.mode === 'DEMO'" class="chat-stage micro">{{ $t('Historical replay · no new execution', '历史回放 · 未启动新执行') }}</p>
    <ol v-if="entries.length" class="agent-thread">
      <li v-for="row in entries" :key="row.key" class="agent-thread-entry" :class="row.role">
        <ChatMessage :role="row.role" :label="t(...(labels[row.role] ?? labels.system))" :status="row.status" :model="row.model"
          :source="row.source === 'MODEL' ? $t('Execution record + advisory model explanation', '执行记录＋模型参考说明') : $t('System summary from execution records', '系统根据执行记录生成的说明')">
          <p>{{ row.text }}</p>
          <p v-for="fact in row.facts" :key="fact" class="micro">{{ fact }}</p>
          <p v-if="row.modelDescription">{{ row.modelDescription }}</p>
          <p v-if="row.reason" class="micro">{{ $t('Decision basis: ', '依据：') }}{{ row.reason }}</p>
          <button class="product-button subtle" type="button" @click="emit('evidence', row)">{{ $t('View evidence', '查看证据') }}</button>
        </ChatMessage>
      </li>
    </ol>
  </component>
</template>
