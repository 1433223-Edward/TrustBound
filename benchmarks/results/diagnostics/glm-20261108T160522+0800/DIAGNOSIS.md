# GLM提案拒绝诊断

目标Run ID：7a9d0a259e8546fd85b2903bb8fe393f。本轮只读排查和离线合成解析检查，0次模型请求、0次Docker执行、无服务/数据库/配额变更。

已确认：供应商调用COMPLETED且finish_reason=stop、content为字符串、长度1608，模型身份与usage已保存。随后报告为INCONCLUSIVE/INVALID_WORKSPACE_PROPOSAL，artifact_hash=null、cases=[]。这是提案进入候选前的拒绝，不是业务用例失败、网络超时、截断或Docker清理失败。

现有model_work将ValueError/TypeError/RecursionError统一映射为INVALID_WORKSPACE_PROPOSAL。JSON语法、重复JSON键、提案顶层形状、PublicExplanation嵌套Schema均可能走此路径。现有服务stdout/stderr没有该响应正文或细分错误；最终日志中的Preview API failed出现在人为停止旧服务时，不能当作本次提案拒绝的原因。

结论：已经确认诊断信息被合并，但无法从现存证据确定GLM具体违反了哪一个字段约束。原始模型正文未保存，不能追溯恢复，也不猜测GLM必然使用了错误格式。

供审核的最小补丁：PROPOSED_DIAGNOSTICS.patch，仅涉及trustbound/workspace_execution.py。保留原有JSON去重、字段集合、非空files和严格解释Schema；仅将JSON/重复键/提案形状/解释校验错误分别传成稳定错误码。不保存API Key、不保存模型推理内容、不新增模型请求或重试、不放宽Permission Gate/沙箱/业务校验。

补丁未应用。已对候选文本做AST语法检查，并用原函数的纯解析定义与假客户端做6组合成夹具的前后检查（共12次），确认接受/拒绝结果未变化；这不是实验样本或真实模型响应复现，不能解释原GLM具体失败原因。

如果批准应用补丁，还需针对错误分类添加针对性测试并重启空闲本地服务。任何GLM重试或继续MiMo均需另行明确授权；原GLM请求已经发生估算费用$0.00077235，补丁无法追溯恢复其正文。
