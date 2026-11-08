import { ref } from 'vue'

export const language = ref('en')
export const t = (english, chinese = english) => language.value === 'zh-CN' ? chinese : english

const states = {
  VERIFIED: '已验证', PASSED: '通过', FAILED: '失败', REJECTED: '已拒绝',
  INCONCLUSIVE: '证据不足', WAITING: '待执行', RUNNING: '执行中', QUEUED: '排队中',
  COMPLETED: '已完成', READY: '就绪', ALLOWED: '允许', RECORDED: '已记录',
  ERROR: '错误', LOADING: '加载中', CONNECTING: '连接中', CONNECTED: '已连接',
  TIMED_OUT: '超时', UNAVAILABLE: '不可用', CONFIRMED: '已确认', INVALID: '无效',
  INCOMPLETE: '未完成', SKIPPED: '已跳过', NOT_RUN: '未运行', UNKNOWN: '未知',
  IMPORTED: '已导入', CLARIFYING: '待澄清', PLAN_READY: '待审批', FROZEN: '已冻结',
  ACCEPTED: '已接受', KEPT_UNVERIFIED: '已人工保留（未验证）', MATCHED: '结果匹配', MISMATCH: '结果不符', EXITED: '进程已退出',
  NOT_CONFIRMED: '未证实', GENERATION_FAILED: '生成失败',
  EXECUTED_UNVERIFIED: '已执行 · 未验证功能', EXECUTION_FAILED: '执行未成功', EXECUTED: '已执行',
  NOT_REQUESTED: '未启用', NOT_OBSERVED: '未收集',
  NOT_RUN_FUNCTIONAL_VERIFICATION_DISABLED: '功能验证关闭 · 未核验反例',
  NOT_RECORDED: '未记录', DEMO: '演示', IDLE: '待执行',
}

export function statusText(value = 'WAITING') {
  return t(value.replaceAll('_', ' '), states[value] ?? value.replaceAll('_', ' '))
}

