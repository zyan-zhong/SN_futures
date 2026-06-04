# Customer Release Report: 0.3.9 Private Research Beta 1

Version: `0.3.9-private-research-beta.1`
Release type: private install-ready research beta
Generated on: `2026-05-30`

## Build Artifact

- Installer: `release/SNInsightTerminal_Setup.exe`
- SHA256: `F623B00B072F2F770F77AC85D346F9DB037B9F178812257CC8C6E97AD503AC7D`
- Private bundle keys: Alpha Vantage and NewsAPI configured in the private bundle, masked in logs and APIs.

## Scope

This build packages the professional terminal workbench with the latest performance work: lightweight terminal summary and snapshot APIs, response caching, task-queue based long-running operations, lazy frontend pages, optimized chart loading, and the no-Tushare professional market analysis mode.

The build remains research-only. It does not publish an active model, does not generate customer predictions, and does not add baseline or fake prediction fallback.

## Acceptance Criteria

- Installer builds with private bundle provider keys without printing complete key values.
- First launch imports private bundle provider keys into local user config when missing.
- Settings reports Alpha Vantage and NewsAPI as configured with masked values only.
- `/terminal` opens without a global loading blocker.
- Lightweight APIs meet the release latency budget: summary and system-health under 300 ms, snapshot-lite under 500 ms.
- Market monitoring shows real price history or a clear provider/cache failure reason.
- Professional market analysis works from real OHLCV data even when Tushare and managed proxy are unavailable.
- Research backtest views show equity/drawdown curves or a clear research empty state.
- Artifact Center lists available manifests, validation reports, curves, and release reports.
- Prediction observation states there is no active model when promotion gate has not passed.
- Runtime secret scan reports no complete key leakage outside allowed local config or private bundle internals.

## Validation Results

- Quality gate: passed.
- Python tests: `pytest` passed, `644 passed`.
- Python unittest discovery: passed, `435 tests OK`.
- Frontend typecheck/build/check:ui: passed.
- Frontend E2E: passed, `19 passed`.
- Installed smoke: passed, including private key import, `/terminal`, `/legacy`, browser smoke, reset behavior, uninstall, and user data retention.
- Market smoke: passed. Realtime success `true`, history success `true`, final status `full_success`, row count `800`, chart available `true`, cache used `false`.
- Performance smoke: passed. `summary=26.135ms`, `system-health=30.803ms`, `snapshot-lite=38.531ms`, `/terminal first content=25.155ms`.
- Secret scan: passed, no complete key leakage detected.

## No-Tushare Analysis Mode

When `SN_TUSHARE_TOKEN` is not configured and managed proxy is disabled, the terminal still provides market analysis based on true OHLCV, technical, mean-reversion, volume, key-level, and regime diagnostics. It explicitly marks basis, inventory, LME tin, and warehouse receipt data as unavailable instead of fabricating them.

## Known Limits

- This is a private research beta, not a live trading or investment advice product.
- LME tin, complete basis, and inventory fields still require a reliable public source, Tushare access where applicable, or managed data proxy.
- Candidate and research backtests remain research artifacts and are not active customer predictions.
- API key embedding is suitable only for private/offline packages; public GitHub releases must not include provider keys.
