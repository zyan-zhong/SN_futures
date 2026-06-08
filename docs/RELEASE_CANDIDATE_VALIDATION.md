# SNInsightTerminal Release Candidate Validation

Validation date: 2026-06-06

This report records the local Release Candidate build and installed-smoke evidence for SNInsightTerminal. It is a validation record only. The installer artifact remains a local ignored build artifact and must be uploaded as a GitHub Release asset, not committed to the source repository.

## RC Validation Pass 5

Validation date: 2026-06-08

This fifth validation pass was run after the installer upgrade cleanup fix. It validated the full local release path: complete quality gate including E2E, clean release rebuild, release safety scans, onedir smoke, fresh installer smoke, and upgrade cleanup smoke with an injected stale private bundle seed. The run was local-only: no GitHub push, no PR, no real provider refresh, no model training, no customer prediction generation, no research backtest generation, and no Feature Store build.

### Source State

- Branch: `main`
- HEAD SHA before local uncommitted cleanup changes: `9b1586d4555d40d9d00c5c1662792dc2cd6b871f`
- Repository cleanliness check: passed
- Tracked forbidden runtime/build/cache artifacts: none
- Release artifact status: local ignored artifact, not committed

### Full Quality Gate

Command:

```powershell
python scripts\quality_gate.py --continue-on-error
```

Result: passed.

- Repo cleanliness: passed
- Secret scan: passed
- Release package safety scan: passed
- Real-result sample/baseline scan: passed
- Historical OHLCV scaling scan: passed
- Python compileall: passed
- API endpoint contract tests: `13 passed`
- Data watermark schema tests: `12 passed`
- Full pytest: `1720 passed`
- Frontend typecheck: passed
- Frontend build: passed
- Frontend UI contract check: passed
- Frontend E2E: `36 passed`
- Total quality gate duration: `277.3s`

### Build Command

Before the build, only repository-local `build/`, `dist/`, and `release/` directories were removed. No user data directory was removed.

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File packaging\build_release.ps1
```

Result: passed.

- `build_release.ps1` exit code: `0`
- Full pytest inside release build: `1720 passed`
- Frontend typecheck/build/check:ui: passed
- PyInstaller onedir build: passed
- Built-in onedir smoke in `build_release.ps1`: passed
- Inno Setup compile: passed
- Inno Setup log parsed `[InstallDelete]` lines for stale `_internal\private` files

### Artifact Summary

- Onedir executable: `dist/SNInsightTerminal/SNInsightTerminal.exe`
- Installer executable: `release/SNInsightTerminal_Setup.exe`
- Installer size: `42,739,742` bytes
- Installer SHA256: `156166B1117D6C58864F90437CFA2C322C8F32BFE1C654A3EECB8DC7EFBDEBA0`

### Release Safety Scan

Commands:

```powershell
python scripts\quality_gate.py --only-scans --continue-on-error
```

Manual `dist/` and `release/` forbidden file scan also ran.

Result: passed.

No forbidden package files were found for `.env`, `secrets.json`, `private_bundle_seed.json`, `private_release_keys.json`, app data, outputs, cache, logs, e2e artifacts, SQLite databases, or log files.

### Onedir Smoke

Command shape:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File packaging\smoke_installed.ps1 `
  -SkipInstall `
  -KeepInstalled `
  -InstalledRoot dist\SNInsightTerminal `
  -UseTempDataDir `
  -ApiPort 19011 `
  -TimeoutSeconds 90
```

Result: passed.

- `/api/terminal/docs`: `200`
- `/api/terminal/data-status`: `200`
- `/api/terminal/settings/status`: Alpha Vantage, NewsAPI, Tushare, and Local API Provider unconfigured
- `/api/terminal/predictions`: blocked or empty
- Prediction list: empty
- Prediction cards: empty
- `sample_data_used=false`
- `baseline_used=false`
- `customer_prediction_generated=false`
- `/terminal`: `200`
- `/legacy`: `200`
- Shutdown endpoint: passed
- Port released: passed
- No `SNInsightTerminal` orphan process remained

### Fresh Installer Smoke

Command shape:

