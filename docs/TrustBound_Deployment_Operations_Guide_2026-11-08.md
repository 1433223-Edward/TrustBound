# TrustBound 部署与运维说明书

> **Current operating reference, with time-bounded deployment observations.** 当前产品边界以根目录 [README](../README.md) 为准；本文记录的 VM 现场状态、服务时限和部署结果必须以实际命令输出复核，不能由本文文字替代验收。

> 记录日期：2026-11-08  
> 范围：Vultr VM 的公网 Billing 离线 Demo、临时 Custom Task 私网预览、私有 Live Agent Workspace  
> 仓库：`https://github.com/1433223-Edward/TrustBound`  
> 说明：本文记录本次对话中使用的命令与配置。VM 当前状态应以现场命令返回为准；**尚无对话内实际返回证明私有 Workspace 已成功完成一次真实 Vultr LLM 请求**。

## 1. 部署目标与架构

TrustBound 采用**公网受限展示 + 私网完整执行**的区分方式，二者不是同一个服务模式。

| 项目 | 公网 Billing Demo | 私网 Custom Task 预览 | 私网 Live Agent Workspace |
|---|---|---|---|
| 访问入口 | `https://66-42-37-36.sslip.io/` | Windows SSH 隧道到 VM `127.0.0.1:8001` | Windows SSH 隧道到 VM `127.0.0.1:8002` |
| 用途 | 评委查看页面及受限 Billing 离线流程 | Custom Task / 离线 Docker 检验 | AI 规划、真实模型调用、Agent 执行与独立验证 |
| 真实 Vultr LLM API | **不开放** | **不调用** | **按权限与预算调用** |
| VM 服务 | `trustbound-api.service`，监听 `127.0.0.1:8000` | `trustbound-custom-preview.service`，临时启动 | `trustbound-workspace-live.service`，独立启动 |
| 生命周期 | 常驻 systemd | `RuntimeMaxSec=15min`，`--collect` | `RuntimeMaxSec=60min`（本次配置） |
| 权限边界 | Caddy HTTPS、可选 Basic Auth、API 路由白名单 | SSH 本机回环访问 | SSH 本机回环访问 + Workspace Bearer Token |

**关于“公网没有连接 API”的准确含义：** 公网**不连接真实 Vultr LLM 推理 API**，也不开放完整 Workspace。若采用仓库中的 `deploy/Caddyfile.stage5c`，Caddy 仍会将**受限的 Billing 离线后端请求**反向代理到 VM `127.0.0.1:8000`；因此不能笼统称公网“没有任何后端 API”。如果运行的是静态阻断版 `deploy/Caddyfile`，其 API 行为又不同；应以 VM `/etc/caddy/Caddyfile` 实际内容为准。

逻辑连接：

```text
Internet browser
    └─ HTTPS https://66-42-37-36.sslip.io/
         └─ Caddy :443
              ├─ frontend/dist 静态页面
              └─ 允许的离线 Billing API → 127.0.0.1:8000（根据生效的 Caddy 配置）

Windows browser http://127.0.0.1:5173/
    └─ SSH -L 127.0.0.1:5173:127.0.0.1:8002
         └─ Vultr VM :8002 私有 Workspace FastAPI + Vue 静态资源
              ├─ Vultr LLM HTTPS API（服务端发起、消耗额度）
              ├─ /run/trustbound-runner.sock
              │    └─ trustbound-runner → Rootless Docker 隔离执行
              └─ 私有 Workspace DB / 配额账本 / 证据目录
```

## 2. 服务器与文件路径

