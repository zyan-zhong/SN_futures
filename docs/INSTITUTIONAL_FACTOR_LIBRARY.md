# 沪锡机构级因子库

本轮补齐的是底层数据接入、标准化和覆盖率审计能力，不训练 active model，不生成客户预测，不降低 promotion gate。

## 因子分组

- `term_structure`：近月/远月合约、主力/次主力、持仓和换月结构。
- `basis`：现货锡价格、现货升贴水、现货-期货基差、基差分位。
- `inventory`：SHFE 库存、SHFE 注册仓单、LME 锡库存、全球显性库存。
- `cross_market`：LME 锡、USD/CNY、DXY、US10Y、内外盘价差。
- `event`：经过新闻相关性 gate 的供应、需求、库存、宏观事件。

## 真实数据原则

- 不使用 SN0 同时冒充 near/far。
- 不用样例数据进入真实因子覆盖率。
- 缺少真实现货、库存、外盘时，因子显示不可用，而不是用常数或随机值补齐。
- 低相关新闻可以在 UI 浏览，但 `used_in_model=false` 的新闻不会进入事件因子。

## 当前输出

- `outputs/fundamentals/sn_contract_curve.json`
- `outputs/fundamentals/sn_term_structure.json`
- `outputs/fundamentals/sn_spot_basis.json`
- `outputs/fundamentals/sn_inventory.json`
- `outputs/fundamentals/sn_warehouse_receipts.json`
- `outputs/fundamentals/sn_cross_market.json`
- `outputs/events/news_events_relevance.json`

## 覆盖率变化

当真实底层文件存在时，`/api/terminal/factors/coverage` 会合并这些字段，再运行 `features_core.build_feature_matrix()`。覆盖率提升只来自真实字段非空率，不通过调参或伪造字段实现。

