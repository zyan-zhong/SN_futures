# 标签变体设计

## 背景

沪锡期货短周期涨跌存在大量低收益噪声区。若强行把所有微小波动标为上涨或下跌，会提高标签噪声，损害校准和成本后表现。

## 标签变体

1. `direction_raw`

原始涨跌方向，仅用于对照。

2. `direction_thresholded`

未来收益绝对值超过成本和噪声阈值时才标方向，否则标记为 no-trade。

3. `triple_barrier_atr`

使用 ATR 上下障碍构造研究标签，用于分析触及路径和风险。

4. `volatility_adjusted_return`

未来收益除以滚动波动率，降低不同波动 regime 下的尺度差异。

5. `high_confidence_meta_label`

研究候选信号是否值得交易，不等于客户交易建议。

## 泄漏控制

- 标签列不能进入 feature columns。
- `ret_`、`direction_`、`tb_` 等列必须从特征集中剔除。
- 末尾未来窗口不足的样本必须删除。
- 重叠标签窗口需要通过 purged walk-forward 处理。

## 使用边界

标签变体只服务于 candidate model 研究，不发布 active，不生成客户预测。
