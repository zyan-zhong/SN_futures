# Candidate V6 Research Plan

Candidate v6 is blocked until real data readiness passes. The current boundary is:

- Do not train candidate v6 during data refresh.
- Do not publish `active_model.json` without explicit human approval.
- Do not generate customer predictions.
- Do not use sample, mock, or baseline data.

## Admission Inputs

Candidate v6 readiness requires at least one real incremental factor group, leakage checks passing, and no sample/mock/baseline flags. Tushare can contribute:

- `raw_market`: `open_interest`, `settlement`
- `inventory`: `warehouse_receipt_delta_1w`, `member_net_position`

If Tushare is missing, permission-denied, quota-limited, rate-limited, or returns no SN rows, the next candidate v6 gated training prompt must remain blocked and report the reason.

## Next Gate

Only after `/api/terminal/models/candidate-v6/readiness` returns `ready` should the gated training prompt run candidate v6 research. Promotion remains dry-run unless a human explicitly approves active release.

## Auxiliary Evidence Boundary

Feature Store v6 may include the new Tushare auxiliary fields, but this is still a data readiness step. It can unblock the next candidate-v6 gated prompt only when:

- at least one real incremental group is present;
- `sample_data_used=false`, `mock_data_used=false`, and `baseline_used=false`;
- leakage/no-lookahead checks pass;
- feature stability evidence from the prior prompt remains available.

This prompt must not train candidate v6, publish active, or generate customer predictions.