| 配置或资源 | 实际路径 / 地址 | 说明 |
|---|---|---|
| VM | `66.42.37.36`，Ubuntu，SSH 用户 `linuxuser` | Vultr 主机；禁止直接公开 API 端口 |
| 公网域名 | `https://66-42-37-36.sslip.io/` | HTTPS + Caddy |
| 项目工作副本 | `/home/linuxuser/apps/TrustBound` | 操作员仓库，不等于正在运行的发布目录 |
| 当前发布指针 | `/srv/trustbound/pointers/current` | 服务启动时使用的代码及 `frontend/dist` |
| 已观察到的发布目录 | `/srv/trustbound/releases/0eb9f8a3ccb6492df54a2825a1a3d50e0474faed` | 本次服务失败日志出现过；以后以 `readlink -f` 为准 |
| 公网 Caddy 配置 | `/etc/caddy/Caddyfile` | 可对照仓库 `deploy/Caddyfile.stage5c` |
| 公网 API 环境 | `/etc/trustbound/backend.env` | 原有公网配置与凭据来源 |
| 公网配额数据库 | `/var/lib/trustbound/stage5c.sqlite3` | 不要删除或重置 |
| 私网 Live 覆盖环境 | `/etc/trustbound/workspace-live.env` | **新增的 Live Workspace 运行配置** |
| 私网 Live systemd unit | `/etc/systemd/system/trustbound-workspace-live.service` | 监听 `127.0.0.1:8002` |
| 私网 Live Workspace DB | `/var/lib/trustbound/workspace-live/workspace.sqlite3` | 项目、审批与运行数据 |
| 私网 Live 配额账本 | `/var/lib/trustbound/workspace-live/quota.sqlite3` | Run、模型调用和 Token 预算 |
| 私网报告目录 | `/var/lib/trustbound/workspace-live/reports/` | 运行报告（部分 Workspace 记录也保存在 Workspace DB） |
| Runner socket | `/run/trustbound-runner.sock` | 共享的私有 Runner IPC |
| 临时 Custom Task drop-in | `/run/systemd/system/trustbound-runner.service.d/95-custom-preview.conf` | 临时开关，录制结束后需单独清理 |
| Windows SSH 私钥 | `$env:USERPROFILE\.ssh\trustbound_vultr_ed25519` | 仅保存在操作者本机，不能上传或展示 |

**注意**：`backend.env` 与 `workspace-live.env` 都可能含有密钥。不要把其完整内容放入 README、Demo 视频、Git 提交或对话。

## 3. 本次部署过程记录

### 3.1 公网 Billing Demo 已通过 Caddy 部署

- 公网入口：`https://66-42-37-36.sslip.io/`。
- Caddy 在 VM 负责 HTTPS、前端静态资源和受限 API 路由。
- 公网 FastAPI 进程监听 `127.0.0.1:8000`，由 `trustbound-api.service` 启动，读取 `/etc/trustbound/backend.env`。
- 本次查看到的公网参数：`TRUSTBOUND_MAX_RUNS=40`、`TRUSTBOUND_MAX_MODEL_CALLS=0`、`TRUSTBOUND_MAX_OUTPUT_TOKENS=0`、`TRUSTBOUND_QUOTA_DB=/var/lib/trustbound/stage5c.sqlite3`。
- 这意味着当前查看的配置**不允许真实 LLM 模型调用**。可用的离线 Billing API 具体取决于实际 Caddy 配置。
- 公网实例不因私网验收而修改或重启。

核对命令：

```bash
sudo systemctl status caddy trustbound-api.service --no-pager
sudo caddy validate --config /etc/caddy/Caddyfile
sudo ss -lntp | grep -E ':8000|:8001|:8002'
curl -sS http://127.0.0.1:8000/api/health
```

若公网页面启用了 Basic Auth，未认证访问返回 `401` 属于预期行为，不代表 HTTPS 故障。

### 3.2 临时 Custom Task 私网预览（8001）

曾使用 Codex 提供的 `sudo bash -s <<'CUSTOM_PREVIEW'` 脚本，通过 `systemd-run --unit=trustbound-custom-preview --collect` 创建临时任务：

- 监听：VM `127.0.0.1:8001`；在 FastAPI 中挂载已构建的 `frontend/dist`。
- 开关：`TRUSTBOUND_PUBLIC_DEMO=0`、`TRUSTBOUND_ENABLE_CUSTOM_TASK=1`、`TRUSTBOUND_ENABLE_LIVE=0`、`TRUSTBOUND_ENABLE_RECOVERY_LIVE=0`。
- 显式移除 `VULTR_INFERENCE_API_KEY` 等凭据，因此**不会调用模型 API**。
- 临时向共享 Runner 注入 `TRUSTBOUND_ENABLE_CUSTOM_TASK=1`；需在无任务运行时重载 Runner。
- 生命周期限制为 15 分钟，服务退出后可因 `--collect` 而无法再通过 `systemctl status` 找到。

本次遇到：

1. Windows `5173` 曾被本地 Vite 开发进程占用，导致 SSH 报 `bind [127.0.0.1]:5173: Permission denied`。
2. 端口释放后 SSH 隧道建立，但 VM `8001` 未监听，浏览器出现 `channel ... Connection refused`。
3. 再次执行脚本时出现 `Custom preview already configured; stop here.`，原因是前一次的 Runner 临时 drop-in 尚在，而预览 unit 已结束。
4. 清理临时 drop-in、重载 Runner 并重新运行完整脚本后，用户确认 **Custom Task 预览已启动成功**。

