# Model Promotion Gate

## Candidate v2 dry-run

`POST /api/terminal/models/promote-candidate?dry_run=true` supports `candidate_version`, including `v2`.

Dry-run mode evaluates the same gate without writing `outputs/model_registry/active_model.json`. If a candidate passes dry-run, the UI should only show that it is eligible for manual active approval. If it fails, the report lists failure reasons and `active_updated=false`.

The current v2 dry-run remains rejected under the unchanged gate. This is expected while DSR, PBO, Reality Check, cost stress, feature stability, and high-confidence sample checks are not all satisfied.

本阶段实现严格 promotion gate。candidate model 只有通过真实 walk-forward、成本后表现、概率校准、数据质量、风险和无泄漏检查后，才允许写入 active registry。

## API

- `POST /api/terminal/models/promote-candidate`
- `GET /api/terminal/models/active-status`
- `GET /api/terminal/models/promotion-report`

## Gate 规则

默认规则：

1. `fold_count >= 3`
2. `validation_sample_count >= 300`
3. `directional_accuracy > naive_directional_accuracy + 0.02`
4. `brier_score <= 0.24`
5. `calibration_error <= 0.08`
6. `cost_adjusted_expectancy > 0`
7. `abs(max_drawdown_proxy) <= 0.25`
8. `feature_coverage >= 0.70`
9. `data_quality_score >= 0.80`
10. `leakage_check_pass = true`
11. `sample_data_used = false`
12. `baseline_used = false`
13. `recent_degradation_triggered = false`

## 通过时

写入：

- `outputs/model_registry/active_model.json`
- `outputs/model_registry/model_artifacts/active_*.json`
- `outputs/model_registry/promotion_report.json`

## 失败时

写入：

- `outputs/model_registry/candidate_rejected.json`
- `outputs/model_registry/promotion_report.json`

失败原因必须为中文。失败时不会写入 `active_model.json`。

## 明确禁止

- baseline 不可 promotion。
- sample data 不可 promotion。
- leakage fail 不可 promotion。
- 成本后期望不为正不可 promotion。
- 未通过 promotion gate 不生成客户预测。
- 不接实盘交易，不构成投资建议，不承诺收益。
