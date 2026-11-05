# TrustBound — 项目总档案 v0.2

> **版本**：v0.2 · 2026-11-05（北京时间）\
> **阶段**：Vultr Agent Rush Hackathon · Challenge 1 / Pattern A\
> **用途**：项目愿景、已验证成果、待办、近期路线、长期发展、比赛提交与 Ownership 交接。\
> **继承文档**：`TrustBound_Hackathon_MasterPlan_2026-11-03.md`（v0.1，保留创意与决策历史，不覆盖）。\
> **当前仓库基线 Git SHA**：`64aacafb21dd62d200fc7d2ce81255948cd55b12`（包含 Runner 的 systemd 修复）。VM 实测发布为 `6fe5290` 加等效的人工 drop-in；源码同步与服务激活分别核验。

## 阅读约定

- **[已验证—本地]**：此前本地实验有实际结果；不代表在 VM 上也已通过。
- **[已验证—VM]**：已有用户提供的 Vultr VM 终端、浏览器或 Codex 探针结果。
- **[已实现，待云验收]**：代码或逻辑已有，但尚缺对应 VM 实测。
- **[进行中]**：正在开发或配置，不能视作完成。
- **[已决定]**：产品/范围决策，不等于已有实现。
- **[候选/后置]**：尚未进入本次比赛的必交付范围。
- 原档案为 **2026-11-03 的计划快照**；本档案按 **2026-11-05 已知进度**更新。未检查到最新源码的事项标注待核实，不凭空声称已完成。

---

## 0. 执行摘要

**一句话定位**：TrustBound 是一个面向开发者的可信代码任务执行与验收系统：Agent 可以提出修改与执行任务，但**不能自行宣布成功**；权限规则、真实隔离执行、独立验收与证据共同决定结论。

**核心口号**：*An agent that can act, but cannot certify its own success.*

**当前成绩**：本地完成真实 Vultr 推理和 Docker 验证实验。Stage 5B 已由用户验收，Vultr VM 上的私有 Web、独立 Runner、Rootless Docker、Unix Socket 权限隔离与离线执行链路均有实测证据。Security Attack Suite、Custom Task v1、Stage 5C 公网 Live 验收和正式提交待完成。

**当前主线**：Stage 5B（已通过） → Security Attack Suite → Custom Task v1（优先在 SSH 私有环境验收，时间不足则后置） → Stage 5C → 功能完整性 Review 与比赛交付 → Semantic Context Router（P2，可选）。

**近期总原则**：先用真实攻击实验建立安全证据，再验证受限自定义任务。保留 Billing 作为可独立交付的稳定 Demo，Custom Task 的进度不阻塞 Stage 5C 和正式提交。

---

## 1. 项目愿景与价值

### 1.1 用户痛点

编程 Agent 可以生成看似合理的补丁，但仍可能：

- 修复了公开测试，却遗漏边界条件，造成“假成功”；
- 试图修改测试、验收材料或越权路径；
- 在执行代码时访问网络、敏感文件或资源失控；
- 自己解释自己的行为、自己给出成功判断，缺少可复查的独立依据。

### 1.2 产品主张

TrustBound 把 **提出行动**、**权限批准**、**受限执行** 和 **独立验收** 分离，以明确的状态与原始证据证明结果。在可信反例出现时，可以进行有界恢复；无法得到充分证据时必须停在 `INCONCLUSIVE`。

它不是通用 IDE、通用 Coding Agent，也不承诺证明任意程序绝对正确。真正差异化的部分是 **安全边界 + 独立验证 + 证据链 + 理性停止**。

### 1.3 目标用户与潜在价值

- **近期**：参加 Hackathon 的开发者工具 Demo，面对评委展示可复现的沙箱限制与真实 Agent 工作流。
- **中期**：AI 辅助开发者、小型工程团队，作为代码修复/变更的额外验证层。
- **长期探索**：可审计 Agent Runtime、代码执行治理、独立验证服务；商业价值与真实需求尚需用户访谈和产品试用验证，不能当成已证实市场。

---

## 2. 系统架构与安全责任

