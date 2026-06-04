# API Latency Budget

## Light APIs

Target: under 300 ms in normal local runtime.

- `/api/terminal/summary`
- `/api/terminal/system-health`
- `/api/terminal/settings/status`
- route/docs/status-style endpoints

## Snapshot Lite

Target: under 500 ms.

- `/api/terminal/snapshot`

The snapshot endpoint must stay lightweight. It must not synchronously run refresh, training, validation, backtest, or provider probes.

## Medium APIs

Target: under 1 second where data files are already present.

- `/api/terminal/data-status`
- `/api/terminal/charts/price-history`
- `/api/terminal/market-analysis`
- `/api/terminal/feature-store/status`
- `/api/terminal/training-dataset/status`

## Heavy Work

Heavy work must use the task queue or a cached status/result endpoint.

- refresh-all
- market/news/cross-market refresh
- feature-store build
- training dataset build
- candidate training
- institutional validation
- research backtest
- learning scheduler runs
- artifact archive generation

## Cache Metadata

Cached API responses include:

- `generated_at`
- `cache_hit`
- `cache_age_seconds`

These fields support stale/cache badges in the frontend and API performance diagnostics.
