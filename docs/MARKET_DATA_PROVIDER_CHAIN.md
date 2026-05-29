# 沪锡真实行情 Provider 链路

## 0.3.3-beta.1 验收状态

- 实时行情链：Sina realtime 已通过 smoke，symbol `nf_SN2606`，返回最新价。
- 历史行情链：AKShare `futures_zh_daily_sina` 已通过 smoke，symbol `SN0`，返回 2710 条历史行情。
- SHFE public：仅作为日线、库存、仓单等辅助源状态，不冒充实时行情；辅助不可用不导致主行情失败。
- last good cache：仅作为缓存展示，不冒充新行情。
- `final_status=full_success` 表示实时行情和历史行情均可用。

## 设计原则

行情刷新分成四条链路，不再用一个 provider 的局部成功代表全部成功：

1. 实时行情：Sina realtime、AKShare realtime。
2. 历史行情：AKShare `futures_zh_daily_sina`、`futures_main_sina`。
3. SHFE public 辅助：日线、仓单、库存、结算等辅助数据，不能冒充实时行情。
4. 最近成功缓存：只作为 fallback，不得当作新行情。

## Provider 尝试顺序

### 实时行情

- Sina：`resolve_target_contract()` 候选符号、`nf_SN0`、`nf_sn0`、`SN0`、`sn0`。
- AKShare realtime：`futures_zh_spot(symbol="SN0"/"sn0", market="CF", adjust="0"/"1")`，并兼容不同函数签名。

### 历史行情

- AKShare `futures_zh_daily_sina`：`SN0`、`sn0`、`SN`、`sn`。
- AKShare `futures_main_sina`：`SN0`、`sn0`、`SN`、`sn`。

### SHFE public

当前版本只作为辅助状态源。未读到可靠日线/仓单数据时返回 `auxiliary_unavailable`，不影响主行情状态。

## 输出文件

- `outputs/sn_live_snapshot.json`
- `outputs/sn_market_history.json`
- `outputs/data_watermark.json`
- `outputs/market_provider_status.json`
- `outputs/last_good_realtime_quote.json`
- `outputs/last_good_market_history.json`
- `outputs/shfe_public_status.json`
- `outputs/shfe_auxiliary_data.json`

## final_status

- `full_success`：实时行情可用，历史行情不少于 60 条。
- `history_only_success`：历史行情不少于 60 条，实时价暂缺。
- `quote_only_partial`：实时价可用，但历史行情少于 20 条，只能展示最新价。
- `cache_only`：只有最近成功缓存，不能当作新行情。
- `failed`：无实时、无历史、无可用缓存。

## 排查方式

查看 `market_provider_status.json`：

- `realtime_attempts`：实时行情每个 symbol 的尝试结果。
- `history_attempts`：AKShare 历史函数和 symbol 的尝试结果。
- `shfe_attempts`：SHFE 辅助源状态。
- `blocking_reasons`：当前阻断预测/回测的原因。
- `next_actions_zh`：下一步建议。
