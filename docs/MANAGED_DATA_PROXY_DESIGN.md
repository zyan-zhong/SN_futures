# 托管数据代理设计

托管数据代理是面向正式客户的免配置数据补齐方案。客户不需要上传 CSV/Excel，也不需要自己维护第三方 API key。客户端默认关闭该能力，只保留接口、配置入口和状态展示。

## 目标

发行方服务器统一维护数据源账号、API key、清洗逻辑和字段映射，客户端通过 license token 获取标准化后的沪锡基本面数据。

规划接口：

- `GET /api/sn/fundamentals/latest`
- `GET /api/sn/fundamentals/history`

可补齐字段：

- `spot_price`
- `spot_premium`
- `spot_futures_basis`
- `shfe_inventory`
- `shfe_warehouse_receipt`
- `lme_tin_close`
- `lme_inventory`
- `global_visible_inventory`

## 客户端状态

当前客户端实现接口状态和配置入口，不要求真实服务器上线：

- `disabled`：默认关闭。
- `token_missing`：已启用但未配置 license token。
- `unavailable`：已配置 token，但服务暂不可用或尚未上线。
- `success`：未来真实服务器返回标准化数据后使用。

## 安全边界

- 第三方 API key 只应保存在发行方服务器。
- 客户端只保存 license token，且只写入本机用户目录。
- 公开安装包不得包含真实 token、`.env`、secrets 或运行期数据库。
- 托管数据代理不生成预测，不发布 active model。

## 与 Prompt 53S 的关系

运行期 key diagnostics 会把 managed proxy 作为独立来源展示，只返回是否已配置、来源和脱敏状态，不返回完整 token。托管代理默认 `disabled`，不会影响客户开箱运行，也不会要求客户上传 CSV/Excel。

## 推荐上线方式

正式客户免配置版本建议由发行方部署托管数据服务，统一补齐公开在线源难以稳定获得的 basis、inventory、warehouse receipt 和 LME tin 数据。私有测试包可以预配置 license token，但不得提交到 GitHub，也不得写入公开 release 包。

## 与私有发行版内置 Provider Key 的关系

私有/offline release 可以临时内置发行方默认 Alpha Vantage / NewsAPI key，用于安装即用和在线刷新验证。该方案无法防止高级用户逆向提取安装包内部资源，因此只适合内部测试或小范围私有交付。

托管数据代理仍是长期推荐方案：客户端只保存 license token，第三方 API key、数据清洗、字段补齐和供应商账号都由发行方服务器维护，客户不需要 CSV/Excel，也不需要自己配置第三方 key。