```text
Browser (Vue)
    |
SSH tunnel (private, verified) / HTTPS + Caddy + auth + quotas [Stage 5C pending]
    |
FastAPI / Orchestrator (Vultr VM)
    |--- TaskSpec / Task Manager
    |--- Executor Agent -> Vultr Serverless Inference [Live 才调用]
    |--- Permission Gate / Policy
    |--- Independent Verdict / Evidence Report
    |--- Adversarial Agent / Bounded Recovery
    |
    +-- constrained Unix socket               [Stage 5B 已验证—VM]
              |
        trustbound-runner service
              |-- trusted tests / fixed execution templates
              |-- task/stage/data validation
              |-- Rootless Docker socket (not available to Web)
              |
        ephemeral sandbox container
              |-- non-root; no network; read-only mounts/rootfs
              |-- CPU / memory / PIDs / wall-clock limits
              +-- stdout/stderr, exit code, hashes, cleanup evidence
```

> **边界澄清**：Vultr Serverless Inference 的 API Key 仅供后端受控进程使用；Runner 不读取推理密钥；不可信代码不得访问 Web 服务、Docker 管理接口、宿主机敏感路径或真实密钥。Rootless Docker 降低权限，但不是绝对安全保证。

### 2.1 各层“到底由谁完成”

| 层次 | 主要职责 | 实现方式 |
|---|---|---|
| Linux 内核 | 用户/组权限、Namespace、cgroup、文件系统与进程机制 | 现成 OS 能力 |
| Docker / Rootless | 创建、限制、清理隔离容器 | Docker CLI/API 与守护进程 |
| Shell / systemd / Caddy | 创建用户、目录权限、发布切换、服务管理、HTTPS/反代 | 部署脚本与服务配置 |
| TrustBound Python | 任务、Agent、策略、Runner 协议、验收、哈希和证据 | 自有应用代码 |
| Vue | 操作流程、结果、Diff、执行和安全证据可视化 | 前端应用 |

**工程判断**：Linux/Docker 提供隔离能力，TrustBound 的价值在于规定谁可以触发哪些受限操作，如何检查操作结果，如何把真实证据映射到可靠的结论。

### 2.2 四种裁决状态

- `VERIFIED`：在已声明、已执行且证据完整的验收范围内通过；不等于程序绝对正确。
- `FAILED`：发现可信的测试失败或行为失败。
- `REJECTED`：违反静态授权、任务范围或完整性政策。
- `INCONCLUSIVE`：测试未完成、Runner 通信/清理异常、哈希不匹配、证据缺失、模型输出截断等，无法可靠断言。

**区分拦截层**：Permission Gate 预先拒绝，不等于证明容器在运行时确实挡住了同类行为。Containment Lab 要分别记录策略拦截证据和沙箱执行证据。

---

## 3. 截至 2026-11-05 的真实进度

### 3.1 核心能力

| 子系统 | 当前状态 | 已知证据 / 限制 |
|---|---|---|
| `TaskSpec` / ExecutionResult / VerificationReport | [已实现] | 本地已有数据契约及测试；细节以当前代码为准 |
| Executor Agent / Vultr Inference | [已验证—本地] | 真实 DeepSeek 模型调用、生成金额舍入修复候选并进入 Docker 执行 |
| Permission Gate | [已验证—VM] | `unauthorized` 返回 `REJECTED`，启动容器数为 0 |
| Sandbox Runner | [已验证—VM，限私有链路] | Rootless 实测资源上限和只读挂载；内置任务的超时与清理通过 |
| Independent Verifier / Evidence | [已验证—VM] | 独立容器执行，公开测试通过但正式验收失败的候选仍为 `FAILED` |
| Adversarial Agent | [已验证—VM，离线模型响应] | Double rounding 正式验收通过，真实容器确认反例后总体为 `FAILED` |
| Bounded Recovery | [已验证—VM，离线模型响应] | 修复成功、耗尽、越权、证据不足、模型错误和超时均完成私有回归 |
| Vue 前端 / FastAPI | [已验证—VM，限私有链路] | Windows 经 SSH 隧道可访问 VM 的 Vue，`/api/tasks` 可读取内置 Billing 任务 |
| 独立 Runner Unix Socket 服务 | [已验证—VM] | Web 可见业务 IPC，两种 Docker socket 均拒绝 Web 连接；Runner 使用专用 Rootless 实例 |
| Security Attack Suite / Containment Lab | [已实现，待云验收] / [候选/后置] | A1–A5 已有固定探针与报告入口；实际 VM 证据待验收，Lab 页面尚未实现 |
| Custom Task v1 | [已实现，待云验收] | 私有离线整数表达式、人工候选和冻结用例已接入；通用模型提议与模型反例发现未实现 |

