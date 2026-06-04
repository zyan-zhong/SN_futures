# Chart Payload Contract

统一图表 payload 由 `src/sn_futures/services/chart_payload_service.py` 生成。所有图表 payload 必须可直接审计来源、单位和空状态原因。

## 通用字段

- `schema_version`: 当前为 `1`。
- `generated_at`: 后端生成时间。
- `chart_type`: 图表类型，例如 `price`、`volume`、`equity_curve`、`drawdown_curve`。
- `x_field`: x 轴字段名。
- `y_fields`: y 轴字段列表。
- `units`: 每组数值字段的单位。
- `source_files`: 后端读取的文件名。
- `research_only`: 是否只属于研究展示。
- `downsampled`: 是否已降采样。
- `downsample_method`: 降采样方法。
- `points`: 图表点。
- `status`: `success` 或 `empty`。
- `missing_reason`: 缺数据原因。
- `message_zh`: 面向 UI 的中文状态。

## 已实现 payload

- `build_price_chart_payload`: 读取 `sn_market_history.json`，输出 OHLC 价格图。
- `build_volume_chart_payload`: 读取 `sn_market_history.json`，输出成交量/持仓量图。
- `build_equity_curve_payload`: 读取 `research_backtests/<version>/equity_curve_<horizon>.csv`，输出研究型收益曲线。
- `build_drawdown_curve_payload`: 读取 `research_backtests/<version>/drawdown_curve_<horizon>.csv`，输出研究型回撤曲线，正值会压到 0。
- `build_factor_coverage_payload`: 读取 `feature_coverage_report.json`。
- `build_high_confidence_payload`: 读取 OOF 高置信分层报告。
- `build_data_source_status_payload`: 读取 provider 状态文件。

## 空状态规则

- 无真实行情历史：`missing_reason=no_market_history_file`。
- 无成交量/持仓量：`missing_reason=no_volume_or_open_interest`。
- 无收益曲线：`missing_reason=no_equity_curve_file`。
- 无回撤曲线：`missing_reason=no_drawdown_curve_file`。
- UI 必须显示空状态，不显示空白画布。

## 禁止

- 不用收益率字段冒充价格。
- 不把研究回测标成 live active 表现。
- 不用 sample data 填补真实图表。
- 不生成预测或客户交易信号。