```powershell
$installRoot = Join-Path $env:TEMP ("SNInsightTerminalInstall_" + [guid]::NewGuid().ToString("N"))
powershell -NoProfile -ExecutionPolicy Bypass -File packaging\smoke_installed.ps1 `
  -SetupPath release\SNInsightTerminal_Setup.exe `
  -InstalledRoot $installRoot `
  -UseTempDataDir `
  -ApiPort 19012 `
  -TimeoutSeconds 90
```

Result: passed.

- Silent install: passed
- Installed executable exists: passed
- Start menu shortcut exists: passed
- `/api/terminal/docs`: `200`
- `/api/terminal/data-status`: `200`
- `/api/terminal/settings/status`: provider keys unconfigured
- `/api/terminal/predictions`: blocked or empty
- Prediction list: empty
- Prediction cards: empty
- `sample_data_used=false`
- `baseline_used=false`
- `customer_prediction_generated=false`
- `/terminal`: `200`
- `/legacy`: `200`
- Shutdown endpoint: passed
- No orphan process remained
- Silent uninstall: passed
- Temporary install root and temporary user data directory removed after smoke

### Upgrade Cleanup Smoke

Command shape:

```powershell
$installRoot = Join-Path $env:TEMP ("SNInsightTerminalInstall_" + [guid]::NewGuid().ToString("N"))
powershell -NoProfile -ExecutionPolicy Bypass -File packaging\smoke_installed.ps1 `
  -SetupPath release\SNInsightTerminal_Setup.exe `
  -InstalledRoot $installRoot `
  -UseTempDataDir `
  -ApiPort 19013 `
  -TimeoutSeconds 90 `
  -InjectLegacyPrivateSeed
```

Result: passed.

- Smoke seeded legacy `_internal\private` files under temporary install root before install
- Installer exit code: `0`
- Legacy private seed files removed from install root: passed
- Legacy private directory empty or absent after install: passed
- `/api/terminal/settings/status`: provider keys unconfigured
- `/api/terminal/predictions`: blocked or empty
- Prediction list: empty
- Prediction cards: empty
- `sample_data_used=false`
- `baseline_used=false`
- `customer_prediction_generated=false`
- Shutdown endpoint: passed
- Port released: passed
- No orphan process remained
- Silent uninstall: passed
- Temporary install root and temporary user data directory removed after smoke

### Outcome

The installer upgrade-path stale private seed risk is resolved for this release candidate. The artifact remains unsigned and should be uploaded as a GitHub Release asset only after the local cleanup changes are checkpointed and reviewed.

## RC Validation Pass 4

Validation date: 2026-06-08

This fourth validation pass was run after the local installer upgrade-path cleanup fix. The run was local-only: no GitHub push, no PR, no real provider refresh, no model training, no customer prediction generation, no research backtest generation, and no Feature Store build.

### Scope

The pass fixed and validated one release blocker from Pass 3: overlay installs did not remove stale `_internal\private` files left by older builds. Those stale files could make the installed app import obsolete private bundle defaults even though the current release artifact did not contain a private seed.

### Source State

- Branch: `main`
- HEAD SHA before local cleanup changes: `9b1586d docs: update local RC validation`
- Worktree state: local installer cleanup changes present
- Repository cleanliness check: passed
- Tracked forbidden runtime/build/cache artifacts: none

### Cleanup Rule

The Inno Setup script now includes `[InstallDelete]` rules scoped only to the installed app directory:

- `{app}\_internal\private\private_bundle_seed.json`
- `{app}\_internal\private\private_release_keys.json`
- `{app}\_internal\private\secrets.json`
- `{app}\_internal\private\.env`
- `{app}\_internal\private` removed only when empty

The cleanup does not target `%LOCALAPPDATA%\SNInsightTerminal`, user `SN_DATA_DIR`, runtime outputs, cache, logs, or the user's local `config\secrets.json`.

### Contract and Quality Checks

Commands:

```powershell
pytest -q tests\test_installer_upgrade_cleanup_contract.py --tb=short
pytest -q tests\test_installer_upgrade_cleanup_contract.py tests\test_release_packaging.py tests\test_private_bundle_build_script_contract.py tests\test_quality_gate_contract.py tests\test_repo_cleanliness_script.py tests\test_private_bundle_smoke_contract.py tests\test_installed_tushare_configured_contract.py tests\test_installer_no_orphan_process_contract.py --tb=short
python scripts\quality_gate.py --skip-e2e --continue-on-error
```

Results:

- Installer upgrade cleanup contract: `4 passed`
- Packaging/release smoke contract subset: `29 passed`
- `quality_gate.py --skip-e2e --continue-on-error`: passed
- Full pytest inside quality gate: `1720 passed`
- Frontend typecheck/build/check:ui: passed

### Build Command

Before the build, only repository-local `build/`, `dist/`, and `release/` directories were removed. No user data directory was removed.

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File packaging\build_release.ps1
```