### 3.2 已知本地真实实验（并非云端最终结果）

- **Gate A**：Vultr Serverless Inference 基础真实调用成功。
- **Gate B**：Executor 针对 Billing 金额舍入产生候选修改，公开测试与独立验收曾在 Docker 中成功运行。
- **Gate C**：Adversarial Agent 提出双重舍入反例（如 `1.23495` / `-1.23495`），真实运行验证预期与候选输出不一致，能推翻错误成功结论；一轮先前实验因模型截断曾为 `INCONCLUSIVE`，不能被算作成功。
- **Gate D / Recovery**：此前有真实恢复调用与修复记录，但需对当前最新源码核对完整证据和新反例复测；不可宣称云端已通过。

### 3.3 Vultr VM / Stage 5A–5B

- [已验证—VM] Ubuntu 24.04，2 vCPU / 4 GB，东京 Shared CPU VM；SSH Key 登录；tmux 已使用。
- [已验证—VM] Docker Engine 29.9.3，`hello-world` 成功；Git 工作副本位于 `/home/linuxuser/apps/TrustBound`，Stage 5A 发布基线为 `ee509ce`。
- [已验证—VM] Python / Node 发布准备、固定发布版本激活、私有 FastAPI 和 Vue/Vite 预览访问链路已打通。
- [已验证—VM] Rootless Docker 基础探针：CPU、内存、PID 限制和容器 UID/GID `65534:65534` 读取只读 `/work` 挂载。
- [已验证—VM] Stage 5B 发布 `6fe5290` 加等效 systemd drop-in：Web 进程可见业务 Unix Socket，但系统 Docker 与专用 Rootless Docker socket 均返回 `PermissionError`。
- [已验证—VM] Run `170a8c4ca9c94b85bc46cf5f7faaccbd` 为 `VERIFIED`，公开测试和正式验收在两个独立容器内运行，均退出 0 并清理。基础执行 6 项、离线对抗 6 项、有限恢复 10 项均通过，结束后专用 Docker 没有残留的 TrustBound 容器。原始报告在 VM 的 `/home/linuxuser/trustbound-stage5b.85f0rR/artifacts/`。
- [尚未验收] Runner 异常退出后的孤儿容器回收、完整攻击套件、Caddy 公网访问、HTTPS、认证、持久化配额与云端 Live Agent。
- [安全待办] SSH 22 曾为排障临时开放较宽来源，上线前需限制管理来源；严禁公开 8000、5173、Docker 管理端口与 socket。
- [安全待办] 现阶段公共 `/api/*` 应继续保持阻断（部署时通过 Caddy 返回 503）；但**不能把尚未安装/验收的 Caddy 当作当前已配置成功**。

### 3.4 离线与 Live 的区别

- **Offline**：在未调用真实 LLM 的情况下，使用固定受信任务及候选数据，检验真实 Docker、策略、验收和证据；不是伪造容器结果。
- **Live**：后端通过 Vultr Serverless Inference 让 Executor / Adversarial / Recovery 参与生成候选与反例；模型输出仍须经过同样的权限、沙箱和验收流程。
- 当前 VM 的 Live Executor 保持关闭，不能因为前端可见或 API 健康，就称为公网真实 Agent 闭环完成。

---

## 4. 比赛硬性要求与交付闸门

**赛事**：Vultr: Agent Rush Hackathon；Challenge 1 — Blast Radius Zero，Pattern A — Sandboxed Code Execution。

根据官方 Vultr 活动说明，必须：

