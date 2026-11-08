# TrustBound — Agent Workspace 产品演进说明

> 版本：Workspace 愿景与架构审计 · 2026-11-06  
> 性质：产品决策与待确认的实施方案。本文独立于项目总档案。  
> 稳定基线：`a4371cc`。Stage 5B/5C、A1–A5 和 Billing Live 的状态依据此前 VM 验收记录。

## 1. 产品目标

TrustBound 是**面向开发者的 AI Agent 安全开发与独立验证平台**。用户导入小型 Python 项目，描述目标，与 Agent 确认修改和验收计划，在受控沙箱中执行并独立验证，最后决定是否接受或导出结果。

核心主张不变：**An agent that can act, but cannot certify its own success.** Agent 可以提案和修改，但不能自行放宽权限或宣称验收成功。

- **Secure Sandbox** 提供受限代码执行、权限隔离、资源控制及可复查的清理证据。
- **Adversarial Verification** 由 Executor 生成方案，Adversarial 独立寻找反例，可信 Verifier 根据证据裁决。Billing 已实现此链路，导入项目在具备可信业务参照后再接入。
- **Semantic Context Reconstruction** 是未来可插拔的语义上下文重组模块，本次比赛不实施。后续可比较启用前后的覆盖、约束保留、延迟与成本。

`VERIFIED` 仅代表本次声明的验收范围通过。通过真实用户反馈、回归测试与评测体系持续迭代覆盖。

## 2. 前端改造原则

在现有 Vue 应用中用统一导航组织五个区域。

- **Home** 为默认入口，简述用户痛点与产品主张，展示用户 → Agent → 权限控制 → 独立 Runner → Sandbox → Verifier → Evidence 的路径。说明 Vultr VM、Serverless Inference 和 Rootless Docker 的职责，提供明显的 Demo 与 Workspace 入口。视频区在素材准备好后嵌入或链接，页面只使用有证据的素材和统计。
- **Demo Replay** 保留 Billing 历史回放、现有执行、对抗和证据展示。仅调整导航、共享样式和明确的可读性问题。
- **Agent Workspace** 接续现有 Local API 与 Custom Task 区域。复用代码浏览、Diff、时间线和 Evidence Report。用户可导入、描述目标、澄清、修改或确认计划，执行后可审查、接受、拒绝或导出。Commit & Push 在单独授权和安全验收完成后才提供。
- **Documentation** 是面向评委与开发者的公开手册。以可核实的 README、架构、实验和部署记录编写 Markdown，提供目录、代码块和架构说明。内容覆盖背景、各 Agent、权限与执行链、工程取舍、开发历程、失败与修复、三套 Demo 操作、安全限制与路线。区分已验证、规划和研究，渲染禁用任意 HTML/脚本，发布前检查内容及证据中是否包含敏感数据。
- **Settings** 先做有实际效果的主题、密度、代码显示和默认视图等本地偏好，并持久化。执行模式和预算由服务端提供，只开放服务端允许的参数。评委沿用已有受控入口。具备可信后端角色鉴权后才提供管理员写入操作。密钥、系统命令和 Docker 控制权限留在部署端。

视觉统一为现代开发工具风格。Home 用主副标题、两个入口、真实架构流程、核心能力卡、Billing 演示入口和部署摘要建立信息层级。Workspace 使用项目启动区、样例入口、左侧文件列表、中间源码与逐文件 Diff、右侧计划与 Agent Activity，下方展示验证和导出。Documentation 提供双语长文、目录、代码块、引用和表格。Settings 采用分类侧栏和内容区。

界面支持 English 与简体中文，首次打开默认英文。语言和 Light / Dark 主题在 Settings 切换并持久化，覆盖导航、页面、主要操作反馈及状态标签。技术标识、原始日志及证据保留原文。浅色主题独立设计代码、Diff 和状态色。桌面优先，较窄屏幕折叠布局，轻量动效尊重 reduced motion。

- **Demo Play**：保留现有 Billing 演示及已验证链路，不做破坏性改动。
- **Local API → Agent Workspace**：把原有展示区域改造成可交互工作区，尽量复用现有任务、代码、Diff、时间线与证据组件；不另建大规模新页面。
- 在现有布局中完成：导入项目、查看文件、自然语言输入目标、Agent 提问/计划摘要、用户确认、运行状态、Diff/证据与最终操作。
- 明确标识：历史回放、离线候选、真实 Vultr LLM 调用、真实 Docker 执行，不能混为一谈。

