# Candidate v3 Research Results

Candidate v3 is a research-only model candidate built from Feature Store v3 and training dataset v3.

## Scope

- Uses real Feature Store v3 fields only.
- Uses purged walk-forward validation.
- Writes OOF traces under `outputs/walk_forward/v3/`.
- Does not write `active_model.json`.
- Does not generate customer predictions.
- Does not use baseline or sample data.

## Outputs

- Candidate registry: `outputs/model_registry/candidate_v3_model_registry.json`
- Training status: `outputs/model_registry/candidate_v3_training_status.json`
- OOF traces: `outputs/walk_forward/v3/oof_trace_*.csv`
- Institutional validation: `outputs/institutional_validation/institutional_validation_report_v3.json`
- Promotion dry-run: `outputs/model_registry/promotion_report_v3.json`

## Interpretation

Any v3 improvement remains research-only until strict promotion gate and human approval pass. A dry-run pass is not an active release.

