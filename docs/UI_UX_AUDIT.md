# SNInsightTerminal 客户级 UI/UX 审计与优化计划

审计时间：2026-05-19  
审计范围：`frontend/` React/Vite 专业终端、旧 `ui_web/` 兼容入口、Terminal API 消费方式、设置页、空状态、错误状态、安装后首次使用体验。  
审计原则：本轮只做结构扫描、问题定位和优化计划，不改模型、因子、回测、数据核心，不重新构建安装包。

## 1. 当前 UI 结构

### 页面

- `DashboardPage`：总览大盘、七周期摘要、价格区间概览、模型健康、学习状态、数据源状态。
- `PredictionPage`：七周期预测卡片和预测区间图。
- `FactorPage`：因子分组占位，包含技术面、均值回归、期限结构、基差、库存、跨市场、事件、Regime。
- `EventPage`：从预测卡片中提取事件依据，显示事件列表和事件分类占位。
- `BacktestPage`：按周期查询回测诊断，展示 walk-forward、成本敏感性、regime 分组。
- `ModelGovernancePage`：模型健康、promotion gate、学习状态。
- `PositionPage`：持仓情景输入与结果展示。
- `ReportsPage`：报告列表、摘要和复制 Markdown。
- `DataStatusPage`：数据源状态卡片。
- `SettingsPage`：API base、本地刷新间隔、技术明细开关、Alpha Vantage / NewsAPI 密钥状态与保存/重置。

### 组件

- 布局：`AppShell`、`Sidebar`、`TopStatusBar`、`SectionCard`。
- 预测：`PredictionGrid`、`PredictionCard`、`SignalBadge`、`RiskBadge`。
- 图表：`PriceChart`、`EquityCurveChart`、`FactorBarChart`、`ProbabilityGauge`、`DrawdownChart`。
- 模型：`ModelHealthPanel`、`PromotionGatePanel`、`LearningStatusPanel`。
- 回测：`BacktestPanel`、`CostSensitivityPanel`、`RegimePerformancePanel`。
- 持仓：`PositionScenarioForm`、`PositionScenarioResult`。
- 报告与数据：`ReportCenter`、`DataSourceStatusPanel`。
- 通用状态：`LoadingState`、`ErrorState`、`EmptyState`、`CollapsibleDebug`、`StatusPill`、`MetricCard`。

### API 与样式

- API client：`frontend/src/api/client.ts`、`terminal.ts`、`types.ts`。
- 数据来源：前端只调用 `/api/terminal/*`，未直接依赖旧 `/api/predictions/live`。
- 样式：`frontend/src/styles/globals.css`，深色终端风格，红涨绿跌，移动端有基础响应式。

## 2. 主要问题清单

### P0：客户开箱即用路径仍不够清楚

首次打开 `/terminal` 时，系统虽然可展示结构，但缺少专门的“首次启动向导”。未配置 API key、无报告、无完整因子诊断、无 active 模型时，用户需要自己理解多个页面的状态，下一步行动不够明确。

影响：

- 新用户可能误以为系统不可用。
- 免费数据源未配置和系统故障之间的区别不够醒目。
- 设置页入口、可跳过配置、配置后可刷新数据的流程没有形成闭环。

建议：

- 增加首次启动状态检测：未配置 key、无报告、无模型、无最新数据时显示“3 步开始使用”。
- 顶部状态栏和 Dashboard 加明显 CTA：“去设置数据源”“跳过并使用本地研究模式”“查看 API 状态”。
- 未配置 API key 时明确写：“系统仍可运行，但外部新闻/宏观数据受限”。

### P0：设置页仍有英文/技术字段直接暴露

设置页可见文本包含 `API Base URL`、`Alpha Vantage key`、`NewsAPI key`，模型页包含 `Active 模型`、`Candidate 模型`，因子页包含 `Regime`，回测页包含 `Walk-forward`。这些术语可以保留为技术名词，但普通 UI 需要中文解释和主标签。

