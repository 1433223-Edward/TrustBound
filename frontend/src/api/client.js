export function createApiClient({ fetcher = globalThis.fetch, now = Date.now,
  sleep = ms => new Promise(resolve => setTimeout(resolve, ms)), requestTimeout = 10000, runTimeout = 120000 } = {}) {
  async function request(path, { signal, ...options } = {}, timeout = requestTimeout) {
    const controller = new AbortController()
    const abort = () => controller.abort()
    if (signal?.aborted) controller.abort()
    signal?.addEventListener('abort', abort, { once: true })
    const timer = setTimeout(abort, timeout)
    try {
      const response = await fetcher(`/api${path}`, { ...options, signal: controller.signal,
        headers: { 'Content-Type': 'application/json' } })
      if (!response.ok) throw new Error(`Backend returned HTTP ${response.status}. 后端尚未连接或请求失败。`)
      if (!response.headers.get('content-type')?.includes('application/json')) {
        throw new Error('Backend not connected: API did not return JSON. 当前页面仅提供前端。')
      }
      return await response.json()
    } catch (error) {
      if (controller.signal.aborted) throw new Error('API 等待已超时或停止；这不代表后端任务已取消。')
      throw error
    } finally {
      clearTimeout(timer)
      signal?.removeEventListener('abort', abort)
    }
  }

  async function listTasks(signal) {
    const data = await request('/tasks', { signal })
    if (!Array.isArray(data.tasks) || !data.tasks.length || data.tasks.some(task =>
      !task.spec?.task_id || !Array.isArray(task.spec.allowed_write_paths) ||
      typeof task.title !== 'string' || typeof task.original?.content !== 'string' ||
      !Array.isArray(task.constraints) || !Array.isArray(task.acceptance_goals))) {
      throw new Error('Invalid task catalog from backend.')
    }
    return data.tasks
  }

  async function startRun(taskId, signal) {
    const data = await request('/runs', { method: 'POST', body: JSON.stringify({ task_id: taskId }), signal })
    if (typeof data.run_id !== 'string' || data.state !== 'QUEUED') throw new Error('Invalid run creation response.')
    return data.run_id
  }

  async function waitForRun(runId, taskId, signal) {
    const deadline = now() + runTimeout
    for (let poll = 0; poll < 120 && now() < deadline; poll++) {
      if (signal?.aborted) throw new Error('停止等待不代表取消后端任务。')
      const data = await request(`/runs/${encodeURIComponent(runId)}`, { signal }, Math.min(requestTimeout, deadline - now()))
      if (data.run_id !== runId || data.task_id !== taskId || data.source !== 'LIVE' ||
          !['QUEUED', 'RUNNING', 'COMPLETED', 'ERROR'].includes(data.state)) throw new Error('Run identity or state mismatch.')
      if (data.state === 'ERROR') throw new Error(data.error?.message || 'Backend execution failed without a verification verdict.')
      if (data.state === 'COMPLETED') {
        if (typeof data.verification?.run_id !== 'string' || data.verification?.task?.task_id !== taskId) {
          throw new Error('Completed run has no matching verification evidence.')
        }
        return data
      }
      await sleep(Math.min(1000, Math.max(0, deadline - now())))
    }
    throw new Error('等待结果超时，后端状态未知；未产生验收结论。')
  }
  return { listTasks, startRun, waitForRun }
}
