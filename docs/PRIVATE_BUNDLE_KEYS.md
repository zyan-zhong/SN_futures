# Private Bundle Keys

Private bundle key embedding is disabled. Provider keys must never be committed, printed, written to release notes as complete values, or embedded in PyInstaller onedir/installer assets. Users configure keys on the local machine through the settings page or `%LOCALAPPDATA%\SNInsightTerminal\config\secrets.json`.

## Supported Providers

The local user secrets file can include:

- `SN_ALPHA_VANTAGE_KEY`
- `SN_NEWSAPI_KEY`
- `SN_TUSHARE_TOKEN`
- `SN_LOCAL_API_PROVIDER_TOKEN`

Legacy `SN_MANAGED_PROXY_TOKEN` and `SN_MANAGED_DATA_PROXY_TOKEN` may still be resolved as backward-compatible aliases, but new local configuration should write the canonical `SN_LOCAL_API_PROVIDER_TOKEN` name.

The release build must not log, package, or embed complete provider keys.

## Build Inputs

Private key build inputs are not supported. `-PrivateBundleKeys`, `-AllowEmbeddedProviderKeys`, and `-RequireAllPrivateProviderKeys` fail fast in `packaging/build_release.ps1`.

Allowed configuration paths:

- settings page save flow
- `%LOCALAPPDATA%\SNInsightTerminal\config\secrets.json`
- process environment variables for local developer runs
- development `.env` only for local development, never for packaging

## Build Command

```powershell
.\packaging\build_release.ps1 `
  -NodePath "C:\Program Files\nodejs\node.exe" `
  -NpmPath "C:\Program Files\nodejs\npm.cmd"
```

## Runtime Import

On first run, the app creates the user data directory and a `secrets.example.json` template. Missing provider keys remain `未配置` until the user configures them locally.

Rules:

- Existing user secrets are not overwritten.
- Settings and key diagnostics expose only `configured`, `source`, and `masked`.
- Reset removes user secrets and does not restore embedded private defaults.
- Unconfigured providers must not generate fake predictions, fake backtests, or fake data-status success.

## Installed Smoke

`packaging/smoke_installed.ps1 -RunBrowserSmoke` validates:

- unconfigured provider status is explicit
- configured keys, if supplied by the local user, are masked
- Tushare API permission, quota, or endpoint status is not required for install success
- Runtime secret scan passes

## Security Boundary

Complete provider keys may exist only in the local user secrets file or local development environment. They must not appear in Git, docs, release logs, frontend dist, PyInstaller `_internal`, diagnostics bundles, cache files, or customer-facing reports.