建议：

- `API Base URL` 改为“后端 API 地址（开发模式）”。
- `Alpha Vantage key` 改为“Alpha Vantage 密钥（可选）”。
- `NewsAPI key` 改为“NewsAPI 密钥（可选）”。
- `Active 模型` 改为“当前生效模型”。
- `Candidate 模型` 改为“候选模型”。
- `Regime` 改为“市场状态（Regime）”。
- `Walk-forward` 改为“滚动样本外回测（Walk-forward）”。

### P0：页面空状态缺少“下一步”

`FactorPage`、`EventPage`、`ReportsPage`、`DataStatusPage` 当前能显示空状态，但多数只说明“暂无数据”，没有告诉用户应该点击哪个按钮、运行哪个任务、或是否需要配置 key。

建议：

- 每个空状态增加下一步按钮或说明。
- 报告中心无报告时提示：“运行报告生成任务”或“先刷新预测后生成报告”。
- 事件数据缺失时提示：“配置 NewsAPI 或等待公开源刷新；未配置时不会影响本地基础功能”。
- 因子诊断缺失时提示：“运行因子诊断任务；当前预测卡仍使用已有终端快照”。

### P0：图表表达还不够专业

`PriceChart` 当前以七周期为横轴展示预测区间，适合摘要，但不是真正的历史/预测时间序列图。客户容易期待看到历史价格、预测区、上下界、事件点和时间轴。

建议：

- 新增主图数据接口消费层，优先使用 `/api/charts/price-forecast?horizon=...` 或后续 `/api/terminal/chart`。
- 图表分为“摘要图”和“单周期时间路径图”，避免把七周期摘要图误认为连续价格路径。
- 图表空状态要说明“暂无时间序列图，请先刷新行情/预测”。
- 图表异常时用中文错误边界，不让 ECharts 异常导致整页中断。

### P0：持仓情景默认输入可能造成误解

持仓情景默认均价为 0，虽然可提交，但对普通用户不友好。表单只有 `min=0`，缺少内联校验和风险提示位置。

建议：

- 默认均价为空，提交前要求填写有效数值。
- 如果方向为“观望”，隐藏或弱化均价/手数字段，避免像交易建议。
- 在提交按钮附近固定显示：“仅生成观察区，不构成交易建议”。
- 输入错误时在字段附近显示中文错误，而不是只在页面顶部显示失败。

## 3. 客户开箱即用问题

### 当前表现

- 安装后 `/terminal` 能打开。
- 顶部有状态栏，底部有合规声明。
- 未配置 key 时数据源页可显示未配置。
- 设置页可保存/重置密钥，并且不写 localStorage。

### 缺口

- 没有“首次启动向导”或“系统可用性清单”。
- Dashboard 缺少“你现在可以做什么”的指导。
- 未配置 key、无 active 模型、无报告、数据过期这些状态分散在不同页面。
- API 失败时虽然不会白屏，但客户很难判断是网络、配置、模型、数据源还是后台任务问题。

## 4. 设置页问题

### 当前优点

- 支持 Alpha Vantage / NewsAPI 配置状态。
- 支持密钥保存与重置。
- 使用 password 输入框。
- 不把密钥写入前端 localStorage。
- 后端 settings API 返回脱敏状态。

### 需要优化

- 英文标签和技术字段仍偏多。
- 保存成功/失败提示是单一 `StatusPill`，缺少更明显的 toast 或结果区。
- 保存后没有提示“下一步：刷新数据源状态”。
- API Base URL 属于开发者设置，应放入“高级设置/开发者模式”折叠区。
- 技术明细开关本地存储，但全局是否生效不够明确。

## 5. Dashboard 问题

### 当前优点

- 有主合约、最新价、涨跌、数据质量、模型状态、风险等级。
- 集成七周期预测摘要、价格区间、模型健康、学习状态、数据源状态。

### 需要优化

