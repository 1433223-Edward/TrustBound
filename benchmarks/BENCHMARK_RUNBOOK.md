# TrustBound Benchmark v2 — 冻结范围与人工操作

本文件取代先前 B–F 方案。只复用当前能力：A现有攻击套件、B单轮提案、C=1/5/10/20、D固定候选、E安全强制保留、F暂缓。没有扩容、修改核心或新增调度器。

## 一个入口

```powershell
Set-Location D:\Projects\TrustBound
. .\.venv\Scripts\Activate.ps1
python benchmarks/benchmark.py
```

该命令显示菜单，输入A/B/C/D/E选择单项，prepare准备规模数据，check检查原始证据，analyze读取已有数据画图。空输入退出。选择B–E后填写manifest路径；只有输入EXECUTE才提交一个真实任务，涉及模型再输入PAID。没有run-all，不自动循环、重试或依次跑完所有实验。每个重复样本由你单独运行。

A菜单显示已有VM操作手册，本地不会启动攻击。真实A必须在已配置的Ubuntu VM执行，见下文；一个Windows进程不能在没有SSH连接信息及Runner身份的情况下替代该入口。

## 环境与费用

```powershell
python --version
python -m pip show pydantic fastapi matplotlib
# 仅当你决定补装绘图库时执行；工具不会自行安装
python -m pip install matplotlib
Get-ChildItem benchmarks/configs
Invoke-RestMethod http://127.0.0.1:5173/api/health
```

实验脚本仅依赖Python标准库；分析PNG/SVG依赖matplotlib，其必要性仅为离线绘图。沿用已有服务启动方式；本工具不启动/部署服务或Docker守护进程。API提交任务会由现有服务启动容器。所有HTTP只允许localhost，VM使用你现有SSH配置隧道。模型key留在服务端；本地可按已有配置设置TRUSTBOUND_WORKSPACE_TOKEN，不能写进JSON。不要在公网服务执行Live实验。

B/C Live产生模型费用；D ON产生对抗模型费用；D OFF、E、A不调用真实模型，仍消耗Docker/VM资源。configs/models.json保留仓库默认ID作为参考，baseline和候选ID由你填写确认；该文件不改变服务配置。单轮实际上限由现有Workspace和服务配额强制控制。无自动付费额度提升。

## 准备可复用项目和数据

B直接复用Inventory、Logs的已注册可信参考规则。以下命令会创建独立Benchmark项目及冻结既有审核样本，不运行模型或容器；不要修改原Demo项目。请先阅读样本目标和验收，再运行freeze：

```powershell
$base = 'http://127.0.0.1:5173'
$headers = @{}
if ($env:TRUSTBOUND_WORKSPACE_TOKEN) { $headers.Authorization = "Bearer $env:TRUSTBOUND_WORKSPACE_TOKEN" }
$project = Invoke-RestMethod -Method Post -Uri "$base/api/workspace/projects/samples/inventory" -Headers $headers -ContentType 'application/json' -Body '{}'
$project.plan | ConvertTo-Json -Depth 30
$freeze = @{ revision=$project.revision; confirm_acceptance=$true; approval='formal'; adversarial_enabled=$false } | ConvertTo-Json
$frozen = Invoke-RestMethod -Method Post -Uri "$base/api/workspace/projects/$($project.project_id)/freeze" -Headers $headers -ContentType 'application/json' -Body $freeze
$frozen | ConvertTo-Json -Depth 30
```

Logs将sample路径inventory换为logs。把$frozen中的project_id、revision、snapshot_hash分别填入manifest的project_id、request.revision、source_hash；source_commit填该服务发布的真实40位commit。脚本提交前会GET核对hash和revision。B.json的request.model_id填你确认且服务allowlist已允许的ID。B只测当前单轮提案与可信验收，不测Tool Calling。模型任务描述见datasets/model-tasks.json；变更需求需独立审批冻结，同一模型比较须用同一快照、目标、验收和预算。

C准备仅生成源码数据，不执行源码：
```powershell
python benchmarks/benchmark.py prepare
```

