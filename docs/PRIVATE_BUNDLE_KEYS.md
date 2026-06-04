# Private Bundle Keys

Private bundle keys are supported only for controlled private/offline research builds. They must never be committed, printed, written to release notes as complete values, or exposed through frontend assets, logs, diagnostics, cache files, or public releases.

## Supported Providers

The private bundle seed can include:

- `SN_ALPHA_VANTAGE_KEY`
- `SN_NEWSAPI_KEY`
- `SN_TUSHARE_TOKEN`
- `SN_MANAGED_DATA_PROXY_TOKEN` from `SN_MANAGED_PROXY_TOKEN` or `SN_MANAGED_DATA_PROXY_TOKEN`, when available

The release build logs only configured/masked status for each provider.

## Build Inputs

Private keys can be supplied by:

- `packaging/private_release_keys.json`
- environment variables such as `SN_BUNDLE_ALPHA_VANTAGE_KEY`, `SN_BUNDLE_NEWSAPI_KEY`, `SN_BUNDLE_TUSHARE_TOKEN`, and `SN_BUNDLE_MANAGED_PROXY_TOKEN`

When `-PrivateBundleKeys` is enabled, `packaging/build_release.ps1` always reads the private keys file and merges it with environment variables. This matters when Alpha Vantage or NewsAPI are supplied by environment variables but Tushare is supplied by the private keys file.

Use `-RequireAllPrivateProviderKeys` for 0.4.2 private research patch builds so missing Alpha Vantage, NewsAPI, or Tushare configuration fails before packaging.

## Build Command

```powershell
.\packaging\build_release.ps1 `
  -PrivateBundleKeys `
  -PrivateKeysFile "packaging/private_release_keys.json" `
  -AllowEmbeddedProviderKeys `
  -RequireAllPrivateProviderKeys `
  -NodePath "C:\Program Files\nodejs\node.exe" `
  -NpmPath "C:\Program Files\nodejs\npm.cmd"
```

## Runtime Import

On first run, `import_private_bundle_keys_if_needed()` imports missing provider keys into `%LOCALAPPDATA%\SNInsightTerminal\config\secrets.json` and records source as `private_bundle`.

Rules:

- Existing user secrets are not overwritten.
- Missing Tushare can be imported independently of Alpha Vantage and NewsAPI.
- Settings and key diagnostics expose only `configured`, `source`, and `masked`.
- Reset removes user secrets and restores private bundle defaults, including Tushare when it exists in the bundle.

## Installed Smoke

`packaging/smoke_installed.ps1 -RunBrowserSmoke -ExpectPrivateBundleKeys` validates:

- Alpha Vantage configured/masked
- NewsAPI configured/masked
- Tushare configured/masked
- Tushare source is `private_bundle`, `user_secrets`, or `env`
- Tushare API permission, quota, or endpoint status is not required for install success
- Runtime secret scan passes

## Security Boundary

Complete provider keys may exist only in local private build input files, the PyInstaller internal private seed, or the user data secrets file after first-run import. They must not appear in Git, docs, release logs, frontend dist, diagnostics bundles, or customer-facing reports.
