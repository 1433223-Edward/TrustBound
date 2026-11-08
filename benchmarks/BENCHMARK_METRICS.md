# Benchmark Metrics v1

统一按 experiment_type、dataset_version、source_commit、模型实际ID、配置、evidence_source 分层。禁止混合 Offline 模型、Live、Demo Replay；Offline 模型仍可能使用真实 Docker。

- First-pass success：首次候选可信VERIFIED数 / 完整首次候选数。未观测首次候选为null。
- Final verified success：最终可信VERIFIED数 / COMPLETED任务数；同时公布全部尝试数、失败、未知、超时。E SECURITY_ONLY不计业务成功，不能与FUNCTIONAL合并比较。
- Structured validity：符合提案schema的响应 / 已收到完整提案响应；非模型自称成功。当前离线分析未自动解析，人工留证据。
- Tool calling success、TTFR：当前非流式固定协议不提供，null。
- Recovery frequency：启动恢复的任务 / 完整可观测任务；恢复成功率=恢复后可信VERIFIED / 已启动且完整观测恢复。未支持时null。
- D confirmed findings仅计可信Verifier重现且确认；false positive需有可信反证，不将INCONCLUSIVE算误报。增量缺陷按配对源码/缺陷身份去重。现工具保存原始对抗报告，尚未自动做配对反例统计。
- Latency：客户端从提交前到终态收到的wall ms，包含轮询间隔；不等于服务端推理耗时。均值/样本标准差仅有效观测；n<5标探索性。p50/p95、队列时间需单独观测，未观测不填0。
- Cost：使用调用ledger estimated_usd，估算非发票；任一调用计费未知则任务成本null。每VERIFIED成本=完整同组所有任务估算成本合计/VERIFIED数；存在未知计费不能发布该值。失败任务费用不能丢弃。
- C源码tokens估算=ceil(UTF8字节/4)，不是模型真实token计数；依赖复杂度当前生成器为0条import边，需注明。实际files_modified来自report.changed_paths。
- F吞吐=完整结束任务数/实验窗口分钟；窗口需包括排空，失败率=失败任务/所有已提交任务。当前仅支持单任务，不能从固定任务耗时推断稳定吞吐。
- A全部定义与缺口沿用security/BENCHMARK_RUNBOOK.md。

配对差异必须同pair_id、输入hash、验收hash、模型、release及非处理配置；每组至少5重复，随机顺序由人决定。不能用不同随机候选证明对抗Agent因果收益。


v2冻结补充：F不运行；C仅1/5/10/20。D以final_decision.status记录最终验收，formal_verification_status保留初始正式验收，不把发现反例后的候选仍算最终成功。D/E配对输出pairs.json；Dcomparison_valid=false不得作有效收益比较。模型请求精确耗时、TTFR及资源峰值不可获取；服务时间戳仅保留实测起止。
