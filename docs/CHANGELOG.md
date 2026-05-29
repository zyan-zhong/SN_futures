# CHANGELOG

## 0.3.3-beta.1 - 2026-05-21

本版本为 real-market-only 客户内部测试版，重点是把真实行情 provider 修复和 no-baseline 策略纳入安装包发行链路。

### 关键变化

- 真实行情链路按实时行情、历史行情、SHFE public 辅助和 last good cache 分离。
- 一键刷新行情会真实尝试 provider，并记录 symbol、返回行数、状态和失败原因。
- 实时行情成功不会阻止历史行情刷新；历史行情成功但实时暂缺时仍可用于图表展示。
- 无 active model 时不生成预测；真实历史行情不足时不生成回测。
- 不生成 baseline 预测，不生成 baseline 回测，不使用 fake prediction。
- sample data 只用于 UI 演示，last good cache 只作为缓存展示，不冒充新行情。

### 验收

- `scripts/smoke_market_data_refresh.ps1` 可验证 provider attempts、price-history 和 no-baseline 策略。
- Playwright 覆盖行情刷新、图表或失败原因展示、无 baseline/fake 文案。
- 所有输出仍仅供沪锡期货量化投研参考，不构成投资建议，不承诺收益，不接实盘交易。

## 0.3.0-beta.1 - 2026-05-20

本版是客户级内部测试版，重点把 Prompt 19-22 的前端体验优化纳入正式安装包构建链路。

### 新增与优化

- 新增客户级首次启动向导：首次打开专业终端时检查数据源配置，允许立即配置、稍后配置或不再自动弹出。
- 优化客户级设置页：支持本机保存 Alpha Vantage / NewsAPI key、脱敏显示、重置密钥、连接检查和路径说明。
- Dashboard 新增状态 Banner 与 6 个核心状态卡：系统状态、主合约与最新价格、数据质量、当前研究信号、模型状态、风险状态。
- 七周期预测卡片改为业务化展示：方向、概率、预测区间、置信度、Trade Edge、数据质量、模型状态、决策说明、核心因子、事件依据、风险提示和路径守门。
- 优化图表容器、DataTable、报告中心和数据源状态页：补齐空状态、错误状态、中文 tooltip、横向滚动和状态解释。
- 新增模块级 ErrorBoundary：页面、面板和图表异常时不再整页白屏，技术明细默认折叠。
- 补齐响应式布局和可访问性：多档断点、明显 focus 样式、中文 aria 标签、窄屏单列布局。
- 新增 UI 合同检查脚本 `npm run check:ui`，自动防止收益承诺、确定性买卖建议、密钥泄露和调试文案回归。
- 保留旧版 UI 入口 `/legacy`，新版专业终端入口为 `/terminal`。

### 发行与验收

- 安装包构建流程继续使用 PyInstaller onedir + Inno Setup。
- 安装后 smoke 验证覆盖 `/terminal`、`/legacy`、`/api/terminal/docs`、settings API、mock key 脱敏保存与 reset、卸载行为。
- 用户数据默认写入 `%LOCALAPPDATA%\SNInsightTerminal`，卸载时默认保留。
- 构建脚本增加 onedir 运行期数据清洁检查，避免 `.env`、`secrets.json`、SQLite、DB、cache、logs 等进入安装包。

### 合规边界

- 不构成投资建议。
- 不承诺收益。
- 不接实盘交易。
- 预测、信号、报告和持仓情景均仅供沪锡期货量化投研参考。