Result: passed.

- `build_release.ps1` exit code: `0`
- Full pytest inside release build: `1720 passed`
- Frontend typecheck/build/check:ui: passed
- PyInstaller onedir build: passed
- Built-in onedir smoke in `build_release.ps1`: passed
- Inno Setup compile: passed
- Inno Setup log parsed `[InstallDelete]` lines for the stale private files

### Artifact Summary

- Onedir executable: `dist/SNInsightTerminal/SNInsightTerminal.exe`
- Installer executable: `release/SNInsightTerminal_Setup.exe`
- Installer size: `42,736,042` bytes
- Installer SHA256: `D4EA8079DFE2E76309235CD23C10D1512CC5698BE25867C55492D7DD33AE431D`

### Upgrade Cleanup Installer Smoke

Command shape:

```powershell
$installRoot = Join-Path $env:TEMP ("SNInsightTerminalInstall_" + [guid]::NewGuid().ToString("N"))
powershell -NoProfile -ExecutionPolicy Bypass -File packaging\smoke_installed.ps1 `
  -SetupPath release\SNInsightTerminal_Setup.exe `
  -InstalledRoot $installRoot `
  -UseTempDataDir `
  -ApiPort 18986 `
  -TimeoutSeconds 90 `
  -InjectLegacyPrivateSeed
```

Result: passed.

- Smoke seeded legacy private files under temporary install root before install
- Installer exit code: `0`
- Legacy private seed files removed from install root: passed
- Legacy private directory empty or absent after install: passed
- `/api/terminal/docs`: `200`
- `/api/terminal/data-status`: `200`
- `/api/terminal/settings/status`: Alpha Vantage, NewsAPI, Tushare, and Local API Provider unconfigured
- `/api/terminal/predictions`: blocked or empty
- Prediction list: empty
- Prediction cards: empty
- `sample_data_used=false`
- `baseline_used=false`
- `customer_prediction_generated=false`
- `/terminal`: `200`
- `/legacy`: `200`
- Mock settings save/reset did not expose complete keys
- Shutdown endpoint: passed
- Port released: passed
- No `SNInsightTerminal` orphan process remained
- Silent uninstall: passed
- Temporary install root removed after uninstall
- Temporary user data directory removed after smoke

### Forbidden Artifact Scan

Release safety scans:

```powershell
python scripts\quality_gate.py --only-scans --continue-on-error
```

Result: passed.

Manual `dist/` and `release/` forbidden file scan also passed. No forbidden package files were found for `.env`, `secrets.json`, `private_bundle_seed.json`, `private_release_keys.json`, app data, outputs, cache, logs, e2e artifacts, SQLite databases, or log files.

### Outcome

The upgrade-path stale private seed risk from Pass 3 is resolved for fresh installer artifacts built from this worktree. Future release smoke should include `-InjectLegacyPrivateSeed` with a temporary `-InstalledRoot` to keep this upgrade cleanup path covered.

## RC Validation Pass 3

Validation date: 2026-06-07

This third validation pass was run after the local second-stage checkpoint commits for provider contracts, provider-only smoke, auditable backtest API flow, and frontend settings/tasks API split. The run was local-only: no GitHub push, no PR, no real provider refresh, no model training, no customer prediction generation, no research backtest generation, and no Feature Store build.

### Source State

