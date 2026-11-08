import { readFile, mkdir, writeFile } from 'node:fs/promises'
const root = new URL('../../', import.meta.url)
const read = (path) => readFile(new URL(path, root), 'utf8')
const reports = JSON.parse(await read('docs/day1-results.json'))
const candidates = Object.fromEntries(await Promise.all(
  ['original', 'fixed', 'public_only', 'timeout'].map(async (id) => [id, await read(`fixtures/billing/${id}.py`)]),
))
candidates.unauthorized = candidates.fixed
const collaboration = {}
for (const [id, path, experiment] of [
  ['adversarial_recorded', 'docs/adversarial-integration-results.json', 'E2'],
  ['recovery_recorded', 'docs/recovery-integration-results.json', 'R1'],
]) {
  const record = JSON.parse(await read(path)).find(row => row.experiment === experiment)
  if (!record?.snapshot?.verification) throw new Error(`Missing recorded evidence: ${path} ${experiment}`)
  const fields = ['run_id', 'task_id', 'verification', 'adversarial_report', 'final_decision',
    'recovery_report', 'adversarial_mode', 'recovery_mode', 'candidate']
  collaboration[id] = { source: path, snapshot: Object.fromEntries(fields.map(key => [key, record.snapshot[key]])) }
}
const data = {
  source: 'docs/day1-results.json',
  publicTests: { path: 'fixtures/billing/public_tests.py', content: await read('fixtures/billing/public_tests.py') },
  tasks: [{
    spec: reports[0].task,
    title: 'Currency rounding',
    description: '修复金额转换时的小数截断错误，确保正负金额在半分边界上采用一致、明确的舍入规则。',
    goal: '将十进制金额字符串转换为整数分，按最近值舍入；恰好半分时远离零。',
    constraints: ['Only billing.py may change', 'Acceptance tests are protected', 'No network · no host credentials', '3s execution deadline'],
    acceptance_goals: ['1.239 → 124 cents', '1.005 → 101 cents', '−1.005 → −101 cents'],
    original: { path: 'billing.py', content: candidates.original },
  }], reports, candidates, collaboration,
}
await mkdir(new URL('../src/data/', import.meta.url), { recursive: true })
await writeFile(new URL('../src/data/demo.json', import.meta.url), JSON.stringify(data, null, 2) + '\n')
console.log('Synced historical reports and reviewed fixtures; no execution performed.')
