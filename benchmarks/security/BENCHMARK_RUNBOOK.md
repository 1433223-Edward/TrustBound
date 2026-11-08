# Experiment A 审计与人工操作手册

范围仅 Experiment A；未改核心业务、Demo 或 Workspace。只读审计，不执行实验。

## 已有清单与四维覆盖矩阵（逐项映射）

- Process Isolation：A1 策略拒绝与只读挂载写入；A2 无外部网络路由；非 root 用户、根文件系统只读。入口 `python -B -m trustbound.attack_suite`，源码 `trustbound/attack_suite.py`、`fixtures/security/probe.py`、`trustbound/runner.py`。
- Secret Hygiene：A3 Runner 合成环境变量及宿主文件不可见；同一入口。只检查凭据变量可见性，不读取真实值。未证明所有进程上下文或 Web/Runner 凭据隔离。
- Resource Limits：A4 主机截止时间；A5 cgroup 内存 OOM；CPU=0.5、Memory=128MiB、PID=32 的配置 inspect 由 Runner 提供。CPU 节流/PID 耗尽未有运行时触发证据。Rootless/cgroup v2/controller 委派检查在 `runner_worker._configure_docker`。
- Lifecycle Discipline：每个 execution 的 cleanup_confirmed、workspace_unchanged；`runner_worker._reconcile_owned_containers` 仅回收指定 label、合法命名的 Web worker 容器，最多 8 个。不等于任意容器清理。`tests/test_admission.py` 有 mock 回收测试。

A1–A5 的判定单元测试在 `tests/test_attack_suite.py`，它验证判定函数，不提供真实隔离证据。A2 只做 UDP 路由查询，不发送数据，不代表全协议出口审计。A1 不证明任意宿主进程访问均被阻断。

## 已有证据及缺失

- `docs/environment-smoke.json`：真实 Docker 格式原始报告，正常运算 sum=6、uid=65534、lo、根写入 errno=30；循环超时 exit=137；两次清理确认。入口 `scripts/check_sandbox.py`。没有 Rootless 身份或 release commit，不能升级为私有 VM 证据；脚本会覆盖该历史文件，因此不建议直接复跑。
- `docs/day1-results.json`：Evidence Report 数组，fixed VERIFIED（合法对照），timeout TIMED_OUT/137，unauthorized REJECTED/零 executions；固定哈希、镜像及清理记录。入口 `python -m trustbound fixed|timeout|unauthorized`。业务 FAILED 不直接表示隔离 FAIL。
- `artifacts/gate-b-*.json`、`gate-c-*.json`、`gate-d-*.json`、`gate-d-final-*.json`：已有业务 verification executions，可辅助追溯，不能代替 A1–A5 专项报告。
- `docs/stage4-offline-results.json` 及 Offline 单元/集成测试：Offline 描述模型路径，不能仅凭 Offline 就认定没有 Docker；需逐 execution 判断。
- `frontend/src/data/demo.json`：Demo Replay 展示副本，不能另算独立样本；回到其 source 原始报告去重。
- 仓库未找到完整 `trustbound-security-a1-a5` 原始运行 JSON。`docs/SECURITY_ATTACK_SUITE.md` 是操作规范，不能当作通过记录。A1–A5 的实际 Rootless 结果目前缺失。
- 现有历史记录是不同用例/阶段，未形成同配置独立重复样本。没有成组匹配的每维合法对照；FRR、Secret Exposure Rate 暂不可可靠统计。

## 最小补充方案

直接复用现有 A1–A5、fixed、timeout、unauthorized，不重写攻击。由操作者安排独占窗口，每组手动重复至少 5 次，记录 release、镜像 digest、配置和时间；每次配 fixed 合法控制。既有正常运算只是通用对照，网络/秘密维度需补充“允许读取已挂载非秘密输入”等专门对照后才能报告该维 FRR。

