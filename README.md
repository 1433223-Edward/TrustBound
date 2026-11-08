# TrustBound

**AI-assisted Code Modification with Human Approval, Isolated Execution, and Security Evidence.**
**面向人工审批、隔离执行与安全证据的 AI 辅助代码修改。**

Built for Vultr: Agent Rush Hackathon 2026 — Challenge 1: Blast Radius Zero.

[Public Demo](https://66-42-37-36.sslip.io/) · [Documentation](docs/README.md) · [Deployment guide](docs/TrustBound_Deployment_Operations_Guide_2026-11-08.md)

## English

### Project overview

TrustBound keeps four decisions separate: an AI may propose a change, a human approves its scope, a restricted executor runs it, and the system preserves evidence of what actually happened. A successful process is not silently treated as proof of business correctness.

Core flow: **Natural Language Task → AI Planning → Human Approval → Executor Agent → Rootless Docker Sandbox → Security Evidence**.

### Core features

- Agent Chat and AI-assisted project planning through the private Workspace.
- Human review and frozen approval of write scope, entrypoint, constraints, and execution intent.
- Executor proposals passed through a server-side permission gate.
- Isolated, bounded execution by a separate Rootless Docker Runner.
- Diff, run history, hashes, sandbox/cleanup evidence, and quota-aware model-request records.
- Vultr Serverless Inference integration only from the trusted private backend.

### Architecture and capability boundary

```text
Public reviewer → HTTPS/Caddy → static UI + allowlisted offline Billing API
Private operator → SSH tunnel → token-protected Workspace → Vultr LLM / approval gate
                                             ↓
                                  Unix socket → Rootless Docker Runner → evidence
```

The public demo at [66-42-37-36.sslip.io](https://66-42-37-36.sslip.io/) is a restricted Billing **offline** demo. Depending on the active Caddy profile, it can proxy only allowlisted offline Billing routes behind Basic Auth; it never exposes the Agent Workspace or real Vultr LLM calls.

The private Live Workspace listens only on VM loopback `127.0.0.1:8002` and is reached through an SSH tunnel. It uses a Workspace Token and explicit quota/authorization controls. Its configuration supports real Vultr calls, but this repository does **not** contain terminal evidence of a successful production LLM request; configuration readiness is not a successful-call acceptance result.

Functional Verification is **off by default** for new Workspace browser preferences. The retained functional path can produce `VERIFIED` only against approved, trusted acceptance criteria. The default security-only path can produce `EXECUTED_UNVERIFIED`; that means the bounded run and its security evidence were intact, not that the change is business-correct. Adversarial and Recovery agents are retained historical/offline or experimental capabilities, not default Live Workspace features.

### Tech stack

Python 3.12, FastAPI/Uvicorn, Vue 3/Vite, SQLite, Caddy, systemd, Vultr Cloud Compute, Vultr Serverless Inference, and Rootless Docker.

### Local development

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-test.txt
.\.venv\Scripts\python.exe -B -m uvicorn trustbound.api:app --host 127.0.0.1 --port 8000 --workers 1

cd frontend
npm ci
npm run dev
```

Run `npm run build`, the relevant Python tests, and Docker checks only where Docker Desktop is available. Do not expose local FastAPI, Vite, or Docker endpoints publicly. See [local Workspace flow](docs/WORKSPACE_LOCAL_FLOW.md).

### Deployment and configuration

The public service loads `/etc/trustbound/backend.env`; the private service loads that file first and then `/etc/trustbound/workspace-live.env`. The documented private paths are `/var/lib/trustbound/workspace-live/workspace.sqlite3`, `/var/lib/trustbound/workspace-live/quota.sqlite3`, and `/run/trustbound-runner.sock`.

Use placeholders only for `VULTR_INFERENCE_API_KEY` and `TRUSTBOUND_WORKSPACE_TOKEN`. Required variables, systemd commands, release/rollback, backup, snapshot, and recovery procedures are in the [deployment operations guide](docs/TrustBound_Deployment_Operations_Guide_2026-11-08.md). A stopped Vultr VM can still incur resource charges; snapshots may also be billed.

### Testing and limitations

Historical offline and Docker evidence is preserved in `docs/` and `benchmarks/`; it is not a claim about the current production deployment. The system is designed for bounded Python projects, not arbitrary public code execution or a multi-tenant code-hosting platform. Container isolation and recorded evidence are defense-in-depth controls, not a proof against every host or container failure.

## 简体中文

### 项目介绍

TrustBound 将四件事明确分开：AI 只提出修改建议；人类审批修改范围；受限执行器运行；系统保存实际发生过程的证据。一次成功运行不会被自动解释为业务需求已经满足。

核心流程：**自然语言任务 → AI 规划 → 人工审批 → Executor Agent → Rootless Docker 沙箱 → 安全证据**。

### 核心功能

- 私有 Workspace 中的 Agent Chat 与 AI 辅助项目规划。
- 人工审核并冻结可写路径、入口、约束和执行意图。
- Executor 提案先经过服务端权限门禁。
- 独立 Rootless Docker Runner 执行有界隔离任务。
- 保存 Diff、运行历史、哈希、沙箱/清理证据与模型请求配额记录。
- 仅由受信任的私有后端调用 Vultr Serverless Inference。

### 架构与能力边界

公网 [Demo](https://66-42-37-36.sslip.io/) 是受限的 Billing **离线**演示。生效的 Caddy 配置可在 Basic Auth 后代理少量白名单 Billing 离线接口，但不开放 Agent Workspace，也不调用真实 Vultr LLM。

私有 Live Workspace 仅监听 VM 回环地址 `127.0.0.1:8002`，通过 SSH 隧道访问，使用 Workspace Token、明确授权和配额限制。环境配置可支持真实 Vultr 调用，但仓库中没有一次生产真实模型请求成功的终端验收证据；“配置就绪”不等于“调用已验收”。

新 Workspace 浏览器偏好默认关闭功能验证。保留的功能验证路径只有在已批准的可信验收标准下才会给出 `VERIFIED`。默认安全执行成功的状态是 `EXECUTED_UNVERIFIED`：它只说明有界执行及安全证据完整，不说明业务正确。Adversarial Agent 与 Recovery Agent 仅保留为历史/离线或实验能力，不属于默认 Live Workspace 功能。

### 本地开发、部署与文档

本地启动、离线流程和限制见 [本地 Workspace 流程](docs/WORKSPACE_LOCAL_FLOW.md)。公网环境文件为 `/etc/trustbound/backend.env`；私网服务先读取它，再读取 `/etc/trustbound/workspace-live.env`。密钥和 Token 只能使用占位符，不能写入仓库。

发布、健康检查、配额查询、systemd、回滚、备份与 Vultr 快照说明见 [部署与运维说明](docs/TrustBound_Deployment_Operations_Guide_2026-11-08.md)。停止 VM 不代表资源不再计费，快照也可能继续收费。

## Documentation

- [Current documentation index](docs/README.md)
- [Deployment and operations guide](docs/TrustBound_Deployment_Operations_Guide_2026-11-08.md)
- [Verification modes](docs/VERIFICATION_MODES.md)
- [Public API / historical contracts](docs/WEB_API_CONTRACT.md)
- [Historical experiments](docs/EXPERIMENTS.md)
