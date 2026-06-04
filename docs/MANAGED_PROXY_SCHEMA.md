# Managed Proxy Schema

Each fundamentals row may include:

- `trade_date`
- `spot_price`
- `spot_premium`
- `spot_futures_basis`
- `shfe_inventory`
- `shfe_warehouse_receipt`
- `lme_tin_close`
- `lme_inventory`
- `near_contract`
- `far_contract`
- `near_contract_close`
- `far_contract_close`
- `near_open_interest`
- `far_open_interest`
- `main_contract`
- `main_contract_switch_flag`

Rows must represent tin / SN data. Copper, aluminium, or generic metal rows must not be used as substitutes.

Feature coverage uses these fields for basis, inventory, LME cross-market, term structure, and open-interest related research factors.