- 无数据时只显示默认或缺失值，缺少“首次使用流程”。
- 数据质量不足时应有醒目降级 banner。
- “当前信号”“模型状态”需要加入解释 tooltip 或说明。
- 总览大盘应增加“数据截止时间 / 本地刷新时间 / API 端口 / 当前版本”。

## 6. 预测页问题

### 当前优点

- 每个周期卡片包含方向、概率、预测收益、数据质量、模型状态、预测区间、决策说明、核心因子、事件依据、风险提示、路径守门。
- 观望、degraded、低数据质量时不会显示交易点位。
- 技术明细默认折叠。

### 需要优化

- 卡片信息密度高，但层级还不够清楚：方向、证据、风险、路径守门应分区更明确。
- “核心因子暂缺”“事件暂缺”需要解释原因：未运行任务、无有效事件、数据源未配置、还是本周期不适用。
- 强信号、弱信号、观望、降级状态需要统一中文视觉规范。
- 需要显示回测口径摘要：样本外、成本后、最近窗口、强信号命中率。

## 7. 图表和表格问题

- 图表容器高度固定为 360px，桌面可用，但窄屏下可能占用过大。
- 图表没有局部错误边界，ECharts 异常时存在模块失败风险。
- 表格主要用 flex/grid 模拟，长文本时可能换行不稳。
- 报告摘要没有 Markdown 渲染，仅文本预览；复制按钮没有成功反馈。
- 回测和模型指标缺少“指标解释”，非开发用户难理解 Brier、ECE、profit factor、degraded。

## 8. 错误/空状态问题

当前已有 `ErrorState`、`EmptyState`、`LoadingState`，但还偏通用。

建议统一状态组件合同：

- `title`：发生了什么。
- `message`：为什么可能发生。
- `nextAction`：下一步怎么做。
- `primaryAction`：可点击动作。
- `severity`：info/warn/error。
- `preserveLastGoodData`：是否保留上一版成功数据。

重点场景：

- 未配置 key。
- 数据源失败。
- 缓存过期。
- 无 active 模型。
- candidate 未晋级。
- 报告未生成。
- 因子诊断未运行。
- 事件源未刷新。

## 9. 可访问性问题

静态扫描发现：

- 未发现统一 `:focus-visible` 样式。
- 未发现 `aria-*` 辅助属性。
- 按钮有文本，但图标按钮和导航缺少更明确的 aria 标注。
- 表单 input 有 label 包裹，这是优点，但错误信息未靠近字段显示。
- 颜色表达已有中文标签，但仍需确保红涨绿跌不作为唯一信息来源。
- 移动端有基础响应式，但没有针对宽表格、图表、侧栏滚动的专项规则。

建议：

- 增加 `button:focus-visible`、`input:focus-visible`、`select:focus-visible`。
- Sidebar nav 加 `aria-current`。
- 错误提示绑定字段。
- 图表加文本摘要，保证无图表也能理解。
- 合规声明保持固定可见，但移动端避免遮挡操作按钮。

## 10. 合规文案风险

当前前端源码未发现：

- `guaranteed profit`
- `buy now`
- `sell now`
- “建议买入”
- “建议卖出”
- “保证盈利”

仍需注意：

- 持仓情景中的“观察区”“风险区”应持续避免“买入/卖出建议”。
- 预测卡“研究观察点位”应继续明确不是交易指令。
- 报告中心复制内容也应包含合规声明。

## 11. 优先级

### P0：必须在客户交付前处理

1. 增加首次启动向导或 Dashboard 引导卡。
2. 设置页普通文案全中文化，技术设置折叠。
3. 所有空状态增加下一步指引。
4. 预测页明确“摘要图”与“单周期时间路径图”的区别。
5. 持仓情景表单增加字段校验和近场错误提示。
6. 图表组件增加错误边界和图表不可用中文回退。

### P1：建议下一个小版本处理

