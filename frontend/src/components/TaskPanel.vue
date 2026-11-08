<script setup>
import { computed, ref } from 'vue'
import { t } from '../i18n.js'
import StatusBadge from './StatusBadge.vue'
import ProjectPlanDialog from './ProjectPlanDialog.vue'
import ProjectFileTree from './ProjectFileTree.vue'
import SnapshotIdentity from './SnapshotIdentity.vue'
const props = defineProps({ task: Object, mode: String, executionMode: String, scenario: String, busy: Boolean,
  adversarialMode: String, adversarialFixture: String, recoveryMode: String, recoveryFixture: String,
  developerTools: Boolean, liveAvailable: Boolean, files: Array, selectedFile: String,
  record: Object, copyAvailable: Boolean, recoveryReport: Object, selectedAttempt: Number })
defineEmits(['scenario', 'executionMode', 'adversarialMode', 'adversarialFixture', 'recoveryMode', 'recoveryFixture',
  'replay-case', 'run', 'select-file', 'select-attempt', 'edit-copy'])
const planOpen = ref(false)
const cases = computed(() => [
  ['public_only', t('False success caught', '识别假成功'), t('Public pass, protected failure', '公开通过，独立验收失败')],
  ['fixed', t('Verified fix', '正确补丁'), t('Public and independent checks agree', '公开与独立检查通过')],
  ['original', t('Baseline bug', '原始错误'), t('Original code fails a declared check', '原始代码违反公开检查')],
  ['timeout', t('Timeout containment', '超时隔离'), t('Deadline, termination and cleanup', '超时、终止与清理')],
  ['unauthorized', t('Policy denial', '权限拒绝'), t('Rejected before container startup', '启动容器前拒绝')],
  ...(props.mode === 'LIVE' ? [['double_rounding', t('Double rounding', '重复舍入'), t('Formal pass, independent counterexample', '正式通过，独立反例')]] : []),
  ...(props.mode === 'DEMO' ? [
    ['adversarial_recorded', t('Counterexample found', '发现反例'), t('Recorded adversarial evidence overturns a pass', '已记录反例推翻正式通过')],
    ['recovery_recorded', t('Repair retried', '恢复修复'), t('Recorded recovery and independent re-verification', '已记录恢复与独立复验')],
  ] : []),
])
</script>