## 3. 目标用户流程

1. **导入**：用户上传小型 Python 项目文件夹或 ZIP；检查文件类型、数量、总体积、解压路径和符号链接，拒绝危险输入。
2. **选择模型并描述目标**：实时模式仅展示部署允许、且在 Vultr 实际目录中支持文本生成的模型。用户用自然语言描述开发目标。查询目录不发起模型生成。
3. **澄清与规划**：Agent 提议修改范围、实现步骤、缺失需求、测试案例和可衡量的验收标准。当前私有预览由离线规则提示并标明来源。问题分类和测试策略属于 Agent 或可信控制层，用户无需先选择问题或攻击类型。
4. **用户决策与冻结**：界面简洁展示计划及验收范围；用户可修改、批准或拒绝。批准后冻结 TaskSpec、允许改动路径、验收材料及其哈希；Executor 无权修改这些可信条件。
5. **受控执行**：Executor 生成候选修改；Permission Gate 审核；独立 Runner 通过 Rootless Docker 在受限环境执行。
6. **独立验证**：显示公开测试、独立验收、必要的对抗反例、容器退出码与清理证据；不充分或不一致的证据标记为 `INCONCLUSIVE`。
7. **用户审查**：查看修改前后 Diff、测试及最终报告；可拒绝、接受或导出 Patch/ZIP。**Commit & Push** 是目标动作，但必须获得明确授权、使用最小范围凭据、默认新分支、禁止 force push；没有安全授权方案时不得提供虚假的成功按钮。

Agent Activity 按需求分析、规划、用户确认、执行、独立验收、对抗测试和最终报告组织，恢复只在真实触发时展示。仅呈现重要决策摘要和已记录证据，未执行的阶段明确标注。测试计数、观察耗时和资源限制状态可根据现有报告展示，不计算虚构可信度。底层测试和 A1–A5 安全攻击实验继续保留。

> LLM 建议的测试不能直接被视为独立可信证明。测试需由用户确认并冻结，实际执行必须在受限沙箱内；`VERIFIED` 仅表示通过已声明的验收范围。

## 4. 三套演示用 Python 小项目

每套均应有独立的 README、明确需求、原始 Bug、公开测试、受保护的独立验收和可重复的最终报告。尽量使用 Python 标准库与固定运行环境，不引入任意依赖安装。

| Demo | 真实问题 | 建议展示的 Bug/边界 | 验收重点 |
|---|---|---|---|
| **D1 Billing Rounding**（保留） | 金额换算和指定舍入规则 | 错误舍入、重复舍入、负数边界 | 公开测试、独立反例、受限恢复与证据 |
| **D2 Inventory Reconciliation**（新增） | 库存入库、出库和订单扣减 | 库存不足时错误扣减、重复 SKU、负库存或部分提交 | 原子性、边界条件、异常输入不改变原数据 |
| **D3 Application Log Summary**（新增） | 解析应用日志并按级别统计 | 把消息正文中的 `ERROR` 当作日志级别、格式异常、时间过滤边界 | 结构化解析、稳定输出、畸形输入处理 |

三套用于证明**同一 Workspace/Agent/Runner/Verifier 框架可以处理不同领域**，而不是为每个案例硬编码专用流程。每个案例都需要一组可现场复现的测试，至少一套非 Billing 用例完成真实 Vultr LLM 提案 → 沙箱执行 → 独立验收。

## 5. 安全与实现范围

- 保留已验收的 Web / Runner Unix Socket 权限分离、Rootless Docker、固定镜像、网络与资源限制、超时清理、密钥隔离、任务限流和持久化配额。
- 上传项目和用户代码属于**不可信输入**；不得在 FastAPI 或 Runner 宿主进程执行项目脚本，也不得让上传内容指定 Docker 管理参数、宿主路径或容器镜像。
- 引入自定义项目后必须重跑 **A1–A5、Billing 回归、权限边界、容器清理与 API 配额**。任何失败不得开放对应公网执行入口。
- 比赛版限制 Python、小型项目、固定执行模板和允许修改的文件范围；不做任意语言、自动安装依赖、完整 Cursor IDE 或无需确认的 Git 写入。
- 既有 `a4371cc` 作为可回滚基线；保持 Demo Play 可独立交付。

