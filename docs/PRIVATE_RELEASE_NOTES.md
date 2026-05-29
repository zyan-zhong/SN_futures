# Private Release Notes

Version: `0.3.8-private-research-beta.1`

## Included

- Professional terminal navigation for market monitoring, news/events, factor research, training datasets, model research, backtest validation, prediction observation, reports, and diagnostics.
- Artifact Center for research runs, manifests, OOF traces, validation reports, equity curves, drawdown curves, trades, and release reports.
- Private bundle default Alpha Vantage and NewsAPI key import for install-ready private distribution.
- Production quality gate script at `scripts/quality_gate.ps1`.
- Release smoke flow with private key import checks and browser smoke support.

## Not Included

- No active model publication.
- No customer prediction generation.
- No baseline or fake prediction fallback.
- No GitHub/public release key workflow.

## Operational Notes

- Public GitHub release builds must not include private provider keys.
- The longer-term production data approach remains managed data proxy or licensed provider integration.
- Installer smoke writes setup/uninstall logs to a temp smoke directory rather than the release directory.
