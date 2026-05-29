# 选择性预测策略

## 原则

选择性预测不是提高全覆盖准确率的捷径，而是控制覆盖率、成本和风险后的研究筛选框架。

必须同时报告：

- 覆盖率。
- 样本数。
- 命中率。
- 成本后期望。
- 回撤代理。
- 阈值来源。

禁止只展示高置信子集命中率而隐藏覆盖率。

## 阈值优化

`selective_threshold_optimizer.py` 输入 validation fold 的：

- calibrated probability。
- expected return。
- realized return。
- realized direction。
- estimated cost。

输出：

- `prob_threshold_up`
- `prob_threshold_down`
- `min_edge`
- `min_confidence`
- `expected_coverage`
- `accuracy_at_coverage`
- `expectancy_at_coverage`
- `drawdown_at_coverage`

## 训练和验证边界

- 阈值只能从训练/验证流程内产生。
- 不允许用最终测试集拟合阈值。
- coverage 过低时，不允许宣传为整体模型能力。
- 只有通过 promotion gate 的 active model 才能进入客户预测链路。
