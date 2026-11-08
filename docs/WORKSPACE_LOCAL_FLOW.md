# Workspace 本地操作与限制

本轮不调用付费模型，不自动 Push 或部署。

## 启动

在 D:\Projects\TrustBound 打开 PowerShell。先启动 Docker Desktop（Linux containers），确认 `docker version` 能返回 Server 版本。若命令找不到，把 Docker CLI 加入 PATH 后重开终端。Runner 使用 trustbound/runner.py 中固定 digest 的 Python 镜像，首次使用需要 Docker 能拉取该镜像。

终端一：

```powershell
.\scripts\start_workspace_preview.ps1
```

默认开启 Workspace、Billing 和重试的模型调用，使用本机已有凭据；额度为 48 次模型调用、196608 输出 Tokens，沿用现有额度账本，不自动清零。仅需离线体验时显式传入 `-EnableLiveFromEnv:$false -EnableBillingLive:$false -EnableRetryFromEnv:$false`。终端二：

```powershell
cd D:\Projects\TrustBound\frontend
npm ci
npm run dev
```

浏览器打开 http://127.0.0.1:5173/ ，进入 Workspace。

## 不花模型费用的完整流程

1. 打开库存或日志准备样例。样例自带源码、独立参考规则、公开用例和验收用例。
2. 打开项目计划书，检查目标、允许修改路径、入口、两组测试及可信依据。可逐项编辑；编辑后先点更新计划。
3. 解决待确认问题，清除已经解决的问题及 NEEDS_CONFIRMATION 标记。审核期望值依据后勾选人工确认，再批准冻结。
4. 使用 Offline / Fixture 模式运行已审阅样例补丁，按界面确认沙盒执行。模型调用为零，Docker 执行真实测试。
5. 检查报告和 Diff。只有通过独立验收的改动可接受；可拒绝改动或下载结果。源码或计划修改后必须重新批准；旧冻结版本保留。

自己的文件夹：选择“打开文件夹”，选择项目根目录。导入支持 .py、.md、.txt 及根目录 TRUSTBOUND_PLAN.json；隐藏目录、node_modules、__pycache__ 和不支持的文件会过滤。最多 20 个源码/文档文件，另可携带一份计划文件；仍限单文件 4 KiB、源码总计 24 KiB，计划 16 KiB，ZIP 64 KiB。至少一个 Python 文件。路径仍须符合后端安全规则。

自有项目可手动填写计划，批准后验证当前源码；需要改动时编辑源码、保存新修订并重新批准，或用开发者选项提交离线候选。独立验收输入必须与公开测试不同。输入和期望输出只能是 JSON；入口形如 main.py:solve，接收一个位置参数，返回 JSON 值。不要填 pytest 代码、命令或异常断言。

## AI 生成（之后由用户主动启用）

在本机 .env 配置已有 Vultr 凭据和模型，直接运行 `start_workspace_preview.ps1` 即默认启用。在 Agent Chat 选择模型、填写目标，点击 AI 生成，按界面确认源码发送。生成只产生草案，仍需审核、解决问题、确认依据和批准冻结。一次生成失败不会自动追加付费重试。不得把模型推导当成自动可信证据。

## 本轮验证边界

后端和前端测试覆盖模拟模型响应及审批链路。未调用真实付费模型。当前执行环境 PATH 中没有 docker 命令，因此本轮没有复跑真实 Docker 端到端执行，也未进行浏览器原生文件夹选择器的人工验证。
