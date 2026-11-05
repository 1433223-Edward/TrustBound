import assert from 'node:assert/strict'
import test from 'node:test'
import { createApiClient } from '../src/api/client.js'

test('custom source and reports use the private endpoints instead of Billing routes', async () => {
  const seen = []
  const response = value => new Response(JSON.stringify(value), { headers: { 'Content-Type': 'application/json' } })
  const client = createApiClient({ fetcher: async (path, request) => {
    seen.push([path, request.body])
    if (request.method === 'POST') return response({ run_id: 'custom-1', state: 'QUEUED' })
    return response({ run_id: 'custom-1', task_id: 'custom-python-v1', state: 'COMPLETED',
      mode: 'custom_offline', source: 'LIVE', verification: { run_id: 'formal-1', task: { task_id: 'custom-python-v1' } } })
  } })
  const body = { source: 'def solve(value): return value', requirements: 'Identity',
    public: [{ input: 1, expected: 1 }] }
  const run = await client.startCustom(body)
  await client.waitForRun(run, 'custom-python-v1', undefined, { mode: 'custom_offline' })
  assert.deepEqual(seen, [
    ['/api/custom-runs', JSON.stringify(body)],
    ['/api/custom-runs/custom-1', undefined],
  ])
})
