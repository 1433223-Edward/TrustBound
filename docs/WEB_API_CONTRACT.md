# TrustBound Web Workspace — 最小 API 契约

> **Historical Stage Record — Not the Current Release State.** 本文保留早期 Billing Web API 与阶段扩展契约；公网当前仅允许 Caddy 白名单中的离线 Billing 路由，私有 Workspace 的当前部署边界见 [README](../README.md) 和 [部署与运维说明](TrustBound_Deployment_Operations_Guide_2026-11-08.md)。

状态：**已实现本地 FastAPI 与真实 Docker 集成**。`trustbound/api.py` 提供接口，
`web_tasks.py` 负责可信任务和模式分发，复用现有执行与验收，不修改沙盒参数。
前端 `src/api/client.js` 仅访问同源 `/api`，不访问 Vultr，不存储 API Key。

## 数据来源与任务

当前真实 TaskSpec 来自 `trustbound/service.py`：`billing-rounding-01`、`billing-v1`、
`allowed_write_paths=["billing.py"]`、`timeout_seconds=3`。
目前只有一个任务。五个候选是该任务的实验场景，不是五个不同任务。
Demo 使用 `docs/day1-results.json` 的真实历史报告和仓库样例代码，显式标记 SAMPLE / 历史回放。
历史报告没有模型提案事件或阶段耗时，不得补造 LLM 调用、时间戳或运行中事件。

## 已实现端点

1. `GET /api/tasks` → `{ tasks: Task[] }`。
2. `POST /api/runs`，body `{ task_id: "billing-rounding-01", mode: "fixture", candidate_id: "fixed" }` → HTTP 202，
   `{ run_id: string, state: "QUEUED" }`。服务端选择可信 TaskSpec 和模型，不接收命令、
   任意代码、容器参数、正式验收内容或自定义写权限。
3. `GET /api/runs/{run_id}` → `RunSnapshot`，前端最多每秒轮询一次，等待总预算 120 秒。
   轮询截止后显示状态未知，不将超时解释为任务取消或执行失败；目前未实现取消端点。
4. `GET /api/health`：服务健康、当前 active_run_id、并发上限及各模式配置可用性。
   此接口不调用 Docker，不把 Web 服务健康解释为 Docker 或模型健康。
5. `GET /api/tasks/{id}`：单个可信任务详情，不存在时 404。

mode 只允许 `fixture` / `offline_executor` / `live_executor`，默认 fixture。
fixture candidate_id 只允许 original/fixed/public_only/unauthorized/timeout，缺省 fixed。
offline_executor 只允许省略 candidate_id 或 fixed，仅模拟模型响应，Runner/Verifier 真实执行。
live_executor 禁止 candidate_id，需 Key、显式 VULTR_MODEL 及 TRUSTBOUND_ENABLE_LIVE=1；
缺配置返回 503。配置就绪不等于认证成功，实际模型请求失败仍产生明确 ERROR，不能假定 VERIFIED。
所有额外 body 字段（包括 files、command、run_id、权限、路径）返回 422；请求体最大 4096 字节。

`Task`：`{ spec: TaskSpec, title, description, goal, constraints: string[], acceptance_goals: string[],
original: { path, content } }`。说明字段由可信服务端维护，不属于当前 Python TaskSpec 字段。
原始代码 path 为 `billing.py`，content 为原始样例 UTF-8 文本。

`RunSnapshot`：

```json
{
  "run_id": "server-generated-id",
  "task_id": "billing-rounding-01",
  "source": "LIVE",
  "mode": "fixture",
  "candidate_id": "fixed",
  "llm_source": "NONE",
  "state": "QUEUED | RUNNING | COMPLETED | ERROR",
  "proposal": null,
  "verification": null,
  "error": null
}
```

source=LIVE 仅代表本次 API 执行，**不代表真实模型调用**。llm_source 为 NONE / OFFLINE_TEST /
VULTR_LIVE_HTTP；始终与 mode 一并显示。candidate 为固定源文件 `{path,content,source:"FIXTURE"}`
或 null，proposal 只用于模型/模拟模型建议，不能拿固定源文件冒充 Agent Proposal。
executor 保存模型编排台账或 null。created_at/started_at/finished_at 为服务端真实 UTC 时间。

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
- Final Decision：Stage 2 优先展示 final_decision.status；无新增字段的旧报告展示 verification.status。正式验收与总体结论分开展示，不能默认缺失阶段通过。
- `EXITED` 不等于测试通过；退出码、timeout、cleanup、workspace、limits 一并展示。
- `changed_paths` 是请求修改范围，不证明宿主文件已被写入。
- 日志保持原始 stdout/stderr；unittest 成功输出也可能在 stderr，不能仅凭 stderr 非空判失败。

## 错误、模式及安全

