# Purged Walk-forward Training

本文档说明 SNInsightTerminal 当前的候选模型验证流程。该流程只用于研究验证，不发布 active model，不生成客户预测，不生成回测信号。

## 输入

- `outputs/training_dataset_manifest.json`
- `outputs/training_datasets/train_1d.parquet`
- `outputs/training_datasets/train_3d.parquet`
- `outputs/training_datasets/train_5d.parquet`
- `outputs/training_datasets/train_10d.parquet`
- `outputs/training_datasets/train_20d.parquet`

这些文件必须来自真实行情数据，`sample_data_used` 必须为 `false`。

## Purged Walk-forward 规则

每个周期独立执行时间顺序验证：

1. 按 `label_start_time` 排序。
2. validation fold 位于 train fold 之后。
3. 训练集中移除与 validation 标签窗口重叠的样本。
4. 每个 fold 后记录至少 horizon 长度的 embargo 样本。
5. 每个 fold 写入：
   - `train_start`
   - `train_end`
   - `validation_start`
   - `validation_end`
   - `train_samples`
   - `validation_samples`
   - `purged_samples`
   - `embargo_samples`

输出文件：

- `outputs/walk_forward/wf_1d.json`
- `outputs/walk_forward/wf_3d.json`
- `outputs/walk_forward/wf_5d.json`
- `outputs/walk_forward/wf_10d.json`
- `outputs/walk_forward/wf_20d.json`

## 指标

每个周期输出：

- `directional_accuracy`
- `balanced_accuracy`
- `precision_up`
- `precision_down`
- `recall_up`
- `recall_down`
- `brier_score`
- `calibration_error`
- `return_mae`
- `return_rmse`
- `information_coefficient`
- `coverage_rate`
- `abstain_rate`
- `cost_adjusted_expectancy`
- `max_drawdown_proxy`
- `fold_count`
- `sample_count`

## 约束

- baseline 只作为内部对照指标，不进入客户预测。
- candidate 不会自动替换 active。
- 没有 promotion gate 通过记录前，系统不生成客户预测。
- 不使用样例数据。
- 不接实盘交易，不构成投资建议。
