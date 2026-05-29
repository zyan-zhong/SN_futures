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

