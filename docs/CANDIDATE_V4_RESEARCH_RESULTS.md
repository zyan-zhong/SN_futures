# Candidate v4 Research Results

## Scope

Candidate v4 is gated by real incremental fields. The pipeline only proceeds when at least one usable cross-market or event factor passes Feature Store coverage checks.

This run does not publish `active_model.json`, does not generate customer predictions, does not lower promotion gate thresholds, and does not use baseline or sample data.

## Readiness Gate

The v4 gate checks:

- `cross_market_feature_cols` is non-empty, or `event_feature_cols` is non-empty.
- Feature Store v4 has `sample_data_used=false` and `baseline_used=false`.
- The training manifest records `incremental_feature_cols`, `excluded_fields`, `exclusion_reasons`, and `no_lookahead_pass`.

If both incremental groups are empty, the run returns:

`没有真实新增 cross-market 或 event 字段，未训练 candidate_v4。`

## Current Local Result

Current local readiness is blocked because the available Feature Store v4 did not expose usable cross-market or event incremental fields. Candidate v4 was not trained.

## Output Paths

- Feature Store: `outputs/feature_store/v4/feature_store.csv`
- Feature Store manifest: `outputs/feature_store/v4/feature_store_manifest.json`
- Readiness report: `outputs/feature_store/v4/v4_readiness.json`
- If unblocked, training dataset: `outputs/training_datasets/v4/train_*.parquet` or `.csv`
- If unblocked, research backtest: `outputs/research_backtests/v4/`
- If unblocked, archive: `outputs/research_runs/<run_id>/`

## Review Notes

Blocked v4 is expected behavior when Prompt 61S and Prompt 62S do not produce real incremental fields. The next step is to restore usable cross-market cache coverage or obtain high-quality NewsAPI event inputs before rerunning v4.