- Branch: `main`
- HEAD SHA: `258b6e3501d11ce805e877ac44ff28a582c0885f`
- Recent checkpoint commits:
  - `20211f2 feat(provider): add local provider HTTP adapter contract`
  - `3e08617 feat(provider): bridge service outputs to provider results`
  - `487bd6e feat(provider): add provider-only smoke harness`
  - `6e85e3f feat(backtest): complete auditable backtest API flow`
  - `258b6e3 feat(frontend): split settings and task API clients`
- Repository cleanliness check before build: passed
- Tracked forbidden runtime/build/cache artifacts: none

### Tool Versions

- PyInstaller: `6.19.0`
- Inno Setup compiler: `C:\Users\Henry Austin\AppData\Local\Programs\Inno Setup 6\ISCC.exe`
- Inno Setup compiler engine: `6.7.3`

### Full Quality Gate

Command:

```powershell
python scripts\quality_gate.py --continue-on-error
```

Result: passed.

- Repo cleanliness: passed
- Secret scan: passed
- Release package safety scan: passed
- Real-result sample/baseline scan: passed
- Historical OHLCV scaling scan: passed
- Python compileall: passed
- API endpoint contract tests: `13 passed`
- Data watermark schema tests: `12 passed`
- Full pytest: `1716 passed`
- Frontend typecheck: passed
- Frontend build: passed
- Frontend UI contract check: passed
- Frontend E2E: `36 passed`
- Total quality gate duration: `270.1s`

### Build Command

Before the build, only repository-local `build/`, `dist/`, and `release/` directories were removed. No user data directory was removed.

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File packaging\build_release.ps1
```

Result: passed.

- `build_release.ps1` exit code: `0`
- Full pytest inside release build: `1716 passed`
- Frontend typecheck/build/check:ui: passed
- PyInstaller onedir build: passed
- Built-in onedir smoke in `build_release.ps1`: passed
- Inno Setup compile: passed

### Artifact Summary

- Onedir executable: `dist/SNInsightTerminal/SNInsightTerminal.exe`
- Installer executable: `release/SNInsightTerminal_Setup.exe`
- Installer size: `42,740,581` bytes
- Installer SHA256: `F1FD25B6D3A65EC51E220AD1147BBAEF5C06574F1BCB7485D616658511E30104`
- `release/SHA256SUMS.txt`: generated by build

### Onedir Smoke

Command:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File packaging\smoke_installed.ps1 `
  -SkipInstall `
  -KeepInstalled `
  -InstalledRoot dist\SNInsightTerminal `
  -UseTempDataDir `
  -ApiPort 18982 `
  -TimeoutSeconds 90
```

Result: passed.

- `/api/terminal/docs`: `200`
- `/api/terminal/data-status`: `200`
- `/api/terminal/settings/status`: Alpha Vantage, NewsAPI, Tushare, and Local API Provider unconfigured
- `/api/terminal/predictions`: blocked or empty
- Prediction list: empty
- Prediction cards: empty
- `sample_data_used=false`
- `baseline_used=false`
- `customer_prediction_generated=false`
- `/terminal`: `200`
- `/legacy`: `200`
- Shutdown endpoint: passed
- Port released: passed
- No `SNInsightTerminal` orphan process remained

Note: the frozen onedir process released the port but did not exit within the smoke timeout. The smoke script forced cleanup as designed and then verified no orphan process remained.

### Installer Smoke

Command:

```powershell
$installRoot = Join-Path $env:TEMP ("SNInsightTerminalInstall_" + [guid]::NewGuid().ToString("N"))
powershell -NoProfile -ExecutionPolicy Bypass -File packaging\smoke_installed.ps1 `
  -SetupPath release\SNInsightTerminal_Setup.exe `
  -InstalledRoot $installRoot `
  -UseTempDataDir `
  -ApiPort 18985 `
  -TimeoutSeconds 90