1. 模型健康和回测指标增加中文解释 tooltip。
2. 报告中心增加 Markdown 预览、复制成功反馈。
3. DataStatus 页面增加“未配置/失败/缓存/过期”的统一说明。
4. 学习与回测页面增加任务时间线。
5. 卡片增加“为什么这样判断”的展开详情和证据优先级。

### P2：体验增强

1. 移动端专门布局。
2. 键盘可访问性和 aria 完整补齐。
3. 主题/字号设置真正全局生效。
4. 客户级截图验收脚本。
5. 终端内“帮助中心/术语解释”。

## 12. 后续 Prompt 任务拆分

### Prompt 19：首次启动向导和设置页

- 新增首次启动向导组件。
- 设置页中文化和分层：普通设置、数据源密钥、高级开发设置。
- 保存/重置密钥加入 toast、下一步指引和近场错误。
- Dashboard 未配置 key 时显示清晰 CTA。

### Prompt 20：Dashboard 与七周期预测展示优化

- 优化七周期卡片层级：方向、证据、风险、路径、回测。
- 增加数据质量降级 banner。
- 增加回测口径摘要和强信号说明。
- 统一信号颜色、标签和中文解释。

### Prompt 21：图表/表格/报告中心优化

- 增加单周期历史/预测分离图入口。
- 图表错误边界和空状态。
- 报告 Markdown 预览与复制成功反馈。
- 回测表格宽屏/窄屏优化。

### Prompt 22：错误边界、空状态、加载状态、响应式和可访问性

- 统一状态组件合同。
- 增加 focus-visible、aria-current、字段错误提示。
- 移动端图表和侧栏布局优化。
- 保证 API 部分失败不影响其它模块。

### Prompt 23：客户级安装后视觉验收与重打包

- 构建前端。
- 安装新版包。
- 人工/自动打开 `/terminal`。
- 验证首次启动、设置页、预测页、报告页、持仓情景页。
- 通过后重新生成内部测试安装包。

## 13. 本轮结论

当前专业终端已经具备发行链路、Terminal API、安装后启动和基础中文界面，但距离“客户开箱即用”仍差一个前端体验收敛轮。最建议先执行 Prompt 19，因为首次启动和设置体验决定用户是否能顺利进入系统；随后执行 Prompt 20 和 Prompt 21，补齐预测卡片证据表达和专业图表。

## 14. Prompt 19 实施记录：首次启动向导与设置页

本轮已补齐客户首次打开 `/terminal` 的配置引导能力：

- 新增首次启动向导，自动检查 settings、data-status 与 system-health。
- Alpha Vantage 或 NewsAPI 未配置时，向导提示用户可立即配置、稍后配置或不再自动弹出。
- 向导明确说明系统用途、研究边界和合规声明。
- 向导不会把任何密钥写入前端持久化存储；前端只保存 `firstRunCompleted` 偏好。
- 设置页增加配置状态卡片、脱敏密钥显示、显示/隐藏输入、单独保存、同时保存、二次确认重置、连接检查、启动路径、数据源说明和故障排查。
- 后端 settings/status 补充用户数据目录、日志目录、报告目录、API 地址、终端地址和最后更新时间。

仍建议下一轮继续做 Prompt 20：Dashboard 与七周期预测展示优化。重点是把“当前可做什么”“为什么这样判断”“数据质量不足如何降级”在总览和预测卡片中表达得更清楚。

## 15. Prompt 20 实施记录：Dashboard 与七周期预测展示优化

本轮已处理 Dashboard 与 Prediction 页面 P0/P1 问题：

