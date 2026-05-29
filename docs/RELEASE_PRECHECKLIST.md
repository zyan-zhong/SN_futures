# SNInsightTerminal 发行前检查清单

## 1. 前端构建

- [ ] `frontend/dist/index.html` 存在。
- [ ] `frontend/dist/assets` 存在且包含 JS/CSS 静态资源。
- [ ] `http://127.0.0.1:8765/terminal` 能打开新专业终端。
- [ ] `/terminal` 页面刷新不会 404。
- [ ] 新终端不出现空白页。
- [ ] 新终端普通用户界面为中文。
- [ ] 技术明细默认折叠。

## 2. 旧 UI 与 API

- [ ] `http://127.0.0.1:8765/legacy` 能打开旧 UI。
- [ ] `http://127.0.0.1:8765/` 当前默认入口仍按预期工作。
- [ ] `http://127.0.0.1:8765/api/terminal/docs` 能打开。
- [ ] `/api/predictions/live` 等旧 API 未被破坏。

## 3. 安全配置

- [ ] `.env` 未提交。
- [ ] `.env.example` 只有占位符。
- [ ] 前端源码不包含真实 API key。
- [ ] `frontend/dist` 不包含真实 API key。
- [ ] 后端日志不打印完整 key。
- [ ] 安装包不包含真实 API key。
- [ ] 静态托管阻止 `/terminal/../.env` 等路径穿越。

## 4. 本地数据与存储

- [ ] `app_data` 或 `SN_DATA_DIR` 可写。
- [ ] 本地 SQLite 或事件库可写。
- [ ] 报告输出目录可写。
- [ ] 模型 registry 目录可写。
- [ ] 首次启动缺少数据源 key 时显示中文“未配置”，系统不崩溃。

## 5. 量化与治理

- [ ] 观望信号不显示交易点位。
- [ ] degraded 模型不显示交易点位。
- [ ] 低数据质量不显示交易点位。
- [ ] candidate 不能绕过 promotion gate。
- [ ] 失败原因中文非空。
- [ ] API 输出不包含 `NaN / Infinity`。
- [ ] 报告不包含字符串 `nan`。

## 6. 安装包前 smoke

- [ ] `python -m compileall -q .` 通过。
- [ ] `pytest -q` 通过。
- [ ] `python -m unittest discover -s tests -p "test*.py" -v` 通过。
- [ ] `cd frontend && npm run typecheck` 通过。
- [ ] `cd frontend && npm run build` 通过。
- [ ] 安装包 smoke：首次启动能打开浏览器。
- [ ] 安装包 smoke：`/terminal`、`/legacy`、`/api/terminal/docs` 可访问。

## 7. 卸载与用户数据

- [ ] 卸载程序不会默认静默删除用户数据。
- [ ] 如需删除用户数据，必须提示用户确认。
- [ ] 升级安装不会覆盖 `.env`。
- [ ] 升级安装不会破坏 `app_data`、模型 registry、报告和事件库。

## 8. 合规

- [ ] UI 固定显示“不构成投资建议”。
- [ ] 报告包含重要声明。
- [ ] 持仓情景不出现“建议买入 / 建议卖出 / 保证盈利 / 稳赚”等表述。
- [ ] 产品不接实盘交易接口。
