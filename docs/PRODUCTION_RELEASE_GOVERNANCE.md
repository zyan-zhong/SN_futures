# Production Release Governance

## Required Gates

Before a private research release is shipped, run:

```powershell
.\scripts\quality_gate.ps1
```

Then build the private installer and run installed smoke:

```powershell
.\packaging\build_release.ps1 `
  -PrivateBundleKeys `
  -PrivateKeysFile "packaging/private_release_keys.json" `
  -AllowEmbeddedProviderKeys `
  -NodePath "C:\Program Files\nodejs\node.exe" `
  -NpmPath "C:\Program Files\nodejs\npm.cmd"

.\packaging\smoke_installed.ps1 -RunBrowserSmoke -ExpectPrivateBundleKeys
```

## Non-Negotiable Controls

- Do not ship full API keys in source, docs, tests, frontend bundles, logs, caches, or diagnostics.
- Do not publish `active_model.json` unless promotion gate has passed.
- Do not generate customer predictions without a promoted active model.
- Do not use sample or baseline outputs as real market, prediction, or backtest evidence.
- Do not delete `tests`, no-baseline policy, real-data policy, secret sanitizer, private bundle docs, legacy UI, or sample data during cleanup.

## Release Directory Policy

The `release` directory should contain only current release artifacts such as the installer, checksum file, and smoke report. It must not contain `.env`, logs, caches, SQLite databases, raw private seeds, or user runtime data.

## Documentation Minimum

The release must keep:

- `docs/NO_BASELINE_PREDICTION_POLICY.md`
- `docs/REAL_DATA_ONLY_POLICY.md`
- `docs/RUNTIME_SECRET_SANITIZATION.md`
- `docs/PRIVATE_BUNDLE_KEYS.md`
- `docs/PROFESSIONAL_TERMINAL_WORKBENCH.md`
- `docs/ARTIFACT_CENTER.md`
- `docs/CODEBASE_CLEANUP_AUDIT.md`
- `docs/CUSTOMER_RELEASE_REPORT_0.3.8_PRIVATE.md`
- `docs/PRIVATE_RELEASE_NOTES.md`
- `docs/RELEASE_GUIDE.md`
