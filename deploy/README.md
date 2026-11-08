# Stage 5A — Deployment Readiness

> **Historical Stage Record — Not the Current Release State.** This Stage 5A baseline preserves its original deployment gates. For the current two-profile topology, paths, commands, and evidence boundary, see [the deployment operations guide](../docs/TrustBound_Deployment_Operations_Guide_2026-11-08.md).

Stage 5B 的私有 Runner 接入与人工验收步骤见 [PRIVATE_RUNNER.md](PRIVATE_RUNNER.md)。
下文保留 Stage 5A 审计基线，公网执行仍由现有 Caddy 配置阻断。

**结论：Linux 私有验证可进入准备阶段；完整公网执行 NO-GO。**
本目录不是已验收的完整云部署。当前 Caddy 仅发布静态 Demo，所有 /api 请求返回 503。
这可以审查页面与部署基础，但不满足 Hackathon 的完整在线执行目标。不要移除封锁绕过下列门禁。

## 当前实现审计

- FastAPI 入口 trustbound.api:app；Ubuntu 使用 Python 3.12，与当前 AST 检查一致。
  requirements-web.txt 固定 fastapi0.162.0/uvicorn0.54.0；测试额外使用 httpx0.28.1。
  这些是仓库版本，不代表 Ubuntu wheel 安装已验证。
- 前端 Vue3/Vite7，Node>=22.12；npm ci 使用 package-lock.json，npm run build 生成 frontend/dist。
  浏览器请求同源 /api；Vite 的 localhost8000 代理只在开发服务器中生效。
  生产环境应由 Caddy 转发，不能将 Vite dev server 暴露公网。
- runner.docker 优先查 PATH 中 Docker CLI，仅在 Windows 找不到时回退 Docker Desktop 路径。
  核心逻辑不要求 WSL2 或 Docker Desktop，Linux 路径来自 pathlib/tempfile。
  但是 Linux POSIX 权限未验收：TemporaryDirectory 通常0700，而容器 UID/GID65534 可能无法读取
  挂载目录；rootless 下还存在 subordinate UID 映射。不能把 Windows 测试视为 Ubuntu 测试。
- 固定镜像 python@sha256:b18b261e1b4974b4f321451ad5251ded85abb22c2b8b262da527dda1d031ab30。
  只挂载临时两文件工作区到 /work、readonly；没有 Docker socket、凭据或项目树挂载。
  容器 readonly rootfs、network none、UID65534、cap-drop ALL、no-new-privileges，
  内存/交换上限均128MiB、CPU0.5、PID32；宿主 wait 超时3秒，finally rm -f 并查询确认清理。
- Docker local 日志轮转 max-size1m/max-file2，但不是宿主 capture_output 的显式字节硬上限。
  捕获输出和报告的复制、磁盘使用仍需限额；模型响应另有1MiB读取上限，控制请求体4096字节。
- RunManager 单进程、单执行线程，忙时429、内存保留50作业；不能增加 workers。
  reports 保存到 service.ROOT/artifacts/web-runs/服务端UUID/report.json，临时写再 replace。
  服务重启不恢复内存作业；磁盘证据保留，没有保留期限、磁盘配额或孤儿容器回收器。
- 候选及测试 SHA256、正式报告 ID、每轮 Recovery 的前驱哈希和独立结果已实现。
  Gate D 最终报告 gate-d-final-f6e0f8a35e3a43b980899d9bac816981.json 为 VERIFIED，
  候选69226f0e9244d6dfedde7d8c2a9a5f3a1e5091b1f569ebe5053bc9817d088eb8。
- .env 在本地存在且被 Git 忽略，没有读取或复制密钥内容；生产通过 systemd EnvironmentFile
  注入，TRUSTBOUND_LOAD_DOTENV=0。Caddy 只读 frontend/dist，不提供证据目录。