## 6. 现有架构复用审计

- **前端**。[`App.vue`](../frontend/src/App.vue) 中现有演示模式的界面名为 Demo Replay。保留其分支、历史数据和 Billing 操作。Workspace 使用现有版面和 [`api/client.js`](../frontend/src/api/client.js) 的同源请求方式，复用代码和证据组件。[`CodeWorkspace.vue`](../frontend/src/components/CodeWorkspace.vue) 和 [`state/workspace.js`](../frontend/src/state/workspace.js) 当前写死了 `billing.py`，新增项目状态与文件视图适配，保留现有 Billing 默认值。现有私有 [`CustomTaskPanel.vue`](../frontend/src/components/CustomTaskPanel.vue) 可参考用例输入交互。
- **任务规范、提案与权限**。[`contracts.py`](../trustbound/contracts.py) 的 `TaskSpec` 已表达允许写路径与超时，`ExecutionResult` 和 `VerificationReport` 已绑定候选、测试及执行状态。Workspace 补充项目快照和冻结规范哈希，保留原报告格式。[`service.py`](../trustbound/service.py) 的 `verify_patch` 及 [`executor.py`](../trustbound/executor.py) 的 `run_executor` 面向 Billing，`parse_proposal` 只收单文件替换。复用 [`inference.py`](../trustbound/inference.py) 的结构化推理、预算和用量记录，新增项目提案解析和逐路径权限检查。比赛版先支持现有白名单文件的替换，创建、删除和改名延后。
- **隔离执行**。[`runner_worker.py`](../trustbound/runner_worker.py) 的 `execute_request` 仅接受 Billing 和私有 Custom Task。[`runner.py`](../trustbound/runner.py) 的 `_execute_fixed_tests` 固定写入 `billing.py` 和 `checks.py`。可复用 Unix Socket 身份校验、固定 Docker 策略、限额检查和清理机制。导入项目需要新的版本化消息与固定执行模板，旧任务继续用原协议语义。[`runner_ipc.py`](../trustbound/runner_ipc.py) 请求上限 64 KiB，项目与用例序列化后的完整消息也必须在此上限内。
- **独立裁决、对抗与恢复**。[`custom_tasks.py`](../trustbound/custom_tasks.py) 的 `_check_cases` 已示范宿主根据结构化期望值比较观察结果。私有 Custom Task 只支持受限的单文件表达式、整数输入和手工候选，需求文本目前仅作记录。[`adversarial.py`](../trustbound/adversarial.py) 的金额参考实现及 [`recovery.py`](../trustbound/recovery.py) 的失败证据提取与候选路径依赖 Billing。先复用裁决规则与尝试预算，只有在项目具备独立可信的参考结果和可绑定候选的失败证据时，才接入对抗和恢复。缺失的阶段按实际状态标注，要求完成的验收证据缺失时给出 `INCONCLUSIVE`。
- **部署与准入**。[`api.py`](../trustbound/api.py) 已有并发控制、请求体上限和报告落盘，[`admission.py`](../trustbound/admission.py) 提供持久化限流与配额。项目归属、冻结版本和导入存储额度是新增能力。[`Caddyfile.stage5c`](../deploy/Caddyfile.stage5c) 保持现有公网 API 白名单。Workspace 单独启用，仅经私有 SSH 通道验收，公网应用层也拒绝 Workspace 接口。

## 7. 最小实现方案与信任边界

