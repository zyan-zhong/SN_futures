# 沪锡 SN 因子工程说明

本文档说明 `sn_futures.features_core` 的分组因子库和统一特征矩阵管道。该层用于把行情、库存、基差、跨市场、新闻事件和市场状态整理成后续模型、回测可复用的特征，不包含未来收益标签。

## 因子分组

### 技术面因子

文件：`src/sn_futures/features_core/technical.py`

用途：衡量趋势、突破、波动和量价确认。包括 `ema_spread_5_20`、`ema_spread_10_60`、`ma_bias_20`、`ma_bias_60`、`roc_5`、`roc_10`、`roc_20`、`breakout_20`、`breakout_60`、`rsi_14`、`atr_14`、`bollinger_z_20`、`cci_20`、`wr_14`、`obv_slope_10`。

依赖字段：`open`、`high`、`low`、`close`、`volume`。

### 均值回归因子

文件：`src/sn_futures/features_core/mean_reversion.py`

用途：识别价格短期过度延伸、RSI反转和跳空回补倾向。包括 `zscore_close_20`、`zscore_close_60`、`rsi_reversal_14`、`gap_reversion`、`price_overextension_score`。

依赖字段：`open`、`close`。

### 期限结构因子

文件：`src/sn_futures/features_core/term_structure.py`

用途：衡量近远月价差、展期收益和换月流动性。包括 `near_far_spread`、`term_structure_slope`、`calendar_spread_momentum`、`roll_yield_proxy`、`open_interest_roll_ratio`、`main_contract_switch_flag`。

依赖字段：`near_contract_close`、`far_contract_close`、`near_open_interest`、`far_open_interest`、`main_contract`。如果缺少多合约数据，系统会在 `missing_feature_report` 中输出中文缺失原因，不会中断训练或预测。

### 基差因子

文件：`src/sn_futures/features_core/basis.py`

用途：衡量现货紧张程度、升贴水变化和交割月基差动量。包括 `spot_futures_basis`、`basis_zscore_60`、`basis_mom_5`、`basis_mom_20`、`basis_percentile_252`、`spot_premium_mom`、`delivery_basis_momentum`、`cash_tightness_score`。

依赖字段：`spot_price`、`close`、`spot_premium`、`delivery_month_flag`。缺少现货或升贴水时自动降级，并保留缺失说明。

### 库存因子

文件：`src/sn_futures/features_core/inventory.py`

用途：跟踪 SHFE、LME 和保税区显性库存压力。包括 `shfe_inventory_delta_1w`、`shfe_inventory_delta_4w`、`lme_inventory_delta_1w`、`global_visible_inventory`、`inventory_percentile_3y`、`inventory_pressure_score`。

依赖字段：`shfe_inventory`、`lme_inventory`、可选 `bonded_inventory`。

### 跨市场因子

文件：`src/sn_futures/features_core/cross_market.py`

用途：刻画 LME 锡、汇率、美元、利率和全球风险偏好对沪锡的联动影响。包括 `lme_tin_return_1d`、`lme_tin_return_3d`、`lme_tin_overnight_return`、`lme_shfe_spread`、`usd_cny_return`、`dxy_return`、`us10y_change`、`global_risk_sentiment_proxy`。

依赖字段：`lme_tin_close`、`usd_cny`，可选 `dxy`、`us10y`、`lme_overnight_return`。

### 新闻事件因子

文件：`src/sn_futures/features_core/event.py`

用途：把新闻政策、供应扰动、需求冲击、库存仓单和宏观事件转化为可入模特征。包括 `news_count_1d`、`news_count_7d`、`supply_shock_score`、`demand_shock_score`、`inventory_shock_score`、`macro_risk_score`、`event_recency_decay_score`、`event_vol_regime_shift`。

依赖字段：`news_event_score` 或 `event_score`，可选 `supply_event_score`、`demand_event_score`、`inventory_event_score`、`macro_event_score`。

### 市场状态因子

文件：`src/sn_futures/features_core/regime.py`

用途：输出 `regime_label`，支持趋势、震荡、事件冲击、流动性偏薄等状态识别。标签包括 `TREND_UP_LOW_VOL`、`TREND_UP_HIGH_VOL`、`TREND_DOWN_LOW_VOL`、`TREND_DOWN_HIGH_VOL`、`RANGE_LOW_VOL`、`RANGE_HIGH_VOL`、`EVENT_SHOCK`、`DELIVERY_SQUEEZE`、`LIQUIDITY_THIN`。

## 统一特征管道

入口：`src/sn_futures/features_core/pipeline.py`

核心函数：`build_feature_matrix(raw_frame)`

输出：

- `feature_df`：统一特征矩阵。
- `feature_metadata`：每个因子的中文说明、分组、方向提示、依赖字段和回看窗口。
- `factor_groups`：按因子组聚合的字段列表。
- `missing_feature_report`：缺失字段与中文降级原因。
- `data_quality_score`：来自数据质量检查的 0 到 1 评分。
- `warnings`：因子构建异常或未来字段移除提示。

## 缺失数据如何降级

免费公开数据经常存在库存、现货、外盘或新闻字段缺口。`features_core` 的策略是：

- 必需价格字段缺失时记录 `missing_feature_report`。
- 可选字段缺失时对应因子使用内部缺失标记或 0，不让系统崩溃；对外 API、报告和 UI 会统一展示为“数据暂缺”等中文状态。
- 后续训练或 smoke pipeline 会对模型特征做前值填充和 0 填充，但缺失原因仍保留在报告中。

## 如何避免未来函数

- 所有 rolling、diff、pct_change 特征只使用当前及历史数据。
- 未来收益、方向、triple-barrier、meta-label 字段只由 `labels` 模块生成。
- `build_feature_matrix` 会自动移除 `ret_*`、`direction_*`、`tb_*`、`meta_*` 等标签字段，避免标签进入特征矩阵。
- 训练前仍建议调用 `labels.leakage_guard.check_feature_label_leakage` 做二次检查。

## 如何接入模型和回测

最小闭环脚本：`scripts/smoke_train_pipeline.py`

流程：

1. 构造或读取 SN 行情数据。
2. 运行 `build_validation_report` 得到数据质量评分。
3. 运行 `build_feature_matrix` 得到统一因子矩阵。
4. 使用 `labels.add_forward_return_labels` 生成目标。
5. 调用 `models.train.train_horizon_models` 训练 baseline/regime 模型。
6. 调用 `models.predict.predict_horizon` 生成预测合同。
7. 将“多头研究观察/空头研究观察/观望”转换为回测信号。
8. 调用 `backtest_core.run_futures_backtest` 做成本后快速回测。

该脚本不依赖真实 API key，只用于验证数据质量、因子、标签、模型、回测之间的工程闭环。
