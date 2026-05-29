# Research Artifact Archive

Each candidate v3 research run can be archived under:

`outputs/research_runs/<run_id>/`

## Contents

- `config.json`
- `feature_store_manifest.json`
- `training_dataset_manifest.json`
- `candidate_registry.json`
- `high_confidence_report.json`
- `institutional_validation.json`
- `promotion_dry_run.json`
- `research_backtest_report.md`
- `equity_curve_*.csv`
- `drawdown_curve_*.csv`
- `trades_*.csv`
- `feature_importance.csv`
- `calibration_report.json`
- `secret_scan_summary.json`

## Security

The archive must not include API keys. Runtime secret scan remains a separate required release validation step.
# v4 archive addendum

Candidate v4 archives are written under `outputs/research_runs/<run_id>/` only after the v4 readiness gate passes and the research pipeline runs.

The archive service supports `candidate_version=v4` and copies the v4 Feature Store manifest, training dataset manifest, candidate registry, OOF summaries, validation reports, promotion dry-run, equity curves, drawdown curves, trades, metrics, and secret scan summary when those files exist.

The archive metadata always marks:

- `research_only=true`
- `active_updated=false`
- `customer_prediction_generated=false`
- `baseline_used=false`
- `sample_data_used=false`
