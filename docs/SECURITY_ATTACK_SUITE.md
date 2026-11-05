# Security Attack Suite A1–A5

这套实验由运维人员在私有 Ubuntu VM 启动。它复用独立 Runner 的 Rootless Docker
连接检查、固定镜像、容器限制、只读挂载、超时和清理逻辑。攻击探针由 Runner
账号下的专用 CLI 运行，Web API 和业务 Unix Socket 都没有新增攻击入口。
该路径独立于正常任务的 socket 激活，Stage 5B 的服务隔离仍由其单独验收覆盖。

- A1 策略层复用固定 `unauthorized` 用例，要求拒绝、零容器、正式验收文件哈希不变。
  运行时另起容器，实际尝试写入 `/work`、根文件系统和宿主合成标记路径。
- A2 在容器内对文档专用地址 `192.0.2.1` 做 UDP 路由查询，不发送报文；
  同时要求接口列表只有 `lo` 且返回 `ENETUNREACH`。
- A3 在 Runner 侧设置临时环境诱饵和合成文件。探针仅记录可见性和读取错误，
  不打印值，不读取真实密钥内容。宿主侧验证合成文件完好。
- A4 要求探针确实进入循环、Runner 触发超时、退出码为 137、容器已清理。
- A5 先读取容器实际 `memory.max` 和 `memory.swap.max`。只有确认 128 MiB、
  无 swap 后才触及内存，最多请求 160 MiB。退出码 137 必须同时有 Docker
  `OOMKilled=true` 才能通过。

## VM 操作与验收

在审核后的发布中保留 `RELEASE_COMMIT`。运行前确认私有 API 健康、任务空闲、
Live 关闭。每项运行时用例前后都检查这些状态。操作员安排独占验收窗口，
避免与浏览器任务同时运行。不会自动调用 Vultr，也无需把模型密钥交给 Runner。

Ubuntu SSH 中以 `linuxuser` 执行。命令假定已按现有发布流程将含本套件的版本
切换到 `current`。

```bash
(
  set -e
  umask 077
  cd /srv/trustbound/pointers/current
  evidence=$(mktemp /home/linuxuser/trustbound-attacks.XXXXXX.json)
  printf 'Evidence: %s\n' "$evidence"
  sudo -H -u trustbound-runner -- \
    ./.venv/bin/python -B -m trustbound.attack_suite > "$evidence"
  python3 - "$evidence" <<'PY'
import json
import sys
with open(sys.argv[1], encoding="utf-8") as f:
    report = json.load(f)
print(report["run_id"], report["status"])
for row in report["results"]:
    print(row["case_id"], row["layer"], row["status"])
PY
)
```

预期一条策略记录和五条运行时记录均为 `PASS`。失败时保留 JSON，并查看
`reason`、`observations`、Docker 退出状态与清理字段。报告中的 Docker 限制
配置与实际触发证据分开，只有实际观测满足判定才通过。异常时可能提前停止，
报告不会把未运行的用例计为成功。

A6–A8、Containment Lab 界面和公网接入均属后续范围。Windows 单元测试只验证
证据判定与既有流程，Ubuntu VM 才能提供这套 Rootless 实验的验收证据。
