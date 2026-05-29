# 沪锡基本面数据源

## 期限结构

目标字段包括 `near_contract_close`、`far_contract_close`、`near_open_interest`、`far_open_interest`、`main_contract_switch_flag`、`roll_yield_proxy` 和 `term_structure_slope`。

当前实现只接受真实多合约数据。若只能获得 `SN0` 或主力连续合约，系统会标记“期限结构不可用”，不会用同一个合约同时冒充近月和远月。

## 现货和基差

目标字段包括 `spot_price`、`spot_premium`、`spot_futures_basis`、`basis_zscore_60`、`basis_percentile_252` 和 `cash_tightness_score`。

缺少真实国内现货锡价格或升贴水时，基差因子不可用。

## 库存和仓单

目标字段包括 `shfe_inventory`、`shfe_warehouse_receipt`、`lme_inventory`、`global_visible_inventory`、`inventory_delta_1w`、`inventory_delta_4w`、`warehouse_receipt_delta_1w` 和 `inventory_percentile_3y`。

库存因子需要真实 SHFE/LME 库存或仓单数据。缺失时只显示缺失说明。

## 外盘、汇率和宏观

目标字段包括 `lme_tin_close`、`usd_cny`、`dxy`、`us10y`、`lme_shfe_spread` 和对应变化率。

Alpha Vantage 可用于 USD/CNY 和 US10Y 辅助数据，但不作为沪锡主行情源。LME 锡收盘价仍需要真实可用数据源补齐。
# Prompt 50S SHFE/AKShare 辅助源补齐

本轮新增 `shfe_public_data_service`，将 SHFE public 从单一状态拆成官网直连、AKShare 库存、仓单、现货基差、交易所日线和会员持仓。官网直连若被人机验证阻断会标记为 `blocked_by_waf`，该状态不视为主行情失败。

新增输出文件：

- `outputs/fundamentals/shfe_public_provider_status.json`
- `outputs/fundamentals/sn_shfe_inventory.json`
- `outputs/fundamentals/sn_shfe_warehouse_receipts.json`
- `outputs/fundamentals/sn_spot_basis.json`
- `outputs/fundamentals/sn_exchange_daily.json`
- `outputs/fundamentals/sn_member_positions.json`

仍然坚持真实数据策略：无锡行、缺字段或函数不可用时只记录原因，不伪造库存、仓单、基差或现货价格。

# Prompt 51S 在线自动数据源扩展层

本轮新增在线数据源 registry 和三个自动扩展服务：

- `online_data_source_registry.py`：统一列出公开在线源、API key 源、LME 探测源和可选托管源，并保证 `client_upload_required=false`。
- `online_cross_market_service.py`：通过 Alpha Vantage 自动尝试 USD/CNY、US10Y 和铜宏观代理。Alpha Vantage 不用于沪锡主行情、现货、库存或基差。
- `online_lme_tin_service.py`：探测 LME tin 结构化数据可用性。没有可靠免费源时标记 `paid_or_unavailable`，不使用铜、铝或新闻价格替代锡价。
- `managed_data_proxy_service.py`：默认关闭的发行方托管数据代理客户端，用于未来免客户配置补齐 spot/basis/inventory/LME 字段。

客户不需要 CSV/Excel，也不需要上传本地数据文件。公开在线源无法返回沪锡相关行时，系统会明确显示 `no_tin_rows`、`function_unavailable`、`key_missing`、`rate_limited`、`paid_or_unavailable` 或 `disabled`，不会伪造数据。