此预览只能验收离线 Custom Task 的 `VERIFIED` / `FAILED`、Diff 与 Docker 证据，**不能当作真实 Live Agent Demo**。

### 3.3 创建私有 Live Agent Workspace（8002）

为了不改变公网 `8000` 与临时预览 `8001`，创建独立私有服务 `trustbound-workspace-live.service`，监听 `127.0.0.1:8002`。

主要步骤如下：

1. 创建 `trustbound-web` 拥有的私有数据目录（`0700`）：`/var/lib/trustbound/workspace-live/` 和 `reports/`。
2. 创建 `/etc/trustbound/workspace-live.env`（权限 `0600`），写入私网 Workspace 模式、Rootless Runner、独立 SQLite 数据文件及预算。
3. 通过 `openssl rand -hex 24` 生成 `TRUSTBOUND_WORKSPACE_TOKEN`。这是访问 Workspace 的 **Bearer Token**，**不是** Vultr API Key。
4. 让新服务依次读取 `/etc/trustbound/backend.env` 与 `/etc/trustbound/workspace-live.env`，**后者覆盖前者的同名变量**。
5. 创建 `/etc/systemd/system/trustbound-workspace-live.service`，以 `trustbound-web` 身份启动 FastAPI，在 `8002` 挂载 `frontend/dist`，保留 Docker Socket 隔离，运行时上限 60 分钟。
6. 初始化私有配额账本并启动服务。首次尝试在启动阶段报 `MODEL_JOURNAL_UNAVAILABLE`；随后发现目录中有 `workspace.sqlite3`，但**缺少 `quota.sqlite3`**。因此需要初始化账本，再重新启动。

本次配置的关键环境变量（只列非密钥值；最终以 VM 中的文件为准）：

```dotenv
TRUSTBOUND_LOAD_DOTENV=0
TRUSTBOUND_PUBLIC_DEMO=0
TRUSTBOUND_ENABLE_WORKSPACE=1
TRUSTBOUND_ENABLE_WORKSPACE_LIVE=1
TRUSTBOUND_ENABLE_LIVE=0
TRUSTBOUND_ENABLE_RECOVERY_LIVE=0
TRUSTBOUND_ENABLE_CUSTOM_TASK=0
TRUSTBOUND_RUNNER_SOCKET=/run/trustbound-runner.sock
TRUSTBOUND_WORKSPACE_DB=/var/lib/trustbound/workspace-live/workspace.sqlite3
TRUSTBOUND_QUOTA_DB=/var/lib/trustbound/workspace-live/quota.sqlite3
TRUSTBOUND_MAX_RUNS=8
TRUSTBOUND_MIN_RUN_SECONDS=0
TRUSTBOUND_MAX_MODEL_CALLS=8
TRUSTBOUND_MAX_OUTPUT_TOKENS=32768
# 以下值必须存在于实际服务环境中，不在文档明文记录：
# VULTR_INFERENCE_API_KEY=***
# VULTR_MODEL=<Vultr 模型 ID>
# TRUSTBOUND_WORKSPACE_TOKEN=***
```

> `TRUSTBOUND_ENABLE_WORKSPACE_LIVE=1` 是私有 Workspace 真实调用的关键开关。`TRUSTBOUND_ENABLE_LIVE=0` 控制的是独立 Billing Live 模式，不阻止 Workspace Live。真实模型调用还必须具备有效凭据、模型、配额和用户授权。

账本初始化命令：

```bash
cd /srv/trustbound/pointers/current
# 仅在目标文件确实不存在时执行，绝不能用删除旧账本来重置额度：
sudo -H -u trustbound-web -- ./.venv/bin/python -B -m trustbound.admission init \
  /var/lib/trustbound/workspace-live/quota.sqlite3
```

启动与诊断：

```bash
sudo systemctl daemon-reload
sudo systemctl start trustbound-workspace-live.service
sudo systemctl status trustbound-workspace-live.service --no-pager -l
curl -sS http://127.0.0.1:8002/api/health
sudo journalctl -u trustbound-workspace-live.service -n 40 --no-pager -l
```

期望 `health` 中：`public_demo=false`、`persistent_quota=true`、`workspace.enabled=true`、`workspace.execution="ROOTLESS_WORKER"`、`workspace.access="token"`、`workspace.live_enabled=true`。

