# Candidate v2 Research Results

This document records the current candidate v2 research status after Prompt 57S cross-market alignment fixes. Prompt 57S did not train a model, did not publish an active model, did not generate customer predictions, and did not use baseline or fake prediction logic.

## Prompt 57S Correction

Candidate v2 was previously intended to include Alpha Vantage cross-market fields, but runtime coverage showed:

- `cross_market=0.0`
- `training_dataset_manifest_v2.cross_market_feature_cols=[]`
- Candidate v2 did not actually receive cross-market feature increment.

The root cause is that the current runtime `sn_cross_market.json` is empty after Alpha Vantage `rate_limited` refreshes, and no non-empty `last_good_cross_market.json` cache exists. The feature coverage layer is now fixed so it only counts cross-market fields after they align to SN trading dates.

## Current v2 Dataset

- Dataset manifest: `%LOCALAPPDATA%\SNInsightTerminal\outputs\training_dataset_manifest_v2.json`
- Dataset version: `v2`
- Feature set: `ohlcv_technical_regime_cross_market_event`
- Feature count: 29
- `cross_market_feature_cols=[]`
- `cross_market_excluded_reason=no_usable_aligned_cross_market_fields`
- `event_feature_cols=[]`
- `sample_data_used=false`
- `baseline_used=false`
- `leakage_check_pass=true`

Sample counts:

| Horizon | Samples |
|---|---:|
| 1d | 2712 |
| 3d | 2710 |
| 5d | 2708 |
| 10d | 2703 |
| 20d | 2693 |

## Current Feature Coverage

| Group | Coverage | Note |
|---|---:|---|
| raw_market | 0.833333 | Real OHLCV available; open interest still incomplete. |
| technical | 1.000000 | Available. |
| mean_reversion | 1.000000 | Available. |
| term_structure | 0.166667 | Near/far contract structure still missing. |
| basis | 0.000000 | No fabricated spot or basis data. |
| inventory | 0.000000 | No fabricated inventory or warehouse data. |
| cross_market | 0.000000 | Current runtime cross-market file is empty. |
| event | 0.875000 | Derived event features exist, but v2 dataset only accepts `event_factor_inputs` high-relevance inputs. |
| regime | 1.000000 | Available. |

## Cross-Market Inclusion Rule

The following fields can enter candidate research only when aligned coverage reaches the threshold:

- `usd_cny_return`
- `us10y_change`
- `copper_global_proxy_return`

The following remain unavailable unless real structured data exists:

- `lme_tin_close`
- `lme_tin_return_1d`
- `lme_tin_return_3d`
- `lme_shfe_spread`

`copper_global_proxy` and its returns are macro proxies only and are never mapped to LME tin.

## Next Candidate Condition

Do not train another candidate until one of these is true:

- Alpha Vantage successfully refreshes non-empty cross-market data.
- A valid non-empty last-good cross-market cache exists and is within alignment rules.
- Managed proxy or another permitted structured source provides real cross-market fields.

If those conditions are not met, candidate research remains OHLCV/technical/regime/event-only.