```

Result: passed.

- Silent install: passed
- Installed executable exists: passed
- Start menu shortcut exists: passed
- `/api/terminal/docs`: `200`
- `/api/terminal/data-status`: `200`
- `/api/terminal/settings/status`: Alpha Vantage, NewsAPI, Tushare, and Local API Provider unconfigured
- `/api/terminal/predictions`: blocked or empty
- Prediction list: empty
- Prediction cards: empty
- `sample_data_used=false`
- `baseline_used=false`
- `customer_prediction_generated=false`
- `/terminal`: `200`
- `/legacy`: `200`
- Mock settings save/reset did not expose complete keys
- Shutdown endpoint: passed
- Port released: passed
- No `SNInsightTerminal` orphan process remained
- Silent uninstall: passed
- Temporary install root removed after uninstall
- Temporary user data directory removed after smoke

### Forbidden Artifact Scan

Release safety scans:

```powershell
python scripts\quality_gate.py --only-scans --continue-on-error
```

Result: passed.

Manual `dist/` and `release/` forbidden file scan also passed. No forbidden package files were found for:

- `.env`
- `secrets.json`
- `private_bundle_seed.json`
- `private_release_keys.json`
- `app_data/`
- `outputs/`
- `cache/`
- `logs/`
- `e2e-artifacts/`
- `*.sqlite`
- `*.sqlite3`
- `*.db`
- `*.log`

### No-Key / No-Data Behavior

The fresh installed smoke verified the required no-key, no-real-data terminal behavior:

- Alpha Vantage: unconfigured
- NewsAPI: unconfigured
- Tushare: unconfigured
- Local API Provider: unconfigured and disabled
- Prediction list: empty
- Prediction cards: empty
- `sample_data_used=false`
- `baseline_used=false`
- `customer_prediction_generated=false`

This confirms the current installer artifact does not emit legacy sample prediction cards as customer predictions when provider keys and real data are absent.

### Environment Note

A first installer smoke attempt against the default install root (`%LOCALAPPDATA%\Programs\SNInsightTerminal`) failed the no-key settings assertion because that directory contained an obsolete `_internal\private\private_bundle_seed.json` from an older installed build. The current `dist/` and `release/` artifacts did not contain that file. A fresh temporary install root passed. Future installed smoke should use `-InstalledRoot <temp path>` or uninstall/clean the previous app install directory before validating no-key behavior. Do not delete `%LOCALAPPDATA%\SNInsightTerminal` user data during this cleanup.

## RC Validation Pass 2

Validation date: 2026-06-07

This second validation pass was run during the local-first second-stage milestone. It validated the current local worktree after the second-stage provider, backtest, intraday, and frontend API contract work. The source repository was not pushed and no PR was created. The validation did not trigger real provider refreshes, model training, customer prediction generation, research backtest generation, or Feature Store builds.

### Source State

- Branch: `main`
- HEAD SHA: `bf55517`
- Latest merge: `Merge pull request #10 from zyan-zhong/docs/release-candidate-validation`
- Worktree state: local milestone changes present and intentionally uncommitted
- Repository cleanliness check: passed
- Tracked forbidden runtime/build/cache artifacts: none

### Full Quality Gate

Command:

```powershell
$env:SN_ALPHA_VANTAGE_KEY=$null
$env:SN_NEWSAPI_KEY=$null
$env:SN_TUSHARE_TOKEN=$null
$env:SN_LOCAL_API_PROVIDER_TOKEN=$null
$env:SN_LOCAL_API_PROVIDER_ENABLED="0"
$env:SN_MANAGED_PROXY_TOKEN=$null
$env:SN_MANAGED_DATA_PROXY_TOKEN=$null
$env:SN_DISABLE_AUTO_SCHEDULER="1"
python scripts\quality_gate.py --continue-on-error
```

Result: passed.

- Repo cleanliness: passed
- Secret scan: passed
- Release package safety scan: passed
- Real-result sample/baseline scan: passed
- Historical OHLCV scaling scan: passed
- Python compileall: passed
- API endpoint contract tests: `13 passed`
- Data watermark schema tests: `12 passed`
- Full pytest: `1683 passed`
- Frontend typecheck: passed
- Frontend build: passed
- Frontend UI contract check: passed
- Frontend E2E: `36 passed`
- Total quality gate duration: `540.6s`

### Build Command

