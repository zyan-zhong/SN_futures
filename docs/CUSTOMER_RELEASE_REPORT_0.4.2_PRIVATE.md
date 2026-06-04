# Customer Release Report: 0.4.2 Private Research Beta 2

Version: `0.4.2-private-research-beta.2`
Release type: private research patch build
Generated on: `2026-06-01`

## Patch Objective

This patch fixes the 0.4.2 beta.1 blocker where the installed application could pass Alpha Vantage and NewsAPI private bundle checks while Tushare still reported `configured=false`, `source=none`.

## Code Changes

- `packaging/build_release.ps1` now always reads `PrivateKeysFile` when `-PrivateBundleKeys` is enabled.
- Private key file values are merged with environment variables for all supported providers.
- `SN_TUSHARE_TOKEN` is included in the private bundle seed when present.
- `-RequireAllPrivateProviderKeys` fails the build if Alpha Vantage, NewsAPI, or Tushare is missing.
- `packaging/smoke_installed.ps1` validates Tushare configured/masked status and reset restore behavior.
- Tushare live API success is not required for install smoke; only configuration presence and privacy are required.

## Build Artifact

- Installer: pending successful required-provider build.
- SHA256: pending successful build.
- Private bundle seed provider list: Alpha Vantage, NewsAPI, Tushare, optional Managed Proxy.

## Validation Status

- New TDD tests: PASS.
- Quality gate: pending.
- API smoke: pending.
- Performance smoke: pending.
- Full system report generation: pending.
- Market data smoke: pending.
- Installed smoke: pending.
- secret scan: pending.

## Current Blocker

The builder-side private key inputs currently do not provide a Tushare key. With `-RequireAllPrivateProviderKeys`, the beta.2 build must stop before packaging until `SN_TUSHARE_TOKEN` is supplied through `packaging/private_release_keys.json` or an approved local environment variable.

No complete token value is printed or recorded in this report.

## Research Artifact Status From 0.4.2

- Tushare `fut_daily`: available from prior refresh, `2715` rows.
- Tushare `fut_settle`: available from prior refresh, `360` rows.
- Tushare `fut_holding`: available from prior refresh, `12` rows.
- Tushare `fut_wsr no_sn_rows`: explicit real-source state; no fake warehouse receipt data.
- Feature Store v7: available.
- Candidate v7: research-only; not eligible for active publication.
- Full system report: available after generation.
- diagnostics bundle: available after report generation.

## Active And Prediction Policy

- No active model publication.
- No customer predictions.
- No baseline or fake prediction fallback.
- No promotion gate change.
- No model strategy change.

## Release Conclusion

The code fix is implemented and covered by TDD tests. The 0.4.2 beta.2 installer cannot be produced as a complete deliverable until the private build input includes Tushare and the required-provider build plus installed smoke pass.
