# Cross-Market Data Alignment Audit

This audit documents Prompt 57S. It only covers Alpha Vantage cross-market data integrity, cache protection, temporal alignment, feature coverage, and training-dataset feature inclusion. It does not train a model, publish an active model, generate customer predictions, or use baseline/fake prediction logic.

## Runtime Snapshot

- Runtime output directory: `%LOCALAPPDATA%\SNInsightTerminal\outputs`
- `sn_market_history.json`: present, 2713 rows
- Market history date range: 2015-03-27 to 2026-05-26
- `fundamentals/sn_cross_market.json`: present, 0 rows in the current runtime snapshot
- `fundamentals/fx_macro_provider_status.json`: `status=rate_limited`, `configured=true`, `key_source=private_bundle`
- `fundamentals/last_good_cross_market.json`: not present in the current runtime snapshot

## Alignment Result

- Raw cross-market row count: 0
- Cross-market date range: unavailable
- Market date range: 2015-03-27 to 2026-05-26
- Exact date overlap: 0
- Aligned non-null count: 0
- Blocking reason: `empty_file`
- `lme_tin_close`: unavailable
- `copper_global_proxy`: kept separate and never mapped to `lme_tin_close`

## Root Cause

The Alpha Vantage integration was configured, but the current refresh returned `rate_limited`. Earlier logic could leave `sn_cross_market.json` as an empty file, so feature coverage saw no aligned cross-market rows. Candidate v2 therefore had no real cross-market increment.

The fix separates two cases:

- If a non-empty `sn_cross_market.json` already exists, `rate_limited`, `key_invalid`, or `network_failed` refreshes preserve that file and report `from_cache=true`.
- If no non-empty cache exists, the system keeps coverage at 0 and reports the explicit blocking reason instead of fabricating fields.

## Implemented Fixes

- Added `cross_market_feature_join_service.py`.
- Standardizes cross-market dates to local trading days.
- Sorts and de-duplicates cross-market rows by date.
- Aligns FX and macro data to SN market history dates.
- Allows forward fill for at most 5 trading days.
- Marks stale rows after the 5-trading-day window.
- Exposes alignment diagnostics to feature coverage and online readiness.
- Keeps `copper_global_proxy` and copper returns separate from LME tin fields.

## Feature Coverage Behavior

When aligned cross-market fields reach the coverage threshold, these fields can enter `usable_feature_cols` and v2 training manifests:

- `usd_cny_return`
- `us10y_change`
- `copper_global_proxy_return`

When the file is empty, stale, or has no date overlap, coverage remains unchanged and the reason is exposed as one of:

- `no_file`
- `empty_file`
- `no_date_overlap`
- `stale_after_alignment`
- `insufficient_non_null_rate`
- `key_missing`
- `rate_limited`

## Current Coverage

Current runtime coverage remains unchanged because no non-empty cross-market cache is available:

- `cross_market`: 0.0
- `training_dataset_manifest_v2.cross_market_feature_cols`: `[]`
- `training_dataset_manifest_v2.cross_market_excluded_reason`: `no_usable_aligned_cross_market_fields`

The TDD fixtures verify that overlapping, non-empty cross-market data does raise coverage and is included in v2 feature columns.

## Boundaries

- No active model was written.
- No customer prediction was generated.
- No baseline prediction or baseline backtest was generated.
- No fake market, cross-market, LME, basis, or inventory field was generated.
