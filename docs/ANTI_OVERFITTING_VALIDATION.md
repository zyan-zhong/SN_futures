# 反过拟合验证

候选模型必须证明其样本外表现不是由多次实验、单一 fold 或单一市场状态偶然产生。本项目采用轻量但可审计的反过拟合验证，后续可扩展为完整 CPCV 与更严格的 White Reality Check。

## Deflated Sharpe Ratio

DSR 在普通 Sharpe 的基础上考虑：

- 样本数量不足带来的不确定性。
- 收益分布偏度和峰度。
- 多次试验后选择最优实验的选择偏差。

DSR 未超过阈值时，candidate 不具备上线资格。

## Probability of Backtest Overfitting

PBO 使用 leave-one-fold-out 的轻量排名估计：

- 在训练 fold 上选择表现最好的周期或策略。
- 检查其在留出 fold 中是否落入后半区。
- 落入后半区比例越高，过拟合风险越高。

PBO 超过阈值时，candidate 不具备上线资格。

## Reality Check

本版实现 bootstrap Reality Check：

- 对中心化后的 fold 表现重采样。
- 估计均值表现显著大于零的 p-value。
- 若 p-value 不达标，则视为未通过。

## CPCV 摘要

完整 combinatorial purged CV 计算成本较高，本版先输出轻量 leave-one-fold-out 摘要，并保留后续升级接口。该摘要不会替代正式 promotion gate，只作为机构级验证报告的一部分。

## 多重检验修正

报告输出 Bonferroni 和 Benjamini-Hochberg 修正结果，用于提示多周期、多实验比较下的显著性风险。
