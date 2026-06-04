# Terminal UI/API Map

本清单用于审计每个可视化页面是否有真实后端来源、按钮是否有 API 或明确静态行为、图表和表格是否有空状态/错误状态。

| 页面 | 使用 API | 按钮 | 图表 | 表格 | 空状态 | 错误状态 | 后端文件来源 | 是否可用 | 是否慢 | 是否需要优化 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 总览 | `/api/terminal/snapshot`, `/api/terminal/summary`, `/api/terminal/charts/price-history` | 刷新/导航 | PriceChart | 关键状态卡 | 无预测时显示暂无 active/暂无预测 | Dashboard 级错误态 | `sn_market_history.json`, `refresh_status.json` | 可用 | 否，lite snapshot | 继续保持轻量 |
| 行情监控 | `/api/terminal/charts/price-history`, `/api/terminal/market-analysis`, `/api/terminal/providers/status-detail`, `/api/terminal/refresh/market` | 刷新行情 | PriceChart 支撑/压力线 | provider attempts, volume/open_interest, cache | 无行情显示 provider 原因 | 页面 ErrorState | `sn_market_history.json`, `sn_live_snapshot.json`, `market_provider_status.json` | 可用 | 否 | 可继续压缩 provider 明细 |
| 新闻与事件 | `/api/terminal/events/news`, `/api/terminal/events/relevance-diagnostics`, `/api/terminal/events/source-quality-report`, `/api/terminal/refresh/news` | 刷新新闻、去设置 | PriceChart | query group、入模/展示/排除新闻 | 0 入模时说明不伪造事件因子 | 页面 ErrorState | `news_raw.json`, `news_events_filtered.json`, `event_factor_inputs.json` | 可用 | 中等 | 可分页排除新闻 |
| 因子研究 | `/api/terminal/factors/coverage`, `/api/terminal/factors/online-readiness`, `/api/terminal/feature-store/status`, `/api/terminal/feature-store/build` | 构建 Feature Store、刷新状态 | FactorBarChart | coverage groups、usable/excluded fields | 无覆盖率提示先刷新行情 | 页面/卡片 ErrorState | `feature_coverage_report*.json`, `feature_store/*/feature_store_manifest.json` | 可用 | 中等，已缓存 | 大 manifest 继续折叠 |
| 训练数据 | `/api/terminal/training-dataset/status`, `/api/terminal/training-dataset/build` | 构建训练数据、刷新 | 无 | horizon 样本、标签分布 | 无 manifest 时显示未构建 | 页面 ErrorState | `training_dataset_manifest*.json`, `training_datasets/*` | 可用 | 中等 | build 可继续默认 async |
| 模型研究 | `/api/terminal/research/experiments`, `/api/terminal/models/candidate-status`, `/api/terminal/models/oof-integrity-report`, `/api/terminal/validation/report`, `/api/terminal/research/artifacts`, `/api/terminal/tasks/*` | 运行实验、自学习、candidate、审批 active | OOF/validation 摘要图表或表 | experiments、candidate 对比、gate checklist | 无实验时显示先构建训练数据 | 卡片 ErrorState | `model_research/*`, `walk_forward/*`, `model_registry/*` | 可用 | 重任务走 task | 继续拆分大表 |
| 回测验证 | `/api/terminal/research/backtest-report`, `/api/terminal/research/equity-curve`, `/api/terminal/research/run-backtest` | 运行研究回测 | EquityCurveChart, DrawdownChart | trades, metrics | 无收益曲线显示 research 空状态 | 页面 ErrorState | `research_backtests/*` | 可用 | 中等 | trades 表分页 |
| 预测观察 | `/api/terminal/predictions`, `/api/terminal/charts/forecast-path`, `/api/terminal/models/active-status`, `/api/terminal/refresh/predictions` | 刷新数据、查看研究/回测/设置 | ForecastPathChart 仅 active 存在时显示 | prediction cards | 无 active 时明确无通过 gate 的 active model | 卡片空态 | `model_registry/active_model.json`, prediction cache | 可用 | 否 | 不显示假未来线 |
| 报告中心 | `/api/terminal/reports`, `/api/terminal/reports/full`, `/api/terminal/research/artifacts`, `/api/terminal/refresh/reports` | 生成报告、查看 artifacts | 无 | reports, artifacts | 无报告时提示生成报告 | 页面 ErrorState | `reports/*`, `research_runs/*` | 可用 | 已缓存 artifacts | 支持下载过滤 |
| 设置与诊断 | `/api/terminal/settings/status`, `/api/terminal/settings/key-diagnostics`, `/api/terminal/providers/test`, `/api/terminal/diagnostics/export`, `/api/terminal/online-data-sources/status` | 保存/测试/重置 key、导出诊断 | 无 | key diagnostics, provider status | 未配置 key 显示配置入口 | ErrorState | `config/secrets.json`, provider status files | 可用 | 否 | 继续保持脱敏 |
| Artifact Center | `/api/terminal/research/artifacts`, `/api/terminal/reports/full` | 下载/复制诊断摘要 | 无 | artifacts list | 无 artifacts 时显示空状态 | 卡片 ErrorState | `outputs/research_runs`, `outputs/research_backtests` | 可用 | 已缓存 | 后续加搜索 |

## 当前连接结论

- 每个主页面至少有一个后端 API 或明确静态说明。
- 刷新/运行类按钮均有 API helper 或任务 API。
- 主要图表均有数据 endpoint 或专业空状态。
- 无 active model 时不显示预测路径，不显示假未来线。
- 重计算应走 `/api/terminal/tasks/*` 或缓存状态，不阻塞首屏。