- 当前 Git HEAD 为53e9970d428c3355d682250be9b029cefeda8c1d，工作区有大量 Stage1–4 未提交文件。
  当前 HEAD 不能代表已验收工程；部署脚本会检查指定 Commit 是否包含当前必要模块。
  本轮不替用户提交或推送。请先人工审查、排除凭据后创建可复现版本。
- 多个 Gate D 测试依赖 gitignored artifacts 中的真实报告；全新 checkout 无法直接重现全部测试。
  下阶段需要把经过审查的脱敏证据转为明确测试资源/外部验收包，不能自动打包整个 artifacts。

## 公网阻断项

1. Web 进程通过线程调用现有 runner，拥有完整 daemon 权限。rootful docker 组等价于极强宿主
   控制权；不能将 Web 加入 docker 组，也不能把 socket 挂到 Web 容器。Rootless 也不是 Docker
   参数白名单：持有该 socket 的 Web 进程仍可管理该用户全部容器和可访问挂载，因此仅改 rootless 不够。
2. 没有请求速率限制、用户/评委访问控制、跨任务的全局提交/模型次数/Token 配额。单并发与
   每任务预算不能阻止连续重复请求。需要重启后仍有效的总预算，不能用进程重启清零规避。
3. 当前 TaskInferenceBudget 每任务最多14次生成 HTTP 尝试/14336预留输出 Token；客户端通常
   30秒、最多2次，仅429重试；Recovery 默认最多2次。Gate B/C/D 独立脚本使用另行授权的
   2048/4096单次配置。Web live 仍使用原默认提案/对抗配置，不能声称已采用 Gate C 成功参数。
   统一 Web Live 展示与预算仍需验收。没有全局美元账单硬上限。
4. API TrustedHost 仅 localhost/127.0.0.1；Origin 只允许本地端口。公网域名需明确白名单和认证。
   不应通过删除 Origin 检查、伪装本地 Host 的方式绕过。无 Origin 请求目前可提交，Origin 不是认证。
5. 控制器软故障 finally 清理已验证，但 SIGKILL、daemon/VM 崩溃、磁盘满的恢复未验证。
   需要专属 worker 容器标记、启动时对账和有界回收，不得批量删除其他容器。
6. 外层 API 错误已脱敏；ExecutionResult.error 仍可能包含 Docker stderr/宿主路径。
   公开报告需要日志/内部路径访问策略。报告 UUID 难猜不等于访问控制。

## 推荐最小目标架构（尚未实现 Runner 分离）

公网 HTTPS -> Caddy -> 静态 Vue + 仅 loopback Web API -> 受限本地 IPC -> 独立 Runner 用户/进程
-> 专用 Rootless Docker -> 一次性容器。模型凭据只留 Web/可信编排进程，Runner 不接收凭据。

Runner 仅接受预定义 Task ID、允许路径的受控候选内容/哈希和固定 phase；不接受客户端镜像、
挂载、Docker 参数、Shell、任意宿主路径或测试脚本。可信测试从不可变 Release 装入。
服务端现有 ExecutionResult/VerificationReport 和 Agent 决策流程保持原样，在
runner._execute_fixed_tests 边界加窄 IPC 适配器即可，无需另造 Executor/Verifier。
鉴于这是跨进程权限调整，5A 只提出接口和门禁，不自行实现。

Ubuntu24.04 rootless 需 uidmap、subuid/subgid、AppArmor 配置、systemd user service/cgroup v2
委派；不可为省事关闭 AppArmor 或全局放开用户命名空间限制。必须验证 memory/cpu/pids 真正
生效，不只看 inspect。临时工作区权限应在专属私有 spool 中设计供映射 UID 读取的只读 staging，
保持容器 UID65534/readonly mount；不使用 chmod777，不挂项目根目录或密钥目录。

## 文件作用与发布边界

