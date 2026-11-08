# Stage 5B 私有 Runner

> **Historical Stage Record — Not the Current Release State.** This document preserves the Stage 5B installation and validation record. The current public/private deployment boundary is documented in [the deployment operations guide](../docs/TrustBound_Deployment_Operations_Guide_2026-11-08.md).

FastAPI 继续监听 `127.0.0.1:8000`。启用私有 Runner 配置后，Web 进程只使用
`/run/trustbound-runner.sock`。该 socket 由 systemd 创建，仅 Web 账号可连接，
Runner 再使用 Linux peer credentials 验证对端 UID。Runner 从自己的
`/run/user/<uid>/docker.sock` 访问 Rootless Docker，无后端密钥配置。

IPC 只允许固定任务、验证阶段、候选内容及哈希。公开测试与正式验收来自 Runner
所在发布版本，对抗测试由 Runner 从有上限的金额数据和现有可信参考规则重建。
Web 对返回的阶段、镜像、候选及测试哈希做匹配。连接或证据失败返回
`INCONCLUSIVE`，部署模式不会退回 Web 进程调用 Docker。开发环境保留原本地入口。

Rootless 容器使用已验收的挂载布局。Runner 的 `0700` 主目录只在宿主侧可见，
每次只挂载其中的一个临时子目录，容器 UID 65534 可读，挂载仍为只读。
Runner 启动时检查 Rootless 模式、cgroup v2/systemd 和 CPU、内存、PID 委派。
这些检查与现有容器配置检查配合使用，实际限额由 VM 内探针验收。

## 人工安装与验收

先由操作员按现有发布流程构建并激活包含本改动的已审核 SHA。使用
`deploy/install-runner.sh` 注册 socket、Runner 服务和 Web drop-in。该脚本
检查两个服务账号的权限、私有工作目录及 Runner Docker socket，安装后只 reload
systemd。Runner 的 drop-in 在 `ProtectHome=tmpfs` 下只挂回自身 UID 的运行目录，
使 Docker socket 可见并能跟随守护进程重建。由操作员在任务空闲时启动 socket、
重启私有 API。之后正常请求会启动
Runner。不要更改 Caddy 的 503 阻断或启用 Live。

通过私有 API 验收 fixed、original、public_only、unauthorized、timeout 和
double_rounding，再用 offline adversarial/recovery 检查反例及版本证据。
应检查 Worker 的实际 UID、Web 对两种 Docker socket 的拒绝、每次容器清理及
Runner 不可用时的 INCONCLUSIVE。VM 的 systemd 与 Docker 联调需要实际完成后记录。

回滚时先等私有任务结束。停用 Web Runner drop-in、reload systemd，并停止
Runner 服务与 socket，然后按现有发布流程切回上一版并重启私有 API。
回滚到 Stage 5A 的私有 API 仅用于读任务和健康检查。公网配额、认证、证据磁盘
配额和异常退出后的容器回收仍需要单独验收，公网执行维持阻断。
