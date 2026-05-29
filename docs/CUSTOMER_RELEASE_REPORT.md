# SNInsightTerminal 客户级内部测试版交付报告

## 1. 版本与安装包

- 版本号：`0.3.1-beta.1`
- 构建时间：`2026-05-21 02:28 +08:00`
- 安装包路径：`release/SNInsightTerminal_Setup.exe`
- 安装包时间戳：`2026-05-21 02:28:32 +08:00`
- 安装包大小：`35,463,879 bytes`
- SHA256：`E2BEAABC6D721172155FEBD9BE1ED4D4DFBDDCE531D85DB1E42D78879A021251`

## 2. 本版重点

- 数据刷新任务中心：用户可在终端点击“一键刷新数据”，触发行情、新闻、事件、特征、预测和报告刷新。
- 真实展示 API：补齐行情历史、预测路径、新闻事件、事件证据、报告全文、因子诊断接口。
- 样例数据模式：首次安装无 key、无缓存时可展示界面结构，并明确标记“样例数据模式”，不作为真实预测。
- 前端接入真实/样例/空状态三态展示：图表、新闻、报告、因子页不再无说明空白。
- 浏览器视觉验收：Playwright 自动检查 Dashboard、预测、事件、报告、设置页，并生成截图。
- 安装后 smoke：验证安装、启动、`/terminal`、`/legacy`、Terminal API、设置密钥脱敏、卸载保留用户数据。

## 3. 构建环境

- Python：`3.12.5`
- Node.js：`v24.15.0`
- npm：`11.12.1`
- PyInstaller：`6.19.0`
- Inno Setup：`6.7.2`
- Inno Setup 路径：`C:\Users\Henry Austin\AppData\Local\Programs\Inno Setup 6\ISCC.exe`
- 系统：Windows 11

## 4. 前端检查结果

- `npm install`：通过，`0 vulnerabilities`
- `npm run typecheck`：通过
- `npm run build`：通过
- `npm run check:ui`：通过
- `npm run test:e2e`：通过，`1 passed`
- E2E 截图目录：`e2e-artifacts/screenshots/`
- 截图文件：`dashboard.png`、`predictions.png`、`data-status.png`、`events.png`、`reports.png`、`settings.png`

说明：Vite 仍提示 ECharts 相关 chunk 大于 500 kB，这是性能优化建议，不阻断本次内部测试版交付。后续可通过图表库按需加载继续减小包体。

## 5. Python 与构建结果

- `python -m compileall -q .`：通过
- `pytest -q`：`213 passed`
- `python -m unittest discover -s tests -p "test*.py" -v`：`Ran 164 tests OK`
- PyInstaller onedir：通过
- onedir smoke：通过
- Inno Setup：通过
- `release/SHA256SUMS.txt`：已更新并包含当前安装包 hash

## 6. 安装后 smoke 结果

执行命令：

```powershell
.\packaging\smoke_installed.ps1 -RunBrowserSmoke
```

结果：通过。

验证项：

- 静默安装成功。
- 安装目录存在：`%LOCALAPPDATA%\Programs\SNInsightTerminal`
- `SNInsightTerminal.exe` 存在。
- 开始菜单快捷方式存在。
- 后端可启动并自动选择端口：`8765`
- `/terminal` 返回 200，且不再显示“专业前端尚未构建”。
- `/legacy` 返回 200。
- Playwright 浏览器 smoke 通过。
- 用户数据目录存在：`%LOCALAPPDATA%\SNInsightTerminal`
- 用户数据子目录存在：`data/cache/logs/reports/models/config/registry/outputs`
- `config/settings.json` 存在。
- `config/secrets.example.json` 存在。
- settings API 可保存 mock key，响应只返回脱敏状态。
- settings reset 可清除 mock key。
- 日志未发现完整 mock key。
- 卸载成功。
- 安装目录已删除。
- 用户数据目录默认保留。

## 7. 安全检查结果

- 安装包未打入 `.env`。
- 安装包未打入 `secrets.json`。
- 安装包未打入本地 SQLite、缓存、日志等运行期数据。
- 前端源码和构建产物未发现真实 API key。
- 前端构建产物未发现收益承诺或确定性买卖指令文案。
- 密钥只允许保存在本机用户目录：`%LOCALAPPDATA%\SNInsightTerminal\config\secrets.json`
- 前端不保存完整 key 到 localStorage。
- Settings API 只返回脱敏 key。

## 8. 客户开箱即用流程