**验收状态边界**：对话已记录私网 Live 服务的配置与第一次失败原因，也记录了账本初始化的修复步骤；但未提供最终 `8002/api/health`、Vultr 模型列表或一次真实 LLM 返回的终端证据。因此不能在文档中宣称 Live 推理已正式验收通过。

## 4. Windows 通过 SSH 使用私有 Workspace

本地浏览器使用 `127.0.0.1:5173`，但只有当该端口由 `ssh` 而非 `node/Vite` 监听时，页面才来自 VM。

PowerShell 启动隧道（前提：VM `8002` 正在运行，Windows `5173` 空闲）：

```powershell
ssh -4 -N `
  -i "$env:USERPROFILE\.ssh\trustbound_vultr_ed25519" `
  -o IdentitiesOnly=yes `
  -o ExitOnForwardFailure=yes `
  -o ConnectTimeout=10 `
  -L 127.0.0.1:5173:127.0.0.1:8002 `
  linuxuser@66.42.37.36
```

打开：`http://127.0.0.1:5173/#workspace`。该连接使用 SSH 加密转发；VM 并未对公网开放 `8002`。

令牌只保存在 VM 的 `/etc/trustbound/workspace-live.env`（root-owned, `0600`）。不要用命令回显、录屏或粘贴该值；客户端应从操作者批准的安全渠道取得它。

在 Windows 检查 `5173` 被谁占用：

```powershell
Get-NetTCPConnection -LocalPort 5173 -State Listen -ErrorAction SilentlyContinue |
  Select-Object LocalAddress, LocalPort, OwningProcess
# 再用 Get-CimInstance Win32_Process 查看 PID 和 CommandLine，确认是本地 Vite 后再关闭。
```

不要误以为“5173 页面可以打开”就已经连接 VM；**必须同时检查 SSH 进程和远端 `8002/api/health`**。

## 5. 停止服务与清理

录完视频后，在没有任务运行时停止私网 Live：

```bash
sudo systemctl stop trustbound-workspace-live.service
```

临时 Custom Task 预览如不再需要，在没有运行中的任务时清理共享 Runner 的临时开关：

```bash
sudo systemctl stop trustbound-custom-preview.service 2>/dev/null || true
sudo rm -f /run/systemd/system/trustbound-runner.service.d/95-custom-preview.conf
sudo systemctl daemon-reload
sudo systemctl stop trustbound-runner.service
sudo systemctl start trustbound-runner.socket
```

此清理针对临时 Custom Task 模式，不应停止公网 Caddy 或删除任何配额账本。`RuntimeMaxSec=60min` 可能自动停止私有 Live 服务，但**不会自动删除独立 env、数据库或 systemd unit**。

## 6. 当前发布、恢复与备份操作

本节是根据仓库 `deploy/` 脚本整理的操作说明，不是已经在 VM 上逐项执行成功的声明。操作前确认服务空闲、目标 SHA 已审阅，且现有发布与数据库没有被覆盖。

### 6.1 从提交构建并激活 Release

`prepare-release.sh` 只接受完整的 40 位 Git commit SHA。它从该提交导出不可变 Release、创建 `.venv`、安装 `requirements-web.txt`，并在 Release 内执行 `frontend/npm ci` 与 `npm run build`；它不携带本机 `.env`，也不会启用公网 API。`activate-static.sh` 原子切换 `/srv/trustbound/pointers/current`，但不会重启 Python 服务。

```bash
COMMIT=<reviewed-40-character-commit-sha>
sudo -u trustbound-deploy bash /srv/trustbound/source/deploy/prepare-release.sh \
  /srv/trustbound/source "$COMMIT"
sudo -u trustbound-deploy bash /srv/trustbound/source/deploy/activate-static.sh "$COMMIT"
readlink -f /srv/trustbound/pointers/current

# Only when no private task is active; the public service may be restarted separately.
sudo systemctl restart trustbound-api.service
sudo systemctl restart trustbound-workspace-live.service
```

Runner Socket、Public API、Private Workspace 和 Caddy 是独立服务：

```bash
sudo systemctl enable --now trustbound-runner.socket
sudo systemctl enable --now trustbound-api.service
sudo systemctl enable --now trustbound-workspace-live.service
sudo systemctl enable --now caddy.service
sudo systemctl status trustbound-runner.socket trustbound-api.service trustbound-workspace-live.service caddy.service --no-pager
curl -fsS http://127.0.0.1:8000/api/health
curl -fsS http://127.0.0.1:8002/api/health
```

