# Candidate 失败归因诊断

本诊断用于解释 candidate model 未通过 promotion gate 的原因。它只读取真实训练、walk-forward、promotion gate 和特征覆盖产物，不发布 active model，不生成客户预测，不降低 promotion gate，也不使用 sample 或 fake prediction。

## 数据来源

- `outputs/model_registry/candidate_training_status.json`
- `outputs/model_registry/promotion_report.json`
- `outputs/walk_forward/wf_1d.json`、`wf_3d.json`、`wf_5d.json`、`wf_10d.json`、`wf_20d.json`
- `outputs/training_dataset_manifest.json`
- `outputs/training_datasets/train_*.parquet`
- `outputs/feature_coverage_report.json`，如果存在

## API

- `GET /api/terminal/models/candidate-diagnostics`

返回内容包括：

- 每个 horizon 的 promotion failure reasons
- walk-forward fold metrics
- 混淆矩阵估算
- 校准分层
- 高置信分层
- return bucket 表现
- regime 表现
- 回撤窗口归因
- top feature importance
- fold 间不稳定特征
- label difficulty
- 中文错误诊断与下一步研究建议

## 当前诊断边界

当前 walk-forward 产物没有保存逐样本 out-of-fold 预测轨迹，因此以下项目无法精确还原：

- 概率 decile 的真实兑现率
- 逐样本 confusion matrix
- top 10% / top 20% confidence 的真实样本集合
- 某个回撤窗口内的逐笔错误信号方向

服务会明确标注这些字段为 `estimated_from_aggregate_metrics` 或 fold-level proxy。下一轮研究优化应优先保存逐样本验证轨迹。

## 研究结论模板

诊断会回答以下问题：

- 是否因子不足导致：查看 feature coverage、feature importance 和 fold stability。
- 是否概率校准不足导致：查看 Brier、ECE 和 calibration bins。
- 是否 label 太噪声导致：查看低收益区域比例、class imbalance 和 return distribution。
- 是否高波 regime 回撤过大导致：查看 drawdown attribution 和 regime performance。
- 是否需要改标签、改特征、改模型、改入场门槛、改风险控制或增加基本面数据。

## 不允许事项

- 不允许把 candidate 直接发布为 active。
- 不允许降低 promotion gate。
- 不允许生成客户预测。
- 不允许使用 baseline prediction 或 baseline backtest。
- 不允许使用 sample data 参与诊断结论。
- 不允许伪造逐样本表现。

## 下一步建议

1. 保存 out-of-fold prediction trace：时间、regime、真实方向、预测方向、raw/calibrated probability、confidence、return、成本后收益。
2. 对 1d/3d 优先做概率校准和强信号筛选。
3. 对 5d/10d/20d 优先做高波 regime 风控和回撤约束。
4. 做 feature stability selection，减少 fold 间不稳定因子。
5. 在基本面、库存、外盘和事件数据不足前，不宣称完整基本面模型增益。
