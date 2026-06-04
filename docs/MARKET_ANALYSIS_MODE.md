# Professional Market Analysis Mode

## 目标

Professional Market Analysis 模式用于在没有 Tushare token、没有 managed proxy、没有完整基本面数据、且没有通过 promotion gate 的 active model 时，仍然基于真实沪锡 OHLCV 行情提供专业、可解释的行情分析。

该模式不是预测，不生成客户预测卡，不输出交易点位，不替代 active model。

## 无 Tushare 仍可分析的内容

- 趋势结构：5/20/60 日均线位置、短中期收益、均线结构和动量分数。
- 波动状态：ATR、20 日实现波动率、Bollinger 宽度和高低波动 regime。
- 关键价位：20/60 日高低点、支撑候选、压力候选。
- 量价状态：成交量趋势、成交量 z-score、成交量动量。
- Regime：趋势/震荡/高波动状态。
- 风险提示：高波动、趋势结构不明确、基本面数据不足、无 active 模型。

## 无 Tushare 不能分析的内容

- 完整期限结构。
- SHFE 仓单和库存变化。
- 现货升贴水和基差。
- LME 锡价格、库存和 LME-SHFE spread。
- 会员持仓排名驱动的资金结构分析。

缺失字段会在 `missing_fundamentals` 和前端“数据缺口”卡片中显示。系统不会使用其它品种或样例数据伪造这些字段。

## 无 active model 为什么不预测

当前项目采用 real-market-only 和 promotion gate 机制。只有 candidate model 通过 walk-forward、成本压力、DSR/PBO、Reality Check、特征稳定性和人工审批后，才允许成为 active model。

如果没有 active model：

- 不生成客户预测。
- 不生成 baseline prediction。
- 不生成 fake prediction。
- 不显示 entry、stop_loss、take_profit。

## API

`GET /api/terminal/market-analysis`

关键字段：

- `analysis_mode=ohlcv_regime_analysis`
- `not_prediction=true`
- `trend`
- `volatility`
- `key_levels`
- `volume_liquidity`
- `regime`
- `risk_flags`
- `missing_fundamentals`
- `next_actions_zh`

## 前端展示

行情监控页展示“专业行情分析”区域：

- 趋势结构卡。
- 波动状态卡。
- 关键价位卡。
- 量价状态卡。
- Regime 状态卡。
- 数据缺口卡。
- 下一步建议。

页面文案明确标注：“这是行情分析，不是预测。”

## 限制

行情分析不构成投资建议，不代表未来收益，不提供买卖建议。缺失基本面字段时，分析范围会收缩到 OHLCV、technical 和 regime。