Before the build, only repository-local `build/`, `dist/`, and `release/` directories were removed. No user data directory was removed.

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File packaging\build_release.ps1
```

Result: passed.

- `build_release.ps1` exit code: `0`
- Full pytest inside release build: `1683 passed`
- Frontend typecheck/build/check:ui: passed
- PyInstaller onedir build: passed
- Built-in onedir smoke in `build_release.ps1`: passed
- Inno Setup compile: passed
- Inno Setup compiler engine: `6.7.3`

### Artifact Summary

- Onedir executable: `dist/SNInsightTerminal/SNInsightTerminal.exe`
- Installer executable: `release/SNInsightTerminal_Setup.exe`
- Installer size: `42,725,907` bytes
- Installer SHA256: `256E11B2F133881586A622985FE8A242FAFEA61F0D34ECF53B1970A07480AAA5`
- `release/SHA256SUMS.txt`: matches installer SHA256

### Onedir Smoke

Command shape:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File packaging\smoke_installed.ps1 `
  -SkipInstall `
  -KeepInstalled `
  -SetupPath release\SNInsightTerminal_Setup.exe `
  -InstalledRoot dist\SNInsightTerminal `
  -UseTempDataDir `
  -ApiPort 18865 `
  -TimeoutSeconds 120
```

Result: passed.

- `/api/terminal/docs`: `200`
- `/api/terminal/data-status`: `200`
- `/api/terminal/settings/status`: Alpha Vantage, NewsAPI, Tushare, and Local API Provider unconfigured
- `/api/terminal/predictions`: blocked or empty
- Prediction list: empty
- Prediction cards: empty
- `sample_data_used=false`
- `baseline_used=false`
- `customer_prediction_generated=false`
- `/terminal`: `200`
- `/legacy`: `200`
- Shutdown endpoint: passed
- Port released: passed
- No `SNInsightTerminal` orphan process remained

Note: the frozen onedir process released the port but did not exit within the smoke timeout. The smoke script forced cleanup as designed and then verified no orphan process remained.

### Installer Smoke

Command shape:

```powershell
$installRoot = Join-Path $env:TEMP ("SNInsightTerminalInstall_" + [guid]::NewGuid().ToString("N"))
powershell -NoProfile -ExecutionPolicy Bypass -File packaging\smoke_installed.ps1 `
  -SetupPath release\SNInsightTerminal_Setup.exe `
  -InstalledRoot $installRoot `
  -UseTempDataDir `
  -ApiPort 18866 `
  -TimeoutSeconds 120
```

Result: passed.

- Silent install: passed
- Installed executable exists: passed
- Start menu shortcut exists: passed
- `/api/terminal/docs`: `200`
- `/api/terminal/data-status`: `200`
- `/api/terminal/settings/status`: Alpha Vantage, NewsAPI, Tushare, and Local API Provider unconfigured
- `/api/terminal/predictions`: blocked or empty
- Prediction list: empty
- Prediction cards: empty
- `sample_data_used=false`
- `baseline_used=false`
- `customer_prediction_generated=false`
- `/terminal`: `200`
- `/legacy`: `200`
- Shutdown endpoint: passed
- Port released: passed
- No `SNInsightTerminal` orphan process remained
- Silent uninstall: passed
- Temporary install directory removed
- Temporary smoke data directory removed

Note: as in the onedir smoke, the frozen installed process released the port but required forced cleanup after the shutdown timeout. The smoke contract passed because cleanup completed and no orphan process remained.

### Forbidden Artifact Scan

Commands:

```powershell
python scripts\quality_gate.py --only-scans --continue-on-error
python scripts\check_repo_cleanliness.py
```

Result: passed.

Manual `dist/` and `release/` scan also passed. No forbidden packaged files were found:

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

### Final Local Checks

- `git diff --check`: passed, with Git line-ending warnings only
- `git status --short`: showed expected local milestone source changes only
- `build/`, `dist/`, and `release/`: local ignored artifacts, not tracked

### Pass 2 Known Limitations

- The installer is still unsigned unless a later code-signing step is added.
- No real provider-key configured smoke was run.
- The build used the local worktree with uncommitted second-stage milestone changes; it is a local validation artifact, not a tagged source release.
- The installer artifact remains a local ignored artifact and must be uploaded as a GitHub Release asset if promoted.

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