- Caddyfile：HTTPS 静态页面，/api 与 /api/* 全部503，没有 reverse_proxy；默认不记录访问日志。
- public_readiness.py：当前架构固定返回 public_execution_ready=false/退出2；没有 force 开关。
- trustbound-api.service：本机8000、单 worker、独立 web 身份，禁止 daemon socket 与 /run/user
  访问，不属于 docker 组。用于私有健康检查，不是可执行 Sandbox 的生产服务。
- backend.env.example：仅空密钥和关闭 Live 的配置模板，安装到 /etc/trustbound/backend.env，0600。
- init-host.sh：经人工授权后在 Ubuntu 建独立身份、目录及私有 unit；不装 Docker、不启动服务。
- prepare-release.sh：作为 trustbound-deploy 从完整40位 Git SHA 导出，检查禁用 env 文件，
  安装到该 Release 的独立 venv，npm ci/build。构建前取消 Vultr 环境变量，不复制本地 .env。
  指定 Commit 不含当前代码会拒绝。存在同 SHA Release 时拒绝覆盖，失败目录需人工审查处理。
- activate-static.sh：原子切换静态 current 链接，记录 previous；重复同版本不覆盖 previous。
- rollback-static.sh：切回 previous。只切静态；私有 API 必须确认空闲后另行重启，无数据迁移。
- healthcheck.sh：无 POST/模型调用。私有健康检查不能证明 Runner/Inference 可用；
  --public-static 还验证公网 /api/health 确实503，防止意外放开执行。

构建使用 Commit + 前端 lockfile + Python直接依赖固定版本；Python传递依赖没有完整锁定和
hash manifest，因此不能声称位级可复现。上线前需冻结传递依赖和系统组件版本。
当前不打包 Web 容器，因此没有任何 image build 注入密钥；一次性沙盒只用固定 digest。

## 创建 VM 后的人工步骤与命令（本轮没有执行）

先获得用户对区域、规格、费用、SSH key 的授权；Vultr 控制台创建 Ubuntu24.04 x86_64，
建议 Shared CPU2vCPU/4GiB/80GB。安全组仅80/443公网，22仅管理IP；不开放8000/5173、
Docker2375/2376或Caddy2019。管理员安装并锁定官方 Caddy、Node>=22.12、Git、Python3.12/venv，
通过官方仓库/签名校验安装，不运行来源不明的 curl|sh。

把人工审查的仓库通过用户授权渠道放到 /srv/trustbound/source；构建用户仅需读权限。
不要上传 Windows .venv、node_modules、本地 .env 或整个 artifacts。

```bash
# 在已批准的 VM / 已审查源码目录执行；这些命令不启用公网执行。
sudo bash deploy/init-host.sh
# 使用真实已审查版本替换下方40位 SHA；不要使用当前不完整旧 HEAD。
sudo -u trustbound-deploy bash deploy/prepare-release.sh /srv/trustbound/source FULL_40_CHAR_COMMIT_SHA
sudo -u trustbound-deploy bash deploy/activate-static.sh FULL_40_CHAR_COMMIT_SHA
# 如要回滚静态版本：
sudo -u trustbound-deploy bash deploy/rollback-static.sh
```

DNS：人工建立域名 A -> VM IPv4；仅在配置好 IPv6/防火墙后加 AAAA。
在 /etc/caddy/Caddyfile 安装本文件，并给 Caddy systemd 进程注入 TRUSTBOUND_DOMAIN。
不能只在当前 shell export 后假定系统服务继承；可由管理员在 Caddy unit drop-in 设置非敏感域名。

```bash
# 使用真实域名；只校验配置不创建模型请求。
sudo env TRUSTBOUND_DOMAIN=demo.example.com caddy validate --config deploy/Caddyfile --adapter caddyfile
sudo systemd-analyze verify /etc/systemd/system/trustbound-api.service
# 完成 DNS/防火墙后，管理员按官方安装方式启动 Caddy，验证证书、80跳转443。
bash deploy/healthcheck.sh --public-static demo.example.com
# 可选的私有 API 健康检查：先用下面工具确认公开执行仍被阻断。
python3 -B deploy/public_readiness.py   # 预期退出2，不能作为成功上线的检查
sudo systemctl start trustbound-api
bash deploy/healthcheck.sh
```

私有服务 EnvironmentFile 由管理员在 VM 上安全编辑，不回传密钥、不放 Git。5A 模板保持 Live=0，
不要提前填真实密钥或启用推理。未来 worker 拆分后再单独授权密钥部署与付费测试。
Caddy 自动签证书需要域名解析和对外80/443可达；这些尚未在 VM 上验证。
运行证据只写 /var/lib/trustbound/evidence，0700，不在 Caddy 根目录。
暂不自动删证据/旧 Release；人工检查磁盘空间并制定保留策略，不能保留无限版本。

## 本地验证与未验证项目

- 86项后端回归通过、46项前端测试通过、Vite生产构建通过。
- Git Bash 的五个脚本 bash -n 通过；Python readiness 文件 AST解析通过。
  首次 Bash 在 Windows 沙箱内被 MSYS权限限制阻止；沙箱外原样语法检查通过，没有执行脚本。
- public_readiness.py 实际返回 false/退出2；没有公开 API 转发路径。
- 没有安装 Caddy/systemd，不能运行其原生解析器；文件只做静态内容审阅，必须在 Ubuntu 执行上面校验。
- 没有执行初始化、构建发布、切换、回滚、SSH、DNS、TLS或 Rootless Docker 安装/测试。
  bash -n 不证明这些流程运行成功。没有新云资源或付费模型请求。

## 费用、人工操作及 Stage5B–5D

本次只读查询官方 API https://api.vultr.com/v2/plans?type=vc2&per_page=100 得到
vc2-2c-4gb：2CPU/4096MiB/80GB/3072GB流量，$20/月、$0.027/小时。约5天基础费$3.24，
实际区域、库存、税费、额度适用服务和结算以创建页/账单为准；不假定$200额度可覆盖所有项目。
备份可能额外20%；快照、流量超额、额外IPv4/存储、域名和 Inference 可能另外收费。
实例关机仍计费，不能用关机作为停止资源账单的方法。涉及删除资源仍需人工授权。

5B（另行授权）：准备VM/SSH/DNS/版本，并实现窄 Runner IPC + 专属 rootless身份；补全域名策略、
访问控制、速率限制、持久化总任务/推理预算、日志配额/报告隔离和有界孤儿回收。先不开放公网执行。
验收：Web 身份不能访问任何 Docker socket；客户端无法指定镜像/路径/命令；Ubuntu各限制实际生效；
SIGKILL/restart/diskfull/daemon故障不产生 VERIFIED；真实密钥和内部证据不公开。

5C：用户明确授权后，启用带访问控制的 HTTPS 执行入口，使用批准预算做一次完整 Live Web 验收。
验收：浏览器操作生成真实模型台账及 Docker证据，包含失败/拒绝/超时和Recovery停止条件；
评委访问范围与全局次数/费用预算可核对。未通过不得解除公开执行503。

5D：冻结已审查Commit与依赖、部署清单和脱敏验收报告，演练静态/后端版本回滚、证据保留、
启动停止与费用关闭流程，准备评委演示和提交包。验收：能从指定版本复建、健康检查和回滚均通过，
没有未说明的安全阻断项；不自动进入下一阶段。

## 官方参考

- Docker Rootless: https://docs.docker.com/engine/security/rootless/
- Ubuntu24.04 rootless/AppArmor: https://docs.docker.com/engine/security/rootless/troubleshoot/
- Docker daemon security: https://docs.docker.com/engine/security/
- Caddy: https://caddyserver.com/docs/caddyfile/directives/respond
- Vultr plans: https://api.vultr.com/v2/plans?type=vc2&per_page=100
- Vultr backup billing: https://docs.vultr.com/support/platform/billing/how-much-does-it-cost-to-enable-automatic-backups
- Vultr stopped-instance billing: https://docs.vultr.com/support/platform/billing/are-stopped-instances-still-billed-on-vultr
