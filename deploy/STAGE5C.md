# Stage 5C：Billing 公网离线 Demo

先在 VM 上验收准入，再启用带认证的 HTTPS。管理员 Live 单独走私有链路。
公网 API 只允许 Billing 固定候选或标准 Offline Executor，可选标准离线对抗。
Custom Task、真实推理和恢复入口都关闭。FastAPI 仍只绑定 127.0.0.1，Web 进程
仍无法访问 Docker socket。现有 `deploy/Caddyfile` 保留为返回 503 的回滚配置。

## 一、私有验收准入

按已验证的 Git SHA 发布流程构建并激活本版本。确认没有运行中的任务后，
由操作者更新 Runner unit，停掉旧 worker，确保新 API 与 worker 使用同一发布。

```bash
sudo bash /srv/trustbound/pointers/current/deploy/install-runner.sh
sudo systemctl stop trustbound-runner.service
sudo systemctl start trustbound-runner.socket
```

准备独立的测试账本。该命令仅新建文件，已有账本会拒绝覆盖。

```bash
cd /srv/trustbound/pointers/current &&
  sudo -H -u trustbound-web -- ./.venv/bin/python -B -m trustbound.admission +    init /var/lib/trustbound/stage5c-test.sqlite3
```

通过 `sudoedit /etc/trustbound/backend.env` 设置下列内容。用实际 DNS 域名
替换 `demo.example.com`，不写协议、端口或路径；每个变量只保留一条定义。
保留原来的模型配置和密钥文件权限。没有 DNS 解析也能先做回环验收。

```ini
TRUSTBOUND_LOAD_DOTENV=0
TRUSTBOUND_ENABLE_LIVE=0
TRUSTBOUND_ENABLE_RECOVERY_LIVE=0
TRUSTBOUND_ENABLE_CUSTOM_TASK=0
TRUSTBOUND_PUBLIC_DEMO=1
TRUSTBOUND_PUBLIC_DOMAIN=demo.example.com
TRUSTBOUND_QUOTA_DB=/var/lib/trustbound/stage5c-test.sqlite3
TRUSTBOUND_MAX_RUNS=2
TRUSTBOUND_MIN_RUN_SECONDS=20
TRUSTBOUND_MAX_MODEL_CALLS=0
TRUSTBOUND_MAX_OUTPUT_TOKENS=0
```

重启 FastAPI。用下面的脚本完成两轮离线 Docker 验收，检查缺少 Origin、
Live 请求、超频和超额。脚本默认固定连接 VM 回环地址。

可在第一轮脚本前做故障回收演练。确保无任务，再用专用 Docker 创建一个带标记、
但不启动的容器，模拟上次退出留下的实例。保存该名称用于验证。以下命令只创建
一只本轮测试容器，不触及其他容器。

```bash
sudo systemctl stop trustbound-runner.service &&
  orphan="trustbound-$(tr -d '-' </proc/sys/kernel/random/uuid)" &&
  sudo -H -u trustbound-runner -- /usr/bin/docker --host unix:///run/user/1001/docker.sock create \
    --pull never --name "$orphan" --label org.trustbound.owner=private-web-runner-v1 \
    --network none --read-only --user 65534:65534 \
    python@sha256:b18b261e1b4974b4f321451ad5251ded85abb22c2b8b262da527dda1d031ab30 /bin/true &&
  printf 'Recovery probe container: %s\n' "$orphan"
```

```bash
read -r -p '输入与 TRUSTBOUND_PUBLIC_DOMAIN 一致的域名: ' demo_domain
sudo systemctl restart trustbound-api.service &&
  curl --fail --silent --show-error --retry 5 --retry-connrefused --retry-delay 1 \
    http://127.0.0.1:8000/api/health &&
  python3 -B /srv/trustbound/pointers/current/scripts/check_stage5c_private.py before-restart "$demo_domain"
```

如果创建了回收探针，第一轮结束后检查 `sudo journalctl -u trustbound-runner.service -n 20 --no-pager`
是否记录回收了一个容器，并检查专用 Docker 的 `ps -a` 中已无该名称。

