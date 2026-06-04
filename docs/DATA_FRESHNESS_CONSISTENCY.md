# Data Freshness Consistency

The terminal uses a single data watermark file:

`outputs/data_watermark.json`

Tracked watermarks include market, price history, cross-market, news, event factors, feature store, training dataset, candidate, backtest, and active model timestamps.

After refresh/build/training/backtest tasks complete, the task queue invalidates terminal caches and updates the relevant watermark. Frontend pages should use stale-while-refreshing behavior: keep the old chart visible, mark it stale, then refresh the active page data when the task completes.

APIs:

- `GET /api/terminal/data-watermark`
- `POST /api/terminal/cache/invalidate`

Sample data can only be shown when real data is absent and sample mode is allowed. Sample data is never allowed in training, candidate models, research backtests, promotion, or active release.
