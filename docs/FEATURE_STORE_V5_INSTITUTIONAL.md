# Feature Store v5 Institutional Data Layer

Feature Store v5 is the versioned research dataset layer that aligns real沪锡 market history with institutional data inputs. It does not train models, publish active models, generate customer predictions, or use baseline/fake prediction paths.

## Inputs

- `outputs/sn_market_history.json`: OHLCV is the primary trading-day index.
- `outputs/fundamentals/sn_tushare_daily.json`: Tushare open interest, settlement, volume, and daily contract fields.
- `outputs/fundamentals/sn_tushare_warehouse_receipt.json`: Tushare warehouse receipt fields.
- `outputs/fundamentals/sn_tushare_holding.json`: Tushare member holding and net-position fields.
- `outputs/fundamentals/managed_fundamentals.json`: managed proxy spot, basis, inventory, LME tin, and term-structure fields.
- `outputs/fundamentals/sn_cross_market.json`: Alpha Vantage USD/CNY, US10Y, and copper macro proxy fields.
- `outputs/events/event_factor_inputs.json`: NewsAPI event factors using only `used_in_model=true` news.

## Alignment Rules

- Market history is the main date index.
- Tushare and managed proxy rows are joined by `trade_date`.
- Cross-market fields are aligned by the cross-market join service and may forward-fill within its configured stale window.
- Event factors are exact-date joins. Missing-event dates are zero only when they represent true no-event observations; event values are not backfilled to earlier dates.
- No future labels or forward returns are allowed in `usable_fields`.

## Outputs

- `outputs/feature_store/v5/feature_store.csv`
- `outputs/feature_store/v5/feature_store_manifest.json`
- `outputs/training_dataset_manifest_v5.json`
- `outputs/training_datasets/v5/train_1d.parquet` or CSV fallback
- `outputs/training_datasets/v5/train_3d.parquet` or CSV fallback
- `outputs/training_datasets/v5/train_5d.parquet` or CSV fallback
- `outputs/training_datasets/v5/train_10d.parquet` or CSV fallback
- `outputs/training_datasets/v5/train_20d.parquet` or CSV fallback

## Manifest Guarantees

The v5 manifest records row count, date range, source quality, usable fields, excluded fields, exclusion reasons, group coverage, no-lookahead status, and whether mock/sample data was detected.

`sample_data_used=false` and `baseline_used=false` are required for production research builds. If managed proxy mock data is present, `mock_data_used=true` is recorded so the result cannot be confused with production-quality fundamentals.

## Coverage Expectations

- Tushare can improve `open_interest`, `settlement`, warehouse receipt, and member-position coverage when a real token is configured.
- Managed proxy can improve spot, basis, inventory, LME tin, and term-structure coverage when the service returns structured rows.
- Alpha cross-market can improve USD/CNY, US10Y, and copper proxy coverage.
- News events improve event-factor coverage only when high-quality tin-related news passes the relevance gate.

Missing sources remain excluded with explicit reasons. The system does not invent basis, inventory, LME, term-structure, or event fields.
