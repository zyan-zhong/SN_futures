# Candidate Model Training

## Candidate v2 update

`candidate_v2` supports versioned training datasets and versioned walk-forward artifacts:

- Dataset manifest: `outputs/training_dataset_manifest_v2.json`
- Dataset files: `outputs/training_datasets/v2/train_*.parquet` or `.csv`
- Candidate registry: `outputs/model_registry/candidate_v2_model_registry.json`
- OOF traces: `outputs/walk_forward/v2/oof_trace_*.csv`

The v2 feature set is named `ohlcv_technical_regime_cross_market_event`. Cross-market and NewsAPI event fields are included only when real runtime data reaches the coverage threshold. If `event_factor_inputs.json` has no `used_in_model=true` events, event columns are intentionally excluded from `feature_cols`.

`candidate_v2` does not overwrite `candidate_v1`, does not write `active_model.json`, and does not generate customer predictions.

本阶段基于真实训练数据集训练 candidate model，并执行 purged walk-forward 验证。它不是 active model 发布流程。

## API

- `POST /api/terminal/models/train-candidate`
- `GET /api/terminal/models/candidate-status`
- `GET /api/terminal/models/walk-forward-results`

## 模型范围

- Logistic/Ridge 只用于内部对照指标。
- Candidate 使用 LightGBM；如果本机未安装 LightGBM，则自动降级到 sklearn `HistGradientBoosting`。
- Regime 样本不足时仅使用 global candidate。
- 概率校准只在 validation fold 内执行。

## 输出

- `outputs/model_registry/candidate_model_registry.json`
- `outputs/model_registry/candidate_training_status.json`
- `outputs/model_registry/candidate_artifacts/*.json`
- `outputs/walk_forward/wf_*.json`

Registry 中 candidate 记录状态固定为 `candidate`。本阶段不会调用 `promote_model`，也不会写入 active registry。

## 不做的事

- 不发布 active model。
- 不生成客户预测。
- 不生成客户回测。
- 不生成 baseline 预测。
- 不使用 sample data。
- 不绕过 promotion gate。

## 下一步

Prompt 43R 应只做 promotion gate 审计与晋级评估。如果 candidate 未通过真实 walk-forward、成本后验证、概率校准和无泄漏检查，必须保留现有 active 或继续显示暂无 active。