- Dashboard 新增客户级 `SystemStatusBanner`，覆盖正常、未配置 key、数据质量不足、无 active 模型、degraded 和 API 失败等状态。
- Dashboard 总览区改为六张核心状态卡：系统状态、主合约与最新价格、数据质量、当前研究信号、模型状态、风险状态。
- 七周期预测页新增周期分组入口：日内、1日、3日、5日、10日、20日、趋势。
- 预测为空时显示中文空状态，并提供刷新终端快照、前往设置、查看数据源状态、查看模型治理按钮。
- PredictionCard 主视图区聚焦方向、信号、概率、预测收益、Trade Edge、数据质量、模型状态、预测区间和交易点位规则。
- 决策说明、因子明细、事件依据、回测摘要和技术明细改为折叠展示，降低信息拥挤。
- 交易点位区域继续遵守观望、降级、低数据质量不显示点位，并明确“非交易建议，仅作投研观察”。
- 概率条增加 45%–55% 中性区间提示，方向不明确时使用中文说明。

仍未完成的问题：

- 图表仍是跨周期摘要图，不是单周期历史/预测时间路径图。
- 模型健康、回测和数据源页面还可以增加面向非开发用户的指标解释。
- 空状态和错误状态后续还应统一成带操作按钮的标准组件。
- 移动端表格、图表和侧栏体验仍需专项验收。

## 16. Prompt 21 实施记录：图表、表格、报告中心和数据源状态优化

本轮已处理图表、表格、报告中心和数据源状态页的客户可读性问题：

- 新增通用 `ChartBox`，统一 ECharts 最小高度、深色容器、窗口 resize、ResizeObserver 和 unmount dispose。
- PriceChart、EquityCurveChart、DrawdownChart、FactorBarChart、ProbabilityGauge 均接入空状态、中文 tooltip、中文坐标轴和非有限数字清洗。
- 新增通用 `DataTable`，支持空状态、加载状态、错误状态、横向滚动、数字/百分比/日期格式化、长文本省略、状态 badge。
- 报告中心升级为报告列表 + Markdown 预览；显示报告类型、生成时间、数据截止时间、模型版本、数据质量、Promotion Gate 状态，并支持复制 Markdown 与下载 `.md`。
- 报告预览会将 `nan` 文本替换为“数据暂缺”，并在报告开头补充合规声明。
- 数据源状态页新增总览指标：正常、未配置、失败、使用缓存、过期。
- 数据源列表统一展示 enabled、success、from_cache、stale、last_update、message_zh。
- 数据源状态页新增“前往设置”“刷新状态”“查看日志位置”操作，以及状态解释。

仍未完成的问题：

- 图表仍以已有摘要数据为主，尚未接入完整单周期历史/预测时间轴图。
- 报告下载目前为前端基于 Markdown 文本生成 `.md`，如果后端后续提供正式文件下载接口，可再接入。
- DataTable 已支持横向滚动，但移动端卡片式表格还未专项实现。
- 图表 chunk 体积仍偏大，后续可考虑 ECharts 按需加载或路由级动态 import。

## 17. Prompt 22 实施记录：错误边界、状态组件、响应式和 UI 合同检查

本轮围绕客户级稳定性做了前端护栏补强，不改动模型、因子、回测或发行安装器：

- 新增 `ErrorBoundary`，并接入 AppShell 主内容区、Dashboard 关键区块、Prediction、Backtest、Model Governance、Reports、Position、DataStatus 和 ChartBox。任一模块渲染异常时只降级该模块，不让整页白屏。
- `ErrorBoundary` 默认只展示中文用户提示：“该模块暂时无法显示，请刷新或查看日志。”技术细节放入默认折叠的“技术明细 / 开发调试信息”，并经过敏感字段清洗。
- `LoadingState`、`EmptyState`、`ErrorState` 统一支持中文标题、说明、主按钮和次按钮；空状态不再只是“无数据”，而是给出下一步动作。
- 响应式布局补齐 1440px、1024-1439px、768-1023px、<768px 四档断点；窄屏下侧栏、状态栏、预测卡片、表格和图表均可读，整页禁止横向溢出，宽表格局部横向滚动。
- 可访问性增强：Sidebar 增加 `aria-current`，图表容器增加 `role="img"` 与中文 `aria-label`，回测周期选择增加 `aria-label`，按钮/input/select/summary/nav item 增加明显 `focus-visible`。
- 新增 `frontend/src/utils/copy.ts` 统一客户级文案，包括“数据暂缺”“暂无交易点位”“已降级为研究观察”“技术明细 / 开发调试信息”和合规声明，降低英文调试文案泄漏风险。
- 新增 `frontend/scripts/check-ui-contract.mjs` 与 `npm run check:ui`，自动检查收益承诺/买卖建议禁词、必须合规文案、密钥安全、ErrorBoundary、FirstRunWizard 和 localStorage 白名单。

