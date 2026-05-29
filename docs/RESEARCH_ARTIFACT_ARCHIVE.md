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

