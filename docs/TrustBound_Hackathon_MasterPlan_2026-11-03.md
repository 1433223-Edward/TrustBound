# TrustBound — Vultr Agent Rush Hackathon 项目总档案

> **文档版本**：v0.1 · 2026-11-03（北京时间）  
> **用途**：赛事信息归档、创意与决策留痕、工程实施总纲、交付验收标准、Codex 交接材料。  
> **状态说明**：`[官方]` 主办方明确规定；`[已决定]` 本次对话确立的项目方向；`[建议]` 尚待本地环境确认的实现选择；`[实验假设]` 需要数据验证；`[待确认]` 尚未核实。  
> **原则**：不把脑暴当作已完成，不把模型评分当作正确概率，不把 Docker 容器当作绝对安全边界。

---

## 0. 一页式执行摘要

- **参赛赛事**：Vultr: Agent Rush Hackathon（lablab.ai × Vultr），线上开发 2026-11-03～11-08。已在页面截图中看到 `Enrolled` 和团队 Dashboard；**不需要再次报名**。此前截图中团队名为 `Twitch stage`，实际队伍归属已通过赛事页确认；队伍名称是否修改由参赛者自行决定。
- **参赛赛道**：`Challenge 1 — Blast Radius Zero`（已决定）；执行模式选 `Pattern A — Sandboxed Code Execution`（已决定）。不做浏览器自动化 Pattern B。
- **项目代号**：**TrustBound**。核心主张：*An agent that can act, but cannot certify its own success.*（Agent 能执行，但不能自行宣称通过验收。）
- **产品定位**：面向开发者的可信代码任务执行与验收系统。通过独立验证、受限权限、隔离执行和可复查证据，减少“看起来成功、实际上失败”的误报。
- **工程主线**：`TaskSpec → Executor Agent → Permission Gate → Ephemeral Sandbox → Independent Verifier → Evidence Report`。之后加入 `Adversarial Agent → Counterexample Check → Bounded Recovery`。
- **核心示范**：小型 Python 项目测试修复；一轮表面成功却因隐藏验收失败被拒绝；越权操作被真实拦截；无限循环在限制内终止，主服务不受影响。
- **今天（11 月 3 日）**：检查环境、建立独立仓库、构造受控 Python 示例、跑通不含 LLM 的隔离执行实验，定义数据契约和验收测试；晚间确认比赛 Kickoff 与云额度。
- **禁止范围漂移**：不提前做复杂 RAG/向量数据库、通用 Coding Agent、多平台集成、任意用户上传代码公网执行、多轮 Agent 辩论或生产级安全认证。

## 1. 赛事事实与规则

### 1.1 时间和入口

