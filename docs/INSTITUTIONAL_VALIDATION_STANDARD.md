# 机构级验证标准

本项目的 candidate model 不会因为单一准确率改善而上线。候选模型必须同时通过真实 walk-forward、反过拟合检验、成本压力、市场状态压力、校准、特征稳定性和风险集中度检查，才允许进入 promotion gate 的后续环节。

## 验证项

1. Deflated Sharpe Ratio：修正样本长度、非正态和多次试验选择偏差。
2. Probability of Backtest Overfitting：估计在多周期或多策略实验中选中偶然优胜者的风险。
3. Reality Check：使用 bootstrap 检验平均表现是否显著优于零。
4. 成本压力：检查 0.5x、1x、2x、3x 成本以及低流动性、跳空、移仓、夜盘滑点场景。
5. Regime 压力：检查高波动、低波动、趋势、震荡、事件冲击、移仓期和极端跳空下的稳定性。
6. 特征稳定性：检查 fold-wise importance 是否被少量不稳定特征主导。
7. 覆盖率约束：高置信子集样本数必须满足最低要求。
8. 集中度约束：不得由单一 fold 或单一 regime 贡献主要表现。

## Promotion Gate 约束

本轮新增的机构级 gate 项包括：

- DSR 必须高于阈值。
- PBO 必须低于阈值。
- Reality Check 必须通过。
- 2x 成本压力下期望不得显著为负。
- 高波动状态回撤必须受控。
- 特征重要性稳定性必须达标。
- 高置信覆盖样本数必须达标。
- 不允许单一 fold 主导表现。
- 不允许单一 regime 主导表现。

## 不变原则

- 不降低既有 promotion gate。
- 不发布 active model。
- 不生成客户预测。
- 不使用 baseline 或 sample 数据冒充真实模型表现。
- 若任一机构级验证项失败，candidate 仍保持 candidate 或 rejected 状态。
# Candidate v2 institutional validation

`POST /api/terminal/validation/run-institutional-check` accepts `candidate_version` and `dry_run`.

For `candidate_version=v2`, validation reads `outputs/walk_forward/v2/wf_*.json` and writes:

- `outputs/institutional_validation/institutional_validation_report_v2.json`
- `outputs/institutional_validation/stress_tests_v2.json`

The v2 validation remains dry-run research only. It does not publish active models, does not generate customer predictions, and does not lower gate thresholds.

Current v2 dry-run result: failed because DSR, PBO, Reality Check, 2x cost stress, feature stability, and high-confidence sample checks are not all satisfied.