1. **导入与归属**。私有入口绑定明确的操作者身份与服务端生成的项目 ID，读取、规划、冻结、运行和导出均校验归属。首版建议仅收 UTF-8 `.py`、`.md`、`.txt`，最多 8 文件、单文件 4 KiB、展开总量 24 KiB，ZIP 上传及最终 IPC 分别设硬上限。流式检查实际展开量，拒绝绝对路径、盘符、父目录跳转、大小写冲突、重复路径、非普通文件、符号链接、加密或嵌套归档，以及 Git 元数据和常见密钥文件。解析后的内容作为受配额管理的快照存放在服务专用目录，由服务端决定物理路径。用户可预览将发给 Vultr 的文件范围，密钥文件筛查无法保证源码中没有内嵌凭据。
2. **规划与冻结**。项目内容作为不可信数据提供给 Planner。结构化计划包含待澄清问题、目标、允许修改路径、步骤、公开用例和受保护的验收条件。未解决的澄清阻止冻结。用项目归属、快照清单哈希、计划版本、需求、写入范围及验收条件生成不可变冻结记录。批准时校验版本，过期或并发编辑后的批准失效。冻结后编辑创建新版本并要求重新确认。规划确认、执行授权、结果接受和 Git 写入是独立动作。首轮用可注入的离线计划测试，无需付费调用。
3. **多文件执行与独立证据**。Web 通过 IPC 发送有界文件内容、阶段、输入数据与哈希。Runner 二次校验请求，在自己的临时目录物化项目，并以固定镜像、固定入口和同等 Docker 约束运行。候选只收到执行所需的输入，可信验收期望值和裁决逻辑留在宿主控制层。现有 Billing 测试与候选共用 Python 解释器，依赖窄 AST 策略，不能直接用它验证一般 Python 项目。Workspace 使用固定 JSON 调用约定，隔离公开和正式验收，用独立容器运行必要的隔离用例。只把候选的有界输出视为观察值，宿主严格匹配输入、类型和期望结果，验收同时要求容器状态、隔离及清理证据。导入测试脚本不进入首版正式验收，Executor 看不到受保护测试或答案。报告绑定按规范路径排序的多文件内容哈希、冻结规范哈希和本轮执行。新候选必须重新验证。
4. **结果导出与 Git**。Patch 和 ZIP 从接受的候选快照与原始快照生成，导出前重查归属、白名单与哈希。只输出规范路径和获准项目内容，排除凭据、运行证据及仓库元数据。Git 写入后置，必须针对目标远程、新分支和具体变更另行授权。Git 凭据与 Runner 隔离，不信任上传项目的 Git 配置或钩子。完成安全验证前隐藏 Commit & Push。

本机单人预览直接通过回环地址使用，无需输入访问令牌。导入的项目保存在仓库外的专用 SQLite 目录，以便恢复快照和审查历史证据。Runner 每次只把当前候选和单条输入放入临时目录，以只读方式挂载到一次性容器。VM 私有 Worker 继续使用 Unix Socket 与独立启用的 Workspace 请求类型，部署入口由现有权限策略控制。

## 8. 实施顺序与验收标准

1. **导入、规划、确认与冻结**。实现私有接口和数据契约，使用离线结构化规划测试。覆盖路径穿越、解压超限、重复或冲突路径、跨项目访问、未澄清不能冻结、过期审批、编辑后重新确认。导入和规划阶段无项目代码执行。
2. **真实受控执行与验收**。先用可复现候选跑通同一冻结版本的提案、权限检查、真实 Docker、宿主独立比对与证据。验证越权在进入 Docker 前拒绝，伪造通过日志、错误哈希、超时或清理失败均无法产生 `VERIFIED`。保留 Billing 与已有私有 Custom Task 回归。
3. **三套 Demo 与界面**。整合 Home、Demo Replay、Agent Workspace、Documentation、Settings。静态导航和证据资料可提前实现。交付三个项目的 README、公开和独立用例、预期结果及复现步骤。用同一执行链路验证不同领域，覆盖计划编辑、用户确认、Diff、证据、接受、拒绝与 Patch/ZIP 导出。界面区分历史回放、离线提案、真实模型调用和真实容器证据。
4. **本地、VM 与比赛交付**。本地执行后端、前端与构建回归。用户在 VM 通过 SSH 私有验收，重测 A1–A5、Rootless Docker 与 Web/Runner 隔离、超时清理、项目权限、证据绑定、公网认证、限流与持久化配额。另行批准预算后，至少一套非 Billing 项目完成真实 Vultr 提案、真实 Docker 和独立验收，保留 Run ID、哈希、用量与日志。交付 README、录屏、PPT 和提交材料，保留 `a4371cc` 回滚路径。

