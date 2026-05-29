# OOF 完整性与高置信子集稳健性验证

本文档记录 Prompt 49S 新增的样本外预测轨迹审计。该验证只用于研究诊断，不发布 active model，不生成客户预测，不降低 promotion gate。

## 审计输入

- `outputs/walk_forward/oof_trace_1d.csv`
- `outputs/walk_forward/oof_trace_3d.csv`
- `outputs/walk_forward/oof_trace_5d.csv`
- `outputs/walk_forward/oof_trace_10d.csv`
- `outputs/walk_forward/oof_trace_20d.csv`
- `outputs/walk_forward/wf_*.json`
- `outputs/training_dataset_manifest.json`

## 完整性检查

每个 horizon 检查：

- `fold_id` 非空。
- 每条记录来自对应 validation fold。
- `timestamp` 不落在该 fold 的训练窗口内。
- `prediction_time` 不晚于 `label_start_time`。
- walk-forward 元数据记录 purge 和 embargo。
- `sample_data_used=false`。
- `baseline_used=false`。
- 不存在重复 `timestamp + horizon + fold_id`。
- trace 中不包含未来收益、方向标签或 triple-barrier 标签列作为特征。

## 高置信子集验证

对 Top 10%、Top 20%、Top 30% confidence 子集分别计算：

- 样本数和覆盖率。
- 方向命中率和平衡准确率。
- up/down precision。
- realized return 均值和中位数。
- 成本后期望。
- 最大回撤代理。
- fold、regime、年份分层命中率。
- worst fold、worst regime、worst year。

## 阻断规则

以下情况只允许继续研究，不允许晋级：

- Top 10% 单一 fold 贡献超过 45%。
- 任一高置信子集单一 regime 贡献超过 50%。
- 任一高置信子集单一年份贡献超过 35%。
- worst fold accuracy 小于 0.52。
- 成本后期望小于等于 0。
- 最大回撤代理超过阈值。
- 样本数过少时，不允许宣传高命中率。

## DSR / PBO / Reality Check Preview

系统会基于高置信 OOF 子集重新计算：

- Deflated Sharpe Ratio preview。
- Probability of Backtest Overfitting preview。
- Bootstrap Reality Check preview。
- 2x 和 3x 成本压力 preview。

这些结果仅用于下一轮 candidate 研究方向判断，不代表 promotion gate 通过。

## API

- `GET /api/terminal/models/oof-integrity-report`
- `GET /api/terminal/models/high-confidence-report?horizon=1d`

## 前端展示

模型治理页新增“高置信子集验证”区域，展示：

- Top 10/20/30 coverage。
- Accuracy。
- Cost-adjusted expectancy。
- Worst fold / regime / year。
- DSR/PBO preview。
- Blocking reasons。

页面必须显示：高置信 OOF 命中率不是客户预测，不代表未来收益，不构成投资建议。
