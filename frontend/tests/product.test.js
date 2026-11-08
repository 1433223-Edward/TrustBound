import assert from 'node:assert/strict'
import { test } from 'node:test'
import { parseManual } from '../src/manual.js'
import { createApiClient } from '../src/api/client.js'
import { language, message, statusText, t } from '../src/i18n.js'
import { workspaceIntent } from '../src/workspaceConversation.js'
import { createWorkspace } from '../src/state/workspace.js'
import { fileTreeRows, importableProjectFile } from '../src/fileTree.js'
import { evidenceTabs } from '../src/evidenceTabs.js'
import demo from '../src/data/demo.json' with { type: 'json' }

test('project tree keeps nested directories and reports each file once', () => {
  const rows = fileTreeRows(['src/util/helpers.py', 'main.py', 'src/util/types.py', 'src/app.py'])
  assert.deepEqual(rows.map(row => [row.path, row.depth, row.directory]), [
    ['main.py', 0, false], ['src', 0, true], ['src/app.py', 1, false],
    ['src/util', 1, true], ['src/util/helpers.py', 2, false], ['src/util/types.py', 2, false],
  ])
  assert.equal(demo.publicTests.path, 'fixtures/billing/public_tests.py')
  assert.match(demo.publicTests.content, /class PublicTests/)
})

test('collaboration replays show saved counterexamples and recovery without calling the API', async () => {
  const workspace = createWorkspace({ demo, client: {}, sleep: async () => {} })
  workspace.selectScenario('adversarial_recorded')
  await workspace.replay()
  assert.equal(workspace.state.finalDecision?.status, 'FAILED')
  assert.ok(workspace.state.adversarialReport.confirmed_count > 0)
  workspace.selectScenario('recovery_recorded')
  await workspace.replay()
  assert.equal(workspace.state.recoveryReport?.final_status, 'VERIFIED')
  assert.ok(workspace.state.recoveryReport.attempts.length > 1)
  workspace.selectMode('LIVE')
  assert.equal(workspace.state.scenario, 'public_only')
})

test('conversation separates an explicit run or restore from a free-form goal', () => {
  assert.deepEqual(workspaceIntent('运行测试'), { kind: 'run' })
  assert.deepEqual(workspaceIntent('列出文件'), { kind: 'files' })
  assert.deepEqual(workspaceIntent('/restore ' + 'a'.repeat(32)), { kind: 'restore', id: 'a'.repeat(32) })
  assert.deepEqual(workspaceIntent('运行测试前先修复边界条件'), { kind: 'goal', goal: '运行测试前先修复边界条件' })
  assert.equal(workspaceIntent('你好').kind, 'greeting')
  assert.equal(workspaceIntent('Hello!').kind, 'greeting')
  assert.equal(workspaceIntent('为什么需要独立验收？').kind, 'question')
  assert.equal(workspaceIntent('Explain the current project').kind, 'question')
})

test('Billing and Workspace use the same five evidence navigation keys in both languages', () => {
  for (const locale of ['en', 'zh-CN']) {
    language.value = locale
    assert.deepEqual(evidenceTabs().map(tab => tab.id), ['summary', 'diff', 'logs', 'adversarial', 'recovery'])
    assert.ok(evidenceTabs().every(tab => tab.label.length > 0))
  }
  language.value = 'en'
})

test('handbook preserves headings, list content and code with stable navigation IDs', () => {
  const result = parseManual('# Manual\n\n## Evidence\n- one\n- two\n```py\n# source comment\n```')
  assert.deepEqual(result, [
    { type: 'heading', level: 1, id: 'documentation/section-1', text: 'Manual' },
    { type: 'heading', level: 2, id: 'documentation/section-2', text: 'Evidence' },
    { type: 'list', items: ['one', 'two'] },
    { type: 'code', text: '# source comment' },
  ])
})

test('handbook never interprets embedded HTML or JavaScript links', () => {
  const markup = '<script>alert(1)</script> [link](javascript:alert(1))'
  assert.deepEqual(parseManual(markup), [{ type: 'paragraph', text: markup }])
})

test('handbook renders quoted claims and status tables as plain data', () => {
  assert.deepEqual(parseManual('> Scope only\n\n| Status | Meaning |\n| --- | --- |\n| VERIFIED | Scoped pass |'), [
    { type: 'quote', text: 'Scope only' },
    { type: 'table', headers: ['Status', 'Meaning'], rows: [['VERIFIED', 'Scoped pass']] },
  ])
})

test('review language defaults to English and localizes statuses and errors', () => {
  assert.equal(t('Settings', '设置'), 'Settings')
  language.value = 'zh-CN'
  try {
    assert.equal(statusText('INCONCLUSIVE'), '证据不足')
    assert.equal(message({ code: 'WORKSPACE_AUTH_REQUIRED' }), '请输入有效的私有 Workspace 令牌。')
  } finally { language.value = 'en' }
})

test('project approval sends only its revision to the private API', async () => {
  const client = createApiClient({ fetcher: async (url, request) => {
    assert.equal(url, '/api/workspace/projects/aabb/freeze')
    assert.equal(request.headers.Authorization, 'Bearer local-test-token')
    assert.equal(request.cache, 'no-store')
    assert.equal(request.redirect, 'error')
    assert.deepEqual(JSON.parse(request.body), { revision: 2 })
    return new Response(JSON.stringify({ state: 'FROZEN' }), {
      headers: { 'content-type': 'application/json' },
    })
  } })
  assert.equal((await client.workspaceProject('/aabb/freeze', 'local-test-token', { revision: 2 })).state, 'FROZEN')
})

test('single-user local preview requests do not send an Authorization header', async () => {
  const client = createApiClient({ fetcher: async (url, request) => {
    assert.equal(url, '/api/workspace/projects/samples/inventory')
    assert.equal(request.headers.Authorization, undefined)
    return new Response('{}', { headers: { 'content-type': 'application/json' } })
  } })
  await client.workspaceProject('/samples/inventory', '', {})
})

test('folder import accepts supported nested files and skips caches and hidden files', () => {
  const file = (name, path) => ({ name, webkitRelativePath: path })
  assert.equal(importableProjectFile(file('main.py', 'project/src/main.py')), true)
  assert.equal(importableProjectFile(file('TRUSTBOUND_PLAN.json', 'project/TRUSTBOUND_PLAN.json')), true)
  for (const path of ['project/.venv/main.py', 'project/__pycache__/main.py', 'project/node_modules/main.py', 'project/image.png']) {
    assert.equal(importableProjectFile(file(path.split('/').at(-1), path)), false)
  }
})
