# Customer Release Report: 0.4.3 Private Research Beta

Version: `0.4.3-private-research-beta.1`
Release type: private research beta
Generated on: `2026-06-01`

## Build Inputs

- Alpha: configured/masked.
- NewsAPI: configured/masked.
- Tushare: configured/masked, source `private_bundle`.
- Managed Proxy: optional; not embedded in this build.

No complete provider key is printed or recorded in this report.

## Build Artifact

- Installer: `C:\Users\Henry Austin\Desktop\SN_futures\release\SNInsightTerminal_Setup.exe`
- SHA256: `2F4F43F70C8616DDC204D848552FB77B9EDC9D545E56D5D835517A89EE193768`
- Size: `41924701` bytes
- Build time: `2026-06-01T20:25:16`

## Quality Gate

- Python compileall: PASS.
- pytest: PASS, `841 passed`.
- unittest discover: PASS, `569 tests`.
- Frontend typecheck: PASS.
- Frontend build: PASS.
- Frontend UI contract: PASS.
- Playwright E2E: PASS, `30 passed`.
- Runtime secret scan: PASS.
- Terminal API smoke: PASS, `23` endpoints, `0` failed.
- Full system TXT report: PASS.

## Installed Smoke

- Silent install: PASS.
- `/terminal`: PASS.
- `/legacy`: PASS.
- Alpha configured/masked: PASS.
- NewsAPI configured/masked: PASS.
- Tushare configured/masked: PASS.
- Tushare source: `private_bundle`.
- Tushare API live success is not required for install acceptance.
- Browser smoke against installed terminal: PASS, `30 passed`.
- Reset restores or retains Alpha / NewsAPI / Tushare private defaults: PASS.
- Runtime secret scan after install: PASS.
- Shutdown and port release: PASS.
- No orphan process remains: PASS.
- Silent uninstall: PASS.
- User data retained after uninstall: PASS.

## Reports And Diagnostics

- full_system_report_latest.txt: `C:\Users\Henry Austin\AppData\Local\SNInsightTerminal\outputs\reports\full_system_report_latest.txt`
- full_system_report_latest.json: `C:\Users\Henry Austin\AppData\Local\SNInsightTerminal\outputs\reports\full_system_report_latest.json`
- diagnostics_bundle.zip: `C:\Users\Henry Austin\AppData\Local\SNInsightTerminal\outputs\diagnostics\diagnostics_bundle.zip`

## Research Status

- Feature Store v7: visible and backed by current real-data feature engineering.
- Feature Store v8: visible as research-lineage status; no fabricated feature data.
- Feature Store v9: visible as research-lineage status; no fabricated feature data.
- Candidate v8: visible, research-only.
- Candidate v9: visible, promotion dry-run pass but institutional validation remains blocked.

## Active And Prediction Policy

- No active model.
- No customer predictions.
- No trading points.
- No baseline or fake prediction fallback.

Active model path checked: `C:\Users\Henry Austin\AppData\Local\SNInsightTerminal\outputs\model_registry\active_model.json`

Current status: file does not exist.

## Known Limits

- Candidate v9 is not active because institutional validation has not passed all required gates.
- Managed Proxy is optional and not embedded in this private bundle.
- Warehouse receipt data remains unavailable when real SN rows are absent; no fake inventory data is generated.

## Delivery Conclusion

`0.4.3-private-research-beta.1` is ready for private research beta delivery.
