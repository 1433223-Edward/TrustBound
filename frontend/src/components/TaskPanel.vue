<script setup>
import StatusBadge from './StatusBadge.vue'
defineProps({ task: Object, tasks: Array, mode: String, executionMode: String, scenario: String, busy: Boolean, adversarialMode: String, adversarialFixture: String, recoveryMode: String, recoveryFixture: String, publicDemo: Boolean })
defineEmits(['task', 'scenario', 'executionMode', 'adversarialMode', 'adversarialFixture', 'recoveryMode', 'recoveryFixture', 'replay', 'run'])
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
    <div class="replay-controls" v-else>
      <label class="field-label" for="execution-mode">后端运行模式</label>
      <select id="execution-mode" :value="executionMode" @change="$emit('executionMode', $event.target.value)">
        <option value="fixture">Fixture · 真实 Docker</option><option value="offline_executor">Offline Executor · 模拟模型 / 真实 Docker</option><option v-if="!publicDemo" value="live_executor">Vultr Live · 需要后端配置</option>
      </select>
      <template v-if="executionMode === 'fixture'">
        <label class="field-label" for="live-candidate" style="margin-top:12px">固定候选 · 本次真实执行</label>
        <select id="live-candidate" :value="scenario" @change="$emit('scenario', $event.target.value)">
          <option value="original">原始 Bug · Baseline</option><option value="fixed">正确补丁 · Verified fix</option><option value="public_only">假成功候选 · False success</option><option value="unauthorized">越权请求 · Policy denial</option><option value="timeout">超时任务 · Containment</option><option value="double_rounding">隐藏双重舍入 Bug · Stage 2</option>
        </select>
      </template>
      <label class="field-label" for="adversarial-mode" style="margin-top:12px">独立对抗验证 · Stage 2</label>
      <select id="adversarial-mode" :value="adversarialMode" @change="$emit('adversarialMode', $event.target.value)">
        <option value="off">Off · 保留正式验收</option><option value="offline">Offline · 模拟提议 / 真实反例执行</option><option v-if="!publicDemo" value="live">Vultr · 独立对抗模型</option>
      </select>
      <template v-if="adversarialMode === 'offline' && !publicDemo">
        <label class="field-label" for="adversarial-fixture" style="margin-top:10px">离线模型响应预设</label>
        <select id="adversarial-fixture" :value="adversarialFixture" @change="$emit('adversarialFixture', $event.target.value)">
          <option value="standard">边界输入与无效提议</option><option value="invalid">全为无效提议</option><option value="timeout">模拟模型请求超时</option><option value="failure">模拟模型 API 失败</option>
        </select>
      </template>
      <label v-if="!publicDemo" class="field-label" for="recovery-mode" style="margin-top:12px">Bounded Recovery · 最多 2 次</label>
      <select v-if="!publicDemo" id="recovery-mode" :value="recoveryMode" @change="$emit('recoveryMode', $event.target.value)">
        <option value="off">Off · 不恢复</option><option value="offline">Offline · 模拟修复 / 真实验证</option><option value="live">Vultr · 需单独授权启用</option>
      </select>
      <template v-if="recoveryMode === 'offline' && !publicDemo">
        <label class="field-label" for="recovery-fixture" style="margin-top:10px">离线恢复响应</label>
        <select id="recovery-fixture" :value="recoveryFixture" @change="$emit('recoveryFixture', $event.target.value)">
          <option value="fixed">正确修复</option><option value="exhausted">连续错误 · 耗尽预算</option><option value="unauthorized">越权修改</option><option value="invalid_json">非法 JSON</option><option value="empty">空响应</option><option value="failure">模型错误</option><option value="timeout">模型超时</option>
        </select>
      </template>
      <button class="primary-button full" :disabled="busy" @click="$emit('run')">{{ busy ? '执行中 / 等待结果…' : 'Run Agent' }}</button>
      <p class="micro">{{ executionMode === 'fixture' ? '固定候选，不调用 LLM；测试与验收真实执行。' : executionMode === 'offline_executor' ? '只模拟模型响应；复用 Executor 和真实容器验收。' : '仅后端可读取 Key；未配置则明确拒绝。' }}</p>
    </div>
    <div class="boundary-note"><span class="boundary-icon">⌑</span><div><strong>Bounded by design</strong><p>执行者提出修改，可信验收器作出裁决。</p></div></div>
  </aside>
</template>
