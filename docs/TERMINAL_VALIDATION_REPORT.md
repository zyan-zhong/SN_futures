# SNInsightTerminal 专业终端最终验收报告

## 1. 验收结论

本轮完成专业前后端终端最终验收准备：保留旧 `ui_web` 与旧 API，不切换 `/` 默认入口，不构建安装包，只补充终端入口、静态托管、安全检查、文档和测试。

当前结论：

- 后端 `/api/terminal/*` 聚合接口可用。
- 新终端 `/terminal` 已具备静态托管能力。
- 旧终端 `/legacy` 保持可访问。
- `frontend/dist` 缺失时，`/terminal` 返回中文构建提示页，不崩溃。
- 当前 Codex 环境无法执行 Node/npm 构建，原因是 `node.exe` 返回 `Access is denied` 且 `npm` 不可用。
- Python 编译和测试通过。

## 2. 专业终端架构

专业终端采用渐进式架构：

- 后端仍使用现有 `ThreadingHTTPServer + BaseHTTPRequestHandler`。
- 旧 API 与旧 UI 保持兼容。
- 新增 `/api/terminal/*` 作为专业前端聚合 API。
- 新增 `frontend/` 作为 Vite + React + TypeScript 中文终端源码。
- 后端通过 `/terminal` 托管 `frontend/dist`。
- 后端通过 `/legacy` 托管旧 `ui_web`。

## 3. 后端 Terminal API

已验收的主要入口：

- `GET /api/terminal/docs`
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

API 输出经过 JSON 清洗：

- 不允许 `NaN / Infinity / -Infinity`。
- 敏感字段脱敏。
- 观望、degraded、低数据质量、edge 非正时不输出交易点位。
- 普通业务说明以中文为主。

## 4. 前端页面和组件

`frontend/` 已包含以下页面：

- 总览大盘
- 七周期预测
- 因子分析
- 事件监控
- 回测与 Walk-forward
- 模型治理
- 持仓情景
- 报告中心
- 数据源状态
- 系统设置

核心组件包括：

- 顶部状态栏与侧边导航
- 七周期预测卡片
- 概率、价格、权益、回撤和因子图表
- 模型健康、晋级门槛和学习状态
- 回测与成本敏感性面板
- 持仓情景输入与结果
- 报告中心
- 数据源状态面板
- 默认折叠的“技术明细 / 开发调试信息”

## 5. `/terminal` 与 `/legacy`

`/terminal` 行为：

- 若 `frontend/dist/index.html` 存在，返回新专业终端。
- 若请求 `/terminal/assets/...` 等静态资源，从 `frontend/dist` 安全读取。
- 若前端 history route 缺少具体文件但 dist 存在，返回 `index.html`。
- 若 dist 不存在，返回中文构建提示页。

`/legacy` 行为：

- 返回旧 `ui_web/index.html`。
- `/legacy/app.js`、`/legacy/styles.css` 等继续从旧 UI 目录读取。

`/` 行为：

- 本轮保持当前默认行为，不切换到新终端。

## 6. 静态托管安全

已实现并测试：

- 禁止 `..` 路径穿越。
- 限制静态读取目录为 `frontend/dist` 与 `ui_web`。
- 支持常见 MIME：HTML、JS、CSS、JSON、SVG、PNG、ICO、WOFF、WOFF2。
- 403/404 不返回本机敏感绝对路径。
- 不读取、不返回 API key。

## 7. Node/npm 构建状态

当前 Codex 环境检测结果：

- `node -v`：失败，`node.exe Access is denied`。
- `npm -v`：失败，`npm` 不可用。

因此本轮未执行：

```powershell
cd frontend
npm install
npm run typecheck
npm run build
```

这不是项目代码失败。需要在用户本机修复 Node.js LTS 安装或权限后运行：

```powershell
.\scripts\build_frontend.ps1
```

生成 `frontend/dist` 后，即可访问：

```text
http://127.0.0.1:8765/terminal
```

## 8. Python 测试结果

本轮需运行：

```powershell
python -m compileall -q .
pytest -q
python -m unittest discover -s tests -p "test*.py" -v
```

当前结果：

- `python -m compileall -q .`：通过。
- `pytest -q`：121 passed。
- `python -m unittest discover -s tests -p "test*.py" -v`：Ran 112 tests OK。

测试重点覆盖：

- Terminal API 可访问。
- `/terminal` 缺 dist 时不崩溃。
- `/legacy` 可访问。
- `/` 默认行为不变。
- 静态托管阻止路径穿越。
- 前端源码不包含确定性收益承诺或确定性买卖建议。
- 技术明细默认折叠。
- 合规声明存在。

## 9. 已知限制

- 当前环境无法执行 Node/npm 构建，因此 `frontend/dist` 尚未生成。
- 新终端尚未经过真实浏览器视觉验收。
- 新终端尚未打包进安装包。
- `/` 默认入口尚未切换到新终端。
- 仍未接入实盘交易接口，也不计划在当前产品边界内接入。

## 10. 下一步安装包发行计划

建议下一阶段 Prompt 15：

1. 在本机修复 Node/npm 环境。
2. 执行 `scripts/build_frontend.ps1`。
3. 启动后端并人工访问 `/terminal`、`/legacy`、`/api/terminal/docs`。
4. 将 `frontend/dist` 纳入 PyInstaller / 安装包资源。
5. 做安装后首次启动 smoke test。
6. 检查安装包不包含真实 API key。
7. 保持卸载时用户数据处理策略明确。

## 11. 合规边界

本系统仅供沪锡期货量化投研参考，不构成投资建议，不承诺收益，不接实盘交易。持仓情景只显示观察区、风险区和不确定性提示，不输出确定性买卖指令。
