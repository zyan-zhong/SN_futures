# Feature Store v3

Feature Store v3 is the reproducible data layer for research datasets. It aligns real SHFE tin market history, Alpha Vantage cross-market fields, and NewsAPI event factor inputs to the SHFE tin trading calendar.

This step does not train models, does not publish an active model, does not generate customer predictions, and does not use baseline or sample data.

## Inputs

- `outputs/sn_market_history.json`
- `outputs/fundamentals/sn_cross_market.json`
- `outputs/events/event_factor_inputs.json`
- `outputs/feature_coverage_report*.json`, when available for audit context
- `outputs/data_watermark.json`, when available for runtime audit context

## Outputs

- `outputs/feature_store/v3/feature_store.csv`
- `outputs/feature_store/v3/feature_store_manifest.json`
- `outputs/training_dataset_manifest_v3.json`, after building training dataset v3
- `outputs/training_datasets/v3/train_1d.csv|parquet`
- `outputs/training_datasets/v3/train_3d.csv|parquet`
- `outputs/training_datasets/v3/train_5d.csv|parquet`
- `outputs/training_datasets/v3/train_10d.csv|parquet`
- `outputs/training_datasets/v3/train_20d.csv|parquet`

## Alignment Rules

- Market history is the primary index.
- Cross-market data is joined by `trade_date`.
- Cross-market values may be forward-filled for at most 5 trading days.
- Cross-market rows older than 5 trading days are marked stale and are not counted as usable coverage.
- Event factor inputs are joined only on exact `trade_date`.
- Dates without model-approved events are filled with zero and marked `true_zero_event`.
- Missing NewsAPI/event data is marked `missing_news_data`.
- The pipeline does not backfill future event information into earlier dates.

## Field Admission

Fields enter `usable_fields` only when they pass coverage and leakage checks.

Common exclusion reasons:

- `all_missing`
- `insufficient_non_null_rate`
- `stale_after_alignment`
- `missing_news_data`
- `no_used_in_model_event_inputs`
- `all_zero_true_zero_event`
- `label_or_future_return_field`

The manifest records `field_sources`, `usable_fields`, `excluded_fields`, and `exclusion_reasons` for reproducibility.

## Training Dataset v3

Build through:

```http
POST /api/terminal/training-dataset/build
```

Payload:

```json
{
  "dataset_version": "v3",
  "feature_store_version": "v3",
  "feature_set": "ohlcv_technical_regime_cross_market_event"
}
```

The dataset builder uses Feature Store v3 `usable_fields`, removes label-like columns, writes forward-return research labels, and drops rows whose future label window is incomplete.

## API

- `POST /api/terminal/feature-store/build`
- `GET /api/terminal/feature-store/status`

Both endpoints return masked/runtime-safe metadata only. They do not expose API keys and do not trigger model training or prediction generation.
