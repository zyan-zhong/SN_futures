# Tushare Futures Data Source

This adapter adds an optional Tushare Pro source for SHFE tin fundamentals. It does not train models, publish active models, generate customer predictions, run baseline forecasts, or connect to live trading.

## Configuration

Set `SN_TUSHARE_TOKEN` in one of the existing secret channels:

- User secrets: `%LOCALAPPDATA%\SNInsightTerminal\config\secrets.json`
- Local private release keys: `packaging/private_release_keys.json`
- Environment variable: `SN_TUSHARE_TOKEN`
- Private bundle seed, if a private release includes it
- Development `.env`

Resolver priority is: user secrets, imported/private release secrets, environment, then development `.env`.

The Settings page only displays `configured/source/masked`. The full token is never returned by terminal APIs, written into frontend assets, or logged.

## Interfaces

The adapter uses these Tushare Pro futures interfaces when the token is configured:

- `fut_basic`: contract information
- `trade_cal`: SHFE trading calendar
- `fut_daily`: futures daily OHLCV, settlement, volume, open interest
- `fut_wsr`: warehouse receipt daily data
- `fut_settle`: settlement parameters, margin rate, fee rate
- `fut_holding`: member volume and position ranking

Only tin rows are retained. Rows for other commodities are rejected and never used as substitutes for SN.

## Output Files

Files are written under `outputs/fundamentals`:

- `tushare_provider_status.json`
- `sn_tushare_contracts.json`
- `sn_tushare_trade_calendar.json`
- `sn_tushare_daily.json`
- `sn_tushare_warehouse_receipt.json`
- `sn_tushare_settlement.json`
- `sn_tushare_holding.json`

## Feature Coverage

When real SN rows are present, feature coverage can improve for:

- `open_interest`
- `settlement`
- `warehouse_receipt_delta_1w`
- `member_net_position`
- term-structure and holding-rank research fields as coverage expands

Missing token, no SN rows, rate limits, or schema mismatches are reported as status reasons. The system does not fabricate spot, basis, inventory, LME, prediction, or backtest data.

## Candidate V6 Boundary

Tushare refresh can improve `open_interest`, `settlement`, `warehouse_receipt_delta_1w`, and `member_net_position`. Candidate v6 may only enter the gated training prompt after readiness is `ready`, leakage checks pass, and no sample/mock/baseline data is used. This data-refresh step never trains models, writes `active_model.json`, or generates customer predictions.

## Auxiliary Parameter Probe

The auxiliary interfaces use a parameter probe before writing data:

- `fut_wsr`: prefers `symbol=SN` plus `trade_date`; optional `exchange=SHFE/SHF` and `start_date/end_date` are recorded if successful.
- `fut_settle`: prefers concrete SHFE contracts such as `SN2406.SHF` plus `trade_date`; date ranges are only used when the provider accepts them.
- `fut_holding`: prefers `symbol=SN` plus `trade_date`, then contract and exchange variants.

The probe report is `outputs/fundamentals/tushare_param_probe_report.json`. It records sanitized parameters, selected parameters, row counts, columns, and explicit status values: `success`, `permission_denied`, `quota_limited`, `no_sn_rows`, `schema_mismatch`, or `request_failed`.
