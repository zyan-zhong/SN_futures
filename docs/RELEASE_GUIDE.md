# SNInsightTerminal Release Guide

Current private research release target: `0.3.8-private-research-beta.1`

This guide covers the Windows private installer build, installed smoke validation, private provider key handling, and release governance. The terminal is a research system. It does not connect to live trading, does not promise returns, and does not generate customer predictions unless a model has passed promotion gate and been explicitly approved as active.

## Prerequisites

- Windows 10 or 11.
- Python with project requirements installed.
- Node.js and npm. The default local paths are `C:\Program Files\nodejs\node.exe` and `C:\Program Files\nodejs\npm.cmd`.
- PyInstaller.
- Inno Setup 6 with `ISCC.exe` on PATH or installed in a standard location.
- Private key file at `packaging/private_release_keys.json` or private build environment variables.

`packaging/private_release_keys.json` is ignored by Git and must never be committed.

## Quality Gate

Run the production quality gate before building:

```powershell
.\scripts\quality_gate.ps1
```

The gate executes:

- `python -m compileall -q .`
- `pytest -q`
- `python -m unittest discover -s tests -p "test*.py" -v`
- `npm run typecheck`
- `npm run build`
- `npm run check:ui`
- `npm run test:e2e`
- `scripts/scan_runtime_secrets.ps1`
- no customer-facing baseline or fake prediction text checks
- no active model unless promotion evidence exists
- private seed static exposure checks
- release tree cleanliness checks
- required governance document checks

## Private Build

Build the private install-ready package:

```powershell
.\packaging\build_release.ps1 `
  -PrivateBundleKeys `
  -PrivateKeysFile "packaging/private_release_keys.json" `
  -AllowEmbeddedProviderKeys `
  -NodePath "C:\Program Files\nodejs\node.exe" `
  -NpmPath "C:\Program Files\nodejs\npm.cmd"
```

The build creates `build/private_bundle_seed.json` only long enough for PyInstaller to embed it in the private bundle, then removes the plaintext build-time seed file. The frontend bundle and release root must not contain the seed.

## Installed Smoke

Run installed smoke after the installer is created:

```powershell
.\packaging\smoke_installed.ps1 -RunBrowserSmoke -ExpectPrivateBundleKeys
```

The smoke validates:

- installer success
- first launch and API availability
- private key import or existing user key detection
- masked settings/key diagnostics
- `/terminal` and `/legacy`
- Playwright browser smoke when frontend dependencies exist
- user data directory creation and retention after uninstall
- no complete key leakage in runtime logs/cache/outputs

Smoke setup and uninstall logs are written under `%TEMP%\SNInsightTerminalSmoke`, not the release directory.

## Release Artifacts

Expected release outputs:

- `release/SNInsightTerminal_Setup.exe`
- `release/SHA256SUMS.txt`
- optional `release/installed_smoke_report.txt`

The release directory must not contain `.env`, `.log`, cache directories, database files, or raw private seed files.

## Security Boundary

Private provider keys may exist only in:

- `packaging/private_release_keys.json` on the builder machine
- PyInstaller internal private seed for the private build
- `%LOCALAPPDATA%\SNInsightTerminal\config\secrets.json` after first launch import

Keys must not appear in source, docs, tests, frontend dist, logs, HTTP cache, diagnostics, release logs, or public GitHub releases.

## Public Release Warning

Do not use `-PrivateBundleKeys` for public GitHub releases. The private bundle key path is intended only for controlled internal/private distribution. The long-term customer-safe approach remains managed data proxy or licensed provider tokens.
