# SNInsightTerminal 专业终端重构任务拆分

本文档把专业前后端终端重构拆分为四轮 Prompt。每轮都必须保持旧 UI、旧 API 和现有测试兼容，不允许引入真实 API key，不允许接入实盘交易接口，不允许承诺收益。

## 总体原则

- 旧 `ui_web/index.html` 不删除，直到新终端通过验收。
- 旧 `/api/*` endpoint 不删除，新增 `/api/terminal/*` 聚合接口。
- 新前端默认只展示中文业务字段，技术细节进入折叠区。
- 前端不生成假概率、假预测、假交易点位。
- 观望、degraded、低数据质量、edge 不足时不显示交易点位。
- 所有预测、报告、持仓情景仅为量化投研参考。

## Prompt 11：后端 terminal API 和 schema 重构

### 目标

建立面向新终端的后端聚合 API，使前端不再直接依赖分散的旧 endpoint。保持旧 API 完全兼容。

### 主要任务

1. 新增后端目录：

```text
src/sn_futures/api/
  __init__.py
  dependencies.py
  routers/
  schemas/
src/sn_futures/terminal/
  terminal_service.py
  summary_builder.py
  snapshot_builder.py
```

2. 新增 schema：

- `TerminalSummary`
- `TerminalSnapshot`
- `TerminalPredictionCard`
- `TerminalModelHealth`
- `TerminalLearningStatus`
- `TerminalBacktestDiagnostics`
- `TerminalPositionScenario`
- `TerminalReport`
- `TerminalDataStatus`
- `TerminalSystemHealth`

3. 新增 endpoint：

- `GET /api/terminal/summary`
- `GET /api/terminal/snapshot`
- `GET /api/terminal/predictions`
- `GET /api/terminal/model-health`
- `GET /api/terminal/learning-status`
- `GET /api/terminal/backtest-diagnostics`
- `POST /api/terminal/position-scenario`
- `GET /api/terminal/reports`
- `GET /api/terminal/data-status`
- `GET /api/terminal/system-health`

4. 保持兼容：

- `v2_api.py` 不删除。
- `api_server.py` 现有路径不删除。
- 新 terminal API 内部复用 `services/` 和 `v2_api.py`。

5. 增加 OpenAPI 准备：

- 如果继续使用 `ThreadingHTTPServer`，先用 schema 文档和测试替代 OpenAPI。
- 如果切换 FastAPI，必须提供兼容适配，不影响旧启动入口。

### 测试

新增或更新：

- terminal summary payload 测试。
- terminal snapshot payload 测试。
- terminal predictions 中文字段测试。
- terminal position scenario 观望/合规测试。
- terminal API JSON 不含 NaN。
- 旧 `/api/predictions/live` 等 endpoint 兼容测试。

### 验收

- `pytest -q` 仍通过。
- `unittest` 仍通过。
- 旧 UI 仍能打开。
- 新 `/api/terminal/*` 返回稳定中文合同。

## Prompt 12：新增 Vite React TypeScript 中文终端前端

### 目标

新增 `frontend/`，构建专业中文终端，但不覆盖旧 `ui_web/`。

### 主要任务

1. 新增前端工程：

```text
frontend/
  package.json
  vite.config.ts
  tsconfig.json
  index.html
  src/
    main.tsx
    App.tsx
    api/
    components/
    pages/
    charts/
    hooks/
    types/
    utils/
    styles/
```

2. 页面：

- 总览大盘。
- 七周期预测。
- 因子分析。
- 事件监控。
- 回测与 Walk-forward。
- 模型治理。
- 持仓情景。
- 报告中心。
- 数据源状态。
- 系统设置。
- 技术明细。

3. 视觉风格：

- 深色金融终端。
- 全中文。
- 红色偏多、绿色偏空、灰蓝观望、琥珀数据异常。
- 卡片高信息密度，但支持展开详情。
- 合规免责声明固定可见。

4. 前端安全：

- 不输入、不保存、不展示 API key。
- 不把 key 放入 bundle。
- 不显示英文调试文案。
- 缺字段显示中文错误，不做假兜底。

5. 图表：

