# SNInsightTerminal 0.3.1-beta.1 发行验收报告

## 构建结论

`0.3.1-beta.1` 已完成客户级安装包构建、前端浏览器视觉验收、Python 回归测试、PyInstaller onedir 构建、Inno Setup 编译和安装后 smoke。

- 安装包：`release/SNInsightTerminal_Setup.exe`
- 时间戳：`2026-05-21 02:28:32 +08:00`
- SHA256：`E2BEAABC6D721172155FEBD9BE1ED4D4DFBDDCE531D85DB1E42D78879A021251`

## 工具版本

- Python：`3.12.5`
- Node.js：`v24.15.0`
- npm：`11.12.1`
- PyInstaller：`6.19.0`
- Inno Setup：`6.7.2`
- Inno Setup 路径：`C:\Users\Henry Austin\AppData\Local\Programs\Inno Setup 6\ISCC.exe`

## 前端验收

执行命令：

```powershell
cd frontend
npm install
npm run typecheck
npm run build
npm run check:ui
npm run test:e2e
```

结果：

- typecheck：通过
- build：通过
- check:ui：通过
- Playwright E2E：通过，`1 passed`
- 截图目录：`e2e-artifacts/screenshots/`

覆盖页面：

- Dashboard：`dashboard.png`
- 七周期预测：`predictions.png`
- 数据源状态：`data-status.png`
- 事件监控：`events.png`
- 报告中心：`reports.png`
- 系统设置：`settings.png`

## Python 回归

执行命令：

```powershell
python -m compileall -q .
pytest -q
python -m unittest discover -s tests -p "test*.py" -v
```

结果：

- compileall：通过
- pytest：`213 passed`
- unittest：`Ran 164 tests OK`

## 构建结果

执行命令：

```powershell
.\packaging\build_release.ps1 `
  -NodePath "C:\Program Files\nodejs\node.exe" `
  -NpmPath "C:\Program Files\nodejs\npm.cmd"
```

结果：

- 前端构建：通过
- UI 合同检查：通过
- PyInstaller onedir：通过
- onedir smoke：通过
- Inno Setup：通过
- 安装包和 `release/SHA256SUMS.txt` 已生成

## 安装后 Smoke

执行命令：

```powershell
.\packaging\smoke_installed.ps1 -RunBrowserSmoke
```

结果：通过。

验证项：

- 静默安装成功。
- 安装目录存在。
- `SNInsightTerminal.exe` 存在。
- 开始菜单快捷方式存在。
- 后端启动并监听 `8765`。
- `/terminal` 返回 200 且不是未构建提示页。
- `/legacy` 返回 200。
- Playwright 浏览器 smoke 通过。
- 用户数据目录和子目录创建成功。
- settings API 保存 mock key 后只返回脱敏状态。
- settings reset 清除 mock key。
- 日志未发现完整 mock key。
- 卸载成功。
- 安装目录删除。
- 用户数据目录默认保留。

## 安全检查

- 未打包 `.env`。
- 未打包 `secrets.json`。
- 未打包本地 SQLite、缓存、日志等运行期数据。
- 前端源码和产物未发现真实 API key。
- 前端产物未发现收益承诺或确定性买卖指令文案。
- API key 仅允许保存在本机用户目录并脱敏展示。

## 已知限制

- 当前内部测试版未代码签名，Windows SmartScreen 可能提示未知发布者。
- ECharts chunk 体积偏大，后续可做按需加载。
- 免费公开数据源可能延迟、限流或失败。
- 无 key、无缓存时会进入样例数据模式；样例不代表真实行情或预测。

## 合规声明

SNInsightTerminal 仅供沪锡期货量化投研参考，不构成投资建议，不承诺收益，不接实盘交易。
# 0.3.2-beta.1 发行验收补充

本次发行目标是将行情源修复、新闻政策 TTL 修复、数据质量评分重构、颜色语义修复和可观测性增强纳入安装包。重点验收项：

- NewsAPI 未配置显示“未配置”，不是“已过期”。
- miit_policy 7 天内不显示已过期。
- shfe_public 非交易时段不误判失败。
- 本地行情缓存存在时显示“使用缓存”，不是“数据源失败”。
- 数据质量展示分项原因，不固定 60%。
- 系统 ok 使用蓝/青，行情涨红跌绿。
- 一键刷新失败时显示具体原因和下一步建议。
- 诊断导出不泄露 key。
- 样例模式醒目标注，不冒充真实数据。
# 0.3.2-beta.1 发行验收补充

- 版本号：`0.3.2-beta.1`
- 安装包路径：`release/SNInsightTerminal_Setup.exe`
- 安装包时间戳：`2026-05-21 11:21:08 +08:00`
- SHA256：`29DB26A895C1D386DD47583C0E6355F225D83276F786377C866746796D12B487`
- 前端检查：`typecheck`、`build`、`check:ui`、`test:e2e` 全部通过。
- Python 检查：`compileall` 通过，`pytest -q` 为 `246 passed`，`unittest` 为 `Ran 164 tests OK`。
- 构建检查：PyInstaller onedir、onedir smoke、Inno Setup 编译均通过。
- 安装后检查：`smoke_installed.ps1 -RunBrowserSmoke` 通过，含 `/terminal`、`/legacy`、Terminal API、settings API、日志脱敏、卸载保留用户数据。
- 数据源专项验收：NewsAPI 未配置按“未配置”处理，新闻/政策/SHFE 公共数据使用合理 TTL 和缓存状态，刷新失败提供 provider 尝试、错误原因和下一步建议。
- 颜色语义验收：系统健康不再与行情涨跌混用，系统正常使用蓝/青，风险/错误使用黄/红；行情涨为红、跌为绿。
- 数据质量验收：分项评分来自行情最新价、历史行情、新闻、事件、报告、预测、模型健康，不再固定约 60%。
- 合规边界：仅供沪锡期货量化投研参考，不构成投资建议，不承诺收益，不接实盘交易。
