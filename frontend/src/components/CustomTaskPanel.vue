<script setup>
import { onUnmounted, ref } from 'vue'

const props = defineProps({ client: { type: Object, required: true } })
const requirements = ref('Return the absolute value of an integer.')
const source = ref('def solve(value):\n    return value\n')
const replacement = ref('def solve(value):\n    return -value if value < 0 else value\n')
const cases = ref(JSON.stringify({
  public: [{ input: 2, expected: 2 }],
  acceptance: [{ input: -3, expected: 3 }],
  challenges: [{ input: 0, expected: 0 }],
}, null, 2))
const running = ref(false)
const error = ref('')
const result = ref(null)
let controller
onUnmounted(() => controller?.abort())

async function run() {
  if (running.value) return
  running.value = true
  error.value = ''
  result.value = null
  controller = new AbortController()
  try {
    const tests = JSON.parse(cases.value)
    if (!tests || Array.isArray(tests) || typeof tests !== 'object' ||
      Object.keys(tests).some(key => !['public', 'acceptance', 'challenges'].includes(key))) {
      throw new Error('测试 JSON 只接受 public、acceptance、challenges。')
    }
    const input = { ...tests, source: source.value, requirements: requirements.value }
    if (replacement.value.trim()) input.replacement = replacement.value
    const id = await props.client.startCustom(input, controller.signal)
    const response = await props.client.waitForRun(id, 'custom-python-v1', controller.signal, { mode: 'custom_offline' })
    const decision = response.final_decision
    if (!['VERIFIED', 'FAILED', 'REJECTED', 'INCONCLUSIVE'].includes(decision?.status) ||
        decision.artifact_hash !== response.verification.artifact_hash ||
        decision.formal_report_id !== response.verification.run_id || !response.custom_evidence ||
        response.llm_source !== 'NONE') {
      throw new Error('Custom task evidence does not match the completed run.')
    }
    result.value = response
  } catch (cause) {
    if (!controller.signal.aborted) error.value = cause.message
  } finally {
    running.value = false
  }
}
</script>

<template>
  <details class="custom-task">
    <summary>{{ $t('Custom Task v1 · Private / Offline', '自定义任务 v1 · 私有 / 离线') }}</summary>
    <p>{{ $t('Submit a single Python function and integer cases for real Docker checks.', '提交单文件 Python 函数及整数用例，由 Docker 真实执行。') }} <code>solve(value)</code></p>
    <form @submit.prevent="run">
      <label>{{ $t('Requirements', '需求') }} <textarea v-model="requirements" rows="2" maxlength="800" required /></label>
      <label>{{ $t('Original Python', '原始 Python') }} <textarea v-model="source" rows="4" maxlength="2000" required /></label>
      <label>{{ $t('Manual candidate (optional)', '人工候选（可选）') }} <textarea v-model="replacement" rows="4" maxlength="2000" /></label>
      <label>{{ $t('Test cases (JSON)', '固定用例 JSON') }} <textarea v-model="cases" rows="9" required /></label>
      <button class="run-button" :disabled="running">{{ running ? 'Running…' : 'Run private checks' }}</button>
    </form>
    <p v-if="error" role="alert">{{ $message(error) }}</p>
    <section v-if="result" aria-live="polite">
      <p><strong>{{ $status(result.final_decision.status) }}</strong> · {{ result.final_decision.reason }}</p>
      <p>{{ result.final_decision.scope }}</p>
      <p class="mono">Run {{ result.run_id }}</p>
      <details><summary>Diff and evidence</summary><pre>{{ result.verification.diff }}</pre><pre>{{ JSON.stringify({ executions: result.verification.executions, ...result.custom_evidence }, null, 2) }}</pre></details>
    </section>
  </details>
</template>

<style scoped>
.custom-task { margin: 1rem; padding: 1rem; border: 1px solid currentColor; }
form { display: grid; gap: .75rem; }
label { display: grid; gap: .25rem; }
textarea { font-family: monospace; color: inherit; background: #151922; padding: .5rem; resize: vertical; }
button { justify-self: start; }
pre { max-height: 16rem; overflow: auto; }
</style>
