# Alpha Rate Limit And Cross-Market Backfill

This document records the Prompt 61S fix for Alpha Vantage rate-limit handling. It does not train models, publish an active model, generate customer predictions, or use baseline/fake prediction logic.

## Problem

Alpha Vantage can return HTTP 200 payloads containing `Note` or `Information` when a key is rate-limited. If that response is treated as a normal success with zero rows, `sn_cross_market.json` can become empty. That causes:

- `cross_market` feature coverage to fall to 0.
- `training_dataset_manifest_v2.cross_market_feature_cols=[]`.
- v2/v3 research candidates to receive no real USD/CNY, US10Y, or copper macro proxy increment.

## Policy

- `rate_limited`, `key_invalid`, `network_failed`, and `schema_mismatch` never overwrite a non-empty cross-market cache.
- A successful endpoint write updates `sn_cross_market.json` and `last_good_cross_market.json`.
- If current refresh is limited but cache exists, status becomes `using_cache_rate_limited`.
- If no cache exists and Alpha is limited, coverage stays 0 and the blocking reason is explicit.
- API keys are never written to logs, cache URLs, diagnostics, or frontend assets.

## Backfill Manager

The backfill manager splits Alpha endpoints:

- `FX_DAILY` for USD/CNY.
- `TREASURY_YIELD` for US10Y.
- `COPPER` for `copper_global_proxy`.

Each endpoint has its own attempt history and cooldown. Runtime refresh can request endpoints in batches instead of issuing all Alpha calls repeatedly during refresh-all.

Outputs:

- `outputs/fundamentals/sn_cross_market.json`
- `outputs/fundamentals/last_good_cross_market.json`
- `outputs/fundamentals/fx_macro_provider_status.json`
- `outputs/fundamentals/alpha_attempt_history.json`

## Feature Use

Feature coverage can use cached cross-market data only when it aligns to SN trading dates:

- Forward fill is limited to 5 trading days.
- Stale rows are marked and excluded from usable coverage.
- `copper_global_proxy` is a copper macro proxy only and is never mapped to `lme_tin_close`.
- Missing LME tin, basis, and inventory fields remain unavailable and are not fabricated.

## User-Facing State

Data status now distinguishes:

- `success`
- `rate_limited`
- `using_cache_rate_limited`
- `key_invalid`
- `network_failed`
- `cooldown`

When `using_cache_rate_limited` appears, users can continue viewing cached cross-market fields while waiting for the next retry window.
