# V2 行情链路回归审计

## 结论摘要

旧 V2 链路中，沪锡行情主要依赖 Sina 期货实时接口，核心连续合约符号为 `nf_SN0`，并结合 `resolve_target_contract()` 生成的近月候选合约一起请求。旧缓存中可以看到 `https://hq.sinajs.cn/list=nf_SN0,...` 的响应，说明 V2 能够通过 Sina 获取沪锡连续合约实时报价。

当前 0.3.2-beta.1 的主要回归点不是单个 provider 不存在，而是刷新流程把“实时价成功”误当作整条行情链路成功，提前停止后续历史行情获取，导致：

- 有时可以拿到最新价，但 `sn_market_history.json` 没有足够历史点。
- 图表、预测、回测缺少真实历史行情输入。
- 前端只能显示刷新失败或空状态。
- SHFE public 辅助源未实现可靠日线/仓单读取时，被用户理解成主行情失败。

## 旧 V2 行情更新方式

旧链路相关实现主要在：

- `src/sn_futures/api_clients.py`
- `src/sn_futures/market_data_hub.py`
- `src/sn_futures/contracts.py`

关键逻辑：

- `SinaFinanceClient.fetch_quotes(symbols)` 请求 `https://hq.sinajs.cn/list=...`。
- `market_data_hub._normalize_sina_quote()` 兼容 `nf_` 连续合约字段。
- `resolve_target_contract()` 生成近月候选合约与连续合约。
- 连续合约默认是 `nf_SN0`。
- 历史行情相关 symbol 通常从 `nf_SN0` 转为 `SN0`。

## 旧 V2 使用的主要 symbol

- Sina 实时：`nf_SN0`
- Sina 近月候选：`nf_SNYYMM`
- 历史行情：`SN0` / `SN`
- 兼容形式：`sn0`、`sn`

## 旧 V2 成功写入的文件

旧链路和后续版本都围绕以下运行期文件组织：

- `sn_live_snapshot.json`
- `sn_market_history.json`
- `data_watermark.json`
- `sn_unified_forecast.json`
- `sn_live_predictions.json`

## 当前差异

当前 `refresh_sn_market_data()` 旧实现把 provider 混在一条链中，只要某个 payload 有 `latest_price` 就提前 `break`，历史行情 provider 没有机会运行。这是本次修复的核心。

另一个差异是缓存原先只有 `last_good_market.json`，无法区分“最近成功实时价”和“最近成功历史行情”，因此前端无法说明到底是哪条链路失败。

## 最可能失败原因

1. Sina 实时报价成功后提前停止，AKShare 历史未执行。
2. AKShare 历史函数和 symbol 兼容不足。
3. 实时行情、历史行情、SHFE 辅助源状态混在一起。
4. 缓存被视为新行情，缺少 `from_cache` 和 `cache_age` 解释。
5. 历史行情不足时仍尝试走预测链路，造成用户误以为系统在“伪预测”。

## 需要恢复的逻辑

- 实时行情和历史行情独立运行。
- 优先恢复 `nf_SN0`、`SN0` 等 V2 可用 symbol。
- AKShare 历史行情必须独立于 Sina 实时行情。
- SHFE public 只作为辅助，不得导致主行情失败。
- 分离 `last_good_realtime_quote.json` 和 `last_good_market_history.json`。
- 真实历史行情少于 60 条时，不生成预测和回测。
- 无 active 模型时，不生成 baseline 预测。