HTTP 非成功、非 JSON、结构不符、run/task 不匹配、网络异常、300 秒等待截止均显示明确错误。
浏览器请求 10 秒超时；不自动重试 POST，以防重复付费执行。
Demo 与 Live 有独立入口；Live 连接失败不得自动回退成 Demo 成功。
刷新清空运行态，不从 localStorage 恢复 RUNNING。切换任务/模式使旧异步结果失效，
但前端停止等待不表示后端已取消执行。
API 使用 Literal 白名单与 extra=forbid、可信 TaskSpec、原 Executor AST 检查，
单进程单执行线程；已有任务时新请求返回 429，不积累执行队列。须以 --workers 1 启动。
控制器不接受任意代码或命令；执行在原有 Runner 的受限容器内。
仅允许本地主机与工作区 Origin，无跨域 CORS 授权；Vite 代理 `/api` 到本机 8000。
内存保留最近 50 条记录，真实快照写入 artifacts/web-runs/{服务器UUID}/report.json。
服务重启后不恢复内存状态，旧 GET 返回 404；磁盘快照保留供审计，不自动续跑。
前端不是安全执行点；没有公网认证、跨进程配额、磁盘保留策略或宿主故障回收器。

## 本轮默认行为

默认 Demo Replay 模式，初始无报告/无补丁；回放只加载静态历史快照，不发送网络请求，
等待期间显示“正在加载历史记录”，不是“Agent 正在执行”。
Local API（内部标识 LIVE）模式会调用健康、任务目录和任务详情，再 POST 与轮询。
运行中只展示后端作业状态；阶段证据在报告实际返回后展示，不伪造逐阶段事件。


## Stage 2 additive adversarial contract

POST /api/runs adds optional `adversarial_mode: off | offline | live` (default off)
and `adversarial_fixture: standard | invalid | timeout | failure` (default standard).
Non-standard profiles require offline mode. `double_rounding` is an additional reviewed,
fixed candidate ID; requests still cannot supply source code, scripts, paths or commands.

Completed snapshots keep the original `verification` unchanged and add:

- `adversarial_report`: null when off; otherwise task_id, artifact_hash, status, source,
  reason, allowlisted context, challenges, execution, driver_hash, raw_response, calls,
  generated_count, valid_count, confirmed_count, generation_parsed, budget.
- Each challenge contains `challenge: {challenge_id, amount, requirement_id, reason}`,
  status INVALID / INCONCLUSIVE / CONFIRMED / NOT_CONFIRMED, expected, actual,
  actual_type and validation reason. Expected is host-derived, never model-authoritative.
- `execution` is the existing ExecutionResult shape with phase=adversarial. It is null
  when no valid input was executed. One restricted container executes at most four inputs.
- `final_decision`: status, formal_status, formal_report_id, artifact_hash,
  adversarial_status, reason, scope. Bind it to verification.run_id and artifact_hash.

Stage statuses: SKIPPED (formal acceptance did not verify), UNAVAILABLE (configuration),
GENERATION_FAILED (model/JSON failure), INCOMPLETE (no valid inputs or insufficient evidence),
COMPLETED (at least one valid input fully observed). An invalid input is not a business failure.
If formal status is VERIFIED, a confirmed mismatch changes overall status to FAILED;
requested but incomplete adversarial validation changes it to INCONCLUSIVE. A completed
bounded check with no confirmed mismatch retains VERIFIED, without claiming universal correctness.
Other formal statuses are preserved. Off retains Stage 1 formal-only behavior.

`source=OFFLINE_TEST` means deterministic model transport with real Docker checks;
`NO_LIVE_CALL` means no model call; `VULTR_LIVE_HTTP` identifies the live client path,
including failed attempts, not proof of successful inference. Inspect status and calls.
Top-level source=LIVE continues to mean a real local Web job, not real LLM inference.


## Stage 3 bounded recovery extension

`POST /api/runs` accepts optional recovery_mode (off default / offline / live) and
recovery_fixture (fixed default / exhausted / unauthorized / invalid_json / empty / failure / timeout).
The server rejects client attempt limits, code, context and evidence uploads. Recovery requires an
explicit adversarial mode. Only offline mode accepts non-default response presets. Live requires
TRUSTBOUND_ENABLE_RECOVERY_LIVE=1 in addition to the existing model configuration/opt-in.
No live calls were performed during Stage 3 development.

Snapshots add `current_attempt` and `recovery_report`. Initial attempt=0; at most two repair attempts.
Progress is persisted and polled through the existing GET run endpoint; the API remains single-worker.
Recovery contains run_id, max_attempts=2, status, current_attempt, validated_attempt_index,
stop_reason, final_status, final_decision and attempts. Per-attempt fields and projection rules are
specified in [BOUNDED_RECOVERY.md](BOUNDED_RECOVERY.md). Stage 1/2 fields remain compatible and
project the last formally evaluated artifact. When recovery is requested, use recovery final_status
as the overall UI verdict; generation failures do not overwrite prior formal evidence.

Frontend polling is bounded to 300 seconds / 300 iterations to accommodate up to three full
validation rounds; per-request timeout remains ten seconds. Ending frontend waiting does not
cancel the owned backend task. Server reports carry actual attempt progress, not simulated events.
