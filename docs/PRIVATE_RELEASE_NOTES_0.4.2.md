# Private Release Notes 0.4.2

Version: `0.4.2-private-research-beta.2`

Installer: pending successful `-RequireAllPrivateProviderKeys` build
SHA256: pending successful build

## Patch Scope

- Fixes private bundle key resolution so `packaging/private_release_keys.json` is always read when `-PrivateBundleKeys` is enabled.
- Supports Tushare in the private bundle seed through `SN_TUSHARE_TOKEN`.
- Keeps environment variable and private keys file merge behavior without printing complete provider keys.
- Adds `-RequireAllPrivateProviderKeys` so Alpha Vantage, NewsAPI, and Tushare must be present before a 0.4.2 private patch package is built.
- Extends installed smoke to validate Tushare configured/masked status without requiring a successful live Tushare API request.

## Included From 0.4.2

- Feature Store v7 visibility, including Tushare-derived cost and positioning fields.
- Candidate v7 research-only status and promotion dry-run result.
- Tushare `fut_daily`, `fut_settle`, and `fut_holding` status surfaces.
- Tushare `fut_wsr no_sn_rows` policy display with no fake warehouse receipt data.
- Research backtest equity/drawdown display and professional empty states.
- Terminal button audit, concise copy, task queue stability, report export, and diagnostics bundle export.

## Validation Status

- TDD patch tests: PASS.
- Full quality gate: pending after private key configuration is complete.
- Private patch build: blocked until build input provides Tushare.
- Installed smoke: pending.
- secret scan: pending.

## Not Included

- No active model publication.
- No customer predictions.
- No baseline or fake prediction fallback.
- No promotion gate relaxation.
- No model strategy changes.

## Operational Notes

- For this patch, `SN_TUSHARE_TOKEN` is required in `packaging/private_release_keys.json` or `SN_BUNDLE_TUSHARE_TOKEN` / `SN_TUSHARE_TOKEN` environment variables.
- Tushare API permission, quota, or live refresh status is not an installation failure; the patch smoke validates configuration presence and masking only.
- `fut_wsr no_sn_rows` remains a valid real-source state and does not allow fabricated warehouse receipt data.
