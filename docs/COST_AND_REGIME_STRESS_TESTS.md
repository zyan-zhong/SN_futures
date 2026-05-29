# 成本与市场状态压力测试

机构级验证必须确认模型不是只在理想成本或单一市场状态下有效。本项目对 candidate 或研究实验结果执行成本压力和 regime 压力测试。

## 成本压力场景

当前覆盖：

- 0.5x cost
- 1x cost
- 2x cost
- 3x cost
- 低流动性滑点
- 跳空开盘滑点
- 移仓期额外成本
- 夜盘滑点

每个场景输出：

- 成本后期望
- Sharpe
- 最大回撤
- 命中率
- 压力场景下是否仍具备上线资格

2x 成本压力下期望为负时，candidate 不允许上线。

## 市场状态压力

当前覆盖：

- high volatility
- low volatility
- trend up
- trend down
- range
- event shock
- roll period
- extreme gap day

每组输出：

- 样本数
- 方向命中率
- 成本后期望
- 最大回撤
- 校准误差
- no-trade rate

高波动状态回撤过大、单一 regime 主导表现，都会导致机构级验证失败。

## 使用限制

压力测试结果只用于模型研究和 promotion gate。它不构成交易建议，不承诺收益，不接实盘交易。