| 官方要求 | TrustBound 的验收表达 | 当前状态 |
|---|---|---|
| Vultr VM 后端编排 | FastAPI 确实运行在 Vultr VM | 私有服务已打通 |
| 所有 Agent LLM 使用 Vultr Serverless Inference | 云端 Live 日志和模型 ID 可核实 | 本地真实调用已有；云端待验收 |
| 真实沙箱而非主进程执行 | 独立 Runner、受限真实容器 | Stage 5B 私有链路已验收 |
| Process Isolation | Web 无 Docker 管理权，沙箱不改宿主环境 | socket 隔离已验证；A1/A2 攻击证据待补 |
| Secret Hygiene | 不传 Vultr Key；使用合成诱饵测试无泄露 | 待验收 |
| Resource Limits | 时间、CPU、内存、PID 限制真实生效 | cgroup 探针与任务超时已验证；A5 内存耗尽待测 |
| Lifecycle Management | 容器按次销毁；异常后可审计回收 | 正常及任务超时清理已验证；服务崩溃后回收待测 |
| Public Web Demo | 有可访问、可认证、真实交互的 HTTPS URL | 未完成 |
| 公开代码与说明 | GitHub 公共仓库、配置/架构/安全说明 | 仓库已同步；公开性和内容待核实 |
| 真实 containment moment 视频 | 清晰展示危险行为及实际拦截/清理证据 | 未录制 |
| 最终提交 | 在 lablab.ai 团队提交页提交完整作品 | 未确认完成 |

**原档案记录的截止**：2026-11-08 22:00 UTC = **北京时间 11 月 9 日 06:00**。以最新赛事 Dashboard 为最终准绳；建议 **11 月 8 日白天冻结代码并完成主要交付**。

**提交包**：项目标题、短/长描述、标签、公共 GitHub、可用 Demo URL、视频、架构及限制说明、演示幻灯片/PDF，以及表单要求的其他材料。不要因增强功能延误正式提交。

官方参考：
- https://community.vultr.com/e/vultr-agent-rush-hackathon
- https://lablab.ai/ai-hackathons/vultr-hackathon
- https://lablab.ai/ai-hackathons/vultr-hackathon/live
- https://lablab.ai/delivering-your-hackathon-solution

---

## 5. 最新功能主线（截至 11 月 5 日）

### 1. P0 — Stage 5B：独立 Runner 与云端离线闭环（已验收）

**目标**：让 FastAPI 在不持有 Docker 管理权限的前提下，完成真实受控代码执行和独立验收。

**验收结果**：用户确认私有离线链路通过。Web → 受限 Unix Socket → 专用 Runner → Rootless Docker 已在 VM 实测，覆盖基础执行、对抗与恢复；权限隔离、资源探针、任务超时与容器销毁的证据见 §3.3。异常退出后的孤儿容器回收仍单独跟踪。公网执行入口保持阻断。

### 2. P0 — Security Attack Suite（下一步）

**目标**：以真实 Runner 证据展示 **Process Isolation、Secret Hygiene、Resource Limits、Lifecycle Management**，并明确指出每次攻击在哪一层被拦截。

| 编号 | 受控攻击类型 | 预期可审计证据 | 优先级 |
|---|---|---|---|
| A1 | 文件越权与只读写入 | 分开记录策略拒绝（零容器）与固定攻击载荷实际写入失败（真实容器）；可信文件哈希不变 | P0 |
| A2 | 无网络容器访问受控目标 | 记录受控目标及连接失败证据；不访问第三方服务 | P0 |
| A3 | 合成密钥或敏感环境变量读取 | 在可信侧设置合成诱饵，沙盒内读取失败，输出和报告不暴露密钥值 | P0 |
| A4 | 无限循环/超时 | 超时停止、对应容器销毁、主 API 仍健康 | P0 |
| A5 | 受控内存耗尽 | 容器的 OOM 状态或 cgroup 事件与内存上限一致；记录退出码、清理和 API 健康 | P0 |
| A6 | PID/进程数量滥用 | PID 上限与失败证据 | P1 |
| A7 | 受控临时磁盘写入 | tmpfs/配额阻止无限占用宿主磁盘 | P1 |
| A8 | 证据哈希错误、缺失或伪造 | 不允许 VERIFIED，改为 INCONCLUSIVE 等正确状态 | P1 |

**实施约束**：攻击载荷由仓库审核并固定，使用合成凭据、受控目标和有界资源。运行时用例必须经过实际任务使用的独立 Runner 和 Rootless Docker。对策略拒绝记录零容器；它不能代替运行时证据。每项记录攻击 ID、发布版本和 Run ID、拦截层、实际结果、限制值与触发证据、容器 ID/退出码及清理状态。证据缺失时标明 `INCONCLUSIVE`，模拟结果不得用于证明运行时隔离。

**完成闸门**：A1–A5 均有真实 VM 结果；至少录下一个完整的 containment moment。A6–A8 有余力再做。若时间紧，先保住真实安全证据和可录屏用例，明确列出未完成项，不以缩减展示代替安全验收。

