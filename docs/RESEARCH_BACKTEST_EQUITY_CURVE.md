# Research Backtest Equity Curve

The research backtest uses only out-of-fold validation traces. It is not a live prediction engine and does not imply future returns.

## Inputs

- `outputs/walk_forward/v3/oof_trace_*.csv`
- OOF `predicted_direction`, `confidence`, `trade_edge`, and realized labels
- Cost and slippage assumptions recorded in metrics

## Outputs

- `outputs/research_backtests/v3/equity_curve_*.csv`
- `outputs/research_backtests/v3/drawdown_curve_*.csv`
- `outputs/research_backtests/v3/trades_*.csv`
- `outputs/research_backtests/v3/metrics_*.json`
- `outputs/research_backtests/v3/research_backtest_report.md`

## Guardrails

- No in-sample prediction is used.
- No active model is published.
- No customer prediction is generated.
- Metrics include cost stress, drawdown, DSR, PBO, and a lightweight Reality Check p-value.
# v4 selector

The research backtest API and UI now support `candidate_version=v4` or `version=v4`.

v4 backtests are only meaningful after candidate_v4 creates OOF traces. If Feature Store v4 is blocked due to no real cross-market or event increment, the backtest remains unavailable and no customer prediction is generated.

The output directory is `outputs/research_backtests/v4/`:

- `equity_curve_*.csv`
- `drawdown_curve_*.csv`
- `trades_*.csv`
- `metrics_*.json`
- `research_backtest_report.md`

These files are research-only and do not imply active model approval.