1. 双击 `SNInsightTerminal_Setup.exe`。
2. 按安装向导完成安装。
3. 点击开始菜单或桌面快捷方式。
4. 本地后端自动启动，浏览器打开 `/terminal`。
5. 首次启动向导允许配置或跳过 API key。
6. 未配置外部数据源时，系统仍可进入终端，并显示“未配置”或“样例数据模式”。
7. 用户可在设置页稍后配置 Alpha Vantage / NewsAPI key。
8. 点击“一键刷新数据”后，终端会尝试生成真实行情、新闻、事件、预测和报告展示。

## 9. 已知限制

- 当前内部测试版未代码签名，Windows SmartScreen 可能提示未知发布者。
- 外部免费数据源可能存在延迟、限流、失败或字段缺失。
- 无 key、无缓存时展示的是样例数据模式，所有样例均不代表真实行情或预测。
- 当前不接实盘交易接口，不提供自动交易功能。
- 图表 bundle 体积仍可进一步优化。

## 10. 合规声明

SNInsightTerminal 仅供沪锡期货量化投研参考，不构成投资建议，不承诺收益，不接实盘交易。期货交易具有高杠杆和高风险，用户需独立判断并自行承担风险。
# 0.3.2-beta.1 客户级内部测试版补充

本版本在 0.3.1-beta.1 的数据刷新、样例模式和浏览器验收基础上，专项修复数据源状态与刷新失败可解释性：

- 数据源状态不再全部折叠为“已过期”。
- NewsAPI 未配置显示“未配置”，并提示前往设置页配置。
- AKShare 新闻源和工信部政策源在未启用自动抓取时显示“未启用”。
- 工信部政策 TTL 调整为 7 天正常、7-30 天较旧但可参考、30 天后过期。
- SHFE 公共数据按日线/库存/仓单/结算节奏判断，非交易时段不误判失败。
- 一键刷新失败时显示 provider 尝试、错误原因和下一步建议。
- 新增诊断导出，不包含完整 key。
- 仪表盘颜色语义修复：系统正常使用蓝/青，行情上涨红、下跌绿。
# 0.3.2-beta.1 客户级内部测试版最终交付记录

- 版本号：`0.3.2-beta.1`
- 安装包路径：`release/SNInsightTerminal_Setup.exe`
- 安装包时间戳：`2026-05-21 11:21:08 +08:00`
- 安装包大小：`35,501,296 bytes`
- SHA256：`29DB26A895C1D386DD47583C0E6355F225D83276F786377C866746796D12B487`
- 前端验收：`npm run typecheck`、`npm run build`、`npm run check:ui`、`npm run test:e2e` 全部通过。
- Python 验收：`python -m compileall -q .` 通过，`pytest -q` 为 `246 passed`，`unittest` 为 `Ran 164 tests OK`。
- 发行构建：PyInstaller onedir、onedir smoke、Inno Setup 均通过。
- 安装后 smoke：`packaging/smoke_installed.ps1 -RunBrowserSmoke` 通过，验证 `/terminal`、`/legacy`、设置 API、脱敏保存/重置、日志无完整 key、卸载保留用户数据。
- 浏览器视觉验收截图：`e2e-artifacts/screenshots/dashboard.png`、`predictions.png`、`data-status.png`、`events.png`、`reports.png`、`settings.png`。
- 本版重点：行情 provider fallback 与可观测性、新闻/政策 TTL、NewsAPI 查询策略、数据质量分项评分、系统状态与行情涨跌颜色语义、诊断导出。
- 合规边界：仅供沪锡期货量化投研参考，不构成投资建议，不承诺收益，不接实盘交易。
# 0.3.3-beta.1 real-market-only 客户内部测试版交付记录

- 版本号：`0.3.3-beta.1`
- 核心原则：只用真实行情；不做 baseline 预测；不做 baseline 回测；无 active model 时不生成预测；无足够真实历史时不生成回测。
- 行情链路：Sina 实时行情、AKShare 历史行情、SHFE public 辅助、last good cache。
- 缓存策略：last good cache 只用于缓存展示，不冒充新行情。
- 样例策略：sample data 只用于 UI 演示，不进入真实模型、预测或回测。
- 真实行情 smoke：源码后端独立端口验收通过，`final_status=full_success`，历史行情 2710 行，可画图且满足后续真实分析前置条件。
- no-baseline 验收：前端和 API 不出现 baseline forecast、baseline backtest、fake prediction、基线预测、基线回测。
- 合规边界：仅供沪锡期货量化投研参考，不构成投资建议，不承诺收益，不接实盘交易。
