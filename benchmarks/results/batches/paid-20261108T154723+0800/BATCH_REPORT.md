# TrustBound 固定付费试验批次报告

批次paid-20261108T154723+0800。本批次已结束，未扩展实验、未重试、无并行模型生成。

## 配额影响与调整

源码核对发现启动脚本和后端部署配置均硬校验累计模型调用<=100。为避免修改核心校验，本轮实际从启动器原48提高到100，满足“不超过2000”，未宣称已配置2000。没有改核心文件。

执行前账本runs=40、calls=8、预留output tokens=30720。首先把本批次绝对限额设为42/10/38912，严格只留2次生成和8192输出预留；已确认重启后原计数及冻结项目未变。执行后计数42/10/38912，恰好增加2/2/8192。历史账本未清空，重启前后备份随报告保存。

批次结束后将累计调用上限提高到100；运行上限42和输出预留上限38912保持已用尽。因此100不是新批次授权，后续任务仍需按新批次补充运行/输出额度。实际启动参数保存在campaign-runtime-config.json，复用配置保存到benchmarks/configs/local-benchmark-campaign.json。原脚本默认值未改。

单请求4096输出Token、Permission Gate、沙箱限制、幂等保护和未知计费处理未改。能强制执行的是累计次数、预留输出Token及任务数；没有美元硬上限，费用估算不是美元限额。总Token字段中的输出实际usage与账本预留输出要分开看。

## B：单轮默认DeepSeek生成

服务器Run ID：8c14ca0f80024019bef48bafd1572b57。
客户端原始记录目录：benchmarks/results/raw/79e75a42c3a84d43b3fcecc69bffae48。

使用专用冻结Inventory项目69e7990423e3492a8b572205116b12b2，revision2，源码snapshot_hash=5f0e2b5a7a6ed4462cb53044f2fc370c5ebd404575de996f8f975f752789a247。

实际响应模型deepseek-v4.1-flash-1017。真实生成1次，输入787/输出1554/总计2341 Token（输出含供应商报告的reasoning用量），预留4096。5个冻结公开/保护用例全部MATCHED，最终VERIFIED，5个容器均确认限制/工作区完整/清理。客户端总耗时37.891秒。账本估算费用$0.00105045，非供应商发票。

## D-ON：固定候选配对

服务器Run ID：74ac28e0760e48bea4c3c735f5ffec06。
客户端原始记录目录：benchmarks/results/raw/a33ff7cc38d74f71803414f019225025。

与已有D-OFF服务器Run ID 962d3363196d46edaa3fff403def161b使用相同double_rounding源码及billing-v1验收。候选hash=941584c0c21d177f69549876fde5c99583924275b2154367c525fb629849533b。

实际响应模型deepseek-v4.1-flash-1017。生成1次，输入321/输出1171/总计1492 Token，预留4096。正式验收原为VERIFIED；独立对抗输入经可信整数oracle与受限容器执行确认：

- 0.00495：期望0，实际1。
- -0.00495：期望0，实际-1。
- 1.23495：期望123，实际124。

三个反例均CONFIRMED，最终FAILED。它们展示同一个双重舍入缺陷，不算3个独立缺陷。无Recovery，不产生“修复成功”结论。3个容器全部清理确认。客户端耗时19.453秒，较OFF多9.140秒；单对样本只描述本次观测，不能断言普遍收益或稳定开销。增加账本估算费用$0.00075075。pairs.json标记MATCHED且comparison_valid=true。

## 批次总计

2次真实生成，输入1108、输出2725、总计3833 Token，预留8192，未超过授权。8个本地Docker容器全部清理确认。基础设施失败0，业务VERIFIED 1、可信反例导致FAILED 1。合计客户端任务时间57.344秒（不包含准备、重启、分析）。估算模型费用$0.00180120，不是发票结算金额。

没有本轮UNKNOWN_BILLING、模型超时或429，不存在自动重发。最终服务健康空闲。历史与新配额均保留；模型journal无未决状态，D路径同时以其calls/usage和全局计数核对。

## 证据与图表

原始JSON、CSV、accepted、轮询报告、调用ledger及integrity.json在上述raw目录。run-index.csv同时列出服务器Run ID与客户端ID，不能混淆。check验证全部5份新旧原始记录通过。

analysis/index.html、statistics.json、pairs.json、summary.csv及PNG/SVG由现有离线分析入口生成。该汇总按真实Live与无模型Docker分组，未混入Demo Replay或合成结果。actual_model_id由响应读取，不从配置推断。未获取真实TTFR、模型精确总延迟和资源峰值，不以0填充。

本轮费用来自API usage与调用时catalog的pricing生成的估算。此前独立公开目录连接超时未被重试，本轮没有增加额外付费smoke请求。

## 下一批模型对比建议（未执行、未授权）

保持同一Inventory snapshot、冻结hash、验收、单请求4096输出、无解释/对抗/恢复、串行、无重试。当前服务allowlist只有默认DeepSeek，先只通过无付费目录查询确认两个候选的精确ID/能力/价格，并由用户批准加入allowlist。

建议候选核对方向：历史目录中的glm-5.3-flash、mimo-v2.6-flash，仅作待确认候选，当前可用性/费用未核实。每个候选先1次生成，最多2次/8192输出；当前默认模型本次1次结果可作探索性参照，但不同时间的单次结果不能宣布普遍排名。更可靠的每模型3次实验应作为之后单独固定批次，不自动扩大。

预算应在执行前重新读持久计数，按本批次新增调用和预留量设置窄额度；不能把长期100次上限作为执行100次的批准。没有美元硬限额时必须说明价格/usage估算的不确定性。

## 修改范围

只改变本地服务启动参数、Benchmark Manifest/配置和证据输出；备份并保留持久数据。没有修改TrustBound核心代码或资源上限，没有VM部署、生产攻击、Commit或Push。