**可选展示**：Containment Lab 可以用预定义按钮或已有报告展示 `Policy Rejected`、`Sandbox Blocked`、`Timed Out`、`Resource Limited`、`Evidence Inconclusive`。录制证据与实时执行须明确标注。Lab 页面不作为 Attack Suite 验收的前提。

### 3. P1 — Custom Task v1（优先私有验收）

**产品目标**：让开发者提供自己的 Python 代码和需求，沿用 TrustBound 的执行与验证流程。Billing 保留为官方稳定 Demo 和回归基线。

- 输入仅限单文件 Python 源码、明确的自然语言需求和受约束的结构化输入/预期输出。限制源文件大小、用例数量、数据类型、依赖和执行时长。
- 用户提交的结构化用例在运行前冻结，记录候选和验收材料哈希。Executor 和对抗模型不能修改验收条件。Runner 从结构化数据构造可信控制脚本；调用方不能提交可执行验收脚本、Docker 参数或宿主机路径。
- 复用 Executor、Permission Gate、独立 Runner、Independent Verifier、对抗测试和 Evidence Report。对抗阶段只在有可信预期或可复查规则时确认反例。缺少可靠验收证据时，必须标明范围或返回 `INCONCLUSIVE`。
- 第一轮只在 SSH 私有环境开放给指定用户。面向公网启用须单独通过权限、身份、配额与隔离验收。禁止匿名、无限制的任意代码执行。

**完成闸门**：在 VM 私有环境用至少一个非 Billing 任务完成端到端验证，覆盖正确结果、业务失败、越权字段拒绝及证据不足；验证验收材料在执行前固定、候选不能改写，并在 UI 标明 `VERIFIED against supplied/approved tests` 的范围。

**时间闸门**：到预留的 Stage 5C 开始时间仍未通过私有验收，就关闭 Custom Task 入口，使用 Billing 完成 Stage 5C 与比赛交付；有余力可用第二个已审查的固定任务展示复用。

### 4. P0 — Stage 5C：受控 HTTPS 公网部署

1. 以 Caddy 提供 Vue 静态页面和反代 FastAPI，保留 `/api` 路径，HTTPS 有效、HTTP 正确跳转。
2. 页面、执行接口和报告查询均需认证；无认证访问返回预期拒绝。
3. 持久化任务、模型调用、Token 预算，控制并发、频率、请求体、日志与证据体积；重启后额度不应归零。
4. FastAPI 仅在 `127.0.0.1:8000`，Docker socket 与管理端口不暴露；SSH 来源收紧。
5. 先开放带认证的**离线 Demo**；随后在明确预算和管理员许可下进行单次真实 Vultr Live 闭环。
6. 失败时先把公网执行接口恢复为 503，再使用已有发布/回滚机制恢复已知可用版本。

**完成闸门**：从外网验证 HTTPS、未认证拒绝、认证用户能运行 Billing、限流确实拦截超频请求、重启不重置任务与推理额度、Docker 权限隔离和证据访问受控。至少完成一次 VM 上受预算约束的真实 Vultr Live Web 实验，记录实际模型、用量、费用估算、Docker 证据及裁决；真实结果可以是失败或证据不足，不用预设补丁替换。Custom Task 的公网开放不计入该闸门。

### 5. P0 — 功能完整性 Review 与比赛交付

重点确认：
- Executor → Permission Gate → Sandbox → Independent Verification → Adversarial → Bounded Recovery 的控制流完整。
- 样例任务状态、候选 Hash、测试 Hash、容器 ID / Exit Code、清理状态、模型 ID、Token 与费用能关联到同一个 Run ID。
- 模型截断、验证失败、执行失败及证据缺失不会错误显示成功；无触发 Recovery 的场景不能伪造 Recovery 过程。
- 复查 Stage 5C 的真实调用记录、费用估算与安全停止条件；Live Recovery 须独立授权。
- Vue 与原始后端报告一致，错误展示真实、可解释。
- 冻结可回滚版本，完成全量回归、证据整理、含 containment moment 的 Demo 录制、README、PPT/PDF 和正式提交；提交后回查链接和状态。

### 6. P2 — Semantic Context Router（交付后可选）

