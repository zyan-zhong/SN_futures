# 真实行情端到端验收报告

本报告记录 Prompt 37 对 Prompt 36R 真实行情链路的端到端验收结果。本轮只验证真实行情刷新、图表展示、数据质量、失败诊断和 no-baseline 策略，不修改模型核心，不生成 baseline，不生成虚假预测。

## 验收入口

命令行 smoke 脚本：

```powershell
.\scripts\smoke_market_data_refresh.ps1 -BaseUrl "http://127.0.0.1:8877" -StartBackend
```

脚本会调用：

- `POST /api/terminal/refresh/market`
- `GET /api/terminal/charts/price-history`
- `GET /api/terminal/runtime-diagnostics`
- `GET /api/terminal/providers/status-detail`

输出文件：

```text
%LOCALAPPDATA%\SNInsightTerminal\logs\market_data_smoke.json
```

## 本机 smoke 结果

本轮使用独立源码后端端口 `8877` 验收，避免被本机已安装旧版 `SNInsightTerminal.exe` 进程占用 `8765` 后返回旧 provider 状态。

实测结论：

- realtime 是否成功：`true`
- history 是否成功：`true`
- provider attempts：`3`
- history row_count：`2710`
- final_status：`full_success`
- 是否使用缓存：`false`
- 是否可画图：`true`
- 是否足以进行后续真实模型分析：`true`
- 预测策略：没有 active model 或真实历史行情不足时不生成预测，不生成 baseline 或 fake prediction。

## Provider attempts

本轮源码链路识别到以下 provider 尝试：

- `sina_realtime`：实时行情成功，使用沪锡主力/连续符号，返回最新价。
- `akshare_futures_zh_daily_sina`：历史行情成功，返回 2710 条历史点。
- `shfe_public`：辅助源当前标记为 `auxiliary_unavailable`，不会导致主行情失败，也不会冒充实时行情。

## price-history 结果

`GET /api/terminal/charts/price-history` 返回历史行情点，可驱动前端行情图。验收标准：

- `points.length >= 20` 时前端必须显示图表。
- `points.length >= 60` 时可进入后续真实模型分析前置条件。
- `points=[]` 时前端必须显示 provider 失败原因和下一步建议。

本轮结果为 `2710` 条，满足图表展示和后续真实分析的数据量要求。

## 数据质量验收

数据质量必须展示分项原因，而不是固定分数：

- 实时行情
- 历史行情
- 新闻
- 事件
- 报告
- 预测
- 模型

本轮行情分项已满足：实时行情可用、历史行情可用。若 NewsAPI 未配置或模型未激活，数据质量仍会如实降级并显示原因，不会硬编码抬分。

## no-baseline 验收

以下行为已纳入测试：

- `/api/terminal/predictions` 不生成 baseline 预测。
- `/api/terminal/backtest-diagnostics` 不展示 baseline 回测。
- 前端预测页不出现 `baseline`、`基线预测`、`基线回测`、`fake prediction`。
- 样例数据不参与真实预测或回测。

如果没有 active model，系统只能显示真实原因，例如“暂无可用 active 模型，未生成预测”，不能用 baseline 或随机预测填空。

## 浏览器验收

Playwright 已增加行情刷新验收：

- 打开 `/terminal`。
- 进入“刷新与数据源”。
- 点击“刷新行情”或直接调用 refresh API。
- 验证 `/api/terminal/providers/status-detail` 有行情链路状态。
- 验证 `/api/terminal/charts/price-history` 返回图表点或中文失败原因。
- 进入“行情与新闻”确认图表或空状态可见。
- 进入“预测观察”确认不出现 baseline/fake 文案。

截图输出：

```text
e2e-artifacts/screenshots/market-refresh-validation.png
```

## 用户排查建议

1. 先点击“一键刷新数据”或“刷新行情”。
2. 查看“刷新与数据源”中的实时行情、历史行情、SHFE 辅助和缓存状态。
3. 如果历史行数 `<20`，无法画有效行情图。
4. 如果历史行数 `<60`，不生成真实预测或回测。
5. 如果 `cache_only`，说明当前只使用最近成功缓存，不能当作新行情。
6. 如果 `failed`，复制诊断信息或运行 `scripts/smoke_market_data_refresh.ps1`。

## 合规声明

所有行情、预测、报告和持仓情景均仅供沪锡期货量化投研参考，不构成投资建议，不承诺收益，不接实盘交易。
