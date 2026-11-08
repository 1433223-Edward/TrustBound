# TrustBound 项目手册

TrustBound 面向希望让 AI Agent 修改代码、又需要可复查验收依据的开发者。核心主张是 An agent that can act, but cannot certify its own success.

> VERIFIED 仅适用于当前声明的验收范围。用户反馈、回归测试与评测可以持续改进覆盖。

## 为什么需要独立验收

模型可以生成看似正确的补丁，公开测试也可能漏掉边界。Billing 实验中的重复舍入候选通过了公开及原正式验收，独立对抗阶段才发现某些输入与可信业务规则不符。项目把提案、权限、执行和裁决分开，让用户看见每一环的证据。

## 系统架构

```text
用户目标 → Agent 提案 → Permission Gate → 独立 Runner
                                             ↓
Evidence Report ← 可信 Verifier ← 受限 Sandbox 的实际结果
```

- Executor 生成结构化候选修改。宿主检查允许修改的文件和代码策略，越权时在创建容器前拒绝。
- FastAPI 负责准入和编排。生产私有 Runner 通过 Unix Socket 接收白名单消息，独立账户持有 Rootless Docker 权限。
- Runner 使用固定镜像、非 root 容器用户、无网络、只读根文件系统和 CPU、内存、进程数限制。公开和正式验收使用不同的容器。
- Evidence Report 记录候选与测试哈希、退出状态、日志、超时和清理证据。VERIFIED 表示通过本次声明的验收范围。

## 对抗验证与恢复

Adversarial Agent 只获得任务要求和待验证候选，提出受约束的输入。对抗模型的预期答案不参与裁决。宿主用可信参考规则计算结果并在真实容器中验证。确认反例可以把原正式验收通过的结果改判为 FAILED。

Recovery 在确认的业务失败上触发。宿主限制尝试次数，并将反例绑定候选哈希。每个新候选重新经过权限、公开、正式和要求的对抗阶段。权限拒绝、证据不足和容器异常会阻止自动恢复。

## 从原型到 Vultr

- 初版用固定的 Billing 代码与补丁验证公开测试、独立验收、拒绝和超时清理，随后接入 Vue 与 FastAPI。
- Stage 2 引入独立对抗上下文。实验中输入 1.00499 的可信期望为 100 分，重复舍入候选返回 101 分。此类偏差通过实际 Docker 输出确认。
- Stage 3 加入有限恢复。真实容器集成实验覆盖恢复成功、次数耗尽、越权、证据不足和模型异常。实验注入了离线提案，容器测试实际执行。
- Stage 4 接入 Vultr Serverless Inference。一次真实对抗实验用尽输出预算，因截断拒绝响应并记录 INCONCLUSIVE。后续实验提高上限并收紧结构化输出。
- Stage 5 将 Web 与 Runner 分开，在 Vultr Ubuntu VM 上以 Rootless Docker 执行。公网 HTTPS Demo 保持认证、限流和持久化配额，仅开放受控 Billing 离线执行。真实模型调用通过单独受控的私有环境验收。

## 如何体验

- Billing Rounding 已可用。打开 Demo Replay，选择原始 Bug、正确补丁、越权或超时场景，查看历史报告。在允许执行的部署中切换现有 Local API 可运行受控 Billing 场景。
- Agent Workspace 私有预览支持导入 ZIP 或文件夹，填写目标、入口函数、修改白名单和用例，再确认冻结。可以执行原始版本或离线候选，查看逐用例证据。通过并接受的修改可以导出 Patch 或 ZIP。
- Inventory Reconciliation 可从 Workspace 导入。案例覆盖库存不足、重复商品、负库存及部分提交，重点是异常请求不改变原数据。
- Application Log Summary 可从同一位置导入。案例覆盖日志级别、格式错误、半开时间区间及稳定输出。

## 如何阅读证据

| 状态 | 含义 |
| --- | --- |
| VERIFIED | 候选通过规定的验收，且运行证据和候选身份一致。 |
| FAILED | 有可信证据表明候选违反验收要求。 |
| REJECTED | 候选违反权限或策略。 |
| INCONCLUSIVE | 请求、执行或证据不完整，无法作出通过结论。 |

历史回放、离线模型提案、实时 Vultr 请求和真实容器执行分别标注。离线提案可以产生真实容器证据，历史回放不启动新容器。

## 安全边界与路线

公开演示限定内置场景，私有项目导入也必须有归属、大小和路径限制。冻结的验收条件只能由用户重新确认新版本。期望值和裁决留在可信宿主，候选只接收必要输入。向 Vultr 发送项目源码前，用户可核对范围。

两个非 Billing 项目已通过本地真实 Docker 离线验收。下一步由操作者审核本地预览，再在私有 VM 重测 Rootless Runner、A1–A5、准入及配额，并授权至少一次非 Billing Vultr 实验。项目级 Adversarial、Recovery 及 Commit & Push 仍需独立实现和验收。Semantic Context Reconstruction 是未来的可插拔语义上下文重组模块，本次比赛不实施。

## 可复查资料

- README.md 记录固定修复、Web API、对抗和恢复入口。
- docs/EXPERIMENTS.md 记录阶段实验和报告快照来源。
- docs/GATE_C_DIAGNOSIS.md 记录对抗请求截断诊断，docs/SECURITY_ATTACK_SUITE.md 记录 A1–A5。
- deploy/PRIVATE_RUNNER.md 与 deploy/STAGE5C.md 记录私有 Runner 和公网受控准入。
- docs/TRUSTBOUND_WORKSPACE_VISION_2026-11-06.md 记录后续产品设计及验收要求。
