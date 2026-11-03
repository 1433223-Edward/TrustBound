# Day 1 环境准备记录

日期：2026-11-03（北京时间）。仅记录实际检查，不代表 Gate A 已通过。

## 已验证

- Windows 11 家庭中文版，64 位，build 26200；PowerShell 7.6.5。
- Python 3.12.7：`D:\Anaconda\python.exe`。
- Git 2.44.0.windows.1；`git init` 已在本项目完成，尚无提交或远端。
- `D:\Anaconda\python.exe -m venv .venv` 创建了隔离解释器，但在沙箱内初始化 pip 失败。
- 沙箱外执行 `.\.venv\Scripts\python.exe -m ensurepip --upgrade --default-pip` 成功；pip 24.2 来自 Python 自带 wheel，没有下载项目依赖。
- `.\.venv\Scripts\python.exe -B -c "import sys; print(sys.prefix != sys.base_prefix)"` 输出 `True`。
- `git check-ignore .venv/pyvenv.cfg .env` 确认两者被忽略。
- WSL 3.0.3，默认 Ubuntu-24.04 使用 WSL2，能够启动。
- Ubuntu 内核：`6.18.54.1-microsoft-standard-WSL2`；PID 1 为 systemd，默认用户为 root。
- Ubuntu 内 `command -v docker` 无输出，`/var/run/docker.sock` 不存在。
- 初始空间：D 盘约 104.1 GiB 可用，C 盘约 17.1 GiB 可用。

## Docker 安装与实际执行

Windows PATH、常见系统安装目录以及 `%LOCALAPPDATA%\Programs\DockerDesktop` 均未发现 Docker。
从 Docker 官网下载了 620496816 字节的安装器。首次单连接下载缓慢，改用六段续传后完成；
合并文件 Authenticode 签名为 `Valid`，签名方为 Docker Inc。
安装命令参数为 `install --user --quiet --accept-license --backend=wsl-2 --wsl-default-data-root=D:\DockerData\TrustBound`，退出码 0。

- Docker Desktop 4.97.0 (244584)，CLI / Linux Engine 29.9.2，cgroup v2。
- 首次镜像拉取因当前终端缺少新 PATH，找不到凭据助手而失败。
  在进程 PATH 前添加 `%LOCALAPPDATA%\Programs\DockerDesktop\resources\bin` 后拉取成功。
- 官方镜像：`python:3.12-slim`。
- 本轮固定 digest：`python@sha256:b18b261e1b4974b4f321451ad5251ded85abb22c2b8b262da527dda1d031ab30`。
- 实际运行：`.\.venv\Scripts\python.exe -B scripts\check_sandbox.py`，退出码 0。
- 正常场景：stdout 包含 `sum: 6`、`uid: 65534`、仅有 `lo` 网络接口，
  写根目录返回 errno 30（只读文件系统）；退出码 0，清理确认成功。
- 受控循环：stdout 为 `loop_started`；宿主侧等待 3 秒后超时并 kill，
  容器退出码 137，状态为未运行，清理确认成功。超时后 `docker info` 成功。
- 两个容器均未挂载任何宿主目录；inspect 确认 network none、只读根目录、
  non-root、cap-drop ALL、no-new-privileges、128 MiB 内存及 swap 总上限、
  0.5 CPU、32 PID 配置。
- 原始配置、状态、stdout/stderr、清理结果保存在 `environment-smoke.json`。

实际执行时间约北京时间 13:31（JSON 的 Docker 时间戳为 UTC）。

## 待验证与边界

- WSL 启动提示 localhost 代理未映射到 NAT 模式；尚未修改任何代理设置。
  Docker Desktop 下镜像拉取成功，但这不证明 Ubuntu 内其他网络请求均可用。
- CPU、内存、PID 等上限已检查 Docker 配置，未做打满资源或 OOM 的压力实验。
- 已验证基本运行、只读文件系统、超时终止、清理及 Engine 后续可响应；
  尚无 API，因此没有进行 API 健康检查，也未声称完成全部 Day 1 验收。
- 本节为环境准备时点记录；后续固定 Runner、验收与契约的完成情况见下节。
- 未触碰其他项目仓库或其他 WSL 发行版，未创建云资源，未执行 commit/push。

## Day 1 固定修复与独立验收（本轮）

继续复用既有 Python、Docker、Git 环境，未安装额外依赖。新增标准库实现：
`trustbound/`、`fixtures/billing/`、`acceptance/billing_v1.py` 和 `tests/test_day1.py`。
需求固定为十进制金额转整数分，最近值舍入，半分远离零。

真实运行命令：

```powershell
.\.venv\Scripts\python.exe -B -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -B -m trustbound all
```

- 单元测试：10 项通过，覆盖契约拒绝、证据缺失/不对应、越权前置拦截、公开测试失败、
  独立验收失败和清理失败裁决。单元测试中的执行证据为 mock，与以下实测分开。
- 首次容器运行报告位于 `artifacts/20261103T071703Z-00bff373/reports.json`。
  local 日志驱动的压缩与 `max-file=1` 冲突，导致启动失败；
  四个获准场景均真实报告 `INCONCLUSIVE`，容器清理成功，没有误报通过。
- 改为 `max-file=2` 后重跑，命令退出码 0，原始结果位于
  `artifacts/20261103T071809Z-a2120e85/reports.json`；可版本管理快照为 `day1-results.json`。
