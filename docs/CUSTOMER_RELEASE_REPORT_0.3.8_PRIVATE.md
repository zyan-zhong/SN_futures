# Customer Release Report: 0.3.8 Private Research Beta 1

Version: `0.3.8-private-research-beta.1`
Release type: private install-ready research beta

## Scope

This build packages the professional terminal workbench, private bundle API key import, real market data refresh, research artifacts, feature store views, candidate research diagnostics, and research backtest displays. It does not publish an active model and does not generate customer predictions.

## Acceptance Criteria

- Installer builds successfully.
- First launch imports private bundle provider keys into the local user config when missing.
- Settings reports Alpha Vantage and NewsAPI as configured with masked values only.
- `/terminal` opens.
- Market monitoring shows price history or a clear provider/cache failure reason.
- Backtest validation shows research equity/drawdown curves or a clear research empty state.
- Artifact Center lists available manifests, OOF traces, validation reports, curves, and release reports.
- Prediction page clearly states there is no active model when promotion gate has not passed.
- Uninstall retains `%LOCALAPPDATA%\SNInsightTerminal`.
- Runtime secret scan reports no complete key leakage outside allowed local config.

## Security And Data Handling

Private provider keys are only allowed in the private bundle seed and the user-local `config/secrets.json` after import. API responses, frontend bundles, logs, caches, diagnostics, and release logs must show only masked values.

## Known Limits

- This is a research beta, not an active trading signal product.
- LME tin, full basis, and inventory sources may remain unavailable unless public sources or managed data proxy provide them.
- Candidate/research backtests are not live predictions and do not constitute investment advice.
