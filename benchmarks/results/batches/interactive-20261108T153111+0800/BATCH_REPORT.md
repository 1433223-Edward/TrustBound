# TrustBound 真实无付费实验批次

批次interactive-20261108T153111+0800；本地Docker Desktop/cgroup v2，不是Rootless VM。

完成3次任务，无执行器故障、无重试，共4容器；资源配置检查、工作区完整性及清理均确认。模型生成0次，本轮模型费用$0。

## 项目与源码

专用Inventory项目69e7990423e3492a8b572205116b12b2，revision=2；snapshot_hash=5f0e2b5a7a6ed4462cb53044f2fc370c5ebd404575de996f8f975f752789a247；frozen_hash=9f9e2203345b75adee51b5836f03caab666a364eec9d0d3f80c6105b59a26bd4。

服务PID38888工作目录为本仓库，源码文件修改时间均早于服务启动。工作区非干净，source_commit仅作基线HEAD；实际本地源码文件哈希另存source-provenance.json，不声称是干净发布。

## 真实服务器Run ID

- E-OFF：1efbe5db76fb44d9b3a2db5f10a655aa。EXECUTED_UNVERIFIED，安全CONFIRMED，1容器，客户端16.469秒。
- E-ON：003b9588dfcf4958a54fd75f13915177。FAILED/WORKSPACE_CASE_MISMATCH，安全CONFIRMED，首个公开用例MISMATCH，1容器，客户端4.218秒。
- D-OFF：962d3363196d46edaa3fff403def161b。VERIFIED，2容器，客户端10.313秒。没有对抗调用。

run-index.json/CSV保存服务器Run ID和客户端记录ID。Toolkit record.run_id是客户端ID；真实服务器ID以accepted.json及原始报告run_id为准。封存的原始文件未修改。

## 结论及限制

E配对源码及冻结验收一致。ON暴露了OFF不检查的库存部分扣减缺陷；ON首例失败后短路。OFF先执行可能包含启动/缓存成本，ON客户端耗时少12.251秒不能解释为开启验证会加速。两组各只执行1容器，未完成全部5用例，不能宣称全用例覆盖或稳定性能优势。

D-OFF只证明固定候选通过声明验收，不证明普遍正确；D-ON未运行，pairs.json的INVALID_PAIR表示尚未成对，不是实验器故障。

actual_model_id=null在本批次是不适用，不是模型身份丢失。D底层usage.billing_status=UNKNOWN但calls=[]，没有本轮已发送且未知计费请求。与Vultr Live、历史Docker、Demo Replay及合成输入分开计数。无真实资源遥测和模型精确请求耗时，相关字段null。

## 证据与图表

三个原始JSON/CSV目录见run-index.json，各自integrity.json均验证通过。analysis/index.html、summary.csv、statistics.json、pairs.json和PNG/SVG已生成。图表group1=E-ON、group2=D-OFF、group3=E-OFF；paired-overhead仅为这对客户端总耗时差，不是纯验证函数耗时。

离线汇总写入曾因系统默认GBK解码UTF8发生错误，已显式使用UTF8完成报告；未因此重复提交任何真实任务。

## 后续付费批次：未执行

本地目录只公布deepseek-v4.1-flash-1017。这是目录/allowlist交集，真实响应模型必须从首个授权业务请求response_model确认，不另发付费smoke。

公开无凭据价格目录GET超时（WinError10060），未重试。仅有11月3日历史价：输入$0.15/百万tokens、输出$0.60/百万tokens，不能当作当前价格或最大费用保证。

建议首批仅B基线1次+D-ON1次：同一模型，最多2次生成，每次4096输出tokens，总8192；关闭解释、恢复和重试。按每次16000输入tokens的规划假设及历史价格，合计估算$0.0097152。这不是最大费用；服务仅强制请求数及输出tokens，没有美元硬上限，不能承诺不超过某个美元预算。

只读账本runs=40、calls=8、tokens=30720；模型journal仅2条FINALIZED，无未决状态。启动器未见显式覆盖参数，脚本默认max_runs=40，因此不能假定还有运行额度。未改配额、重启服务或清空账本。

paid-batch-proposal.json列出需用户单独批准的候选绝对限额：runs=42、calls=10、output_tokens=38912；执行前须重新核对消费量。这些提案未应用。多模型B因只有一个可用模型暂缓；C另需冻结规模项目及4次生成的后续批次，不伪装已经ready。

## 本轮边界

没有修改核心代码/限制、安装依赖、切换正式模型或额度；无VM部署/安全攻击/Commit/Push。只创建专用项目、Manifest与结果。付费阶段停在授权前。
