# Strategy Optimization Policy

Strategy optimization is research-only and cannot lower promotion gates.

## Rules

- Thresholds are selected only from earlier training folds.
- Validation folds are evaluation-only.
- Candidate v3 remains non-active after optimization.
- Single-year, single-fold, or single-regime concentration is handled by institutional validation and promotion gate checks.

## Outputs

- `outputs/model_research/strategy_optimization/v3/all_trials.csv`
- `outputs/model_research/strategy_optimization/v3/optimization_report.json`

## Non-Goals

- No active publishing.
- No customer predictions.
- No baseline promotion.
- No fake prediction or fake returns.

