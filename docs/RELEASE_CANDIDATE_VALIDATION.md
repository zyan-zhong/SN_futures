# SNInsightTerminal Release Candidate Validation

Validation date: 2026-06-06

This report records the local Release Candidate build and installed-smoke evidence for SNInsightTerminal. It is a validation record only. The installer artifact remains a local ignored build artifact and must be uploaded as a GitHub Release asset, not committed to the source repository.

## RC Build Summary

- Repository: `SN_futures`
- Product: `SNInsightTerminal`
- Build type: Windows PyInstaller onedir plus Inno Setup installer
- Git SHA: `4db83a4f75befdaefe2c66767b0a2120faec963a`
- Onedir executable: `dist/SNInsightTerminal/SNInsightTerminal.exe`
- Installer executable: `release/SNInsightTerminal_Setup.exe`
- Installer size: `42,663,202` bytes
- Installer SHA256: `96F8973A6701AA6F24618507DEB89B5734E06094E2DCFDAF7033FEBA5222B391`

## Tool Versions

- PyInstaller: `6.19.0`
- Inno Setup compiler: `6.7.3`
- ISCC path: `C:\Users\Henry Austin\AppData\Local\Programs\Inno Setup 6\ISCC.exe`
- Node.js used by release build: `C:\Program Files\nodejs\node.exe` (`v24.15.0`)
- npm used by release build: `C:\Program Files\nodejs\npm.cmd` (`11.12.1`)

## Commands Used

Initial repository state and cleanliness:

```powershell
git status --short
git branch --show-current
git log --oneline -5
python scripts/check_repo_cleanliness.py
```

Tool checks:

```powershell
pyinstaller --version
Test-Path "C:\Users\Henry Austin\AppData\Local\Programs\Inno Setup 6\ISCC.exe"
& "C:\Users\Henry Austin\AppData\Local\Programs\Inno Setup 6\ISCC.exe" /?
```

Build command:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File packaging\build_release.ps1
```

Release safety scans:

```powershell
python scripts/quality_gate.py --only-scans --continue-on-error
```

Installed smoke command shape:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File packaging\smoke_installed.ps1 `
  -SetupPath "release\SNInsightTerminal_Setup.exe" `
  -InstalledRoot "<temp install root>" `
  -UseTempDataDir `
  -ApiPort <temp port> `
  -TimeoutSeconds 120
```

Regression checks after installed smoke:

```powershell
pytest -q tests/test_private_bundle_build_script_contract.py tests/test_quality_gate_contract.py tests/test_repo_cleanliness_script.py tests/test_private_bundle_smoke_contract.py tests/test_installed_tushare_configured_contract.py tests/test_installer_no_orphan_process_contract.py --tb=short
python scripts/quality_gate.py --skip-e2e --continue-on-error
git diff --check
```

## Build Results

- `build_release.ps1`: passed
- Full pytest during release build: `1647 passed`
- Frontend `typecheck`: passed
- Frontend `build`: passed
- Frontend `check:ui`: passed
- PyInstaller onedir smoke: passed
- Inno Setup compile: passed
- Installer generated: yes
- Installer path: `release/SNInsightTerminal_Setup.exe`

## Installed Smoke Results

The installed smoke used a temporary install root and `-UseTempDataDir`. Provider keys were cleared and the local API provider was disabled for the smoke run.

- Installer silent install: passed
- Installed executable exists: passed
- Start menu shortcut exists: passed
- `/api/terminal/docs`: `200`
- `/api/terminal/data-status`: `200`
- `/api/terminal/settings/status`: provider keys unconfigured
- `/api/terminal/predictions`: blocked or empty
- `/terminal`: `200`
- `/legacy`: `200`
- Shutdown endpoint: passed
- Port released after shutdown: passed
- No `SNInsightTerminal` orphan process remained after smoke cleanup
- Silent uninstall: passed
- Temporary user data directory removed after smoke

## No-Key / No-Data Behavior

The installed smoke verified the required no-key, no-real-data terminal behavior:

- Alpha Vantage: unconfigured
- NewsAPI: unconfigured
- Tushare: unconfigured
- Local API Provider: unconfigured and disabled
- Prediction list: empty
- Prediction cards: empty
- `sample_data_used=false`
- `baseline_used=false`
- `customer_prediction_generated=false`

This confirms the installed terminal does not emit legacy sample prediction cards as customer predictions when provider keys and real data are absent.

## Forbidden Artifact Scan

The release safety scan and manual dist/release scan passed. No forbidden package files were found in `dist/SNInsightTerminal` or `release/`.

Forbidden file and directory classes checked:

- `.env`
- `secrets.json`
- `private_bundle_seed.json`
- `private_release_keys.json`
- `app_data/`
- `outputs/`
- `cache/`
- `logs/`
- `*.sqlite`
- `*.sqlite3`
- `*.db`
- `*.log`

`python scripts/check_repo_cleanliness.py` also passed after the build and smoke. The `build/`, `dist/`, and `release/` outputs remain ignored local artifacts.

## Regression Results

- Packaging regression subset: `21 passed`
- `python scripts/quality_gate.py --skip-e2e --continue-on-error`: passed
- Full pytest in quality gate: `1647 passed`
- Frontend `typecheck`: passed
- Frontend `build`: passed
- Frontend `check:ui`: passed
- `git diff --check`: passed
- `git status --short`: clean

## Known Limitations

- The installer artifact is unsigned unless code signing is added later. Windows SmartScreen may warn about an unknown publisher.
- A real provider-key configured smoke has not been run. This RC validates the no-key/no-real-data safety path only.
- The installer artifact is a local ignored artifact. It should be uploaded as a GitHub Release asset, not committed to the source repository.
- The installed smoke verifies local startup and API behavior. It does not trigger real API refresh, model training, predictions, backtests, or Feature Store builds.

## Troubleshooting Note

Do not set `SN_DATA_DIR` or `SN_INSIGHT_DATA_DIR` globally for the full pytest phase of `packaging/build_release.ps1`. An initial build attempt failed because a global `SN_INSIGHT_DATA_DIR` overrode test-level temporary directories and broke test isolation. The successful RC build did not set global `SN_DATA_DIR` or `SN_INSIGHT_DATA_DIR` for full pytest.

For installed smoke, use `packaging/smoke_installed.ps1 -UseTempDataDir` so only the installed smoke process receives isolated runtime directories.
