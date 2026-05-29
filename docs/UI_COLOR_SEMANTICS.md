# UI 颜色语义

本轮将系统健康颜色与行情涨跌颜色进一步分离，避免“正常显示红色、不正常显示绿色”的反向语义。

## 行情颜色

按中国行情习惯：

- 上涨 / 偏多：红色，使用 `price_up`、`market-up`。
- 下跌 / 偏空：绿色，使用 `price_down`、`market-down`。
- 横盘 / 持平：灰色，使用 `market-flat`。

## 系统状态颜色

系统状态不复用行情红绿：

- 正常 / 可用：蓝色或青色，使用 `system_ok`、`info`、`banner-ok`。
- 使用缓存 / 未配置 / 等待交易时段：黄色或橙色，使用 `warning`、`banner-warning`。
- 请求失败 / 数据不足 / 已过期：红色警示，使用 `error`、`banner-error`。
- 样例模式：紫色或黄色提示，必须标注“样例”。

## 组件约定

- `StatusPill` 只表达系统状态，不表达行情涨跌。
- `TopStatusBar` 的价格涨跌使用 `market-up` / `market-down` / `market-flat`。
- `SystemStatusBanner` 使用 `banner-ok` / `banner-warning` / `banner-error`。
- 数据质量优秀使用蓝/青；需谨慎使用黄；数据不足使用橙/红警示。

## 禁止混用

- 系统正常不得使用行情上涨红色。
- 系统异常不得使用行情下跌绿色。
- 数据不足不得显示为绿色正常。
- 涨跌颜色必须同时配中文标签，不能只靠颜色表达。
