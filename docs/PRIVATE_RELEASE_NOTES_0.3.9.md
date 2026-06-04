# Private Release Notes 0.3.9

Version: `0.3.9-private-research-beta.1`

Installer: `release/SNInsightTerminal_Setup.exe`
SHA256: `F623B00B072F2F770F77AC85D346F9DB037B9F178812257CC8C6E97AD503AC7D`

## Included

- Lightweight terminal APIs for summary, system-health, and snapshot-lite.
- Terminal performance smoke script at `scripts/smoke_terminal_performance.ps1`.
- Task queue support for long-running refresh, training, validation, backtest, and scheduler operations.
- Frontend lazy loading, request timeout/deduping, polling backoff, and chart performance improvements.
- Professional market analysis mode based on real OHLCV data when Tushare and managed proxy are unavailable.
- Workbench pages for market monitoring, events, factor research, training data, model research, backtest validation, prediction observation, reports, settings, and artifacts.
- Private bundle default Alpha Vantage and NewsAPI key import for install-ready private distribution.

## Not Included

- No automatic active model publication.
- No customer prediction generation without an approved active model.
- No baseline, sample, or fake prediction fallback.
- No public GitHub release key workflow.

## Operational Notes

- Settings and diagnostics show only masked provider keys and source metadata.
- Runtime secret scanning must pass before delivery.
- If a slow provider or rate limit occurs, the UI should show cache/stale/error state rather than blocking the whole terminal.
- 2026-05-30 delivery validation passed: quality gate, market smoke, performance smoke, installed browser smoke, and runtime secret scan.
