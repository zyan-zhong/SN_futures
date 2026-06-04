# Terminal Visualization Accuracy

## 行情图

- x 轴日期来自 `/api/terminal/charts/price-history` 的 `points[].time`。
- y 轴价格来自 `close/high/low`，不混用收益率。
- 支撑/压力线来自 `/api/terminal/market-analysis` 的 `key_levels`。
- 无真实 price-history 时显示 provider 失败原因或空状态，不绘制假线。

## 研究回测

- 收益曲线来自 `/api/terminal/research/equity-curve` 和 `outputs/research_backtests/*/equity_curve_*.csv`。
- 回撤曲线来自 research backtest report/drawdown files，页面标注 research only。
- 不标记为 active live performance。

## 预测路径

- 无 active model 时不显示未来路径。
- 不使用 baseline/fake prediction。
- PredictionPage 只在 active 通过后展示真实 active prediction。

## 因子与训练数据

- 因子覆盖率来自 feature coverage report，usable fields 与 coverage group 对齐。
- 训练数据样本数、特征数和标签分布来自 training dataset manifest。
- `used_in_model=false` 的新闻不进入 event factor inputs。

## 数据源状态

- `key_missing`、`rate_limited`、`disabled`、`from_cache` 和 `stale` 必须明确显示。
- cache 不冒充新数据。
- key 不进入前端、日志、图表或诊断摘要。
