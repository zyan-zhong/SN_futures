# SNInsightTerminal Release Guide

Current private research release target: `0.4.2-private-research-beta.2`

Latest RC validation evidence: [RELEASE_CANDIDATE_VALIDATION.md](RELEASE_CANDIDATE_VALIDATION.md).

This guide covers the Windows installer build, installed smoke validation, local provider key handling, and release governance. The terminal is a research system. It does not connect to live trading, does not promise returns, and does not generate customer predictions unless a model has passed promotion gate and been explicitly approved as active.

## Prerequisites

- Windows 10 or 11.
- Python with project requirements installed.
- Node.js and npm. The default local paths are `C:\Program Files\nodejs\node.exe` and `C:\Program Files\nodejs\npm.cmd`.
- PyInstaller.
- Inno Setup 6 with `ISCC.exe` on PATH or installed in a standard location.
- Provider keys are configured only on the user's local machine after install, through the settings page or `%LOCALAPPDATA%\SNInsightTerminal\config\secrets.json`.

## Quality Gate

Run the production quality gate before building:

```powershell
.\scripts\quality_gate.ps1
```

The gate executes:

- repo cleanliness check
- secret scan
- release package safety scan
- no sample/demo/baseline used as real result scan
- no historical OHLCV live scaling scan
- `python -m compileall -q src scripts tests`
- API endpoint contract tests
- data watermark schema tests
- `pytest -q`
- `npm run typecheck`
- `npm run build`
- `npm run check:ui`
- optional `npm run test:e2e`

## Build

Build the install-ready package:

```powershell
.\packaging\build_release.ps1 `
  -NodePath "C:\Program Files\nodejs\node.exe" `
  -NpmPath "C:\Program Files\nodejs\npm.cmd"
```

`-PrivateBundleKeys`, `-AllowEmbeddedProviderKeys`, and `-RequireAllPrivateProviderKeys` are disabled. The build must not create or package `private_bundle_seed.json`, `private_release_keys.json`, `.env`, `secrets.json`, runtime cache, logs, outputs, or SQLite files.

## Installed Smoke

Run installed smoke after the installer is created:

```powershell
.\packaging\smoke_installed.ps1 `
  -UseTempDataDir `
  -ApiPort 8765 `
  -TimeoutSeconds 60 `
  -RunBrowserSmoke
```

The smoke validates:

- installer success
- first launch and API availability
- isolated `SN_DATA_DIR` / `SN_INSIGHT_DATA_DIR` when `-UseTempDataDir` or `-DataDir` is supplied
- explicit unconfigured provider status on first launch
- `/api/terminal/predictions` returns blocked/empty output with `sample_data_used=false`, `baseline_used=false`, and `customer_prediction_generated=false` when no provider keys or real data are configured
- masked settings/key diagnostics when the local user configures keys
- masked settings/key diagnostics
- `/terminal` and `/legacy`
- Playwright browser smoke when frontend dependencies exist
- user data directory creation and retention after uninstall
- no complete key leakage in runtime logs/cache/outputs

Smoke setup and uninstall logs are written under `%TEMP%\SNInsightTerminalSmoke`, not the release directory.

`-ExpectPrivateBundleKeys` is disabled and must not be used as an acceptance path. Provider keys stay in the installed user's local config only; the smoke clears provider key environment variables before launching the terminal.

### Upgrade Cleanup Smoke

Before publishing an installer, validate that overlay install removes stale private bundle files left by older builds:

```powershell
$installRoot = Join-Path $env:TEMP ("SNInsightTerminalInstall_" + [guid]::NewGuid().ToString("N"))
.\packaging\smoke_installed.ps1 `
  -SetupPath release\SNInsightTerminal_Setup.exe `
  -InstalledRoot $installRoot `
  -UseTempDataDir `
  -ApiPort 8766 `
  -TimeoutSeconds 90 `
  -InjectLegacyPrivateSeed
```

`-InjectLegacyPrivateSeed` is allowed only with an explicit temporary `-InstalledRoot`. It seeds obsolete `{app}\_internal\private` files before install and verifies the installer removes them. It must never target the default user install directory or `%LOCALAPPDATA%\SNInsightTerminal` user data.

## Release Artifacts

Expected release outputs:

- `release/SNInsightTerminal_Setup.exe`
- `release/SHA256SUMS.txt`
- optional `release/installed_smoke_report.txt`

The release directory must not contain `.env`, `.env.local`, `secrets.json`, `private_bundle_seed.json`, `private_release_keys.json`, `.log`, cache directories, runtime outputs, database files, or screenshots.

## Security Boundary

Provider keys may exist only in:

- `%LOCALAPPDATA%\SNInsightTerminal\config\secrets.json`
- process environment variables for local developer runs
- development `.env` for local development only, never for packaging

Keys must not appear in source, docs, tests, frontend dist, logs, HTTP cache, diagnostics, release logs, or public GitHub releases.

## Public Release Warning

Do not use embedded private provider keys for any release. GitHub releases should publish installer assets only; provider keys stay on the user's local machine.
