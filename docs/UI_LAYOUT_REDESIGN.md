# UI 布局专项修复说明

本轮只处理网页终端布局、信息架构、响应式和视觉验收，不改模型、回测、行情 provider 核心。

## 页面过宽根因

- 主工作区和卡片网格缺少 `min-width: 0`，导致 grid/flex 子项撑开页面。
- 表格、长 URL、诊断文本和 provider 错误信息没有可靠换行或局部横向滚动。
- 图表 canvas/svg 在容器变化后可能保持旧宽度。
- 旧导航入口偏技术化，栏目过多，普通客户第一次打开时不容易判断下一步。
- 系统状态颜色和行情涨跌颜色曾复用相近语义，容易出现“正常像错误、异常像正常”的感知问题。

## 修复策略

- 全局限制 `html/body/#root` 不产生整页横向滚动。
- `app-shell`、`workspace`、`section-card`、grid 子项统一设置 `min-width: 0` 与 `max-width: 100%`。
- 长文本统一使用 `overflow-wrap: anywhere`，技术明细、`pre/code` 在自身区域横向滚动。
- 表格只允许 `.data-table-wrap` 内部横向滚动，避免撑开整个页面。
- 图表外层继续使用 `ChartBox` 管理最小高度和 resize。

## 响应式断点

- `>=1440px`：多列专业终端布局。
- `1024-1439px`：两列/三列混合，图表和表格保持可读。
- `768-1023px`：侧栏压缩，卡片减少列数。
- `<768px`：单列布局，侧栏横向滚动，表格内部滚动。

## 验收

Playwright 视觉验收新增以下视口：

- `1366x768`
- `1280x720`
- `1024x768`
- `768x1024`
- `390x844`

每个视口检查 `documentElement.scrollWidth` 与 `body.scrollWidth` 不超过 `window.innerWidth + 2`，并保存截图到 `e2e-artifacts/screenshots/`。
