# Customer Release Report: 0.4.0 Private Research Beta 1

Version: `0.4.0-private-research-beta.1`
Release type: private install-ready research beta
Generated on: `2026-05-31`

## Build Artifact

- Installer: `C:\Users\Henry Austin\Desktop\SN_futures\release\SNInsightTerminal_Setup.exe`
- Installer timestamp: `2026-05-31 12:43:26`
- SHA256: `2DFCB32C2DF7C55C1FD3AEE5A107BD4EA14E47BD1E60CD7E0389689D863FB188`
- Private bundle keys: Alpha Vantage and NewsAPI validated as configured/masked. No complete provider key value is recorded in this report.

## Scope

This build packages the private research terminal with the Prompt 85A frontend stability fixes, backtest empty-state hardening, Playwright webServer stability updates, report diagnostics actions, and existing private release configuration.

The build remains research-only. It does not publish an active model, does not generate customer predictions, and does not add baseline or fake prediction fallback.

## Validation Results

- Quality gate: PASS.
  - Python compileall: PASS.
  - Python pytest: PASS, `685 passed`.
  - Python unittest discover: PASS.
  - Frontend typecheck: PASS.
  - Frontend build: PASS.
  - Frontend UI contract: PASS.
  - Playwright E2E: PASS, `27 passed`.
  - Runtime secret scan: PASS.
  - No active model gate: PASS.
  - No fake/baseline customer prediction copy gate: PASS.
  - Required governance docs: PASS.
- API smoke: PASS, `23` Terminal API endpoints checked, `0` failures, no secret leak detected.
  - Output: `C:\Users\Henry Austin\AppData\Local\SNInsightTerminal\outputs\diagnostics\all_api_smoke.json`
- Performance smoke: PASS.
  - `summary`: `18.88 ms` / `300 ms`.
  - `system-health`: `17.91 ms` / `300 ms`.
  - `snapshot-lite`: `28.736 ms` / `500 ms`.
  - `terminal-first-content`: `18.004 ms` / `2000 ms`.
  - Output: `C:\Users\Henry Austin\AppData\Local\SNInsightTerminal\logs\terminal_performance_smoke.json`
- Market data smoke: PASS.
  - `realtime_success`: `True`.
  - `history_success`: `True`.
  - `provider_attempt_count`: `3`.
  - `history_row_count`: `800`.
  - `final_status`: `full_success`.
  - `from_cache`: `False`.
  - `can_chart`: `True`.
  - `market-analysis`: available.
  - Output: `C:\Users\Henry Austin\AppData\Local\SNInsightTerminal\logs\market_data_smoke.json`
- Installed smoke: PASS.
  - Silent install: PASS.
  - Installed startup: PASS.
  - `/terminal`: PASS.
  - `/legacy`: PASS.
  - Installed browser smoke: PASS, `27 passed`.
  - Alpha Vantage configured/masked: PASS.
  - NewsAPI configured/masked: PASS.
  - Key diagnostics masking: PASS.
  - Runtime secret scan: PASS.
  - Shutdown API and port release: PASS.
  - No orphan SNInsightTerminal process after shutdown: PASS.
  - Silent uninstall: PASS.
  - User data retained after uninstall: PASS.
- Full system TXT report: `C:\Users\Henry Austin\AppData\Local\SNInsightTerminal\outputs\reports\full_system_report_latest.txt`
- Diagnostics bundle: `C:\Users\Henry Austin\AppData\Local\SNInsightTerminal\outputs\diagnostics\diagnostics_bundle.zip`
- Active model present: NO. Checked release/runtime active-model paths are absent.
- Customer predictions generated in this release run: NO. Existing historical prediction artifacts were not refreshed by this release validation and are not part of the deliverable evidence.

## Known Limits

- This is a private research beta, not a live trading or investment advice product.
- LME tin, complete basis, inventory, and some institutional fields still depend on configured provider availability.
- Research backtests remain research artifacts and are not active customer predictions.
- Private provider key embedding is suitable only for private/offline packages; public releases must not include provider keys.
- The package was validated as a private research delivery only; active model publication remains disabled.

## Compliance Statement

SNInsightTerminal is provided for沪锡期货量化投研参考 only. It does not constitute investment advice, does not promise returns, does not place trades, and does not generate customer-facing predictions without an approved active model.

Release conclusion: this installer can be delivered as `0.4.0-private-research-beta.1` private research beta. It must not be treated as an active-model or customer-prediction release.