<template>
  <aside class="task-panel">
    <div class="task-scroll">
    <ProjectFileTree :files="files" :selected="selectedFile" :can-fork="copyAvailable" :disabled="busy" @fork="$emit('edit-copy')" @select="$emit('select-file', $event)" />
    <SnapshotIdentity :id="record?.run_id" :hash="record?.artifact_hash" :label="$t('Evidence snapshot', '证据快照')" />
    <label v-if="recoveryReport?.attempts.length > 1" class="field-label">
      {{ $t('Recorded candidate version', '已记录的候选版本') }}
      <select :value="selectedAttempt" @change="$emit('select-attempt', Number($event.target.value))">
        <option v-for="attempt in recoveryReport.attempts.filter(item => item.verification)" :key="attempt.attempt_index" :value="attempt.attempt_index">
          {{ $t('Attempt', '尝试') }} {{ attempt.attempt_index }} · {{ $status(attempt.final_decision?.status || 'RECORDED') }}
        </option>
      </select>
    </label>
    <div class="file-actions">
      <button type="button" class="primary-button" @click="planOpen = true">{{ $t('View project plan', '查看项目计划书') }}</button>
      <button v-if="copyAvailable" type="button" class="primary-button" :disabled="busy" @click="$emit('edit-copy')">{{ $t('Open editable copy', '打开可编辑副本') }} ↗</button>
    </div>
    <ProjectPlanDialog v-model="planOpen" :title="$t('Billing project plan', 'Billing 项目计划书')">
    <p class="task-description">{{ $t('Fix fractional truncation when converting currency to cents.', task.description) }}</p>
    <div class="task-section"><h3>{{ $t("Repair goal", "修复目标") }} <span>{{ $t("GOAL", "目标") }}</span></h3><p>{{ $t('Round decimal amounts to the nearest cent, with half cents away from zero.', task.goal) }}</p></div>
    <div class="task-section"><h3>{{ $t("Writable scope", "允许修改") }} <span>{{ $t("WRITE SCOPE", "修改范围") }}</span></h3><div class="file-scope mono"><span>◇</span> {{ task.original.path }}<StatusBadge status="ALLOWED" :label="$t('write', '可写')" /></div></div>
    <div class="task-section"><h3>{{ $t("Execution limits", "执行约束") }} <span>{{ $t("CONSTRAINTS", "约束") }}</span></h3><ul class="constraint-list"><li v-for="constraint in task.constraints" :key="constraint"><span aria-hidden="true">⌁</span>{{ constraint }}</li></ul></div>
    <div class="task-section"><h3>{{ $t("Acceptance targets", "验收目标") }} <span>{{ $t("ACCEPTANCE", "验收") }}</span></h3><ul class="acceptance-list mono"><li v-for="goal in task.acceptance_goals" :key="goal">{{ goal }}</li></ul></div>
    <p class="micro">{{ $t('The official Billing demonstration uses a fixed, read-only plan.', '官方 Billing 演示使用固定只读计划。') }}</p>
    </ProjectPlanDialog>
    <details class="demo-guide">
      <summary>{{ $t('What each scenario shows', '查看各场景的差别') }}</summary>
      <dl>
        <dt>{{ $t('Baseline', '原始错误') }}</dt><dd>{{ $t('The original calculation fails a declared test.', '原始计算违反公开用例。') }}</dd>
        <dt>{{ $t('Verified fix', '正确补丁') }}</dt><dd>{{ $t('Public and independent acceptance checks agree.', '公开测试和独立验收均通过。') }}</dd>
        <dt>{{ $t('False success', '假成功') }}</dt><dd>{{ $t('Public tests pass, protected acceptance finds the defect.', '公开测试通过，受保护验收发现缺陷。') }}</dd>
        <dt>{{ $t('Policy denial', '越权拒绝') }}</dt><dd>{{ $t('A protected write is rejected before Docker starts.', '在 Docker 启动前拒绝受保护文件写入。') }}</dd>
        <dt>{{ $t('Timeout', '超时') }}</dt><dd>{{ $t('The runner terminates the task and records cleanup.', 'Runner 终止任务并记录清理。') }}</dd>
        <dt>{{ $t('Double rounding', '重复舍入') }}</dt><dd>{{ $t('Formal acceptance passes. In Local API, the independent adversary can overturn it with a verified counterexample.', '正式验收通过。本地 API 中的独立对抗可凭已验证反例推翻结果。') }}</dd>
      </dl>
      <p class="micro">{{ $t('Replay reads a stored report. Fixture runs real Docker. Offline Executor uses a simulated proposal. Vultr uses a live proposal when authorized.', '回放读取历史报告。固定候选运行真实 Docker，离线 Executor 使用模拟提案，Vultr 模式需要授权真实提案。') }}</p>
      <p class="micro">{{ $t('Adversarial verification looks for counterexamples. Recovery submits a new candidate and reruns all checks within its attempt budget.', '独立对抗寻找反例。恢复在次数限制内提交新候选并重跑全部检查。') }}</p>
    </details>
    </div>
    <div class="replay-controls" v-if="mode === 'DEMO'">
      <span class="field-label">{{ $t('Recorded cases', '历史案例') }}</span>
      <div class="demo-case-list">
        <button v-for="([id, title, detail]) in cases" :key="id" type="button" :disabled="busy"
          :class="{ selected: id === scenario }" @click="$emit('replay-case', id)">
          <strong>{{ title }}</strong><small>{{ detail }}</small>
        </button>
      </div>
      <p class="micro">{{ $t("Inspect a stored report without running an agent or container.", "仅查看已有报告，不运行 Agent 或容器。") }}</p>
    </div>
    <div class="replay-controls" v-else>
      <template v-if="!developerTools">
        <label class="field-label" for="billing-experience">{{ $t('Execution experience', '执行体验') }}</label>
        <select id="billing-experience" :value="executionMode === 'live_executor' ? 'live_executor' : 'fixture'" @change="$emit('executionMode', $event.target.value)">
          <option value="fixture">{{ $t('Offline / Fixture', '离线 / 样例') }}</option>
          <option v-if="liveAvailable" value="live_executor">{{ $t('Live Agent', '实时 Agent') }}</option>
        </select>
        <div v-if="executionMode !== 'live_executor'" class="demo-case-list">
          <button v-for="([id, title, detail]) in cases" :key="id" type="button" :disabled="busy"
            :class="{ selected: id === scenario }" @click="$emit('scenario', id)">
            <strong>{{ title }}</strong><small>{{ detail }}</small>
          </button>
        </div>
      </template>
      <details v-else><summary>{{ $t('Developer controls', '开发者控制') }}</summary>
      <label class="field-label" for="execution-mode">{{ $t("Execution mode", "后端运行模式") }}</label>
      <select id="execution-mode" :value="executionMode" @change="$emit('executionMode', $event.target.value)">
        <option value="fixture">{{ $t("Fixture · real Docker", "Fixture · 真实 Docker") }}</option><option value="offline_executor">{{ $t("Offline Executor · simulated proposal / real Docker", "Offline Executor · 模拟模型 / 真实 Docker") }}</option><option v-if="liveAvailable" value="live_executor">{{ $t("Vultr Live · backend configuration required", "Vultr Live · 需要后端配置") }}</option>
      </select>
      <template v-if="executionMode === 'fixture'">
        <label class="field-label" for="live-candidate" style="margin-top:12px">{{ $t("Fixed candidate · real execution", "固定候选 · 本次真实执行") }}</label>
        <select id="live-candidate" :value="scenario" @change="$emit('scenario', $event.target.value)">
          <option value="original">{{ $t("Baseline bug", "原始 Bug · Baseline") }}</option><option value="fixed">{{ $t("Verified fix", "正确补丁 · Verified fix") }}</option><option value="public_only">{{ $t("False-success candidate", "假成功候选 · False success") }}</option><option value="unauthorized">{{ $t("Policy denial", "越权请求 · Policy denial") }}</option><option value="timeout">{{ $t("Timeout containment", "超时任务 · Containment") }}</option><option value="double_rounding">{{ $t("Hidden double-rounding bug", "隐藏双重舍入 Bug · Stage 2") }}</option>
        </select>
      </template>
      <label class="field-label" for="adversarial-mode" style="margin-top:12px">{{ $t("Independent adversarial verification", "独立对抗验证 · Stage 2") }}</label>
      <select id="adversarial-mode" :value="adversarialMode" @change="$emit('adversarialMode', $event.target.value)">
        <option value="off">{{ $t("Off · formal acceptance", "Off · 保留正式验收") }}</option><option value="offline">{{ $t("Offline · simulated proposals / real challenges", "Offline · 模拟提议 / 真实反例执行") }}</option><option v-if="liveAvailable" value="live">{{ $t("Vultr · independent adversary", "Vultr · 独立对抗模型") }}</option>
      </select>
      <template v-if="adversarialMode === 'offline'">
        <label class="field-label" for="adversarial-fixture" style="margin-top:10px">{{ $t("Offline response preset", "离线模型响应预设") }}</label>
        <select id="adversarial-fixture" :value="adversarialFixture" @change="$emit('adversarialFixture', $event.target.value)">
          <option value="standard">{{ $t("Edge cases and invalid proposals", "边界输入与无效提议") }}</option><option value="invalid">{{ $t("Invalid proposals only", "全为无效提议") }}</option><option value="timeout">{{ $t("Simulated model timeout", "模拟模型请求超时") }}</option><option value="failure">{{ $t("Simulated model API failure", "模拟模型 API 失败") }}</option>
        </select>
      </template>
      <label class="field-label" for="recovery-mode" style="margin-top:12px">{{ $t("Bounded Recovery · up to 2 attempts", "Bounded Recovery · 最多 2 次") }}</label>
      <select id="recovery-mode" :value="recoveryMode" @change="$emit('recoveryMode', $event.target.value)">
        <option value="off">{{ $t("Off", "Off · 不恢复") }}</option><option value="offline">{{ $t("Offline · simulated repair / real verification", "Offline · 模拟修复 / 真实验证") }}</option><option v-if="liveAvailable" value="live">{{ $t("Vultr · separate authorization required", "Vultr · 需单独授权启用") }}</option>
      </select>
      <template v-if="recoveryMode === 'offline'">
        <label class="field-label" for="recovery-fixture" style="margin-top:10px">{{ $t("Offline repair response", "离线恢复响应") }}</label>
        <select id="recovery-fixture" :value="recoveryFixture" @change="$emit('recoveryFixture', $event.target.value)">
          <option value="fixed">{{ $t("Correct repair", "正确修复") }}</option><option value="exhausted">{{ $t("Repeated failure · budget exhausted", "连续错误 · 耗尽预算") }}</option><option value="unauthorized">{{ $t("Unauthorized change", "越权修改") }}</option><option value="invalid_json">{{ $t("Invalid JSON", "非法 JSON") }}</option><option value="empty">{{ $t("Empty response", "空响应") }}</option><option value="failure">{{ $t("Model error", "模型错误") }}</option><option value="timeout">{{ $t("Model timeout", "模型超时") }}</option>
        </select>
      </template>
      </details>
      <button class="primary-button full" :disabled="busy" @click="$emit('run')">{{ busy ? $t("Executing…", "执行中 / 等待结果…") : $t("Run Agent", "运行 Agent") }}</button>
      <p class="micro">{{ executionMode === 'fixture' ? $t("A fixed candidate runs in real Docker without inference.", "固定候选，不调用 LLM；测试与验收真实执行。") : executionMode === 'offline_executor' ? $t("Only the model response is simulated. Container verification is real.", "只模拟模型响应；复用 Executor 和真实容器验收。") : $t("The backend requires its own model configuration.", "仅后端可读取 Key；未配置则明确拒绝。") }}</p>
    </div>
    <div class="boundary-note"><span class="boundary-icon">⌑</span><div><strong>{{ $t("Bounded by design", "受限执行") }}</strong><p>{{ $t("The executor proposes changes. The trusted verifier decides.", "执行者提出修改，可信验收器作出裁决。") }}</p></div></div>
  </aside>
</template>
