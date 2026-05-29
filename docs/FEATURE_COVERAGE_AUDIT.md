# 真实因子覆盖率审计

本轮只审计真实数据能够支撑的因子覆盖率，不训练模型、不生成预测、不生成回测、不接入 baseline。

## 数据来源

- `outputs/sn_market_history.json`：真实沪锡历史行情，当前可提供 OHLCV 历史序列。
- `outputs/sn_live_snapshot.json`：实时行情快照和主合约信息。
- `outputs/events/event_store.json`、`outputs/events/news_events.json`：新闻和事件证据；如存在，会按事件日期映射为事件分数。
- `outputs/shfe_auxiliary_data.json`：SHFE 辅助数据；当前可靠库存/仓单字段仍不足。
- `outputs/data_watermark.json`：运行期数据水位和质量说明。

## 当前真实可用因子

在当前本机缓存中，`sn_market_history.json` 约有 2710 行历史行情。可支撑：

- `raw_market`：`open`、`high`、`low`、`close`、`volume` 可用；`open_interest` 暂缺。
- `technical`：EMA spread、均线偏离、ROC、breakout、RSI、ATR、Bollinger Z、CCI、WR、OBV slope 等技术因子可用。
- `mean_reversion`：收盘价 z-score、RSI reversal、gap reversion、price overextension 等均值回归因子可用。
- `regime`：可基于价格、成交量、波动和事件分数生成 regime label、趋势分数和波动分数。
- `event`：如果新闻/事件文件存在且事件日期能映射到行情日期，可生成事件热度、供应/需求/库存/宏观冲击、事件衰减和事件波动切换因子。

## 当前部分可用因子

部分可用取决于最新新闻/事件是否能覆盖行情时间窗口。若新闻事件为空、过旧或日期无法匹配，则事件组会降级为不可用。

## 当前不可用因子

以下因子组主要缺底层字段：

- `term_structure`：缺 `near_contract_close`、`far_contract_close`、`near_open_interest`、`far_open_interest` 等多合约期限结构字段。
- `basis`：缺 `spot_price`、`spot_premium` 等现货和升贴水字段。
- `inventory`：缺 `shfe_inventory`、`lme_inventory` 等库存字段。
- `cross_market`：缺 `lme_tin_close`、`usd_cny`、`dxy`、`us10y` 等外盘和宏观字段。

## 训练准备度

- 基础 OHLCV 技术模型：当前具备前置条件。
- 完整基本面模型：当前不具备前置条件，需要补齐基差、库存、外盘、汇率、美元指数、利率和更稳定的事件数据。

## API

- `GET /api/terminal/factors/coverage`

返回：

- 样本数和日期范围。
- 每个因子组的覆盖率。
- 可训练、部分可用、不可用因子列表。
- 缺失底层字段。
- 训练准备度说明。

## 边界

该审计接口只读取真实运行期缓存并构造 feature matrix。它不会训练模型，不会生成预测，不会生成回测，也不会把 sample data 写入真实分析链路。
# Prompt 50S SHFE 辅助数据覆盖率更新

因子覆盖率服务已接入以下新增文件：

- `sn_shfe_inventory.json`
- `sn_shfe_warehouse_receipts.json`
- `sn_spot_basis.json`
- `sn_exchange_daily.json`
- `sn_member_positions.json`

覆盖率审计会继续区分 `function_unavailable`、`no_tin_rows`、`missing_required_columns`、`source_blocked` 和 `stale_cache_only` 等原因。若现货、库存、仓单或交易所日线仍缺真实锡数据，对应 basis、inventory、term_structure 和 member-position 衍生因子继续标记为不可用或部分可用，不会为了提升覆盖率填充伪造数据。
 
# Prompt 51S 在线源覆盖率更新

因子覆盖率服务已接入新的在线扩展文件：

- `outputs/fundamentals/sn_cross_market.json`
- `outputs/fundamentals/sn_lme_tin.json`
- `outputs/fundamentals/managed_proxy_fundamentals.json`，如果未来托管服务可用
- `outputs/fundamentals/fx_macro_provider_status.json`
- `outputs/fundamentals/lme_tin_provider_status.json`

当前自动在线可用字段取决于配置和公开源返回结果：

- Alpha Vantage key 可用时，可自动补齐 `usd_cny`、`usd_cny_return`、`us10y`、`us10y_change`，以及可选 `copper_global_proxy`。
- LME tin 若无可靠免费结构化源，`lme_tin_close` 和 `lme_inventory` 仍标记为不可用。
- 现货、基差、库存和仓单若 AKShare/公开源没有沪锡行，仍标记为不可用；推荐后续通过发行方托管数据服务或正式数据供应商补齐。

本轮不训练模型、不发布 active、不生成客户预测。样例数据、baseline 和客户本地文件不会进入真实因子覆盖率。

# Prompt 52S 在线因子准备度结论

新增 `online_feature_readiness_service.py` 和 `GET /api/terminal/factors/online-readiness`，用于判断在线字段是否足以支持下一轮研究：

- `raw_market`、`technical`、`mean_reversion`、`regime` 继续作为当前优先研究方向。
- 如果 Alpha Vantage key 已配置且刷新成功，`cross_market` 可加入 `usd_cny_return` 与 `us10y_change` 等宏观字段。
- `basis`、`inventory`、`lme` 若仍缺真实结构化字段，覆盖率不应提升。
- 当前公开在线源不能提供的字段，推荐通过发行方托管数据服务或正式供应商补齐。

客户不需要上传 CSV/Excel。该报告不训练模型、不生成预测、不发布 active。