每阶段分别记录修改范围、复用与新增、实测结果、未验证事项及下一阶段目标。Workspace 延期或安全验收受阻时，比赛使用已验收的 Billing 公网 Demo 和 A1–A5 执行证据。

## 9. 后续方向（不阻塞本次提交）

- 安全可审计的 Git Commit & Push 完整集成；多文件重构、更多语言与依赖管理。
- 可插拔 Semantic Context Router：Direct/Router 可切换，硬性约束强制传递。
- Router 开关消融、组件回归、端到端延迟、Token 成本及验收表现对比。
- 持续完善攻击测试、沙箱隔离与可复查证据表达。

## 10. 本地预览与云端审核

私有 Workspace 默认关闭，公开部署配置拒绝其接口。Windows 预览使用本地 Docker Desktop，VM 继续要求隔离 Runner 和 Unix Socket。使用 PowerShell 7 构建并启动。

```powershell
npm --prefix frontend run build
.\scripts\start_workspace_preview.ps1
```

打开 `http://127.0.0.1:8000/#workspace` 即可导入项目。本机预览面向单人使用，服务仅监听回环地址。每次执行都使用独立的临时文件和容器，历史快照与报告继续保存在本机。

导入 Inventory 或 Log Summary，确认并冻结预置方案。先选择原始版本观察失败，再选离线候选并载入已审阅补丁。查看公开和独立用例、Diff、容器限制与清理证据。接受通过的变更后可导出。自定义项目可上传文件夹或 ZIP 并填入 JSON 用例，例如 `[{"input": 1, "expected": 2}]`。记下项目 ID 与运行 ID 可重新打开结果。

只有在决定执行真实 Vultr 实验时才更新根目录 `.env`。修改 `VULTR_INFERENCE_API_KEY`，确认 `VULTR_MODEL`，并显式设置 `TRUSTBOUND_ENABLE_WORKSPACE_LIVE=1`。如系统环境注入了同名 Key 或模型，系统值优先。停止预览后用 ` .\scripts\start_workspace_preview.ps1 -EnableLiveFromEnv` 重启。只有在页面确认发送范围并点击执行后才会发起生成。预览账本保留一笔最多 4096 输出 Token 的生成预算，重启不会恢复已消耗额度。Vultr Base URL 仍为后端固定地址。

云端验收由操作者执行。先保持公网配置关闭 Workspace，仅通过 SSH 隧道使用私有 API。在 Web 与 Runner 服务分别显式启用 `TRUSTBOUND_ENABLE_WORKSPACE=1`，Web 另设专用 `TRUSTBOUND_WORKSPACE_TOKEN`、`TRUSTBOUND_WORKSPACE_DB` 和持久化配额。工作区 SQLite 目录由 Web 账户独占且权限为 0700。Runner 只配置功能开关，模型凭据仍只存在 Web 后端。先验收 Workspace 离线、Billing、A1–A5 和两个服务的权限隔离，再由操作者单独授权真实模型实验。公网 Caddy 白名单保持原范围。

模型选择默认仅开放后端配置的 `VULTR_MODEL`。私有部署可用进程环境变量 `TRUSTBOUND_WORKSPACE_MODELS` 提供额外允许的模型 ID，以逗号分隔。模型还必须出现在 Vultr 文本模型目录中，执行时再次核对。

## 11. 聊天、计划书与回退

- Workspace 右栏用于对话和权限申请。自由文本进入计划书编辑，`/files` 经同意读取已导入的文件列表，`/run` 使用已冻结计划并请求沙箱执行权限。Workspace 设置可选默认候选，或拒绝执行。当前对话使用本地规则，真实 Vultr 提案仍只在明确授权的执行模式中使用。
- 计划书在同页弹窗中审核与编辑，根目录文件名为 `TRUSTBOUND_PLAN.json`。冻结后可单独下载，接受后的 ZIP 包含根目录计划书。重新导入时自动预填草稿，任何导入文件都不能作为既有审批证明。浏览器保留原目录，由用户选择下载文件的位置。
- 可在计划书中冻结独立挑战用例。可信宿主比较实际 Docker 输出，挑战失败会影响最终结果。挑战期望值和计划文件不进入候选沙箱或模型提案上下文。当前挑战由操作者提供，Billing 保留模型独立提议及有界自动恢复。
- 对同一计划下已经接受的候选，可在聊天中申请回退。批准后从已保存候选重跑公开、独立和已冻结的挑战检查，生成新报告并引用原运行 ID。用户可以继续检查旧报告。

