# OOF 样本外验证轨迹诊断

OOF trace 是 walk-forward 或 research experiment 在每个 validation fold 上保存的逐样本 out-of-fold prediction trace。它只用于研究诊断，不是客户预测，不会发布 active，也不会绕过 promotion gate。

## 文件位置

候选模型 walk-forward：

- `outputs/walk_forward/oof_trace_1d.csv`
- `outputs/walk_forward/oof_trace_3d.csv`
- `outputs/walk_forward/oof_trace_5d.csv`
- `outputs/walk_forward/oof_trace_10d.csv`
- `outputs/walk_forward/oof_trace_20d.csv`

研究实验：

- `outputs/model_research/experiments/<experiment_id>/oof_trace_<horizon>.csv`

每个 trace 旁边会生成 `.summary.json` 摘要。

## 字段

核心字段包括：

- `horizon`
- `fold_id`
- `timestamp`
- `label_start_time`
- `label_end_time`
- `close`
- `realized_direction`
- `realized_return`
- `realized_vol`
- `raw_prob_up`
- `calibrated_prob_up`
- `predicted_direction`
- `expected_return`
- `confidence`
- `trade_edge`
- `selected_signal`
- `no_trade_reason`
- `regime_label`
- `regime_volatility_score`
- `regime_trend_score`
- `data_quality_score`
- `feature_coverage_score`
- `model_family`
- `model_id`
- `calibration_method`
- `cost_assumption`
- `sample_weight`
- `is_high_confidence_top_10`
- `is_high_confidence_top_20`
- `error_type`
- `drawdown_contribution`

## 可计算诊断

OOF trace 支持精确计算：

- 混淆矩阵。
- 概率校准分桶。
- confidence decile 表现。
- Top 10% / Top 20% 高置信样本命中率。
- 高置信错误样本列表。
- Regime 错误热区。
- 回撤贡献样本。

## API

- `GET /api/terminal/models/oof-trace-summary?horizon=1d`
- `GET /api/terminal/models/oof-trace-sample?horizon=1d&limit=200`
- `GET /api/terminal/research/oof-trace-summary?id=<experiment_id>`

## 使用边界

- OOF trace 不是客户预测。
- OOF trace 不发布 active。
- OOF trace 不使用 sample data 参与真实模型验证。
- OOF trace 不用于降低 promotion gate。
- 没有 active model 时，前端仍不能生成客户预测。
