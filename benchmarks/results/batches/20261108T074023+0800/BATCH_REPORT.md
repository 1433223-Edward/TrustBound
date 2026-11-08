# TrustBound 有限无人值守批次报告

批次 ID：20261108T074023+0800（Asia/Shanghai）。此为批次ID，不是实验Run ID。

## 实际完成

- 使用项目 `.venv/Scripts/python.exe` 调用既有 `benchmark.py prepare`，生成1/5/10/20文件数据。四份均通过文件数量、单文件4KiB、总计24KiB静态检查。它们是生成的测试输入，不是实验结果。
- `benchmark.py check` 已运行：退出码1，`No raw records found`。当前Benchmark raw目录没有记录，不能声称完整性检查通过，也不是发现数据损坏。
- `benchmark.py analyze` 已运行：退出码1，`No raw observations; no charts generated`。没有新实验数据，不生成虚构新结果图。
- 历史分析只读存档 `docs/environment-smoke.json` 和 `docs/day1-results.json`，保留原始字节及SHA256，导出JSON/CSV、PNG/SVG/HTML。共5条历史业务报告、8条唯一容器执行记录，其中8条确认清理、2条记录超时；这些不是独立重复实验，不能外推成功率。未导入Demo Replay副本。
- 项目虚拟环境没有matplotlib，未安装依赖。历史图表使用已有 `D:/Anaconda/python.exe` 的matplotlib，渲染缓存放本批次目录。脚本只读取存档，不导入TrustBound或联网。

## 本轮真实实验：0项提交

D-OFF、E-OFF、E-ON全部跳过。D缺source_commit/source_hash和真实pair_id；E另缺project_id。Manifest没有擅自补全。

对 `http://127.0.0.1:5173/api/health` 仅进行一次只读GET，返回URLError，底层PermissionError。当前执行环境无法核实服务健康、空闲与有效Runner限制；这不等于已证明服务停止。未尝试提高权限、打开其他端口、重启服务或Docker、SSH公网VM。

三个实验均没有Run ID，记null；无本轮容器运行、无本轮模型请求。不把跳过记为实验失败或通过。

## 付费实验：0项提交

B/C/D-ON没有固定批次付费授权、批准费用上限、已核对的服务预算与环境，Manifest不完整。模型确认文件confirmed_by_operator=false，B/C实际模型为空。D-ON的服务实际模型也未核实。现有参考Token/请求上限不是本批次生效预算证明。

仅交付PENDING_COMMANDS.ps1中的待执行命令。提交行全部注释，未执行PAID或付费参数。没有新增模型费用；历史记录费用未知，保留null，不推算发票。

## A安全覆盖

只读复用两份历史Docker格式原始报告，没有启动A1–A5攻击。未在artifacts/docs中找到完整REAL_ROOTLESS_DOCKER专项原始报告。

- Process Isolation：INCONCLUSIVE。存在历史只读根、非root、lo接口和策略拒绝记录；不代表完整Rootless文件/进程/网络边界通过。
- Secret Hygiene：NOT_TESTED。无A3完整合成秘密运行报告。
- Resource Limits：INCONCLUSIVE。历史超时终止可观察；A5 OOM、CPU/PID触发NOT_TESTED，inspect配置不代替执行证据。
- Lifecycle Discipline：INCONCLUSIVE。选定历史容器8/8有cleanup_confirmed=true，仅限这8个记录；孤儿故障回收和长期泄漏NOT_TESTED。

## 文件索引

- `offline-actions.json`：prepare/check/analyze命令、退出码及stdout/stderr。
- `health-check.json`：唯一健康请求及权限失败类型。
- `execution-decisions.json` / `.csv`：每项Manifest、缺项、提交状态、Run ID、费用字段。
- `paid-authorization-check.json`：付费授权缺失判断。
- `datasets/`、`dataset-validation.json`：测试输入及限制检查。
- `historical-raw/`：历史原始JSON存档，不混入新raw实验目录。
- `historical-analysis/index.html`：真实历史证据图表与说明。
- `historical-analysis/security-coverage.csv`：四维场景状态及缺失证据。
- `historical-analysis/historical-executions.csv` / `historical-tasks.csv`：历史容器与Run ID。
- `historical-analysis/statistics.json`：历史统计、来源及摘要。
- `evidence-integrity.json`：本批次证据/报告/图表SHA256清单；不含绘图缓存，不是真实性签名。

## 需要人工处理

在可访问的既有授权环境确认服务与Runner；填写发布commit、真实源码hash、冻结project_id/revision和真实pair_id。E-OFF execution_input须匹配项目。不要将这些缺失字段自动“修复”为本地猜测值。

付费阶段另需事先批准固定模型/样本/次数及总费用上限，并证明服务端强制限制已生效。本批次不提供、推断或新建该授权。

没有修改核心代码、资源限制、正式模型或后台配额；没有新调度器、重试、部署、Commit或Push。当前批次已停止。
