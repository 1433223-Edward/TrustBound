# TrustBound 候选模型比较批次

批次model-compare-20261108T155750+0800，状态STOPPED_AFTER_INVALID_PROPOSAL。执行1次GLM生成，MiMo未执行；无重试、无修复模型输出、无核心代码修改。

## 配置与实时目录

无凭据公开catalog GET成功，确认DeepSeek默认模型、glm-5.3-flash、mimo-v2.6-flash及其JSON/推理参数支持。价格（USD/百万tokens）：DeepSeek输入0.15/输出0.60；GLM输入0.10/输出0.35；MiMo输入0.10/输出0.25。目录存candidate-catalog.json，实际响应身份仍以调用返回为准。

保持默认VULTR_MODEL不变，仅将两候选加入本地TRUSTBOUND_WORKSPACE_MODELS。使用既有启动参数临时设绝对限额44次任务/12次模型调用/47104预留输出tokens，即原累计42/10/38912之外仅留2次生成和8192输出。累计模型上限现有校验支持100，本轮未改核心校验。

## GLM真实结果

真实服务器Run ID：7a9d0a259e8546fd85b2903bb8fe393f。
原始记录：benchmarks/results/raw/26d86766e6b84f4ab442f9db8c645083。
实际response_model=glm-5.3-flash；只有一次attempt、finish_reason=stop。输入741/输出1995/总2736 Token，预留4096。客户端总耗时7.266秒。estimated_usd=$0.00077235，已知估算费用但非发票金额。

与DeepSeek使用同一专用Inventory项目69e7990423e3492a8b572205116b12b2、revision2、源码hash及冻结验收。结果INCONCLUSIVE / INVALID_WORKSPACE_PROPOSAL，未进入可信业务测试，创建容器0个。不是“Docker清理失败”，清理不适用。

提案JSON形状或解释Schema在现有代码中被拒绝；原始API报告没有保留未通过校验的模型提案正文，因此不能确定具体哪个字段不合规。不能据此声称模型修复代码在业务用例上失败，更不能声称总体能力差。现有reasoning预算请求1536，供应商返回reasoning_tokens=1546；这是实际元数据，不将该细分预算提示当精确硬上限。总输出1995未超过4096。

## 停止与费用保护

原始文件integrity验证通过，模型调用费用已知；安全业务执行证据未产生。按保留的“不完整/不明确结果即停止”边界关闭本批次，没有重试GLM，也未执行MiMo。MiMo为NOT_RUN，不将缺失值当0或计入成功率分母。

账本从42/10/38912变为43/11/43008，恰好1次任务、1次调用、4096输出预留。journal无未决/UNKNOWN_BILLING。最终服务健康空闲。

停止后恢复累计调用上限100，将运行及输出绝对上限收至已用量43和43008，未使用的一次批次额度已关闭，历史计数保留。没有美元硬限额；次数与输出Token预留才是现有强制保护，估算费用不是上限。

## 与已有DeepSeek基线的探索性对照

- DeepSeek：一次生成，5个冻结用例通过，VERIFIED；输入787/输出1554，客户端37.891秒，估算$0.00105045。
- GLM：一次生成，提案校验拒绝、0个业务用例执行，INCONCLUSIVE；输入741/输出1995，客户端7.266秒，估算$0.00077235。
- MiMo：未运行，暂无数据。

来源相同不表示不同模型token计数必然相同。GLM较短延迟包含提前拒绝，不能解释为更快完成修复。每模型仅1次，不能推断普遍排名或显著性。

## 数据与图表

run-index.csv和batch-summary.json列出真实服务器ID、客户端ID、费用及原因。原始JSON/CSV、accepted、轮询、调用usage及hash清单在raw目录。全部6份已有原始记录完整性检查通过。

analysis/index.html及PNG/SVG由现有分析入口离线生成，按实际模型/来源分层，不混入Demo Replay或合成结果。本批次GLM的INCONCLUSIVE不能被图表中的0个VERIFIED误读为业务验收失败；MiMo不画虚构点。

## 下一步（未执行）

先审查提案协议/现有日志能否解释格式拒绝。若确需补最小诊断日志，应另行说明修改范围并取得批准；不在此批次改代码或自动重发。是否继续MiMo或重试GLM，需要用户明确决定，原GLM请求已经计费。

仅改本地启动参数、Benchmark配置与结果。无核心功能修改、资源扩容、部署、Commit或Push。
