# 最终GLM协议诊断与Benchmark冻结

状态：BENCHMARK_FROZEN。已按批准执行且只执行一次新GLM生成，无重试、无MiMo调用、无后续扩展实验。

## 本次真实诊断

服务器Run ID：2434e519a3394b2abc1d7b156f08dadd。
客户端记录：dbe28d0b477e47c8b127834afc9f877c。
原始JSON/CSV及调用证据：benchmarks/results/raw/dbe28d0b477e47c8b127834afc9f877c。

与前次相同Inventory项目、revision2、源码snapshot_hash与冻结验收；model glm-5.3-flash、单次4096输出、reasoning预算1536、无解释/对抗/恢复。默认模型未切换。服务加载的是仅细分错误码的补丁，安全及提案接受/拒绝规则未变。

真实response_model=glm-5.3-flash；attempt=1，finish_reason=stop。输入741、输出1969、总计2710 Token；预留4096。客户端总耗时10.313秒。估算费用$0.00076325，低于用户预留$0.01，但估算不是发票或美元硬限制。

最终INCONCLUSIVE，精确reason=WORKSPACE_PROPOSAL_INVALID_SHAPE。新补丁的错误分类已在真实模型调用上生效：这一次JSON解析和重复键检查已通过，在顶层字段或files结构的检查中被拒绝，尚未进入解释Schema或业务验收。可能的具体分支包括根不是对象、字段集合不允许、files不是非空对象；没有保留响应正文，因此不能确定具体是哪一种，更不能追溯断定前次GLM也完全相同。

创建容器0，清理不适用，不是Docker清理失败。没有修补模型输出、放宽Schema或自动重发。真实业务正确性未被验证，不能把它统计成业务用例执行失败或总体模型能力差。

## 批次关闭与保护

账本43/11/43008 -> 44/12/47104，恰好增加1次任务、1次调用、4096输出预留。无未决/UNKNOWN_BILLING，journal FINALIZED=5，实际生成记录与计数一致。历史计数保留。

批次结束后累计调用上限保持100；运行上限44和预留输出上限47104保留已耗尽，后续生成没有授权也没有本批次剩余额度。最终本地服务健康空闲。没有美元硬限制，真正强制的是任务数、请求数和输出Token预留。

## 冻结后的B/D/E真实数据

7次真实任务，4次付费生成；模型输入2590、输出6689、合计9279 Token，估算费用总计$0.00333680（仅本系列Benchmark，不是项目全部历史消费）。12个已创建容器全部清理确认。MiMo未运行；C规模模型实验暂未运行，A仅有已有历史证据。

- B/DeepSeek：1次，5个冻结用例通过，VERIFIED。
- B/GLM：前次一般提案拒绝+本次精确INVALID_SHAPE，均未进入业务验收。两次不是成功率对比所需的对等重复设计；后一次明确标为protocol_diagnostic。
- D-OFF/ON：固定候选同验收。OFF通过；ON的3个可信输入反例确认同一双重舍入缺陷，最终降为FAILED。不能说3个独立缺陷，也没有Recovery成功结论。
- E-OFF/ON：OFF为EXECUTED_UNVERIFIED；ON首例发现库存缺陷。早退与启动开销混杂，不能声称开启验证更快。

FROZEN_RUNS.csv给出各服务器Run ID、模型、分组、费用及原始路径；FROZEN_SUMMARY.json含分母和分类。现有离线入口生成analysis/index.html、PNG/SVG、statistics.json、pairs.json及summary.csv，未混入Demo Replay或合成诊断夹具。缺失TTFR、资源峰值和精确模型请求延迟不当0，小样本不做统计显著性或普遍模型排名。

## 测试与证据边界

补丁5项离线诊断测试及7项Mock回归通过；重启后5项最小真实HTTP冒烟通过，账本不变。此前卡住的HTTP集成回归仍为INTERRUPTED_NOT_PASSED，不能因冒烟通过而改成通过。

本次以及此前7份原始记录均通过hash完整性检查。HTTP及Mock诊断不是安全攻击执行证据；本地Docker也不能称作Rootless公网VM安全验收。工作区非干净，HEAD仅作源码基线，实际代码hash另存，不伪造干净发布版本。

## Documentation / Demo交接

建议视频只重放已有Evidence Report和图表，不为录屏暗中新增模型或容器实验。可按以下顺序组织：

1. E-OFF安全执行但无业务VERIFIED，E-ON揭示库存缺陷。
2. DeepSeek单轮候选经5个可信用例验收通过。
3. 固定Billing候选原验收通过，独立对抗反例令最终结论降级。
4. GLM输出不合协议被拒绝，展示细分错误码、模型身份、成本和停止策略。
5. 说明限制：样本小、未测TTFR/资源峰值、未完成C/MiMo/新Rootless A、完整HTTP集成未通过。

对展示材料，允许写“这些明确任务上的观测”，不写“模型普遍排名”“所有安全维度通过”或“零成本”。冻结文件作为Documentation与Demo取数入口，后续若要新实验需新的固定批次授权。

无新增核心功能、安全规则变更、VM部署、Commit或Push。