| 项目 | 时间或地址 | 来源/说明 |
|---|---|---|
| 官方赛事 | [lablab.ai 赛事主页](https://lablab.ai/ai-hackathons/vultr-hackathon) | [官方] |
| 实时 Dashboard | [赛事 Live 页](https://lablab.ai/ai-hackathons/vultr-hackathon/live) | [官方] |
| Vultr 赛题 | [Vultr Community 活动页](https://community.vultr.com/e/vultr-agent-rush-hackathon) | [官方] |
| 线上开发 | 2026-11-03～11-08 | [官方] |
| 平台开始/报名关闭 | 2026-11-03 15:00 UTC = **北京时间 11 月 3 日 23:00** | [官方 Live 页] |
| Vultr 活动议程 Kickoff | 2026-11-03 16:00–17:00 UTC = **北京时间 11 月 4 日 00:00–01:00** | [官方 Vultr 活动页]；与平台“开始时间”不是同一个时点 |
| 最终提交 | 2026-11-08 22:00 UTC = **北京时间 11 月 9 日 06:00** | [官方 Live 页] |
| 推荐内部冻结 | 北京时间 11 月 8 日白天完成提交包 | [建议] 留出部署/视频/平台故障缓冲 |
| 官方入门 | [Getting Started](https://lablab.ai/getting-started-guide) | [官方] |
| 平台提交指南 | [Submission Guidelines](https://lablab.ai/delivering-your-hackathon-solution) | [官方] 具体以该赛事提交表单为准 |

**当前参赛状态（据用户截图）**：已经报名（Enrolled）、能够进入团队 Dashboard、左侧存在 `Submit Project` 提交入口；截图无法证明 Vultr 账号、云额度和提交权限已配置完毕。Discord 是否已经绑定个人资料仍需在相应页面确认。

### 1.2 Challenge 1 硬性要求

**[官方]** 做一个在 Vultr 上部署的 Web Agent，能够完成真实工作（执行代码**或**操作浏览器），将动作隔离在沙盒内，并返回可验证的真实执行结果：

1. **Vultr VM**：后端中央控制与任务编排（不是仅静态网页托管）。
2. **Vultr Serverless Inference**：Challenge 1 的 Agent LLM 调用走该服务；官方给出 OpenAI-compatible base URL：`https://api.vultrinference.com/v1`。
3. **隔离执行**：使用容器或临时实例，在应用进程外执行，严禁在 FastAPI 主进程中直接执行模型生成代码。
4. **Process Isolation**：执行与主机、主应用运行时隔离。
5. **Secret Hygiene**：API Key 和凭据不得进入沙盒。
6. **Resource Limits**：每次执行设置时间和内存等限制。
7. **Lifecycle Management**：每次任务后重置或销毁环境。
8. **真实多步骤工作流**：不是只聊天或假装执行；应展示计划→执行→返回结果→验证（必要时重试）。
9. **公开 Web Demo**：产品形态，能在浏览器访问。

**执行模式**：
- Pattern A（已选）：用户任务 → 模型写代码/补丁 → 沙盒真实执行 → 返回结果 → 验收/解释，失败可反馈重试。
- Pattern B（本次不选）：容器浏览器（如 Playwright）执行、截图与视觉验证。

**评审维度（官方未给出本赛道具体权重）**：Application of Technology、Presentation、Business Value、Originality。

### 1.3 云额度及注意事项

- 官方表示每位参赛者可获得 **200 美元 Vultr credits**，礼品码在 Kickoff 提供；官方页面还要求使用未曾关联 Vultr 账号的有效邮箱创建账户以领取相应额度。请以实际领取页面的条款为准。
- **不要**为了尽快开发而在未确认额度、计费或需要绑定支付方式时贸然开通付费资源。
- 官方指出本次活动不提供 Vultr GPU 资源。
- Vultr 是云基础设施提供商；VM = 远程 Linux 服务器，Serverless Inference = 云端模型推理 API，不是 Agent 框架。

### 1.4 最终交付清单

- [ ] lablab.ai 赛事团队 Dashboard 中完成正式提交（必需；Vultr Community 展示不能替代）
- [ ] 公开 GitHub 仓库（README、运行方法、架构和 Vultr 使用说明）
- [ ] 实际部署在 Vultr VM 的后端与可用 Web Demo URL
- [ ] 使用 Vultr Serverless Inference 的真实 Agent 调用与证据
- [ ] 项目标题、短描述、长描述、技术标签
- [ ] 视频演示，**必须展示一个真实 containment moment**：如沙盒超时终止或模拟越权阻止
- [ ] 演示幻灯片 PDF；封面图（官方通用指南标为可选，具体按赛事表单）
- [ ] 解释用户痛点、商业价值、创新点、限制及尚未解决的问题
- [ ] 依赛事表单和官方规则完成最终合规检查；作品原创且满足赛事所述许可约束

---

## 2. 目标、个人价值与取舍

### 2.1 目标优先级 [已决定]

1. **真正完成并提交第一次 Hackathon**：走通从赛题分析、架构、工程实现到公开部署、演示、交付的完整闭环。
2. **理解真实 Agent 工程**：Runtime、Tool Dispatcher、Sandbox、Permission Gate、Verification、Fault Handling、Cloud Deployment。
3. **形成可用于 AI Agent / AI Backend 面试的可展示项目**：讨论问题定义、约束、失败案例、取舍与实测数据，而非只有前端截图。
4. **具有业务价值**：目标用户暂定为使用 AI 辅助编程、需要可信验收的开发者/小团队。
5. **探索长期可扩展的 Agent 可靠性产品方向**：安全治理、证据与可复现验收，但不假定已验证市场需求。
6. 争取名次是额外收益，不优先于可交付性。

### 2.2 为什么选择 Challenge 1

- Challenge 2 更直接面向企业工作流，但 Challenge 1 也可以服务开发团队的真实业务痛点。
- 当前已有 Aim Coach（Tool Calling、多轮 Agent）和 RAG/FastAPI 项目经验，进入 Sandbox/Runtime/验证环节能补足新的、可解释的工程能力。
- 避免做“普通聊天机器人 + UI”；要展示实际执行和可信验收。

### 2.3 产品故事

**问题**：编程 Agent 声称修复成功，测试可能覆盖不足、测试被修改、越权执行或存在未识别的失败。用户无法仅凭 Agent 的自我报告放心接受修改。

**解决办法**：TrustBound 把“产生修改”和“验收修改”分开：在受限环境运行代码，用独立、可复查的证据判断是否满足明确定义的验收范围。必要时由独立对抗 Agent 提出反例，并在有界预算下恢复。

**产品口号**：*An agent that can act, but cannot certify its own success.*

**注意**：项目降低误报风险，不声称程序绝对正确、无法逃逸沙盒，或已经获得统计校准的可信概率。

---

## 3. 创意演变、备选方案与最终收敛

### 3.1 早期对比

- `Challenge 1`：更深的 Agent 执行、安全、控制流、验证；缺点是安全和部署复杂。
- `Challenge 2`：更直接面向企业流程与业务场景；但这次选择更贴合自身技术成长的 Challenge 1。
- 两者并非互斥：将 Challenge 1 做成帮助开发团队验收 Agent 产出的业务产品。

### 3.2 曾探讨的七条灵感（保留记录，**非全部开发目标**）

| 代号 | 原始创意 | 保留价值 | 当前处理 |
|---|---|---|---|
| ProofPatch | 自动修复并附带真实测试证据 | 修复 + 独立验收 | 融入主线 |
| Agent Firewall | 最小权限与拒绝越权 | 权限边界 | P0 基础 / 动态授权后置 |
| ShadowFlow | 浏览器预演、提交前审批 | 用户可视化风险 | 本次不做 |
| RecoveryLab | 错误分类、受限重试、停止 | 故障处理 | P1 |
| DataTrust | 数据修复、保持业务约束 | 数据领域潜在应用 | 本次不做 |
| WebProof QA | 浏览器 QA 和可复现 Bug 报告 | 可执行证据 | 本次不做 |
| ReproAgent | 干净环境重跑、复现性 | 验证可信度 | 视时间部分融入 |

### 3.3 方案演变

- `ProofGate`：独立验收、对抗测试、证据分级；创新主线。
- `PermissionPilot`：任务范围授权、分阶段权限；安全主线。
- `RecoveryOS`：故障分类、有界修复、理性停止；恢复主线。
- `TrustLoop / TrustBound`：用可信控制层连接上述机制。**最终工作名称取 TrustBound**。

### 3.4 用户提出的关键原创假设 [实验假设]

1. **Context Separation**：执行者和对抗者不共享完整会话历史，避免互相说服和输出污染；但可以访问各自职责必需的原始需求及待验证代码。
2. **Semantic Context Routing**：对长任务做分句/切块、向量化，根据 Agent 职责检索相关任务片段，而不是把完整 Prompt 交给每个 Agent。
3. **Mandatory Constraint Propagation**：否定、权限、关键验收等硬约束不得被语义检索 Top-K 丢掉；需结构化必传与来源溯源。
4. **Independent Adversarial Verification**：Executor 正向实践，Adversarial Agent 只找反例；双方**不辩论**，由外部独立验证器裁决。
5. **Evidence Scoring / Evidence Graph**：证据可按完整性、覆盖度、有效性等维度评价，但评分不是成功概率，也不可替代一票否决的硬性门槛。
6. **Rational Stopping**：故障分类后决定重试、修复、请求批准或停止；避免盲目追求任务成功。

这些假设目前没有实验结果，不能写作已解决的 Prompt Injection、正确性或安全性难题。

---

## 4. 验证理论与设计原则（浓缩）

### 4.1 多版本系统的共同失效

- Knight & Leveson (1986) 研究了不同开发者独立实现的多个程序版本，发现独立开发不等于错误独立；多个实现可能对同一输入共同失败。
- **工程启示**：两个上下文隔离的 Agent 可能具有相同盲区。不要用“两个 Agent 都认为正确”替代独立执行证据。
- 参考：[An Experimental Evaluation of the Assumption of Independence in Multi-Version Programming](https://doi.org/10.1109/TSE.1986.6312924)。

### 4.2 值得借鉴的传统验证方法

| 机制 | 目的 | TrustBound 可用方式 |
|---|---|---|
| 单元 / 集成 / 回归测试 | 检查具体输入输出 | P0 独立 pytest 验收 |
| Property-Based Testing | 生成更多满足性质的输入 | P1/P2 边界测试 |
| Metamorphic Testing（蜕变测试） | 没有已知标准答案时检查输入输出关系 | 检查订单顺序不变性等**已确认**业务性质 |
| Mutation Testing（变异测试） | 故意引入 Bug，测试验证系统灵敏度 | P2 检查 Evidence 机制本身 |
| Static Analysis | 检查源代码结构与明确规则 | P0 检查禁止修改文件；复杂分析后置 |
| Model Checking | 验证有限状态系统中的转移 | P2 检查未验收不得成功、越权后不得继续 |
| Formal Verification | 证明明确定义的逻辑性质 | 只作为理论，不承诺通用证明 |
| Proof-Carrying Code | 提交可检查的证明材料 | 借用 Evidence Package 思想，**不等于形式化证明** |
| Differential / N-version Testing | 不同实现交叉检查 | 仅辅助，警惕共同失效 |
| Counterfactual Verification | 探索修改对结果的贡献 | 长期研究方向，不进入本次 MVP |

### 4.3 Evidence 的最终机制草案

**先硬规则，后软评价**：

- Hard Gates：关键测试未通过、越权、修改验收材料、执行证据无法对应特定代码版本 → 不能标为已验证成功。
- Acceptance Status：`VERIFIED`（在指定范围内通过）、`FAILED`（存在已确认失败）、`INCONCLUSIVE`（证据不足）、`REJECTED`（执行或完整性违规）。
- Assurance Level（未来建议）：`L0 Claimed`、`L1 Observed`、`L2 Checked`、`L3 Challenged`、`L4 Assured`；L4 也不是绝对正确。
- Evidence Dimension（未来建议）：`Integrity`（完整性与来源）、`Coverage`（验收覆盖）、`Validity`（证据是否支持结论）。
- Evidence Graph（未来）：`Claim → Supporting Evidence / Counterexample → Verification Outcome`，注明来源、版本、执行环境；避免所有证据简单平均。
- **本次 MVP 选择**：保留结构化证据记录和硬性验收；不先实施无法校准的 0—100“可信概率”。

---

## 5. MVP 产品需求与使用流程

### 5.1 目标用户与场景

- **用户**：开发者 / 小型工程团队。
- **使用场景**：对预置的小型 Python 项目提出修复目标，观察 Agent 生成补丁、在沙盒中运行测试、由独立机制验收并返回依据。
- **输入边界**：本次 Demo 使用维护者审核的、确定依赖版本的测试仓库/样例；不提供任意访客上传任意代码的公共执行服务。

### 5.2 核心流程

```text
User Task + TaskSpec (immutable acceptance/policy)
                  │
                  ▼
            Task Orchestrator
                  │
                  ▼
             Executor Agent ───→ proposed patch / action
                  │
                  ▼
        Permission Gate (non-LLM)
           ├─ deny ─────────────→ REJECTED / review
           └─ allow
                  │
                  ▼
          Ephemeral Sandbox Runner
             (code/test execution)
                  │
                  ▼
         Independent Verifier
             ├─ pass ───────────→ VERIFIED
             ├─ fail ───────────→ FAILED or bounded retry
             └─ insufficient ──→ INCONCLUSIVE
                  │
                  ▼
       Evidence Report + diff + trace
```

**P1 增量**：Executor 交付候选补丁后，Adversarial Agent 在独立上下文中阅读用户原始需求与候选代码，提出符合需求的反例；独立验证器执行反例，确认有效后才决定是否让 Executor 受限修复。对抗者与执行者不直接辩论。

### 5.3 功能模块

| 模块 | 职责 | 优先级 | 完成定义 |
|---|---|---|---|
| Task Manager | 创建任务、记录状态、预算和历史 | P0 | 单任务的每一步可追踪 |
| Executor Agent | 根据 TaskSpec 提出补丁、分析失败 | P0（Day 2） | 生成可执行的候选修改 |
| Permission Gate | 检查修改路径、执行权限与策略 | P0 | 拒绝未授权修改，不能 LLM 自行放行 |
| Sandbox Runner | 受限环境运行任务，收集结果，销毁容器 | P0（Day 1） | 能执行、超时、清理、限制资源 |
| Independent Verifier | 不依赖 Executor 自报成功，独立检查 | P0 | 有真实测试和不可修改的验收条件 |
| Evidence Report | 版本标识、diff、stdout/stderr、测试结果、状态 | P0 | 可复查报告 |
| Adversarial Agent | 找边界反例，不与 Executor 对话 | P1 | 有至少一个经过真实验证的反例 |
| Recovery Controller | 识别失败类型，控制重试/停止 | P1 | 有限次数恢复或停止 |
| Semantic Context Router | 职责检索、约束必传、溯源 | P2 | 有与无路由的约束召回对比实验 |
| Evidence Score / Graph | 来源、覆盖、有效性多维可信判断 | P2 | 有规则与人工样例校准，不虚构概率 |

### 5.4 非功能要求

- **隔离**：不在 API 进程执行候选代码；凭据不可达；外部网络默认不可用；资源、进程与耗时受限；执行后环境清理。
- **可靠性**：验证失败不能显示成功；超时和异常有明确状态；任务 ID 与代码版本标识对应。
- **可审计**：保留动作建议、权限决定、执行结果、测试证据与终止原因。
- **安全服务暴露**：公网只开放必要的 Web/API 入口；公开 Demo 要限制调用次数、并发和执行规模。
- **真实演示**：主流程不可由固定假返回值伪装成成功。

---

## 6. 系统设计与数据契约

### 6.1 主要组件（逻辑）

1. **Web UI**：创建受控示例任务，查看执行时间线、diff、Evidence Report、权限拒绝与复测。
2. **FastAPI Backend**：API、任务管理、业务校验、运行时编排与日志；部署在 Vultr VM。
3. **Agent Runtime**：模型调用（Vultr Serverless Inference）、工具调度、最多轮次、失败分类。
4. **Permission Gate**：纯程序化决策；根据受信 TaskSpec 检查 `operation + resource + scope`。
5. **Sandbox Runner**：可信控制器启动受限临时环境，捕获实际进程输出；不能把容器管理权限交给 LLM。
6. **Independent Verifier**：检查已授权变更与不可被候选修改的测试/验收条件，独立执行或复验。
7. **Evidence Store**：保存任务记录、版本哈希、diff、测试结果、权限决定、报告（初版可 SQLite + 文件）。
8. **Adversarial Agent（P1）**：专门提出反例，输出结构化候选测试或质疑；不能改动验收标准或自行提升权限。

### 6.2 三个关键契约（草案）

```json
{
  "TaskSpec": {
    "task_id": "uuid",
    "sample_id": "billing-rounding-01",
    "user_goal": "Fix incorrect currency rounding",
    "allowed_write_paths": ["src/billing.py"],
    "protected_paths": ["tests/", "acceptance/"],
    "network_allowed": false,
    "max_attempts": 2,
    "timeout_seconds": 10,
    "acceptance_id": "billing-v1"
  }
}
```

```json
{
  "ExecutionResult": {
    "task_id": "uuid",
    "attempt": 1,
    "sandbox_id": "ephemeral-id",
    "artifact_hash": "sha256:...",
    "exit_code": 1,
    "timed_out": false,
    "stdout_ref": "...",
    "stderr_ref": "...",
    "resource_limits_applied": true,
    "cleanup_confirmed": true
  }
}
```

```json
{
  "VerificationReport": {
    "task_id": "uuid",
    "artifact_hash": "sha256:...",
    "status": "FAILED",
    "policy_decisions": [],
    "acceptance_checks": [],
    "counterexamples": [],
    "evidence_refs": [],
    "limitations": ["Only declared acceptance conditions were checked"]
  }
}
```

这三个对象是**接口提案**，字段会在落地时精简和校验。不可把 `allowed_write_paths`、`protected_paths` 等信任策略交给模型任意修改。

### 6.3 计划采用的技术（选择建议，不是全部已安装）

| 部分 | 候选 | 说明 |
|---|---|---|
| 本地环境 | Windows PowerShell + Python venv + Docker Desktop/WSL2（待检查） | 首先盘点，不臆断已安装 |
| API | Python、FastAPI、Pydantic | 与既有学习经验一致 |
| Runtime | 轻量显式状态机 / Tool Dispatcher | MVP 先保证可解释、可测；不必先引入重型框架 |
| Model | Vultr Serverless Inference | C1 要求，模型 ID 依当前官方列表确定 |
| Sandbox | Linux Docker 容器，或隔离更强的运行时 | 初版 Docker + 审核样例；不宣称安全等级超出实际配置 |
| 验证 | pytest + 独立验收脚本 | 测试素材与代理候选代码隔离 |
| UI | Vue 3（可先简单页面） | 不让视觉工作阻挡纵向闭环 |
| 存储 | SQLite + 任务产物文件 | 小规模 Demo 足够 |
| 部署 | Vultr VM 上的后端与 Web | 需要核对 VM 的网络、计费和容器能力 |

### 6.4 目录结构建议

```text
trustbound/
  README.md
  .gitignore
  .env.example
  pyproject.toml
  backend/
    app/
      main.py
      api/
      domain/           # TaskSpec, ExecutionResult, VerificationReport
      runtime/          # orchestration and state transitions
      security/         # authorization and policy checks
      sandbox/          # trusted runner controller
      verification/     # independent acceptance
      storage/
    tests/
  frontend/             # later: Vue UI
  fixtures/
    billing_rounding/   # curated buggy sample (safe, fixed dependencies)
  acceptance/            # independently managed, protected checks
  scripts/
  docs/
    ARCHITECTURE.md
    SECURITY_BOUNDARIES.md
    EXPERIMENTS.md
    SUBMISSION_CHECKLIST.md
```

**目录结构不强制**；可由 Codex 按最小变更原则调整。不要为了目录完整性制造空模块和过多样板文件。

---

## 7. 沙盒、安全和故障理论（开工前应掌握）

### 7.1 Sandbox

**定义**：为不可信或潜在危险的程序提供受限执行空间，减少其影响范围。要控制进程、文件系统、网络、CPU、内存、执行时长和生命周期。

**必须理解**：
- 容器通常共享宿主机内核；Docker 不等于绝对安全，也不等于强隔离虚拟机。
- Namespace 主要控制进程可见的资源，Cgroup 主要约束资源用量。
- 不能把 Docker Socket、宿主机目录、密钥、云凭据或过大权限交给模型生成代码。
- 可信 Runner 与不可信执行载荷是不同安全域；必须检查 Runner 自身权限。
- `--network none`、non-root、`--cap-drop ALL`、`--security-opt no-new-privileges`、只读根文件系统、只读挂载、临时文件系统、内存/CPU/PID 上限、外部超时清理都值得评估，但要**实测生效**。
- 若未来开放任意公众代码上传，需重新评估隔离级别：可能需要微虚拟机、gVisor、专用实例、严格配额等。

**本赛事实用边界**：先用预审核样例与受控恶意测试，公开演示入口采用限制访问和配额；不开放通用远程代码执行 API。

### 7.2 Authentication vs Authorization vs Policy Enforcement

- **Authentication**：确认身份。
- **Authorization**：判断该身份/任务是否有权进行特定操作。
- **Least Privilege**：仅授予当前任务和阶段的最低必需权限。
- **Policy Decision / Enforcement**：规则决定能否执行，实际执行点在受信代码/沙盒配置中生效；模型说明或理由不能自动扩权。
- **Trust Boundary**：不同信任等级的数据不能互相冒充指令。用户要求、检索文档、项目 README、执行日志、Agent 推测要分别标记来源。

### 7.3 Agent Runtime 与状态机

必须理解 `State`、`Tool Call`、`Dispatcher`、`Execution Result`、`Timeout`、`Retry Budget`、`Cleanup`、`Stop Condition`。

建议状态（后续可以简化）：

```text
CREATED → PLANNED → POLICY_CHECKED → RUNNING → VERIFYING
                        │              │          ├─ VERIFIED
                        └─ REJECTED     ├─ FAILED
                                       ├─ INCONCLUSIVE
                                       └─ RECOVERING → POLICY_CHECKED (bounded)
```

不变量：
- 不能在 `VERIFYING` 尚未通过时转为 `VERIFIED`。
- 任何权限拒绝不得被模型自行解释为可绕过。
- 达到预算或超时后不得无限重试。
- 每个执行轮次需要能定位对应的输入版本、执行环境、测试与输出。
- 执行中断/异常也需执行清理，清理失败要显式暴露。

### 7.4 Prompt Injection 与 RAG 上下文隔离

- 外部代码注释、README、错误日志和检索结果均是**数据**，不是新系统指令。
- 上下文隔离可减少交叉污染，但不能防止经过结构化输出继续携带恶意文本。
- 向量相似度不能保证检索到所有否定性约束、跨句引用与例外条件。
- 若实现 Semantic Context Routing，必须为不可省略的授权/验收约束使用结构化必传，并提供片段来源追踪；不能用相似度 Top-K 决定权限。

### 7.5 Verified / Validated 的界限

- 测试通过只能说明**当前验收范围内**通过，并不自动证明所有输入或真实业务场景都正确。
- 静态审查与 LLM 对代码的主观评价不能替代真实执行。
- 对抗 Agent 提出的性质需要确认符合原始需求；不允许凭空发明新需求使 Executor 无法过关。

---

## 8. 四组必做 Demo/验收实验

| 编号 | 场景 | 如何制造 | 必须看到的真实证据 | 预期状态 |
|---|---|---|---|---|
| E1 | 正常修复 | 小型 Python Bug | 代码 diff、退出码、测试通过 | `VERIFIED`（仅限定范围） |
| E2 | 假成功 | 公开测试通过但保留独立边界用例失败 | 验收脚本独立运行失败与具体用例 | `FAILED`，不得虚报成功 |
| E3 | 权限越界 | 尝试修改 `acceptance/` 或其他受保护路径 | 真实策略拒绝记录，无受保护文件变更 | `REJECTED` |
| E4 | 资源失控 | 受控无限循环或超时任务 | Runner 超时终止、容器销毁、API 健康正常 | `FAILED` / `TIMED_OUT`，不影响主服务 |

**额外实验（P1）**：对抗 Agent 提出反例 → 验证器复现 → Executor 有界修复 → 重新验收。建议选 1 个清晰的可复现案例，而非大规模 Benchmark。

**可能测量的指标**：False Success Rate、Verified Success Rate、Unauthorized Action Block Rate、Correct Stop Rate、Recovery Success Rate、平均尝试次数、端到端耗时、资源开销、证据对应关系完备度。

**实验对照（若有余力）**：Baseline A（基本 Agent + 最低安全隔离）、Baseline B（Agent + 常规测试）、TrustBound（独立验收 + 对抗验证）；在相同任务/模型/预算下比较。指标必须由实测生成；样本过小不能宣称具有行业普适性。

---

## 9. 11 月 3—8 日路线与退出条件

| 日期（北京时间） | 主任务 | 当天必须有的可见成果 | 失败时缩减策略 |
|---|---|---|---|
| **11/03** | 本地环境检查、仓库、受控 Python fixture、Sandbox Runner 最小实验、数据契约；Kickoff/额度 | 不依赖模型的隔离执行与真实日志 | UI/数据库/模型接入统统后移 |
| **11/04** | 接入 Vultr 推理 API、Executor 和最小 Runtime；验证单任务端到端 | 真实模型生成候选修改，在隔离环境执行 | 用简单确定性工作流替代复杂 Agent 框架 |
| **11/05** | 权限规则、独立验收、证据报告；E2/E3/E4 | 可拒绝假成功和越权，超时可控 | 延后评分 UI 和历史管理 |
| **11/06** | 独立 Adversarial Agent、有限恢复（P1） | 至少一个真实反例和修复/停止案例 | 仅保留对抗检验，恢复手动触发 |
| **11/07** | Vultr VM 云部署、Web UI、公开演示验证 | 实际公开访问，完整流转可用 | UI 极简，优先稳定和可访问 |
| **11/08** | 回归、Demo 录屏、README、幻灯片、正式提交 | 完整提交包和赛事确认信息 | 冻结功能，只修阻断性交付 Bug |

**交付闸门**：

1. **Gate A / Day 1**：真实 Sandbox 可运行/超时/清理；没有任何假日志。
2. **Gate B / Day 2**：Vultr LLM → 真实候选代码 → 执行结果闭环。
3. **Gate C / Day 3**：独立验收和权限拒绝可靠可重现。
4. **Gate D / Day 5**：Vultr 云端公开演示可访问。
5. **Gate E / Day 6**：真实提交完成，有视频、代码、架构说明。

若 Gate B/C 延迟，优先保障 E1—E4 和云部署，**不能牺牲必须的沙盒隔离来赶功能**。

---

## 10. 今天立即开始的工程任务（Day 1）

### 10.1 顺序

- [ ] 在本地确认 Python、Git、Docker（含 Windows Docker Desktop/WSL2）的实际状态；查看必要权限及可用磁盘空间。
- [ ] 若 `D:\Projects\TrustBound` 未存在，创建独立目录和本地 Git 仓库；**不要触碰 AimCoach/reforge/personal-os 仓库**。
- [ ] 添加 `README.md`、`.gitignore`、`.env.example`、一个最小 Python 示例、一个真实独立验收测试。
- [ ] 先实现 **不依赖 LLM** 的受限 Runner 骨架：可信侧调用固定的、经审核的代码样例 → 启动临时容器 → 捕获输出/退出码 → 超时终止 → 清理。
- [ ] 验证普通执行成功，以及一个受控超时场景。
- [ ] 用 Python 数据模型定义 `TaskSpec`、`ExecutionResult`、`VerificationReport`，先写模型校验测试。
- [ ] 将实际已完成的命令、日志、测试结果写进 `docs/EXPERIMENTS.md`，标出不确定性和下一步。
- [ ] 在赛事开始后关注 Discord/Kickoff，按官方说明领取 $200 额度；不未经确认地创建可能收费的云资源。

### 10.2 今天的完成标准

1. 本地仓库真实存在，可用 `git status` 检查状态。
2. 有一个安全、固定、可复现的 Python 示例。
3. 受限执行路径产出真实结果与退出码。
4. 超时后环境能够被清理，主程序仍可工作。
5. 安全边界被文档描述，尚未实现的保护明确记为 TODO，不用“沙盒已完全安全”这类说法。

### 10.3 给 Codex 的首轮可复制提示词

> **以下提示词用于今天第一阶段。不要一次性让 Codex 开发完整产品。**

```text
你现在协助我从零启动 2026 Vultr Agent Rush Hackathon 的独立参赛项目 TrustBound。

项目目标：Challenge 1 / Pattern A。建立可信 Agent 代码执行的最小可验证骨架。今天只做本地基础设施与隔离执行实验，不实现完整 Agent、多 Agent、RAG、复杂前端或公网部署。

工作范围：仅限 D:\Projects\TrustBound。若目录已存在，先检查并报告，不要覆盖或删除任何已有内容。不要修改 D:\Projects\AimCoach、D:\Projects\reforge、D:\Projects\personal-os。禁止 git push、git reset --hard、擅自创建付费云资源、公开服务或将密钥提交到仓库。

第一步先只做环境审计并向我报告：
1) Windows / PowerShell、Python、venv、Git 的版本和路径。
2) Docker CLI/Engine、Docker Desktop、WSL2 是否可用；若不可用，列出最小安装或修复方案，不擅自安装。
3) 当前目标磁盘剩余空间是否足够；不执行全盘扫描或系统清理。
4) 是否存在同名项目目录或已有 Git 仓库。

审计结束后，若环境可用，再按最小变更原则实现：
- 清楚的 README、.gitignore、.env.example 和最小项目结构；
- 一个确定性小型 Python Bug/测试 fixture；
- 不调用大模型的 Sandbox Runner 最小执行链路，严格使用固定、已审核的任务样例；
- 记录真实 stdout/stderr、exit code、timeout、清理结果；
- 一个普通执行场景和一个受控超时场景，证明限制机制实际生效；
- 最小 TaskSpec / ExecutionResult / VerificationReport 数据契约及基本测试。

安全边界：执行不能发生在 FastAPI 主进程；不把凭据或宿主机敏感目录挂给沙盒；不向不可信载荷暴露容器管理接口；不开放公网上传任意代码；不要将 Docker 容器宣称为绝对安全。

工程输出规范：
- 改动前先说明原问题、具体修改对象/范围及预期效果；
- 必要的函数和关键变量写可读、上下文连贯的英文注释；
- 每轮结束提供文件清单、真实运行命令、测试结果、已验证/未验证事项、下一步；
- 不为凑架构创建无用模块，不自动生成大规模文档；
- 如需安装依赖、改系统配置、开云资源或进行明显有风险的操作，先明确提示。

先执行“环境审计”并报告。在我明确确认环境方案后，再进入骨架和 Runner 实现。
```

### 10.4 对应的手动环境检查命令（PowerShell）

```powershell
python --version
py --version
git --version
docker --version
docker info
wsl --status
Test-Path 'D:\Projects\TrustBound'
Get-PSDrive -Name D
```

> 如果 `docker info` 报错或 `wsl --status` 不可用，先记录输出，**不要**直接尝试不理解的系统修改或清理。若 D 盘并非实际工作目录，则需调整项目位置。

---

## 11. 项目管理约定

- **主目标优先**：安全执行最小闭环 > 独立验证 > 对抗反例 > 自动恢复 > RAG 路由 > 评分体系扩展。
- **学习与编码并行**：Codex 可负责实现，但每个阶段需要能讲清文件职责、控制流、数据流、边界条件、失败案例和测试结果；不接受只会展示但无法解释的“黑盒项目”。
- **验证先于宣传**：只有真实跑出的结果才写进 Demo、README、简历。未测数字不要声称已提升成功率或减少成本。
- **安全优先**：不要对真实生产系统、第三方网站或用户数据做危险测试；仅用受控样例。
- **提交前**：检查密钥、许可、公开文件内容、URL 可访问性和云资源费用。
- **范围冻结**：新增功能必须说明它影响哪个官方硬性要求或哪个最核心演示用例；否则后置。

## 12. 待确认事项（不阻挡 Day 1 审计）

- [ ] Docker Desktop / WSL2 在本机的安装和可用状态。
- [ ] `D:\Projects\TrustBound` 是否已有文件或仓库。
- [ ] `D:` 磁盘可用容量；容器镜像可能需要一定空间。
- [ ] Vultr 账号及 200 美元 credit 的领取状态与实际消费限制。
- [ ] Vultr Serverless Inference 具体可用模型 ID、额度、认证方式、网络连通性。
- [ ] 赛事实时公告是否更改提交要求或具体日程。
- [ ] 公开 Demo 是否采用受限试用/预设任务；需有防滥用限制。
- [ ] 团队 Dashboard 中提交按钮什么时候可用。

## 13. 官方法规与技术资料

### 赛事及交付

1. [lablab.ai — Vultr: Agent Rush Hackathon](https://lablab.ai/ai-hackathons/vultr-hackathon)（赛道、技术、额度、提交、评审）
2. [lablab.ai — Live Dashboard](https://lablab.ai/ai-hackathons/vultr-hackathon/live)（时间与赛事进度）
3. [Vultr Community — Agent Rush Hackathon](https://community.vultr.com/e/vultr-agent-rush-hackathon)（Challenge 1 执行模式、隔离、安全要求、会议议程）
4. [lablab.ai — Getting Started](https://lablab.ai/getting-started-guide)（报名、团队、Discord、提交入口）
5. [lablab.ai — Submission Guidelines](https://lablab.ai/delivering-your-hackathon-solution)（视频、PPT、公开仓库、描述字段；以活动表单为准）
6. [lablab.ai — Hackathon Rule Book](https://lablab.ai/hackathon-rules)（通用规则与格式）

### 参考理论与工程文档

7. [Knight & Leveson (1986), An Experimental Evaluation of the Assumption of Independence in Multi-Version Programming](https://doi.org/10.1109/TSE.1986.6312924)
8. [Docker Engine: Resource Constraints](https://docs.docker.com/engine/containers/resource_constraints/)
9. [Docker Engine: Rootless Mode](https://docs.docker.com/engine/security/rootless/)
10. [OWASP — LLM Top 10](https://genai.owasp.org/llm-top-10/)
11. [Vultr Serverless Inference](https://docs.vultr.com/products/inference)

> **引用层级说明**：官方规则优先于本文；技术文档用于解释如何实现，不能替代安全审计；历史研究只支持其原研究范围，不能直接推导本次多 Agent 的实测可靠性。

---

**当前执行口令（给下一位参与者 / Codex）**：**从第 10 节 Day 1 环境审计开始，不要从多 Agent 功能开始开发。**
