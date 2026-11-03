# TrustBound

面向受控 Python 修复任务的隔离执行与独立验收实验。项目范围与路线见
[项目总档案](TrustBound_Hackathon_MasterPlan_2026-11-03.md)。

当前已实现不依赖 LLM 的固定金额 Bug 样例、最小 Sandbox Runner、独立验收和 JSON 报告。

本地 Python 环境：

```powershell
D:\Anaconda\python.exe -m venv .venv
.\.venv\Scripts\python.exe --version
```

不需要修改 Anaconda 全局环境。Docker Desktop 采用 WSL2 后端，容器数据位于
`D:\DockerData\TrustBound`。安装后重新打开终端以加载 Docker PATH。

复现环境检查（需要 Docker Desktop 已运行）：

```powershell
docker pull python:3.12-slim
.\.venv\Scripts\python.exe -B scripts\check_sandbox.py
```

脚本只执行预先审核的固定代码，不接收任意代码或挂载宿主目录。每次运行解析本地镜像
digest，并覆盖 `docs/environment-smoke.json`。测试成功不代表任意代码执行服务安全。

真实执行记录及未验证事项见 `docs/EXPERIMENTS.md`。

## 固定修复实验

需求是将十进制金额字符串转换为整数分，采用最近值舍入，恰好半分时远离零
（`ROUND_HALF_UP`）。例如 `1.239 → 124`、`1.005 → 101`、`-1.005 → -101`。
本轮仅覆盖声明的有限金额样例，未定义无效输入、NaN 或超大金额行为。

```powershell
.\.venv\Scripts\python.exe -B -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -B -m trustbound all
```

也可将 `all` 换成 `original`、`fixed`、`public_only`、`unauthorized` 或 `timeout`。
CLI 仅接受这些候选 ID，不接受命令、代码文本、路径或自定义授权策略。
每次运行的 JSON 写入独立的 `artifacts/<UTC时间>-<run_id>/reports.json`。
CLI 退出码 0 表示各场景的实际状态符合预期，**不代表所有候选均通过验收**。

- `original`：截断小数，公开测试失败，报告 `FAILED`。
- `fixed`：公开测试和新容器中的独立验收都通过，报告 `VERIFIED`。
- `public_only`：使用银行家舍入，公开测试通过但半分边界验收失败，报告 `FAILED`。
- `unauthorized`：预定义请求包含修改 `acceptance/billing_v1.py`，在启动容器前报告 `REJECTED`。
- `timeout`：固定无限循环由宿主超时终止，报告 `FAILED`，执行状态为 `TIMED_OUT`。

`fixtures/billing/` 保存原始代码、完整文件替换补丁、公开测试与受控失败样例；
`acceptance/billing_v1.py` 是可信正式验收材料；`trustbound/contracts.py` 定义三个契约；
`service.py` 控制固定任务、范围检查和验收裁决；`runner.py` 负责容器生命周期。
本轮可审查的真实报告快照为 [docs/day1-results.json](docs/day1-results.json)。

## 信任与隔离边界

TaskSpec、候选注册表和正式验收标准来自可信仓库，用户输入只选择固定 ID，不能重定义策略。
候选代码从不在宿主 Python 中导入或执行；只读挂载专用临时目录中的两份文件。
公开测试与独立验收使用不同临时目录和不同容器，候选不能修改验收副本，
宿主正式验收文件在执行前后做内容一致性检查。验收副本不是保密机制。

执行使用已固定 digest 的 Python 镜像，禁止拉取漂移标签；如果该镜像不存在，可手动执行：

```powershell
docker pull python@sha256:b18b261e1b4974b4f321451ad5251ded85abb22c2b8b262da527dda1d031ab30
```

每个容器采用 non-root、network none、只读根目录和工作区、cap-drop ALL、
no-new-privileges、128 MiB 内存及 swap 总量、0.5 CPU、32 PID，日志轮转上限约 2 MiB。
启动前 inspect 检查限制配置；等待执行限时 3 秒，Docker 控制命令另有 30 秒超时。
Docker Socket、宿主项目目录和宿主环境变量不传入容器。

报告包含候选及验收 SHA-256、diff、真实 stdout/stderr、退出码、超时原因、
配置检查、工作区完整性和清理结果。仅测试通过、证据对应且清理成功时才可 `VERIFIED`；
控制器错误或清理无法确认产生 `INCONCLUSIVE`。
这套机制以可信仓库和受审核候选为前提，不支持任意公众代码，也没有提供通用沙盒安全证明。
