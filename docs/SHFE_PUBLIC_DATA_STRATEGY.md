# SHFE Public Data Strategy

本轮目标是把笼统的“SHFE public 不可用”拆成可诊断的真实辅助源状态，补齐沪锡机构级因子所需的库存、仓单、现货基差、交易所日线和会员持仓数据。该流程只采集真实公开数据，不训练模型，不发布 active，不生成客户预测，不使用 baseline。

## 数据源拆分

- SHFE 官网直连：只做可访问性探测。如果返回人机验证、WAF 或非数据页面，状态为 `blocked_by_waf`。这不是主行情失败，不影响 Sina/AKShare 行情链路。
- AKShare SHFE 库存：尝试 `futures_inventory_99`、`futures_inventory_em`，只保留锡/SN 行。
- AKShare 仓单：尝试 `futures_warehouse_receipt`、`futures_inventory_99`，只保留锡/SN 行。
- 现货基差：尝试 `futures_spot_price`、`futures_delivery_match`，缺真实现货价时不计算基差。
- 交易所日线/持仓：尝试 `futures_zh_daily_sina`、`futures_zh_daily`、`futures_hist_table_em`，用于补齐成交量、持仓量和结算价。
- 会员持仓排名：尝试 `futures_member_position_rank`，可用时写入真实会员持仓辅助文件。

## 状态语义

- `blocked_by_waf`：SHFE 官网直连被人机验证阻断，系统已尝试 AKShare/缓存辅助源。
- `function_unavailable`：当前 AKShare 版本没有该函数。
- `no_tin_rows`：函数返回数据，但没有锡/SN 相关行。
- `missing_required_columns`：有锡行，但缺少标准化所需字段。
- `request_failed`：请求或解析失败。
- `正常`：写入了真实锡相关数据。

## 输出文件

- `outputs/fundamentals/shfe_public_provider_status.json`
- `outputs/fundamentals/sn_shfe_inventory.json`
- `outputs/fundamentals/sn_shfe_warehouse_receipts.json`
- `outputs/fundamentals/sn_spot_basis.json`
- `outputs/fundamentals/sn_exchange_daily.json`
- `outputs/fundamentals/sn_member_positions.json`

## 约束

- 不用其它品种冒充锡。
- 不用 `SN0` 同时冒充近月和远月。
- 不生成库存、仓单、基差的虚假数值。
- 不生成 active、不生成客户预测、不使用 baseline。
