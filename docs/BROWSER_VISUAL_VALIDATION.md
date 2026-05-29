# 浏览器自动化视觉验收

本项目使用 Playwright 对专业中文终端做客户级浏览器验收，目标是确认页面不是空白、核心页面有内容、关键按钮可点击，并且图表、新闻、报告区域能显示真实数据、样例模式或清晰空状态。

## 如何运行

在项目根目录先确保后端依赖和前端依赖已经安装，然后执行：

```powershell
cd frontend
npm run typecheck
npm run build
npm run check:ui
npm run test:e2e
```

当前 Windows/Codex 环境中 `node` 可能被 WindowsApps 受限路径拦截，因此 `package.json` 的 e2e 脚本使用 `C:\Progra~1\nodejs\node.exe` 调用 Playwright CLI。

## 截图位置

E2E 截图保存到：

```text
e2e-artifacts/screenshots/
```

包含：

- `dashboard.png`
- `predictions.png`
- `data-status.png`
- `events.png`
- `reports.png`
- `settings.png`

## 验收标准

Playwright 测试会检查：

- `/terminal` 可打开。
- Dashboard 有核心内容，不白屏。
- 首次启动向导如出现，可以点击“稍后配置”进入终端。
- 七周期预测、数据源状态、事件监控、报告中心、系统设置页面可切换。
- 页面不显示 `undefined`、`null`、`NaN`。
- 页面不出现“保证盈利”“建议买入”“建议卖出”“稳赚”等违规文案。
- 若后端返回 `sample_mode=true`，页面必须出现“样例”标识。

## 安装后 smoke

安装包 smoke 脚本支持可选浏览器验收：

```powershell
.\packaging\smoke_installed.ps1 -RunBrowserSmoke
```

该模式会在安装后的本地服务启动后设置：

- `SN_E2E_SKIP_WEBSERVER=1`
- `PLAYWRIGHT_BASE_URL=http://127.0.0.1:<实际端口>/terminal/`

然后复用同一套 Playwright 测试。

## 常见失败原因

- 后端未启动或端口不可访问。
- Vite 开发服务未启动。
- Playwright 依赖未安装，可运行 `npm install`。
- Chrome/Edge 被系统策略阻止。
- 页面 API 返回错误，但应显示中文 ErrorState，不能白屏。
- 首次安装后未刷新真实数据，此时应显示样例模式或空状态。

合规声明：本系统仅供沪锡期货量化投研参考，不构成投资建议，不承诺收益，不接实盘交易。
