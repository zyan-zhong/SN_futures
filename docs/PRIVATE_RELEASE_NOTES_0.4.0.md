# Private Release Notes 0.4.0

Version: `0.4.0-private-research-beta.1`

Installer: `release/SNInsightTerminal_Setup.exe`
SHA256: `2DFCB32C2DF7C55C1FD3AEE5A107BD4EA14E47BD1E60CD7E0389689D863FB188`

## Included

- Frontend E2E stabilization after Prompt 85A: robust lazy-page waits, local/session storage isolation, and mocked POST task actions in browser tests.
- Backtest validation page empty-state hardening for missing, null, or partial research backtest reports.
- Chart rendering safeguards so empty chart payloads show professional empty states instead of initializing empty ECharts instances.
- API client timeout, network-disconnect, empty-response, and non-JSON response normalization.
- Playwright webServer stability improvements for fixed/overridable ports, strict Vite binding, non-desktop terminal URL, and safer server reuse.
- Full system TXT report, diagnostics bundle, settings-page report actions, and installed-smoke validation carried forward for private research delivery.
- Event page stabilization for live provider payloads where keyword evidence fields may arrive as scalar strings rather than arrays.

## Validation

- Quality gate: PASS, including `685` pytest tests and `27` Playwright E2E tests.
- Installed smoke: PASS, including install, launch, `/terminal`, `/legacy`, configured/masked provider diagnostics, runtime secret scan, browser smoke, shutdown, no orphan process, uninstall, and retained user data.
- Full system TXT report: `C:\Users\Henry Austin\AppData\Local\SNInsightTerminal\outputs\reports\full_system_report_latest.txt`
- Diagnostics bundle: `C:\Users\Henry Austin\AppData\Local\SNInsightTerminal\outputs\diagnostics\diagnostics_bundle.zip`

## Not Included

- No automatic active model publication.
- No customer prediction generation.
- No model strategy change.
- No fake, sample, or baseline customer prediction fallback.
- No public release key workflow.

## Operational Notes

- Private provider configuration is used only through the existing local release configuration.
- Settings and diagnostics must show provider state as configured/masked only.
- Runtime and release logs must not contain complete provider keys.
- Market analysis remains research-only and must show professional unavailable/empty states when a data provider is slow, empty, or unavailable.