再次重启服务并保留同一个数据库，预期 `429 RUN_QUOTA_EXHAUSTED`。

```bash
sudo systemctl restart trustbound-api.service &&
  curl --fail --silent --show-error --retry 5 --retry-connrefused --retry-delay 1 \
    http://127.0.0.1:8000/api/health &&
  python3 -B /srv/trustbound/pointers/current/scripts/check_stage5c_private.py after-restart "$demo_domain"
```

生产演示使用单独初始化的 `/var/lib/trustbound/stage5c.sqlite3`，按同样方式
运行 `trustbound.admission init`。改用该路径，设定审核后的总运行数和间隔，
例如 40 次和 5 秒，模型调用与输出额度仍为 0。保留测试账本，生产重启或发布
时继续使用原生产账本。数据库不可用时执行返回 503；不要用新账本绕过总配额。

## 二、受认证的公网 HTTPS

部署前，核实实际域名 A 记录指向 VM，公网仅开放 80/443，管理 SSH 按来源限制。
不要开放 8000、5173 或 Docker 管理端口。安装支持 `basic_auth` 的 Caddy
（2.8 或更新版本），以 [Caddy 官方 Ubuntu 安装说明](https://caddyserver.com/docs/install#debian-ubuntu-raspbian)
为准。打开公网前，先完成上面的私有配额验收和 Runner 故障回收检查。

1. 在 VM 上运行 `caddy hash-password`，用交互提示输入评委密码。用
   `sudoedit /etc/caddy/trustbound-judges.caddy` 填一行 `评委用户名 密码哈希`，
   只填哈希。新文件设为 `root:caddy`、`0640`，不放进 Git。
2. 用 `sudo systemctl edit caddy.service` 注入 `TRUSTBOUND_DOMAIN`，值为
   上面的同一个域名。保留当前配置的备份。先验证候选，再安装和启动/重载。

```bash
sudo env TRUSTBOUND_DOMAIN="$demo_domain" caddy validate \
  --config /srv/trustbound/pointers/current/deploy/Caddyfile.stage5c --adapter caddyfile
```

验证成功、备份完成后再切换配置。

```bash
sudo install -m 0644 /srv/trustbound/pointers/current/deploy/Caddyfile.stage5c /etc/caddy/Caddyfile &&
  sudo systemctl daemon-reload &&
  sudo systemctl reload-or-restart caddy.service
```

从 VM 之外验证 HTTP 跳转 HTTPS、有效证书、页面与 API 未认证均为 401、
认证后可运行 Billing 并查询报告，`/api/custom-runs` 为 404。用现有 Web 账号
复核两个 Docker socket 均不可访问。验证公开配置回滚至 `deploy/Caddyfile` 后
公网 `/api/health` 返回 503；回滚不重置预算。

## 三、管理员私有 Live

单独批准模型、最大请求次数、输出 Token、超时和费用范围后再运行。
临时关闭公网 API（使用静态 503 配置），使用 SSH 隧道及私有 API。
私有模式设置 `TRUSTBOUND_PUBLIC_DEMO=0` 并保留持久化账本，按批准额度设置
`TRUSTBOUND_MAX_MODEL_CALLS` 和 `TRUSTBOUND_MAX_OUTPUT_TOKENS`。
每次真实生成尝试（含重试）发送前扣减全局额度；不对未知账单退款。
此额度只计算生成调用和预留输出 Token，实际输入、输出和估算费用仍由现有报告记录。
关闭 Live、恢复公开离线 profile 后，重新验收公网路由。

正常 Runner 每轮清理容器。Worker 启动时只会回收自己标记的临时容器，最多
8 个，身份或清理证据不匹配即拒绝启动。要在 VM 做一次故障回收演练，核对
受控标记容器被回收、无关容器保持不变。旧版未标记容器不自动删除。
报告受单份 512 KiB 与总量 64 MiB 限制；证据存储失败会阻止启动或拒绝给出成功裁决。
现有静态 readiness 脚本保留为阻断提醒，只有真实 VM 和外网证据可确认 Stage 5C 通过。