输出datasets/generated-v2/scale-1.json、scale-5.json、scale-10.json、scale-20.json。每份包括files、plan、metadata；相同任务为solve(value)从+1改+2，其他文件是无依赖干扰项。文件字节/粗估tokens/深度/import边数固定记录，不能解释为复杂依赖项目。

导入一个规模并审批：
```powershell
$data = Get-Content benchmarks/datasets/generated-v2/scale-5.json -Raw | ConvertFrom-Json
$payload = @{files=$data.files} | ConvertTo-Json -Depth 30
$project = Invoke-RestMethod -Method Post -Uri "$base/api/workspace/projects" -Headers $headers -ContentType 'application/json' -Body $payload
$data.plan.revision = $project.revision
$draft = Invoke-RestMethod -Method Post -Uri "$base/api/workspace/projects/$($project.project_id)/plan" -Headers $headers -ContentType 'application/json' -Body ($data.plan | ConvertTo-Json -Depth 30)
$freeze = @{revision=$draft.revision; confirm_acceptance=$true; approval='formal'} | ConvertTo-Json
$frozen = Invoke-RestMethod -Method Post -Uri "$base/api/workspace/projects/$($project.project_id)/freeze" -Headers $headers -ContentType 'application/json' -Body $freeze
$frozen | ConvertTo-Json -Depth 30
```

C.json填写项目hash/revision/model_id和file_count=5；其他阶梯同样人工执行。数据metadata.source_hash是生成器自己的摘要，不等于服务snapshot_hash，运行manifest必须使用服务hash。单文件4096 bytes、总容量24KiB、模型消息12000字符、IPC64KiB均保持；Live超限作为真实失败记录，不能加大参数。导入/plan/freeze若失败，尚未提交实验，应保存HTTP错误并标注PREPARATION_REJECTED；不能把它算作成功运行。当前准备脚本未自动收集这三步的失败记录。

## 单项配置与运行

先只检查配置，无HTTP、模型或Docker：
```powershell
python benchmarks/benchmark.py B --manifest benchmarks/configs/B.json
python benchmarks/benchmark.py C --manifest benchmarks/configs/C.json
python benchmarks/benchmark.py D --manifest benchmarks/configs/D-off.json
python benchmarks/benchmark.py E --manifest benchmarks/configs/E-on.json
```

正式执行，每次一条，由你决定顺序/重复次数：
```powershell
python benchmarks/benchmark.py B --manifest benchmarks/configs/B.json --execute --allow-paid-inference
python benchmarks/benchmark.py C --manifest benchmarks/configs/C.json --execute --allow-paid-inference
python benchmarks/benchmark.py D --manifest benchmarks/configs/D-off.json --execute
python benchmarks/benchmark.py D --manifest benchmarks/configs/D-on.json --execute --allow-paid-inference
python benchmarks/benchmark.py E --manifest benchmarks/configs/E-off.json --execute
python benchmarks/benchmark.py E --manifest benchmarks/configs/E-on.json --execute
```

也提供run_A.py至run_E.py独立入口，参数同总入口对应子命令。

D无需Workspace项目：固定double_rounding候选+同一billing-v1验收，Recovery OFF。source_hash填写fixtures/billing/double_rounding.py实际SHA256，source_commit填写服务release commit。ON/OFF每对填相同非占位pair_id，每次重复用新pair_id。ON模型由服务VULTR_MODEL确定，必须记录实际response_model；OFF没有模型生成不虚构model ID。分析匹配候选/验收hash，并要求可信挑战执行及已知费用才标comparison_valid。NOT_CONFIRMED不自动等于误报。禁止把随机Workspace提案的ON/OFF当固定候选消融。

E选择同一冻结项目original源码，两份manifest只变group、correctness_verification及OFF必需execution_input。OFF的execution_input必须是该项目合法输入：规模整数项目用0；Inventory/Logs用其public_cases[0].input。模型与对抗均关闭。OFF仍执行安全流程，不能输出业务VERIFIED。覆盖差异源于执行不同数量的用例，不等于单个检查函数纯耗时。额外资源无遥测时不可获取。

