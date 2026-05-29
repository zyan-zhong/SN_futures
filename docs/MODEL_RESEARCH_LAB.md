# 模型研究实验室

## 目标

模型研究实验室用于改进 candidate model 的研究流程，不负责发布 active model，不生成客户预测，也不降低 promotion gate。

本模块关注：

- 真实 out-of-sample 稳定性。
- 高置信子集命中率和覆盖率。
- 成本后期望和回撤代理。
- Brier score、ECE 和校准曲线。
- 特征重要性稳定性。

## 模型候选

- LightGBM GBDT classifier/regressor，如果本机依赖可用。
- LightGBM random forest mode，作为树模型稳健性研究方向。
- sklearn HistGradientBoosting fallback。
- ExtraTrees / RandomForest，作为稳定性对照。
- ElasticNet / HuberRegressor，作为稳健回归对照。
- Logistic/Ridge 只允许作为内部对照指标，不进入客户预测页。
- CatBoost 依赖较重，本阶段不强制进入发行包。

## 实验产物

每次实验写入独立目录：

```text
outputs/model_research/experiments/<experiment_id>/
```

包含：

- `config.json`
- `feature_set.json`
- `label_config.json`
- `walk_forward_results.json`
- `threshold_results.json`
- `calibration_report.json`
- `feature_stability.json`
- `promotion_preview.json`

实验目录禁止覆盖旧实验。

## 发布边界

- 不写 `active_model.json`。
- 不写客户预测缓存。
- 不修改 promotion gate 阈值。
- 不用 sample data。
- 不用伪造行情、伪造收益或伪造预测。

若实验结果改善，也只能进入后续 candidate 训练和严格 promotion gate。
