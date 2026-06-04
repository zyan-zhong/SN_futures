# Visualization Design System

本终端图表用于真实行情研究、因子研究和研究型回测展示，不发布 active，不生成客户预测，不展示伪未来路径。

## 图表原则

- 标题短：说明图表对象，不写长段解释。
- 副标题只放数据来源、freshness、research-only 状态。
- Tooltip 只显示时间、字段、单位和数值。
- 图例默认不超过 5 项。
- 技术细节进入折叠面板或诊断区。
- 无数据时显示专业空状态，不渲染空白画布。
- 图表必须有文字状态，不只依赖颜色。

## 色彩规范

- 行情上涨：红色。
- 行情下跌：绿色。
- 系统正常：蓝/青色。
- Warning：黄色。
- Error：红色。
- Research-only：灰/紫色，并必须有文字标识。
- Sample：黄/紫色，并必须有样例标识。

## 行情监控

- 价格图使用 `price-history` 的交易日期作为 x 轴。
- y 轴价格单位为 `CNY/ton`，不能混用收益率。
- 成交量作为柱状图，可与价格图同屏但使用独立 y 轴。
- 支撑/阻力线来源于 `market-analysis.key_levels`。
- 缺持仓量时显示缺字段状态，不填假值。

## 回测验证

- Equity curve 只来自 research backtest / OOF 信号。
- Drawdown curve 值必须为 0 或负数，单位为百分比。
- 所有研究型图表必须标注 research-only。
- 不得标成 live active performance。

## 模型研究

- OOF confidence decile、calibration bins、fold/year/regime heatmap、feature stability 均属于研究验证图。
- 高置信 OOF 命中率不是客户预测，不代表未来收益。

## 性能

- ECharts 通过动态 import 懒加载。
- 图表容器使用 `ResizeObserver`，页面切换时释放实例。
- 大数据 payload 使用 stride downsampling，并保留首尾点。
- 非当前页面不渲染图表。
- 表格类大数据必须分页或只展示摘要。