- `original`：公开测试退出码 1（`1.239` 得到 123 而非 124），最终 `FAILED`。
- `fixed`：公开测试 2 项、独立验收 1 项（含 10 个金额 subcase）均通过，两个退出码为 0，最终 `VERIFIED`。
- `public_only`：公开测试退出码 0；独立验收退出码 1，五个半分边界失败，最终 `FAILED`。
- `timeout`：宿主等待 3 秒后 kill，容器退出码 137，记录 `TIMED_OUT` 和触发原因，最终 `FAILED`。
- `unauthorized`：提出对受保护验收文件的写请求，策略拒绝，执行记录为空，最终 `REJECTED`。
- 六个实际执行容器均 `cleanup_confirmed=true`、`workspace_unchanged=true`、`limits_verified=true`。
  `docker ps -a --filter name=trustbound-` 输出为空；随后 Engine 返回 29.9.2。

保护方式：只读绑定全新临时工作区，绝不挂载宿主项目或正式验收目录。
正式验收由可信仓库读入，使用同一候选字节快照在新容器中验证；
报告携带候选和测试 SHA-256，不能仅凭公开测试通过或候选自报成功进入 VERIFIED。
`changed_paths` 表示固定候选提出的变更范围，不表示已写入宿主文件；越权请求不会被应用。

尚未验证：CPU/内存/PID 打满时的压力行为、任意恶意 Python 代码、容器逃逸防御、
并发任务、API 健康检查、LLM 调用及云部署。资源限制已检查配置，不能等同于压力实测。
本轮完成的是受控固定任务的执行和验收闭环。

## Day 2 Vultr 接口与受控 Executor（等待凭据）

- 已审查 Day 1 源码、测试及证据，在修改前创建本地基线 commit `2213003`
  （`Establish Day 1 sandbox and independent verification baseline`），未 push。
  初始总档案中的三处 Markdown 行末双空格触发 diff whitespace 提示，保留原稿未改写。
- 从宿主进程及用户环境只检查配置存在性，未发现 `VULTR_INFERENCE_API_KEY`、
  `VULTR_API_KEY` 或 `VULTR_MODEL`；未搜索其他项目或读取凭据文件。
- 真实 GET `https://api.vultrinference.com/v1/models?format=openrouter` 成功，返回 13 个模型，
  原始目录保存于 `artifacts/vultr-catalog-live.json`，可审查摘要见 `vultr-model-selection.json`。
- 选择 `deepseek-v4.1-flash-1017`：官方 quickstart 使用它，实时目录确认文本输出、
  response_format、max_completion_tokens 和可选推理；价格为输入 $0.15/百万 Token、
  输出 $0.60/百万 Token。选择考虑任务规模和低成本，并非能力评测结论。
  公开目录中存在不代表当前账号已获授权或已充值。
- 新增标准库 HTTP client、受限 Executor、离线测试；提取 service 的公共验收流程供两种入口复用。
  TaskSpec/ExecutionResult/VerificationReport 契约、正式验收文件及 Runner 容器参数没有修改。
- 本轮密钥缺失的实际 CLI：`.\.venv\Scripts\python.exe -B -m trustbound.executor`，
  返回 BLOCKED，单独进程退出码 2，`source=NO_LIVE_CALL`、calls 为空、无验证结论。
  初始记录位于 `artifacts/executor-30f775e87fa346eba201a0d78a7e2225/report.json`；
  最终就绪快照见 `executor-readiness.json`。
- `.\.venv\Scripts\python.exe -B -m unittest discover -s tests -v`：26 项通过
  （原 10 项 + 新增 16 项）。首次新增测试曾因 tuple 与 JSON list 的断言比较失败，
  已改为检查空执行集合，未改变策略或放宽验收。
- 离线覆盖结构正确/异常/重复 JSON key、受保护路径、限制语法、Token 预算传递、
  usage/费用估算、缺失 usage、截断输出、模型 ID 不一致、认证/API 失败、超时、
  429 有界重试和密钥回显脱敏。测试的 transport/verification mock 不算真实 LLM 证据。
- 真实容器回归命令 `.\.venv\Scripts\python.exe -B -m trustbound all` 退出码 0，
  五个固定场景依次为 FAILED、VERIFIED、FAILED、FAILED、REJECTED；
  原始记录 `artifacts/20261103T073039Z-33110ef2/reports.json`。这是固定样例回归，非模型补丁实测。

调用预算：每 HTTP 操作 30 秒 socket 超时，最小请求 64 Token，补丁请求 1024 Token，
每份请求材料最多 12000 JSON 字符；仅明确的 429 最多重试一次。
连接/读取超时或 5xx 不盲目重试，费用保持 UNKNOWN；有 usage 时按实时目录单价估算，
不假定失败请求免费，也不将缺失 usage 记为 0。

本轮真实推理调用数 **0**，推理支出 **$0**。尚未执行最小模型请求或真实模型生成补丁验收。
需要用户在 Vultr 控制台确认账号、有效 Serverless Inference 额度及使用资格，并在本地
运行环境设置 `VULTR_INFERENCE_API_KEY`；不要将密钥发入聊天。之后再运行 Executor 验证两次请求
及真实补丁。未使用其他付费服务替代。本轮代码改动保留为未提交，等待用户验收。

官方资料：
- https://api.vultrinference.com/docs/get-started/quickstart
- https://api.vultrinference.com/docs/reference/list-models
- https://api.vultrinference.com/docs/reference/create-chat-completion
- https://api.vultrinference.com/docs/models
