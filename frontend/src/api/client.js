export function createApiClient({ fetcher = globalThis.fetch, now = Date.now,
  sleep = ms => new Promise(resolve => setTimeout(resolve, ms)), requestTimeout = 10000, runTimeout = 300000 } = {}) {
  async function request(path, { signal, headers, download, ...options } = {}, timeout = requestTimeout) {
    const controller = new AbortController()
    const abort = () => controller.abort()
    if (signal?.aborted) controller.abort()
    signal?.addEventListener('abort', abort, { once: true })
    const timer = setTimeout(abort, timeout)
    try {
      const response = await fetcher(`/api${path}`, { ...options, signal: controller.signal,
        headers: { 'Content-Type': 'application/json', ...headers } })
      if (!response.ok) {
        const body = response.headers.get('content-type')?.includes('application/json') ? await response.json() : null
        throw new Error(`HTTP ${response.status} · ${body?.error?.code || 'API_ERROR'}: ${body?.error?.message || '后端尚未连接或请求失败。'}`)
      }
      if (download) return await response.blob()
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

  async function startRun(taskId, signal, options = {}) {
    const data = await request('/runs', { method: 'POST', body: JSON.stringify({ task_id: taskId, ...options }), signal })
    if (typeof data.run_id !== 'string' || data.state !== 'QUEUED') throw new Error('Invalid run creation response.')
    return data.run_id
  }

  async function startCustom(body, signal) {
    const data = await request('/custom-runs', { method: 'POST', body: JSON.stringify(body), signal })
    if (typeof data.run_id !== 'string' || data.state !== 'QUEUED') throw new Error('Invalid custom run response.')
    return data.run_id
  }

  async function waitForRun(runId, taskId, signal, { mode, candidateId, onUpdate } = {}) {
    const deadline = now() + runTimeout
    const runsPath = mode === 'custom_offline' ? '/custom-runs' : '/runs'
    for (let poll = 0; poll < 300 && now() < deadline; poll++) {
      if (signal?.aborted) throw new Error('停止等待不代表取消后端任务。')
      const data = await request(`${runsPath}/${encodeURIComponent(runId)}`, { signal }, Math.min(requestTimeout, deadline - now()))
      if (data.run_id !== runId || data.task_id !== taskId || data.source !== 'LIVE' ||
          !['QUEUED', 'RUNNING', 'COMPLETED', 'ERROR'].includes(data.state)) throw new Error('Run identity or state mismatch.')
      if (mode && (data.mode !== mode || (mode === 'fixture' && data.candidate_id !== candidateId))) {
        throw new Error('Execution mode or candidate mismatch.')
      }
      onUpdate?.(data)
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
  return { listTasks, startRun, startCustom, waitForRun,
    workspaceProject: (path, token, body, signal, download = false) => request(`/workspace/projects${path}`, {
      signal, download, headers: token ? { Authorization: `Bearer ${token}` } : undefined,
      cache: 'no-store', redirect: 'error',
      ...(body === undefined ? {} : { method: 'POST', body: JSON.stringify(body) }),
    }, path.endsWith('/generate-plan') ? 75000 : requestTimeout),
    health: signal => request('/health', { signal }),
    getTask: (id, signal) => request(`/tasks/${encodeURIComponent(id)}`, { signal }),
  }
}