`8002` health only demonstrates service/configuration state; it does not prove a successful provider inference or a completed user task. The public Caddy profile must still be checked against its active `/etc/caddy/Caddyfile`.

### 6.2 Environment files and safe operational checks

`trustbound-api.service` reads `/etc/trustbound/backend.env`. The private Workspace unit must read `/etc/trustbound/backend.env` first and `/etc/trustbound/workspace-live.env` second, so private values override public defaults. Both files are root-owned `0600`; never copy them into a Release or this repository.

The public offline profile uses `TRUSTBOUND_PUBLIC_DEMO=1`, disables model budgets (`TRUSTBOUND_MAX_MODEL_CALLS=0`, `TRUSTBOUND_MAX_OUTPUT_TOKENS=0`), and uses its own `TRUSTBOUND_QUOTA_DB`. The private profile requires `TRUSTBOUND_PUBLIC_DEMO=0`, `TRUSTBOUND_ENABLE_WORKSPACE=1`, `TRUSTBOUND_ENABLE_WORKSPACE_LIVE=1`, `TRUSTBOUND_WORKSPACE_TOKEN=<workspace-token>`, `TRUSTBOUND_WORKSPACE_DB=<workspace-db>`, `TRUSTBOUND_QUOTA_DB=<quota-db>`, `TRUSTBOUND_MAX_RUNS=<approved-limit>`, `TRUSTBOUND_MAX_MODEL_CALLS=<approved-limit>`, `TRUSTBOUND_MAX_OUTPUT_TOKENS=<approved-limit>`, `TRUSTBOUND_RUNNER_SOCKET=/run/trustbound-runner.sock`, `VULTR_INFERENCE_API_KEY=<secret>`, and `VULTR_MODEL=<approved-model-id>`.

Do not print secrets while diagnosing. Inspect unit configuration and recent redacted logs instead:

```bash
sudo systemctl cat trustbound-api.service trustbound-workspace-live.service
sudo journalctl -u trustbound-api.service -u trustbound-workspace-live.service -u trustbound-runner.service -n 100 --no-pager -l
sudo -u trustbound-web sqlite3 /var/lib/trustbound/workspace-live/quota.sqlite3 \
  'SELECT runs, calls, tokens, last_run FROM budget WHERE id = 1;'
```

The quota query assumes the host has the `sqlite3` CLI. If it does not, install it through the approved OS package process or use an approved read-only SQLite viewer; do not reset or replace the ledger just to inspect it.

### 6.3 Rollback and recovery

Do not roll back with a task in flight. `rollback-static.sh` only switches the static pointer to the previously prepared immutable Release. After checking the pointer, restart the private API only while idle and re-run local loopback health checks.

```bash
sudo systemctl stop trustbound-workspace-live.service
sudo -u trustbound-deploy bash /srv/trustbound/source/deploy/rollback-static.sh
readlink -f /srv/trustbound/pointers/current
sudo systemctl start trustbound-workspace-live.service
curl -fsS http://127.0.0.1:8002/api/health
```

This does not migrate or roll back SQLite data, reset quotas, rotate secrets, or change Caddy. Recover those separately from approved backups if a Release/database compatibility problem is found.

### 6.4 VM snapshots and local backup

Before a material deployment change, create a Vultr VM snapshot through the Vultr control plane and record its timestamp, source VM, and tested Release SHA in an operator-only record. Snapshot creation/restoration was not performed or verified by this repository. Snapshots may continue to incur storage charges; stopping a VM does not necessarily end VM, storage, IP, backup, or snapshot billing. Confirm current pricing and resource deletion in the Vultr console before assuming charges stop.

For a local backup, stop the private Workspace only if a consistent offline copy is required, then copy `/etc/trustbound/` (secrets handled through an approved encrypted process), `/var/lib/trustbound/workspace-live/`, the current and previous Release SHA, Caddy configuration, and any required Runner configuration to an encrypted operator-controlled location. Test restoration on a non-production host before relying on it.

If the instance is destroyed, rebuild the host identities, rootless Docker, Caddy/DNS/firewall, systemd units, encrypted environment files, Runner socket, immutable Release, Workspace/quota databases or their restored backups, and SSH access. A VM snapshot alone is not a substitute for a documented secret-recovery and DNS plan.