CPU 节流、PID 边界、宿主进程可见性、Web/Runner 合成凭据隔离、异常退出及长序列资源泄漏仍是缺口。当前固定 CLI 未暴露这些探针；本轮仅保留待验收设计，不生成可在宿主误执行的压力代码。后续使用专用受审固定容器 harness、有限子进程数和双重 deadline，复用 Runner，不能凭 inspect 宣称压力测试通过。孤儿回收需专用独占环境和当前 label 所有权，不能在现有服务中制造崩溃；暂仅有 mock 证据。

## 人工运行命令

Windows 只分析：
```powershell
Set-Location D:\Projects\TrustBound
python --version
New-Item -ItemType Directory -Force benchmarks/results/raw | Out-Null
# 将 VM 原始 JSON 复制至 raw；选择一个不存在的输出目录，历史数据不会被覆盖
python benchmarks/security/analyze.py benchmarks/results/raw/attack-01.json --out benchmarks/results/processed/A-01
Invoke-Item benchmarks/results/processed/A-01/security.svg
```
分析脚本仅标准库，不导入 TrustBound、不调用模型/Docker，不产生费用。多个报告路径以空格分开；重复 run_id 拒绝。原始 JSON 保留，CSV 携带原文件 SHA256。只接受明确 REAL_ROOTLESS_DOCKER 原始套件，拒绝 Replay/Offline 混入。格式/证据错误直接报错，保留原文件排查。重复生成时指定新的 --out。

Ubuntu VM（仅操作者手动执行；本轮未执行）：
```bash
cd /srv/trustbound/pointers/current
# 要求已有发布、私有 API 健康空闲且 Live 关闭；不执行部署
umask 077
mkdir -p /home/linuxuser/benchmark-security
report=$(mktemp /home/linuxuser/benchmark-security/attack.XXXXXX.json)
sudo -H -u trustbound-runner -- ./.venv/bin/python -B -m trustbound.attack_suite > "$report"
printf 'exit=%s report=%s\n' "$?" "$report"
# 配对合法对照：使用已有服务配置、Runner IPC 的正常运维身份执行
./.venv/bin/python -B -m trustbound fixed
```
套件会启动真实 Docker；不调用 LLM，无模型费用，但消耗 VM CPU/内存。预期一条策略和五条 runtime PASS；失败或提前停止保留 JSON，检查 reason、api_before/after、execution.error 和 cleanup_confirmed，停止后续重复。Ctrl+C 后不要假定清理成功，由运维按既有生命周期规则核对。fixed 输出 artifacts 时间戳目录和 reports.json；不可在未配置 Runner IPC 的主机直接运行。套件错误日志需同时人工保存；空 JSON/启动失败不计成功。

## 指标与结果模板

Containment Rate = runtime PASS / (PASS+FAIL)，按 case、release、配置分别分析，同时公布 planned、unknown 与证据完整率，缺失/INCONCLUSIVE 不当成功。当前脚本输出逐 case 指标，禁止跨 release/config 混合输入。
FRR = 被错误拒绝的合法控制 / 已完整观察合法控制；Secret Exposure Rate = 确认合成秘密暴露 / 完整秘密探针；Resource Enforcement Rate = 确认限制触发 / 完整资源探针（配置检查不进入分母）；Cleanup Success Rate = 确认清理成功 / 已创建且需清理容器，未知单列。A3 FAIL 不必等于秘密暴露，须核对 observations；这些指标当前保留人工判读，不从笼统 status 推导。

每次另存元数据 JSON：experiment_id、run_id、dataset_version=A-v1、source_commit、source_hash、configuration、started_at、completed_at、actual_model_id=null、input_tokens=null、output_tokens=null、estimated_cost=null、execution_status、verification_status、security_status、evidence_reference、failure_reason。无模型调用使用 null，不伪装实际模型或零计费。补充控制记录应注明配对 run_id、预期/实际行为和证据路径。不能把未运行模板当数据。

v2补充：离线分析提供PNG、SVG热力图及HTML（需要matplotlib，不自动安装）。主入口见 ../BENCHMARK_RUNBOOK.md。四维只做覆盖分类，不把缺控制组的case平均成四维安全分数。样本均按探索性结果标注，不声称显著性。
