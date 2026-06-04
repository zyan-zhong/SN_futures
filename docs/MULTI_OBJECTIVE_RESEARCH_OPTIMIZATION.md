# Multi-Objective Research Optimization

The multi-objective optimizer evaluates candidate OOF traces without publishing an active model.

## Objectives

Maximize:

- Cost-adjusted expectancy.
- Top-20% high-confidence accuracy.
- Deflated Sharpe Ratio.
- Feature stability.

Minimize:

- Max drawdown.
- Probability of Backtest Overfitting.
- Turnover.
- Fold/regime concentration risk.

## Constraints

- No mock data for promotion.
- No sample data.
- 2x cost-stress expectancy must not be negative.
- Worst-fold accuracy must meet the configured threshold.
- Worst-regime accuracy must meet the configured threshold.
- High-confidence sample count must meet the configured threshold.

## Outputs

- `outputs/model_research/multi_objective_optimization/<version>/optimization_report.json`
- `outputs/model_research/multi_objective_optimization/<version>/all_trials.csv`

The optimizer records blocking reasons. A clean report may mark the candidate as eligible for manual review, but active promotion still requires the separate promotion gate and manual approval.