比赛交付完成且有余力时，再实现可开启、关闭和移除的上下文插件。近期只保持 Context Builder 接口清晰，默认沿用 Direct Context。插件和实验设计见 §8。

---

## 6. 近期时间安排与缩减策略

> 以最终提交为最高硬约束；本时间表是执行建议，Codex 的工作应围绕当前阻断点而非并行扩张。

| 时间 | 最高优先任务 | 退出标准 | 超时缩减 |
|---|---|---|---|
| 11/05 | Stage 5B 独立 Runner 与 VM 私有离线验收 | 已通过，证据见 §3.3 | 仅处理新发现的阻断性回归 |
| 11/06 | Security Attack Suite A1–A5 | 每项有实际结果，至少一个可录制的 containment moment | A6–A8 与独立 Lab 页面后置 |
| 11/06 晚–11/07 早 | Custom Task v1 的私有验收 | 非 Billing 单文件任务通过 §5 的安全和证据闸门 | 到 5C 开始时间即停，使用 Billing 交付 |
| 11/07 起 | Stage 5C：HTTPS、认证、持久化配额、云端 Live | 认证离线 Demo 与受预算约束的真实 Vultr Web 验收 | 公网仅保留已审核固定任务 |
| 11/07–11/08 | 功能完整性 Review、录屏、README、PPT/PDF | 全量回归完成，报告和提交材料可复查 | 停止新功能 |
| 11/08 白天 | 正式提交及回查 | lablab.ai 提交状态确认为成功 | 仅修提交阻断问题 |

**硬性缩减顺序**：P2 Router 默认后置；再后置 A6–A8 和可选 Lab 界面；Custom Task 到时间闸门立即收敛。保留沙箱隔离、受控公网 Demo、真实 Vultr 模型调用、真实拦截视频和正式提交所需的时间与安全要求。

---

## 7. Demo 故事与展示策略

### Demo A — Agent 修复 + 独立验收

使用 Billing 或其他审核固定任务：用户发起任务 → Vultr LLM 生成候选补丁 → Permission Gate 检查 → Runner 运行公开及独立验收 → 报告真实差异、退出码与 Hash。展示对抗反例如何推翻“表面成功”。

### Demo B — Containment Lab（比赛关键）

在同一个 VM 上触发受控超时、受保护文件写入或网络禁止操作；同时展示沙盒失败、宿主机/原文件未变化、容器被销毁、API 仍健康。**至少一个完整镜头包含“危险动作 → 实际阻断 → 清理证据”。**

### Demo C — 通用性（仅在稳定后加入）

用第二个审核样例，或受控 Custom Task v1，现场展示不同问题也能沿用同一安全执行与验收管线。不要在 Demo 中临时启用匿名任意代码执行。

**展示排序**：业务痛点 → TrustBound 控制流 → 真实模型动作 → 独立证据 → containment moment → 适用场景与局限。视觉效果服务证据，而不是掩盖证据。

---

## 8. 后期项目方向（比赛后，不在本次必交付）

**比赛期间的边界**：优先完成安全执行、真实攻击实验、受限自定义任务、受控公网 Demo 和提交材料。通用多语言执行、任意仓库导入、完整平台化及路由研究留到交付后。

### Phase A — Ownership / 项目理解与维护

按模块完成五个问题：**What（职责）/ Why（必要性）/ How（控制流和数据流）/ Failure（故障与边界）/ Change（修改定位）**。优先研究：`contracts.py`、`runner.py`、`service.py`、`inference.py`、`executor.py`、`adversarial.py`、FastAPI、部署脚本、Vue 页面。最终能自己解释和修改关键流程，并建立故障手册。

### Phase B — 通用任务与开发者体验

- 完善 Custom Task：更多代码文件、明确的任务策略与审批、可信测试模板、版本化任务与 Run 历史。
- Git/PR 导入与变更审查、可追溯的工作区、报告导出和可重复执行。
- 更严格的沙箱配置、审计日志、预算治理、权限模型和安全更新。

### Phase C — 可靠性研究

