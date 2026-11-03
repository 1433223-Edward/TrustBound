<script setup>
import StatusBadge from './StatusBadge.vue'
defineProps({ task: Object, tasks: Array, mode: String, scenario: String, busy: Boolean })
defineEmits(['task', 'scenario', 'replay', 'run'])
</script>

<template>
  <aside class="task-panel">
    <div class="section-heading"><span class="eyebrow">TASK EXPLORER</span><span class="muted mono">01</span></div>
    <div class="task-scroll">
    <label class="field-label" for="task-select">预定义任务</label>
    <select id="task-select" :value="task.spec.task_id" @change="$emit('task', $event.target.value)">
      <option v-for="item in tasks" :key="item.spec.task_id" :value="item.spec.task_id">{{ item.title }}</option>
    </select>
    <div class="task-identity"><span class="python-icon">py</span><div><strong>{{ task.title }}</strong><small class="mono">{{ task.spec.task_id }}</small></div></div>
    <p class="task-description">{{ task.description }}</p>
    <div class="task-section"><h3>修复目标 <span>GOAL</span></h3><p>{{ task.goal }}</p></div>
    <div class="task-section"><h3>允许修改 <span>WRITE SCOPE</span></h3><div class="file-scope mono"><span>◇</span> {{ task.original.path }}<StatusBadge status="ALLOWED" label="write" /></div></div>
    <div class="task-section"><h3>执行约束 <span>CONSTRAINTS</span></h3><ul class="constraint-list"><li v-for="constraint in task.constraints" :key="constraint"><span aria-hidden="true">⌁</span>{{ constraint }}</li></ul></div>
    <div class="task-section"><h3>验收目标 <span>ACCEPTANCE</span></h3><ul class="acceptance-list mono"><li v-for="goal in task.acceptance_goals" :key="goal">{{ goal }}</li></ul></div>
    </div>
    <div class="replay-controls" v-if="mode === 'DEMO'">
      <label class="field-label" for="scenario-select">历史回放场景 · Sample</label>
      <select id="scenario-select" :value="scenario" @change="$emit('scenario', $event.target.value)">
        <option value="public_only">假成功被拒绝 · False success</option><option value="fixed">正确补丁 · Verified fix</option><option value="original">原始 Bug · Baseline</option><option value="timeout">超时终止 · Containment</option><option value="unauthorized">越权拒绝 · Policy denial</option>
      </select>
      <button class="primary-button full" :disabled="busy" @click="$emit('replay')"><span :class="{ spinner: busy }" aria-hidden="true">{{ busy ? '' : '▷' }}</span>{{ busy ? '加载历史记录…' : 'Replay sample' }}</button>
      <p class="micro">仅查看已有报告，不运行 Agent 或容器。</p>
    </div>
    <div class="replay-controls" v-else><button class="primary-button full" :disabled="busy" @click="$emit('run')">{{ busy ? '等待后端…' : 'Run Agent' }}</button><p class="micro">需要真实 FastAPI。连接失败不会转为 Demo。</p></div>
    <div class="boundary-note"><span class="boundary-icon">⌑</span><div><strong>Bounded by design</strong><p>执行者提出修改，可信验收器作出裁决。</p></div></div>
  </aside>
</template>