仍未完成的问题：

- 当前 Vite 构建仍提示 ECharts bundle 偏大。该提示不阻塞发行，但后续可做路由级动态加载或 ECharts 按需注册。
- 仍需在重新发行安装包前运行完整 `build_release.ps1`，否则安装包内不会包含本轮前端优化后的 `frontend/dist`。
## Prompt 23 实施记录：客户级安装包重构建与验收

本轮已将 Prompt 19-22 的客户级 UI/UX 优化重新构建进入 Windows 安装包 `release/SNInsightTerminal_Setup.exe`，版本号为 `0.3.0-beta.1`。

已完成：

- 前端 `npm run typecheck`、`npm run build`、`npm run check:ui` 均通过。
- Python `compileall`、`pytest -q`、`unittest discover` 均通过。
- PyInstaller onedir 构建通过，`/terminal` 和 `/legacy` 均可访问。
- Inno Setup 安装包构建通过，安装包时间戳为 `2026-05-20 02:08:26 +08:00`。
- 安装后 smoke 通过，覆盖静默安装、快捷方式、终端访问、settings API、mock key 脱敏保存/重置、日志安全、卸载与用户数据保留。
- 构建脚本已增加 onedir 运行期数据清洁检查，避免 `.env`、`secrets.json`、SQLite、DB、cache、logs 等进入安装包。

仍建议后续优化：

- 对 ECharts 做按需加载或路由级动态加载，降低前端首包体积。
- 增加浏览器自动化视觉回归，覆盖首次启动向导、Dashboard、预测页、设置页、报告中心与数据源状态页。
- 外部客户发布前加入代码签名，降低 Windows SmartScreen 的未知发布者提示。
## Prompt 31 实施记录：布局、导航、响应式与视觉验收

本轮围绕“页面太宽、内容显示不完整、组件超出框外、导航栏目设计不合理”做专项修复，不改模型、回测、行情 provider 核心。

已完成：

- 主导航改为客户任务导向：总览、刷新与数据源、行情与新闻、预测观察、回测验证、报告中心、设置与诊断。
- 因子诊断、模型治理、持仓情景保留在“高级模式 / 技术明细”折叠区，不删除功能，但降低默认认知负担。
- 全局布局补齐 `min-width: 0`、`max-width: 100%`、`overflow-wrap: anywhere` 和局部横向滚动规则，避免表格、长 URL、错误文本、图表 canvas 撑开整页。
- `DataTable` 只在自身容器内横向滚动，整页不再被宽表格撑开。
- `EventPage` 调整为“行情与新闻”，上方展示行情历史图，下方展示新闻事件。
- `TopStatusBar` 将行情涨跌颜色与系统状态颜色分离：涨用红、跌用绿，系统正常用蓝/青。
- `SystemStatusBanner` 改用 `banner-ok`、`banner-warning`、`banner-error`，避免系统正常显示行情红色。
- Playwright 视觉验收新增 1366x768、1280x720、1024x768、768x1024、390x844 五个视口，并检测 `scrollWidth`，防止横向溢出回归。

仍需后续注意：

- 本轮未重新打包安装器；若要让安装包包含这些前端布局优化，需要重新运行 `packaging/build_release.ps1`。
- 部分历史文档仍存在编码损坏文本，不影响前端运行，但后续文档整理时建议统一重写。
