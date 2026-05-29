# 运行期数据刷新工作流

SNInsightTerminal 安装包只包含程序、前端资源、配置样例和必要文档，不包含用户本地缓存、真实 API key、运行期数据库或模型运行产物。首次打开终端时，如果用户数据目录为空，页面会显示样例模式、空状态或诊断信息，而不会伪造真实行情、新闻、预测或回测。

## 一键刷新流程

点击“一键刷新数据”后，后端按顺序执行：

1. 行情：刷新真实沪锡实时价、历史行情、SHFE 辅助状态和最近成功缓存。
2. 新闻：NewsAPI 已配置时拉取锡、沪锡、LME tin、缅甸、印尼、半导体、光伏、库存等相关新闻；未配置时明确跳过。
3. 事件：把新闻整理为事件证据，并写入事件 store。
4. 特征：记录事件特征刷新状态，供后续训练/预测链路使用。
5. 预测：仅在真实历史行情充足且有可用 active 模型/真实预测结果时生成；否则写明原因。
6. 报告：真实数据不足时生成“数据不足版报告”，不伪造方向、收益或命中率。

## 真实行情链路

行情刷新拆成四条独立链路：

- 实时行情：Sina `nf_SN0` 与候选合约，AKShare `futures_zh_spot`。
- 历史行情：AKShare `futures_zh_daily_sina`、`futures_main_sina`。
- SHFE public 辅助：日线、仓单、库存、结算等辅助源，不作为实时主行情源。
- 最近成功缓存：`last_good_realtime_quote.json` 与 `last_good_market_history.json`。

实时价成功不会跳过历史行情刷新。历史行情成功但实时价失败时，终端仍可显示历史图，并说明“历史行情可用，实时价暂缺”。

## 行情 final_status

- `full_success`：实时行情可用，历史行情不少于 60 条。
- `history_only_success`：历史行情不少于 60 条，实时价暂缺。
- `quote_only_partial`：实时价可用，但历史行情少于 20 条，只能展示最新价。
- `cache_only`：只有最近成功缓存，不能当作新行情。
- `failed`：无实时、无历史、无可用缓存。

## 输出文件

刷新状态：

- `%LOCALAPPDATA%\SNInsightTerminal\outputs\refresh_status.json`
- `%LOCALAPPDATA%\SNInsightTerminal\outputs\refresh_history.json`
- `%LOCALAPPDATA%\SNInsightTerminal\logs\refresh_YYYYMMDD.log`

行情文件：

- `%LOCALAPPDATA%\SNInsightTerminal\outputs\sn_live_snapshot.json`
- `%LOCALAPPDATA%\SNInsightTerminal\outputs\sn_market_history.json`
- `%LOCALAPPDATA%\SNInsightTerminal\outputs\data_watermark.json`
- `%LOCALAPPDATA%\SNInsightTerminal\outputs\market_provider_status.json`
- `%LOCALAPPDATA%\SNInsightTerminal\outputs\last_good_realtime_quote.json`
- `%LOCALAPPDATA%\SNInsightTerminal\outputs\last_good_market_history.json`
- `%LOCALAPPDATA%\SNInsightTerminal\outputs\shfe_public_status.json`
- `%LOCALAPPDATA%\SNInsightTerminal\outputs\shfe_auxiliary_data.json`

新闻和事件文件：

- `%LOCALAPPDATA%\SNInsightTerminal\outputs\events\news_raw.json`
- `%LOCALAPPDATA%\SNInsightTerminal\outputs\events\news_events.json`
- `%LOCALAPPDATA%\SNInsightTerminal\outputs\events\provider_status.json`
- `%LOCALAPPDATA%\SNInsightTerminal\outputs\events\event_store.json`
- `%LOCALAPPDATA%\SNInsightTerminal\outputs\events\event_evidence_by_horizon.json`

预测文件：

- `%LOCALAPPDATA%\SNInsightTerminal\outputs\sn_unified_forecast.json`
- `%LOCALAPPDATA%\SNInsightTerminal\outputs\sn_live_predictions.json`

报告文件：

- `%LOCALAPPDATA%\SNInsightTerminal\reports\sn_daily_report.md`
- `%LOCALAPPDATA%\SNInsightTerminal\reports\sn_weekly_report.md`
- `%LOCALAPPDATA%\SNInsightTerminal\reports\sn_monthly_report.md`
- `%LOCALAPPDATA%\SNInsightTerminal\reports\sn_event_report.md`

## 预测与回测门禁

系统明确禁止 baseline 预测、baseline 回测、随机预测和样例数据冒充真实结果。以下情况不会生成真实预测/回测：

- 真实历史行情少于 60 条。
- 当前只有缓存行情。
- 当前是样例模式。
- 没有可用 active 模型或真实预测结果。

用户会看到中文原因，例如：

- “真实历史行情不足 60 条，未生成预测/回测。”
- “当前仅有缓存行情，未生成新的真实预测。”
- “暂无可用 active 模型或有效预测结果，未生成预测。”

## 如何排查行情图为空

1. 先点击“一键刷新数据”。
2. 打开“刷新与数据源”，查看实时行情、历史行情、SHFE 辅助和最近成功缓存。
3. 检查 `market_provider_status.json` 中的 `realtime_attempts`、`history_attempts`、`blocking_reasons`。
4. 历史点数少于 20 时，不能绘制有效行情图。
5. 历史点数少于 60 时，不能生成预测/回测。

## 如何排查新闻为空

1. 在设置页确认 NewsAPI 是否已配置。
2. 未配置时是正常降级，不应显示为“已过期”。
3. 已配置但为空时，查看刷新状态中的 query attempts、返回条数和错误原因。

## 合规边界

所有预测、信号、报告和持仓情景均仅供沪锡期货量化投研参考，不构成投资建议，不承诺收益，不接实盘交易。

