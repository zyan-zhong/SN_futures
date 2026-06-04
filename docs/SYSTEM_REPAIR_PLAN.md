# System Repair Plan

`system_repair_plan` is a read-only diagnostic artifact generated from the latest full system report and existing smoke/performance/model/backtest diagnostics.

## Inputs

- `outputs/reports/full_system_report_latest.txt`
- `outputs/reports/full_system_report_latest.json`
- `outputs/diagnostics/all_api_smoke.json`
- `outputs/performance/api_performance_report.json`
- `outputs/model_registry/active_absence_diagnostics.json`
- `outputs/model_registry/promotion_report*.json`
- `outputs/research_backtests/**/metrics_*.json`

## Outputs

- `outputs/diagnostics/system_repair_plan.json`
- `outputs/diagnostics/system_repair_plan.md`

## API

- `POST /api/terminal/diagnostics/build-repair-plan`
- `GET /api/terminal/diagnostics/repair-plan`

## Safety Boundary

The triage service only reads existing diagnostic artifacts and writes the repair plan files above. It must not train models, refresh heavy data jobs, publish active models, or generate customer predictions.

The output keeps `active_updated=false` and `customer_prediction_generated=false` so the UI and tests can assert that the diagnostic pass stayed inside the release safety boundary.
