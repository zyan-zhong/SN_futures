# Candidate v5 Research Results

Candidate v5 is trained from Feature Store v5 and training dataset v5. It remains a candidate-only research model.

## Scope

- Train candidate v5 only.
- Generate purged walk-forward OOF traces.
- Generate research-only equity curves, drawdown curves, trades, and metrics.
- Run institutional validation including DSR, PBO, Reality Check, cost stress, and dominance checks.
- Run promotion dry-run only.
- Do not write `active_model.json`.
- Do not generate customer predictions.
- Do not lower the promotion gate.

## Inputs

- `outputs/feature_store/v5/feature_store.csv`
- `outputs/feature_store/v5/feature_store_manifest.json`
- `outputs/training_dataset_manifest_v5.json`
- `outputs/training_datasets/v5/train_*.parquet`

## Outputs

- `outputs/model_registry/candidate_v5_model_registry.json`
- `outputs/model_registry/candidate_v5_training_status.json`
- `outputs/walk_forward/v5/wf_*.json`
- `outputs/walk_forward/v5/oof_trace_*.csv`
- `outputs/research_backtests/v5/equity_curve_*.csv`
- `outputs/research_backtests/v5/drawdown_curve_*.csv`
- `outputs/research_backtests/v5/trades_*.csv`
- `outputs/research_backtests/v5/metrics_*.json`
- `outputs/model_research/multi_objective_optimization/v5/optimization_report.json`
- `outputs/model_research/multi_objective_optimization/v5/all_trials.csv`
- `outputs/institutional_validation/institutional_validation_report_v5.json`
- `outputs/research_runs/<run_id>/`

## Decision Policy

Promotion dry-run can report that a candidate is eligible for manual review, but it must not publish active automatically. If DSR, PBO, Reality Check, cost stress, fold/year/regime dominance, or data-quality checks fail, the candidate remains research-only.

The v5 pipeline is not a live trading signal and does not constitute investment advice.