const errors = {
  EXECUTED_WITHOUT_FUNCTIONAL_VERIFICATION: ['Code executed; functional correctness was not verified.', '代码已执行，功能正确性未验证。'],
  WORKSPACE_EXECUTION_NOT_SUCCESSFUL: ['Execution did not complete successfully; no functional verdict was produced.', '执行未成功完成，未产生功能正确性裁决。'],
  WORKSPACE_FUNCTIONAL_REAPPROVAL_REQUIRED: ['Approve a plan with trusted functional acceptance before enabling correctness verification.', '请先补齐可信功能验收条件并重新批准计划，再启用正确性验证。'],
  WORKSPACE_AUTH_REQUIRED: ['Enter a valid private Workspace token.', '请输入有效的私有 Workspace 令牌。'],
  WORKSPACE_LOCAL_ONLY: ['This preview accepts requests from the local machine.', '此预览仅接受本机请求。'],
  INVALID_PROJECT_PATH: ['Use a relative project path with supported characters.', '请使用受支持的项目相对路径。'],
  UNSUPPORTED_PROJECT_FILE: ['Only Python, Markdown and text files are supported.', '仅支持 Python、Markdown 和文本文件。'],
  INVALID_ZIP: ['This archive could not be read.', '无法读取此压缩包。'],
  PROJECT_TOO_LARGE: ['The project exceeds the import limits.', '项目超过导入限制。'],
  CONFLICTING_PROJECT_PATH: ['The project contains conflicting file paths.', '项目中存在冲突的文件路径。'],
  UNSUPPORTED_ZIP_ENTRY: ['The archive contains an unsupported entry.', '压缩包含有不受支持的条目。'],
  PYTHON_FILE_REQUIRED: ['Import at least one Python file.', '请至少导入一个 Python 文件。'],
  INVALID_WORKSPACE_REQUEST: ['Check the source, plan or run inputs.', '请检查源码、计划或运行参数。'],
  INVALID_WRITE_SCOPE: ['Select existing Python files from the project.', '请选择项目中现有的 Python 文件。'],
  INVALID_ENTRYPOINT: ['Use an existing Python path and a function name.', '请填写现有 Python 文件路径和函数名。'],
  INVALID_OR_OVERLAPPING_CASES: ['Use distinct, bounded inputs across both suites.', '两组用例必须使用不同且大小受限的输入。'],
  STALE_WORKSPACE_REVISION: ['Reopen the project and review its latest plan.', '请重新打开项目并审核最新计划。'],
  WORKSPACE_PLAN_NOT_READY: ['Resolve the open questions before approving.', '请先处理待澄清问题再确认。'],
  WORKSPACE_FREEZE_REQUIRED: ['Approve the current plan before running.', '请先确认当前计划再执行。'],
  WORKSPACE_APPROVAL_ROUTE_MISMATCH: ['Use the approval step assigned by the Planning Gate.', '请使用 Planning Gate 指定的确认流程。'],
  WORKSPACE_EXECUTION_MODE_UNAVAILABLE: ['The selected execution mode is unavailable.', '所选执行模式不可用。'],
  WORKSPACE_MODEL_UNAVAILABLE: ['The model is unavailable under this deployment policy.', '当前部署策略下此模型不可用。'],
  WORKSPACE_PROJECT_NOT_FOUND: ['Project not found.', '未找到该项目。'],
  WORKSPACE_RUN_NOT_FOUND: ['Run not found for this project.', '此项目下未找到该运行。'],
  WORKSPACE_RUN_INTERRUPTED: ['Execution was interrupted before a report was saved.', '运行在保存报告前中断。'],
  WORKSPACE_VERIFIED_CHANGE_REQUIRED: ['Only a verified change for the current plan can be accepted.', '只可接受当前计划下通过验证的修改。'],
  WORKSPACE_EXPORT_REQUIRES_ACCEPTANCE: ['Accept the change before exporting.', '请先接受修改再导出。'],
  WORKSPACE_DISABLED: ['Private Workspace is disabled.', '私有 Workspace 未启用。'],
  RUN_CAPACITY_REACHED: ['Another task is running. Try again when it finishes.', '另一个任务正在运行，请稍后再试。'],
  RUN_QUOTA_EXHAUSTED: ['The deployment has reached its run quota.', '部署已达到运行配额。'],
  REQUEST_TOO_LARGE: ['The request exceeds the size limit.', '请求超过大小限制。'],
  ORIGIN_DENIED: ['The request came from an unapproved origin.', '请求来源未经许可。'],
  FROZEN_PUBLIC_AND_ACCEPTANCE_MATCHED: ['Public and independent cases matched the frozen plan.', '公开及独立用例符合冻结方案。'],
  FROZEN_ALL_CHECKS_MATCHED: ['Public, independent and challenge cases matched the frozen plan.', '公开、独立验收和挑战用例均符合冻结方案。'],
  INVALID_PROJECT_PLAN: ['The root plan is invalid for this source snapshot.', '根目录计划书与导入快照不兼容。'],
  WORKSPACE_RESTORE_REQUIRES_ACCEPTED_RUN: ['Restore requires an accepted verified run under the same plan.', '回退需要同一计划下已通过并接受的运行。'],
  WORKSPACE_RETRY_UNAVAILABLE: ['There is no eligible verified failure for a retry under this plan and budget.', '当前计划和预算下没有可用于重试的已核验失败。'],
  WORKSPACE_RETRY_ALREADY_USED: ['This run has already been retried.', '这次运行已经重试过。'],
  WORKSPACE_CASE_MISMATCH: ['Observed output differed from the approved expectation.', '实际输出与已确认的期望不符。'],
  INVALID_WORKSPACE_OBSERVATION: ['The sandbox did not return a valid JSON observation.', '沙盒没有返回有效的 JSON 观察结果。'],
  WORKSPACE_CANDIDATE_POLICY_DENIED: ['The candidate violated the frozen write scope or file policy.', '候选违反冻结的修改范围或文件策略。'],
  WORKSPACE_EXECUTION_NOT_INTACT: ['Execution, integrity or cleanup evidence is incomplete.', '执行、完整性或清理证据不完整。'],
  WORKSPACE_RUNNER_UNAVAILABLE: ['The sandbox runner is unavailable.', '沙盒 Runner 不可用。'],
}

