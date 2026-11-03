# TrustBound Web Workspace — 最小 API 契约

状态：**接口提案，尚无 FastAPI 实现**。本轮只开发独立前端；不改变 Python 核心执行/验收逻辑。
前端 `src/api/client.js` 仅访问同源 `/api`，不访问 Vultr，不存储 API Key。

## 数据来源与任务

当前真实 TaskSpec 来自 `trustbound/service.py`：`billing-rounding-01`、`billing-v1`、
`allowed_write_paths=["billing.py"]`、`timeout_seconds=3`。
目前只有一个任务。五个候选是该任务的实验场景，不是五个不同任务。
Demo 使用 `docs/day1-results.json` 的真实历史报告和仓库样例代码，显式标记 SAMPLE / 历史回放。
历史报告没有模型提案事件或阶段耗时，不得补造 LLM 调用、时间戳或运行中事件。

## 建议端点

1. `GET /api/tasks` → `{ tasks: Task[] }`。
2. `POST /api/runs`，body 仅 `{ task_id: "billing-rounding-01" }` → HTTP 202，
   `{ run_id: string, state: "QUEUED" }`。服务端选择可信 TaskSpec 和模型，不接收命令、
   任意代码、容器参数、正式验收内容或自定义写权限。
3. `GET /api/runs/{run_id}` → `RunSnapshot`，前端最多每秒轮询一次，等待总预算 120 秒。
   轮询截止后显示状态未知，不将超时解释为任务取消或执行失败；目前未实现取消端点。

`Task`：`{ spec: TaskSpec, title, description, goal, constraints: string[], acceptance_goals: string[],
original: { path, content } }`。说明字段由可信服务端维护，不属于当前 Python TaskSpec 字段。
原始代码 path 为 `billing.py`，content 为原始样例 UTF-8 文本。

`RunSnapshot`：

```json
{
  "run_id": "server-generated-id",
  "task_id": "billing-rounding-01",
  "source": "LIVE",
  "state": "QUEUED | RUNNING | COMPLETED | ERROR",
  "proposal": null,
  "verification": null,
  "error": null
}
```

`proposal` 可为 `{ analysis: string, files: { "billing.py": "full replacement source" } }`，
仅代表模型建议，不代表已执行或通过。`verification` 原样沿用现有 VerificationReport JSON，
包含 `task`、`candidate_id`、`artifact_hash`、`acceptance_hash`、`status`、`policy_reason`、
`changed_paths`、`diff`、`executions`、`limitations`；executions 沿用 ExecutionResult。
`COMPLETED` 必须有匹配任务的最终 verification，不能用 HTTP 200 或 proposal 判成功。
外层 run_id 是异步作业 ID，verification.run_id 保留现有验证器生成的报告 ID，二者可以不同；
服务端必须维护正确绑定，不能为了匹配前端而改写原始报告身份。前端核对外层作业 ID、任务 ID，
并验证内层报告任务及证据结构。
`error` 为 `{ code, message }`；`ERROR` 表示接口/编排错误，不是正式的 FAILED 验收裁决。
对缺 Key、预算不足和 API 错误，返回明确 error，不生成 VERIFIED。

## 视图适配规则

- Agent Proposal：仅有 proposal 才显示“已提供”；固定报告中标记“未记录”，候选来源显示固定 fixture。
- Permission Check：依据 policy_reason；当前受保护路径拒绝时 executions 为空。
- Sandbox Execution：由 executions 推导配置检查、执行状态和清理信息，不伪造独立沙盒事件。
- Public Tests：查找 phase=`public`；Independent Verification：查找 phase=`acceptance`。
- Final Decision：只展示 verification.status；缺失阶段显示“未运行/无证据”，不能默认通过。
- `EXITED` 不等于测试通过；退出码、timeout、cleanup、workspace、limits 一并展示。
- `changed_paths` 是请求修改范围，不证明宿主文件已被写入。
- 日志保持原始 stdout/stderr；unittest 成功输出也可能在 stderr，不能仅凭 stderr 非空判失败。

## 错误、模式及安全

HTTP 非成功、非 JSON、结构不符、run/task 不匹配、网络异常、120 秒等待截止均显示明确错误。
浏览器请求 10 秒超时；不自动重试 POST，以防重复付费执行。
Demo 与 Live 有独立入口；Live 连接失败不得自动回退成 Demo 成功。
刷新清空运行态，不从 localStorage 恢复 RUNNING。切换任务/模式使旧异步结果失效，
但前端停止等待不表示后端已取消执行。
后续 FastAPI 需负责输入白名单、TaskSpec 可信来源、Executor AST 检查、限流与预算、
运行记录存储、凭据保管、日志脱敏和服务端权限强制执行。前端不是安全执行点。

## 本轮默认行为

默认 Demo Replay 模式，初始无报告/无补丁；回放只加载静态历史快照，不发送网络请求，
等待期间显示“正在加载历史记录”，不是“Agent 正在执行”。
Live 模式中的 Run Agent 会尝试上述接口；当前无后端时明确失败，不产生虚假通过。