A沿用security/BENCHMARK_RUNBOOK.md。已有历史Docker证据是docs/environment-smoke.json与docs/day1-results.json；不视作Rootless A1–A5全部通过。策略层、真实容器、Offline模型和Demo Replay分别标注；不重复计数。四维分类：A1/A2 Process Isolation、A3 Secret Hygiene、A4/A5 Resource Limits；每个容器清理字段归Lifecycle Discipline。CPU/PID触发、孤儿故障注入、长期泄漏仅列缺口。

Ubuntu已有发布内手动执行（真实Docker，无模型费用）：
```bash
cd /srv/trustbound/pointers/current
umask 077
report=$(mktemp /home/linuxuser/trustbound-attacks.XXXXXX.json)
sudo -H -u trustbound-runner -- ./.venv/bin/python -B -m trustbound.attack_suite > "$report"
printf 'exit=%s evidence=%s\n' "$?" "$report"
```

不能在Windows或宿主直接运行probe.py。A预期策略一条、runtime五条；缺项INCONCLUSIVE，不计通过。合法对照复用既有fixed入口，具体命令见security手册。

## 输出、停止和失败分类

B–E输出results/raw/<uuid>/：manifest、project（D除外）、health、accepted、轮询JSON、record.json、record.csv、integrity.json。JSON原样保留，raw和processed分离，UUID目录不覆盖。hash清单检测改动，不是签名或真实性证明。没有accepted表示可能未提交，但网络中断可能不确定，仍要查服务；不要自动重试。

health忙、HTTP拒绝、hash/revision不符时停止。容器清理失败、服务ERROR、模型失败或轮询超时后停止后续重复；保留原始报告中的reason/error及HTTP状态和结构化code。Ctrl+C只停止客户端，不取消服务任务；以accepted中的run_id检查服务终态，不能马上重发。已提交但结果不完整的计费未知，不填写0。

## 只读检查、统计和重新画图

```powershell
python benchmarks/benchmark.py check
python benchmarks/benchmark.py analyze --out benchmarks/results/processed/review-v2
Invoke-Item benchmarks/results/processed/review-v2/index.html
# A从VM复制原始JSON后单独导入
python benchmarks/benchmark.py A --report benchmarks/results/raw/attack-01.json --out benchmarks/results/processed/A-v2
Invoke-Item benchmarks/results/processed/A-v2/index.html
```

check验证B–E所有raw证据哈希；analyze再次验证后输出summary.csv、statistics.json、pairs.json、PNG/SVG、index.html与报告。A解析不同格式，单独导入；不会混到B–E模型统计。每次使用新输出目录。菜单analyze自动生成唯一目录；可随时重画，不调用模型/Docker。

图表来自原始结果：A观测热力图、B成本/验收散点与延迟、C规模/延迟/输入tokens/成本、D/E分组结果及配对JSON、每VERIFIED成本。小样本均探索性标注；未知值不画成0。无数据不生成虚构图。D有效配对不足时仅输出无效原因，不得形成有效收益结论。资源峰值、TTFR和未埋点阶段耗时始终null；保留服务started/finished时间，不将其冒充模型请求耗时。

## 已准备与未准备

已准备：A复用入口/分类/离线导入；B/C/E现有HTTP单任务入口；D固定候选配对入口；规模数据生成与plan；独立A–E包装脚本；总菜单；JSON/CSV与哈希检查；离线统计、PNG/SVG/HTML和分析测试。

未准备且保持冻结：F；CPU/PID压力触发与复杂故障注入；长期泄漏；多轮Agent；TTFR；真实资源峰值遥测。模型请求总延迟现有ledger只有started_at没有完成时间，无法从已有报告精确还原，标不可获取；只有客户端总耗时和服务起止可获取。D自动可信收益结论以实际证据为前提。导入阶段失败的自动统计尚未接入，需人工保留HTTP记录。

本轮只进行了语法/JSON及离线分析模块检查，没有Benchmark运行、模型请求、Docker启动、VM部署、Commit或Push。操作权留给你。
