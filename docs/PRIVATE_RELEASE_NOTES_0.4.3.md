# Private Release Notes 0.4.3

Version: `0.4.3-private-research-beta.1`

Release type: private research beta

Installer: `C:\Users\Henry Austin\Desktop\SN_futures\release\SNInsightTerminal_Setup.exe`

SHA256: `2F4F43F70C8616DDC204D848552FB77B9EDC9D545E56D5D835517A89EE193768`

## Scope

- Private bundle includes required Alpha, NewsAPI, and Tushare configured/masked provider inputs.
- Tushare is required for the private build input and remains masked in logs, settings, diagnostics, and release reports.
- Feature Store v7 remains the current real-data training feature store.
- Feature Store v8 and Feature Store v9 status are visible as research-lineage states, with no fabricated data backfill.
- Candidate v8 and Candidate v9 research status are visible.
- Candidate v9 remains research-only because institutional validation has not passed all active gates.
- `fut_wsr no_sn_rows` remains an explicit real-source state; no fake warehouse receipt data is included.

## Validation

- Quality gate: PASS.
- Python tests: PASS, `841 passed`.
- unittest discover: PASS, `569 tests`.
- Frontend typecheck/build/UI contract: PASS.
- Playwright E2E: PASS, `30 passed`.
- Installed smoke: PASS.
- Runtime secret scan: PASS.
- full_system_report_latest.txt: generated.
- diagnostics_bundle.zip: generated.

## Installed Smoke Highlights

- Alpha configured/masked: PASS.
- NewsAPI configured/masked: PASS.
- Tushare configured/masked: PASS.
- `/terminal`: PASS.
- `/legacy`: PASS.
- Browser smoke: PASS.
- Reset restores or retains Tushare private default: PASS.
- Shutdown and uninstall: PASS.

## Not Included

- No active publication.
- No customer prediction generation.
- No model strategy changes.
- No promotion gate relaxation.
- No baseline or fake prediction fallback.