- **Semantic Context Router（P2，可选）**：保留同一个 Context Builder 接口，在 Direct Context 与 Semantic Router 间切换。硬性权限、禁止操作、任务目标和关键验收条件由可信宿主无条件注入，语义检索只补充上下文。开启、关闭或移除插件不应影响 Agent、Runner 和 Verifier 的核心契约及裁决。
- **Router 验收与消融**：先回归验证开关和移除路径，检查检索未命中时硬约束仍完整。再在相同任务、模型、预算和验收规则下比较 Router ON/OFF 的 Token、延迟、成本、任务通过率、约束保留率与反例发现能力。报告样本量及失败案例，由真实结果决定是否保留，不预设 Router 优于 Direct Context。
- Evidence Graph / Assurance Level：做来源、覆盖、有效性与证据关联的可解释评价；不构造无校准的“正确概率”。
- Property-Based / Metamorphic / Mutation Testing，用更多可复现反例研究验证器漏检情况。
- 在相同任务、模型和预算下做 Baseline 对比，使用真实统计结果，不因少量 Demo 声称普适提升。

### Phase D — 产品化与商业验证

面向个人开发者和小团队验证付费/使用意愿；探索 CLI、PR Check、CI 插件、托管服务的需求。任何成本收益、误报下降或安全提升必须经过实验与用户反馈再陈述。

---

## 9. 技术与安全边界（始终有效）

1. **真实执行 ≠ 绝对安全**：Docker 共享宿主机内核；Rootless 只是降低宿主机权限风险。
2. **LLM 输出不可信**：不能自行扩权、修改可信验收标准、指定宿主路径/容器管理选项、传入可执行控制脚本。
3. **证据必须有来源**：测试/候选 Hash、版本、执行环境、退出码与清理状态要匹配；缺失不得输出 VERIFIED。
4. **Secret Hygiene**：真实 Vultr Key 不进入 Git、前端、Runner 或沙箱；密钥文件限后端受控服务访问。
5. **可公开 ≠ 可匿名执行**：公网必须有身份认证、全局持久化配额与频率限制。
6. **安全测试仅在可控范围**：不操作真实第三方系统，不测试真实凭据，不让资源压力试验伤害宿主机。
7. **发布纪律**：本地 Codex 可以改代码和执行本地测试；VM 配置与发布由用户亲手执行；重要改动先说明原问题、范围、效果和实测结果。
8. **项目所有权**：本次优先完成比赛；赛后系统复审代码并理解关键决策，不把工具协助完成等同于已经掌握。

---

## 10. 当前唯一下一步与交接给 Codex 的口令

**当前唯一下一步**：审核并在私有 VM 验收 Security Attack Suite 的 A1–A5。以现有 Stage 5B 独立 Runner 为执行基线，先产出可复查的安全证据，再评估 Containment Lab 页面。

**给 Codex 的近期目标**：

> 基于现有 TrustBound 独立 Runner 实现固定、审核过的 A1–A5 攻击用例。分别记录 Permission Gate 提前拒绝和真实沙箱限制，保留每项资源、退出、宿主完整性与清理证据；不接收用户自定义攻击载荷。先做本地回归，再由用户在 VM 私有环境亲自验收。公网执行和 Live 继续关闭。待攻击证据完整后，按时间闸门推进 Custom Task v1，再进入 Stage 5C。

**最新决策冻结**：
- 已通过：Stage 5B 私有执行与 Runner 权限隔离。
- 比赛核心：A1–A5 攻击证据、至少一个 containment moment、Stage 5C 受控 HTTPS 与真实 Vultr Live、正式提交。
- 条件增强：私有 Custom Task v1、Containment Lab 页面及 A6–A8。未完成的 Custom Task 不阻塞 Stage 5C 或提交。
- 后置：Semantic Context Router（P2）、Evidence Graph、通用多语言执行、复杂 CI/PR 集成和全面 Ownership Review。

---

## 11. 更新记录

- **v0.1 · 2026-11-03**：赛事事实、产品理念、工程草案、P0/P1/P2 优先级与初始时间表。
- **v0.2 · 2026-11-05**：记录 Stage 5A–5B 的实测与验收；将 Security Attack Suite 设为下一步，Custom Task v1 调整到 Stage 5C 前私有验收；补齐安全与交付闸门，保留 Semantic Context Router 为交付后 P2 可选插件。

> **档案定位**：v0.1 回答“为什么选择这个方向”；v0.2 回答“今天做到了哪里、下一步是什么、哪些事情不该抢占交付时间”。后续每通过一个云端闸门，只更新对应状态和证据，不反复重写全部历史。
