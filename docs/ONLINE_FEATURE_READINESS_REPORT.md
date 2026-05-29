# Online Feature Readiness Report

This report documents the online feature-readiness layer through Prompt 57S. It only audits data availability, alignment, and research readiness. It does not train an active model, generate customer predictions, use baseline logic, or fabricate missing fields.

## Customer Data Path

- Customers do not need to upload CSV or Excel files.
- The terminal automatically attempts public online sources, API-key sources, and optional managed proxy sources.
- Alpha Vantage is used only for FX, Treasury, and macro proxy fields.
- NewsAPI is used only for event-news inputs.
- AKShare is used for market and selected futures public data.
- LME tin, spot, basis, inventory, and warehouse fields remain unavailable when no reliable structured source is available.
- The system does not synthesize unavailable fields.

## Prompt 57S Cross-Market Alignment

Online readiness now uses aligned cross-market diagnostics instead of raw file presence alone. A field is counted as available only when it has sufficient non-null coverage after alignment to SN trading dates.

Current runtime state:

- Alpha Vantage key is configured through the private bundle path.
- Alpha Vantage refresh currently returns `rate_limited`.
- `sn_cross_market.json` exists but currently has 0 rows.
- No non-empty `last_good_cross_market.json` cache is available in the runtime directory.
- Cross-market readiness reports `empty_file`, so v2 feature coverage is not raised.

Alignment rules:

- FX and macro fields can forward-fill onto SN trading dates for at most 5 trading days.
- Rows beyond the 5-trading-day window are marked stale and excluded from usable coverage.
- `copper_global_proxy` is never treated as `lme_tin_close`.
- `lme_tin_close` remains unavailable unless a real structured LME tin source exists.

Fields that can enter v2 feature columns when real aligned coverage reaches threshold:

- `usd_cny_return`
- `us10y_change`
- `copper_global_proxy_return`

## Current Runtime Coverage

- `raw_market`: 0.833333
- `technical`: 1.000000
- `mean_reversion`: 1.000000
- `term_structure`: 0.166667
- `basis`: 0.000000
- `inventory`: 0.000000
- `cross_market`: 0.000000
- `event`: 0.875000
- `regime`: 1.000000

## Current v2 Dataset Status

- `training_dataset_manifest_v2.json` exists.
- `cross_market_feature_cols=[]`
- `cross_market_excluded_reason=no_usable_aligned_cross_market_fields`
- `event_feature_cols=[]`
- `sample_data_used=false`
- `baseline_used=false`
- `leakage_check_pass=true`

## Research Readiness

Can continue:

- OHLCV technical research.
- Mean-reversion research.
- Regime-aware research.
- Event research only when `event_factor_inputs.json` contains `used_in_model=true` events.
- Cross-market research only after a non-empty aligned Alpha Vantage cache exists.

Not recommended now:

- Full basis model while `spot_price`, `spot_premium`, and `spot_futures_basis` remain unavailable.
- Full inventory model while `shfe_inventory`, `shfe_warehouse_receipt`, and `lme_inventory` remain unavailable.
- LME tin spread model while `lme_tin_close` remains unavailable.
- Full term-structure model while near/far contract curves remain unavailable.

## Boundary

This readiness report is an input-quality and feature-availability audit. It does not publish active models and does not generate customer-facing predictions.
