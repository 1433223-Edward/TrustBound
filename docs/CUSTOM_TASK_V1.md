# Custom Task v1 私有验收

Custom Task 与 Billing 共用 FastAPI 的单任务队列、独立 Runner、固定 Docker
沙盒和 VerificationReport。原有 Billing 路径及回归保持可用。

第一版接受单文件 Python 的 `def solve(value): return ...`、自然语言需求和结构化整数
用例。支持有界整数算术、比较和条件表达式。导入、调用、属性访问、循环、文件和命令
均超出本版本的代码策略。请求体上限 8 KiB，执行候选上限 2000 UTF-8 字节，每阶段最多
4 个互不重复的输入。

原始源码可直接验证，也可提供人工 replacement。人工候选复用 Executor 的结构化提案解析，
无模型调用。需求保留在证据里，验收范围是提交前冻结的用例。公开、正式和可选反例阶段各用
不同容器；容器只接收本阶段输入，宿主独立比较预期值。验收缺失或 Runner 证据不可用返回
`INCONCLUSIVE`。反例可推翻正式通过。Custom Task v1 的通用模型生成、模型驱动的反例
发现和自动恢复尚未实现。当前反例阶段只使用用户预先提供的输入和预期值。

## VM 私有模式

构建并激活审核后的提交后，操作员通过 `systemctl edit trustbound-api.service` 和
`systemctl edit trustbound-runner.service` 分别给两项服务加以下 opt-in。保留原有
Runner socket 配置、Rootless drop-in 和 Web 对 Docker socket 的屏蔽。

```ini
[Service]
Environment=TRUSTBOUND_ENABLE_CUSTOM_TASK=1
```

在任务空闲时重启 API 和 Runner，确认 Web `/api/health` 的
`custom_task.enabled=true`、`live_executor.enabled=false`。若要临时关闭，
将两个 opt-in 值设为 `0` 并重启这两个服务。通过现有 SSH 隧道进入 Local API，
页面底部会显示 Custom Task v1。保留 Stage 5A Caddy 的公网 API 阻断。在 Stage 5C
代理正常 API 时，继续单独阻断 `/api/custom-runs` 和 `/api/custom-runs/*`，
除非已完成自定义任务额外的公网安全验收。

在 VM 上用现有私有 API 运行以下检查。脚本只提交固定示例，无推理调用。

```bash
python3 -B /srv/trustbound/pointers/current/scripts/check_custom_task_integration.py
```

预期：人工修复为 `VERIFIED`；原始代码为 `FAILED`；正式通过但预置反例失败时总体
为 `FAILED`；缺少正式用例为 `INCONCLUSIVE`；导入被策略拒绝且容器数为 0；
命令字段返回 HTTP 422。实际容器和证据保存在后端现有 Run 记录中。

Billing 继续作为 Stage 5C 和比赛提交的稳定路径。Custom Task 的私有验收与后续模型
接入独立于 Billing 的公网交付。
