# TrustBound Web Code Workspace

独立 Vue 3 + Vite + JavaScript 前端，原生 CSS，无 UI 库。不需要启动 Python 或 Docker 即可查看 Demo。
默认回放已有报告；切换 Local API 可连接本机 FastAPI 并真实执行 Docker。
浏览器不访问 Vultr，也不接收 API Key。

## 启动与构建

在 `D:\Projects\TrustBound\frontend` 运行：

```powershell
npm ci
npm run dev
npm test
npm run build
```

开发地址 `http://127.0.0.1:5173/`；生产产物 `dist/`。Vite 固定使用本机 5173 端口，
端口被占用时明确失败，不自动换端口。使用 `npm run preview` 可预览生产产物。
Node 版本要求见 package.json；当前实测 Node 22.17.0。

predev/prebuild/pretest 都会运行 `scripts/sync-fixtures.mjs`，只读取上层仓库的真实代码与
`docs/day1-results.json`，同步至 `src/data/demo.json`，不运行候选代码、容器或模型。
源报告没有模型提案和事件时间线，因此页面不显示虚构的 Agent 生成或阶段耗时。
正式验收源码未打包到浏览器；任务目标只是可信样例的说明元数据。

## 组件与状态

- `App.vue`：页面组装、模式切换、导航和错误提示。
- `components/TaskPanel.vue`：固定任务说明、约束、场景选择、回放/执行入口。
- `components/CodeWorkspace.vue`：Original / Proposed、Diff / After 切换。
- `components/CodePanel.vue`：只读代码、行号和轻量语法着色；文本插值，不使用 v-html。
- `components/ExecutionTrace.vue`：根据报告适配六个阶段，无伪造的阶段事件。
- `components/EvidencePanel.vue`：裁决、测试结果、退出码、超时、清理、Diff 与可展开日志。
- `components/StatusBadge.vue`：统一状态标签。
- `state/workspace.js`：唯一业务状态源；模式/任务/场景切换清空证据，使旧异步响应失效。
- `api/adapter.js`：真实报告校验、阶段适配、差异分行与代码标记。
- `api/client.js`：同源 tasks / runs API，HTTP 超时、有限轮询，无自动 POST 重试。

组件通过 props 读取状态，通过 emit 请求状态模块改变；Diff/日志等纯展示选项由组件本地管理。
页面不存储 RUNNING 状态，刷新恢复初始空闲视图。

## 实际交互

默认只有一个真实任务，五个场景不是五个任务。先选择历史场景，再点击 Replay sample。
Demo 显示明确 SAMPLE 标记；正确补丁显示 SAMPLE VERIFIED，不等于实时 Agent 成功。
Run Agent 在 Demo 模式提示切换；Local API 支持 fixture / offline_executor / live_executor，
失败不回退到 Demo。fixture 显示 DOCKER 标签；offline_executor 显示 MOCK LLM，只有模型响应是模拟的。
可切换 Diff/After、证据 Overview/Raw diff/Execution logs，逐项展开 stdout/stderr；日志独立滚动。

## API 接入

契约见 `../docs/WEB_API_CONTRACT.md`，FastAPI 已实现于 `trustbound/api.py`，后端启动方法见根 README。
Vite 已代理 `/api` 到 `http://127.0.0.1:8000`，支持健康、可信任务详情、创建执行与轮询结果。
模型凭据始终保留在后端；生产部署、用户认证、跨进程队列与自动恢复未实现。

## 本轮验证结果

- `npm test`：34 项通过，包含契约适配、假成功/超时/越权展示、模式与任务重置、
  旧响应失效、POST 不重试、HTTP/JSON 异常、请求超时和轮询截止。
- `npm run build`：Vite 7.3.7 生产构建通过。
- Python/API 单元测试：33 项通过；原 26 项保留，新增 7 项 API 控制测试。
- 本地 HTTP 返回 200。实际浏览器检查初始空状态、显式加载、假成功、正确补丁、
  越权拒绝、超时证据、Diff/After、日志展开、Live 无 API 的明确错误，以及刷新重置。
- DOM 尺寸检查在 1366×768 时 document 为 1366×768，无页面横向/纵向溢出；
  回放按钮在视口内。2913 字符的正式验收 stderr 在日志区域内滚动。
- 初版浏览器测试是历史回放；本轮已通过同源代理真实触发固定候选与离线 Executor。
  六场景真实 HTTP/Docker 记录见 `../docs/web-integration-results.json`，未调用 Vultr。

## 文件清单

```text
frontend/
  README.md
  package.json
  package-lock.json
  index.html
  vite.config.js
  scripts/sync-fixtures.mjs
  src/main.js
  src/App.vue
  src/style.css
  src/api/client.js
  src/api/adapter.js
  src/state/workspace.js
  src/data/demo.json
  src/components/StatusBadge.vue
  src/components/TaskPanel.vue
  src/components/CodeWorkspace.vue
  src/components/CodePanel.vue
  src/components/ExecutionTrace.vue
  src/components/EvidencePanel.vue
  tests/workspace.test.js
```

仓库其余本轮变更：新增 `docs/WEB_API_CONTRACT.md`；`.gitignore` 增加前端依赖与构建缓存忽略项。
原有 Executor 阶段未提交的后端文件保留原状。