- 历史区/预测区分离。
- 最新价、预测中枢、上下区间。
- 方向概率副图。
- 区间宽度副图。
- 事件标记、换月点、数据异常标记。

### 测试

- `npm run typecheck`
- `npm run build`
- `npm run lint`，如果配置。
- UI 中文文案扫描。
- API 失败不白屏测试。
- 观望不显示交易点位测试。

### 验收

- 新前端可通过 Vite dev server 打开。
- 旧 UI 不受影响。
- 七周期预测、模型健康、学习状态、持仓情景和报告中心均接真实 API。

## Prompt 13：前后端联调与本地静态托管

### 目标

让新终端可由 Python 后端静态托管，保留旧 UI 作为 legacy fallback。

### 主要任务

1. 路由规划：

- `/terminal`：新 React 终端。
- `/legacy`：旧 `ui_web` 终端。
- `/`：验收通过前仍可指向旧 UI；验收通过后切换到新终端。

2. 静态资源：

- `frontend/dist` 构建产物进入 `src/sn_futures/static/terminal/` 或打包资源目录。
- PyInstaller spec 收集新静态资源。

3. Vite proxy：

- dev 模式代理 `/api` 到 `http://127.0.0.1:8765`。

4. Windows 启动脚本：

- 启动后端。
- 打开 `/terminal`。
- 如果新终端失败，提供 `/legacy` 回退入口。

5. README 更新：

- 新终端开发命令。
- 新终端构建命令。
- legacy fallback 说明。

### 测试

- 源码运行 API smoke。
- Vite dev server smoke。
- 后端静态托管 smoke。
- PyInstaller 产物 smoke。
- `/terminal` 与 `/legacy` 均可打开。

### 验收

- 新终端可由本地 API server 托管。
- 旧 UI 仍可访问。
- 打包后静态资源路径正确。

## Prompt 14：终端最终验收

### 目标

完成发行前终端验收，确认后端、前端、数据安全、合规和打包质量。

### 检查项

1. 后端测试：

```powershell
python -m compileall -q .
pytest -q
python -m unittest discover -s tests -p "test*.py" -v
```

2. 前端测试：

```powershell
cd frontend
npm install
npm run typecheck
npm run build
npm run lint
```

3. UI 中文检查：

- 普通界面不出现英文调试字段。
- 技术字段仅在“技术明细 / 开发调试信息”折叠区。
- 长文本可展开，不撑破布局。

4. key 泄露检查：

- `.env` 不提交。
- `.env.example` 仅占位符。
- 前端 bundle 无 key。
- 日志不打印完整 key。

5. NaN 检查：

- API JSON 不含 NaN / Infinity。
- 报告不显示 `nan`。
- UI 缺失值显示中文状态。

6. 观望/降级交易点位检查：

- 观望无 entry / stop_loss / take_profit。
- degraded 模型无交易点位。
- 低数据质量无交易点位。
- trade_edge <= 0 无交易点位。

7. 文档与验收报告：

- `README.md`
- `RELEASE_NOTES.md`
- `docs/VALIDATION_REPORT.md`
- `docs/TERMINAL_ARCHITECTURE.md`
- `docs/TERMINAL_REBUILD_TASKS.md`

8. 发行检查：

- `release/` 只保留正式安装包。
- 旧安装包归档。
- 覆盖安装不丢用户数据。
- 新装、无网、断源、缓存过期均有中文提示。

### 验收输出

- 测试结果。
- smoke 截图或日志。
- 已知限制。
- 是否可以发布。
- 合规声明。

## 风险点

- 前端工程化会引入 Node 依赖，需避免与 Python 打包流程冲突。
- React build 产物路径必须兼容 PyInstaller。
- 新终端不能把旧前端兜底逻辑带回来。
- 新 API schema 必须稳定，否则图表和页面会频繁破裂。
- 新终端上线前必须保留 `/legacy`。

## 是否可以进入 Prompt 11

可以。当前后端服务层和 97 个测试为 Prompt 11 提供了足够稳定的基础。建议先新增 `/api/terminal/*` 聚合与 schema，不急于切换框架或替换旧 UI。