export function message(value) {
  const text = value?.message ?? String(value ?? '')
  const code = value?.code ?? text.match(/^HTTP \d+ · ([A-Z0-9_]+)/)?.[1] ?? text
  if (Object.hasOwn(errors, code)) return t(...errors[code])
  if (/Failed to fetch|NetworkError/i.test(text)) return t('The backend could not be reached.', '无法连接后端。')
  if (/超时或停止/.test(text)) return t('The request timed out or was stopped. The backend may still be running.', text)
  if (/等待结果超时/.test(text)) return t('Waiting timed out. No verdict has been recorded.', text)
  if (/Demo Replay 不会启动任务/.test(text)) return t('Demo Replay loads historical records. Switch to Local API to execute a task.', text)
  if (/Backend not connected: API did not return JSON/.test(text)) return t('The backend did not return JSON.', '后端没有返回 JSON。')
  if (/^HTTP \d+ · /.test(text) || value?.code) return `${t('Request unsuccessful', '请求未完成')} · ${code}`
  return text
}

const planEnglish = {
  '预期行为与成功标准是什么？': 'What behavior and success criteria do you expect?',
  '允许修改哪些现有 Python 文件？': 'Which existing Python files may be changed?',
  '哪个函数接收 JSON 输入并返回 JSON 结果？': 'Which function accepts JSON and returns a JSON result?',
  '提供至少一个可供 Executor 查看和复现的公开用例。': 'Add a public case the Executor can inspect and reproduce.',
  '提供至少一个输入不同的独立验收用例及可信期望值。': 'Add an independent case with a distinct input and a trusted expected result.',
  '在允许的文件内提案': 'Propose changes within the approved files',
  '运行公开用例': 'Run the public cases',
  '独立比较冻结的验收结果': 'Compare observations independently against the frozen expectations',
  '覆盖正常行为、边界及错误输入': 'Cover normal behavior, boundaries, and invalid input',
  '为每个用例给出可比较的期望值': 'Provide a comparable expected result for each case',
}
export const planText = text => t(planEnglish[text] ?? text, text)

const traceCopy = {
  'Agent Proposal': 'Agent 提案', 'Permission Check': '权限检查', 'Sandbox Execution': '沙盒执行',
  'Public Tests': '公开测试', 'Independent Verification': '独立验收', 'Final Decision': '最终裁决',
  'Only billing.py may be changed.': '只允许修改 billing.py。',
  'Isolated Linux container · no network.': '隔离的 Linux 容器，无网络。',
  'Declared public test suite.': '声明的公开测试。',
  'Protected billing-v1 acceptance.': '受保护的 billing-v1 验收。',
  'Evidence first. Decision second.': '根据证据作出裁决。',
  'Limits checked': '已检查限制', 'Limits unconfirmed': '限制未确认',
  'Container removed': '容器已移除', 'Cleanup unconfirmed': '清理未确认',
}
const traceEnglish = {
  '固定回放不含 LLM 提案记录。': 'The recorded fixture has no model proposal.',
  '固定候选 · 无模型调用；Docker 将真实执行。': 'Fixed candidate · real Docker execution without inference.',
  '后端未提供模型提案记录。': 'The backend supplied no model proposal record.',
  '等待后端提案；浏览器不直接调用 LLM。': 'Waiting for the backend proposal.',
  '未运行；不能推断为通过。': 'This phase did not run.',
  '结论来自 VerificationReport，不来自模型声明。': 'The verdict comes from the verification report.',
}
export const traceText = (text = '') => t(traceEnglish[text] ?? text,
  text.replace(/^Fresh container · exit /, '独立容器 · 退出码 ').split(' · ')
    .map(part => traceCopy[part] ?? part.replace(/^Exit /, '退出码 ')).join(' · '))
