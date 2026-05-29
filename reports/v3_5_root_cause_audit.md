# SNInsightTerminal V3.5 Root Cause Audit

生成时间：2026-05-16

## 结论摘要

本轮审计确认，发行前最容易造成“看起来刷新了但实际不可验证”的问题集中在四类合同：交易时间轴、数据水位、预测元数据、模型晋级边界。修复后的系统不再把缺字段预测展示为正常结果，不再让图表层自行推导未来索引，也不允许未验证的 candidate 模型替换 active。

## 已确认根因与修复

### 1. 夜盘未来索引错误

根因：旧 `generate_future_trading_index()` 会用当前系统时间覆盖传入的 `last_timestamp`，导致测试或回放周五夜盘时被错误推到新的系统时间附近。

修复：移除该覆盖逻辑，未来索引只基于传入时间和 SHFE SN 交易日历生成。`test_friday_night_session_does_not_jump_to_monday` 已覆盖。

### 2. 数据水位字段不稳定

根因：不同输出目录里存在 `outputs` 与 `app_data/outputs` 两套缓存，旧 API 有时读到较空的 `sn_unified_forecast.json`，导致 `latest_price/latest_quote_time` 缺失。

修复：新增多目录候选读取与评分机制，优先选择包含 live quote、cards、watermark、quality 的最新有效 payload。同时补齐别名字段：`latest_price`、`latest_quote_time`、`fetch_timestamp`、`source`、`data_age_seconds`、`stale_status`、`using_fallback`。

### 3. 预测元数据缺失

根因：部分缓存中的预测卡只有方向和价格字段，缺少发行前必需的 `prediction_id/model_version/data_timestamp/feature_set_id/cache_key`，UI 可能无法判断是否为旧预测。

修复：新增 `_ensure_prediction_metadata()`，对七周期卡片补齐模型版本、数据时间、水位、特征集、scaler、事件 hash、promotion 状态和 cache key。新增 `test_prediction_metadata_contract.py` 作为回归测试。

### 4. cache key 不显式包含 horizon

根因：旧 cache key 是纯哈希，虽然大概率唯一，但人工排查周期混用时不可读。

修复：cache key 改为 `sn-v3.5:{horizon}:{model_version}:{hash}`，并纳入系统真实性审计。

### 5. 图表预测点位二次推导

根因：图表 API 中存在本地 forecast point 简化生成逻辑，可能绕过统一路径守门。

修复：图表预测点统一由 `build_forecast_curve()` 生成，保留 center/lower/upper、方向概率和路径修复元数据。

### 6. 模型优化不能直接替换 active

根因：用户要求同步优化模型，但真实训练、walk-forward、事件消融耗时且依赖数据水位，不能用未验证模型覆盖 active。

修复：新增受控任务类型 `train_candidate/walk_forward/event_ablation/promotion_check`，当前返回治理报告和状态。candidate 未通过方向优先 promotion gate 时显示 `active_retained` 或 `candidate_failed_or_not_run`，不伪造提升。

## 当前 smoke 状态

本地 API smoke 显示：

- 七周期 cards 可返回。
- 每张卡均有 `prediction_id`、`model_version`、`signal_strength`、`data_timestamp`。
- 数据水位字段可见。
- 若本地缓存行情过旧，系统显示 `stale` 与 `using_fallback=true`，不会伪装成最新实盘数据。

## 测试结果

```text
python -m unittest discover -s tests -p "test*.py" -v
Ran 44 tests
OK

pytest -q
44 passed

python -m compileall -q src
OK
```

## 仍需真实数据任务验证

完整模型优化仍需要在真实历史切片与事件库上执行 walk-forward、事件消融、概率校准和 promotion gate。若数据源不可用或样本不足，系统必须显示 `candidate_failed_or_not_run`、`insufficient_data` 或具体失败原因，不得宣称模型精度提升。

## 合规说明

本审计与修复仅用于沪锡期货 SN 量化投研系统工程质量提升，不构成投资建议、交易建议、收益承诺或风险承诺。