## 12. Task Triage 与 Planning Gate

Workspace 先由宿主分流，再请求独立的执行授权。**DIRECT** 适用于目标明确、单文件且已有公开与独立用例的低风险任务。聊天卡片展示目标、范围和具体用例，快速确认后可申请执行。**CLARIFY** 对少量缺失条件提问，仅展示所需字段，补齐后重新分流。**PLAN_REQUIRED** 对多文件、高影响、破坏性、多个关联目标、缺项较多或主动要求规划的任务打开计划审核。正式计划包含目标、范围、实施步骤、验收、约束、待答问题及风险，可编辑、重新生成、批准或取消。

确定性规则先锁定高影响及多文件任务，模型无法降级。仅完整但语义难以判定的任务可在用户单独授权后调用 Vultr。请求只包含目标、入口、预估范围和项目路径，最多一次生成、1024 输出 Tokens，复用部署配额。结构异常、超时、无权限或服务不可用时保留正式审核。模型提出的验收建议不能变成已批准的预期值。

快速确认与正式批准生成带版本的 Approved TaskSpec，绑定项目 ID、重新校验的源码快照 Hash、目标、写入范围、用例及宿主执行预算。旧版本审批无法确认新草案，快照内容不符时禁止提交。Planning Gate 仅授予任务进入执行审批的资格。Permission Gate、现有 Runner、沙箱资源限制和独立 Verifier 仍独立生效。

私有 SQLite 记录分流、修订和批准事件。具备实测样本后可评估计划误触发率、复杂任务漏触发率、澄清补全效果、额外 Token、延迟及计划修改与接受情况。没有评测样本时仅记录事实，不展示推测指标。

## 13. 执行体验与 Agent 协作展示

Demo Replay 从历史报告读取证据。原有五个案例继续可回放，新增的对抗与恢复卡片取自已经保存的 E2 和 R1 真实 Docker 实验。Billing 的 Offline / Fixture 运行固定候选，离线 Executor 预设则注入模拟模型响应。两者的 Docker 和 Verifier 都实际运行。Workspace 的 Offline / Fixture 使用已审阅样例、人工提交的候选或原始快照，无推理请求。Live Agent 使用 Vultr 生成候选，并经过同一 Permission Gate、Docker 与 Verifier。

开发预设放在 Vite 开发模式或本机私有预览的 `?developer=1` 中。Activity 按 Executor、Adversarial、Recovery、Verifier 等角色展示报告和真实执行摘要。Workspace 冻结的用户挑战会明确标注来源。Activity 不共享 Agent 上下文，结构化证据可以单独展开。

Retry Fix 使用现有次数上限，针对同一冻结计划的一条已确认公开或挑战失败生成新候选，每轮仍需授权并重跑验收。独立验收用例留在宿主。同一失败最多派生一次重试，整条链最多两次并受全局配额约束。Discard 将未接受候选标为拒绝，代码区显示原始快照，报告继续保留。

本机默认关闭真实恢复。需单独审核时，可在根目录 `.env` 启用 Workspace Live 和 `TRUSTBOUND_ENABLE_RECOVERY_LIVE=1`，并用 `.\scripts\start_workspace_preview.ps1 -EnableLiveFromEnv -EnableRetryFromEnv` 启动。预览账本的共享调用额度仍生效。

## 14. 统一工作台与 Agent 对话

Billing Demo Replay 是工作台视觉基准。Workspace 沿用它的网格、文件树、代码对比、快照标识和 Evidence Report 框架。Demo 文件树展示 Billing 候选对应的源码与已公开测试。恢复回放可切换已完成验证的候选版本。回放证据保持只读，私有 Workspace 可从当前候选创建独立项目副本并编辑本地草稿。

Workspace 右栏合并需求对话、模型选择、任务确认和真实执行记录。报告按角色呈现规划、执行、对抗、独立验收及恢复事件。角色共享展示区域，各自的模型上下文与宿主安全策略独立。代码草稿只有在授权后才交由现有 Runner 验收。
