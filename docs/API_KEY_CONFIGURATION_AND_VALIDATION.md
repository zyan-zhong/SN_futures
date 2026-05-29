# API Key 配置与运行期验证

## Prompt 55A-private live smoke

私有发行版内置 key 导入后，应额外验证：

- Alpha Vantage：`POST /api/terminal/refresh/cross-market` 能读取发行方默认 key；成功时 `sn_cross_market.json` 包含 `usd_cny`、`usd_cny_return`、`us10y`、`us10y_change`，可选包含 `copper_global_proxy`。Copper 只能作为宏观代理，不能冒充 `lme_tin_close`。
- NewsAPI：`POST /api/terminal/newsapi/test` 与 `POST /api/terminal/refresh/news` 不应返回 `key_missing`；请求使用 `X-Api-Key` header，`request_params_sanitized` 不含 key。
- `GET /api/terminal/events/relevance-report` 用于确认入模新闻、仅展示新闻和已排除新闻数量。
- `GET /api/terminal/factors/online-readiness` 用于确认 cross-market 字段是否真正进入在线因子准备度。

所有 API 响应、缓存、日志和诊断包只能包含脱敏状态。

本说明对应 Prompt 53S。目标是让 Alpha Vantage、NewsAPI 和托管数据服务的 key 在运行期被统一读取、脱敏展示和安全验证，避免终端误显示 `key_missing`。

## 读取优先级

运行期 key resolver 按以下顺序读取：

1. 用户目录 `config/secrets.json`，包括首次启动从私有发行版 seed 导入的默认 key。
2. 环境变量：`SN_ALPHA_VANTAGE_KEY`、`SN_NEWSAPI_KEY`、`SN_MANAGED_DATA_PROXY_TOKEN`。
3. 开发环境 `.env`。

private bundle seed 只作为首次启动导入来源，不作为 provider 每次请求时的直接读取来源。用户手动保存的 key 优先于发行方默认 key。

占位值和掩码值，例如 `***`、`****`、`your_alpha_vantage_api_key_here`，会被视为未配置，避免误判为可用 key。

## Settings API

相关接口：

- `GET /api/terminal/settings/status`
- `GET /api/terminal/settings/key-diagnostics`
- `POST /api/terminal/settings/secrets`
- `POST /api/terminal/settings/reset`

`settings/status` 和 `key-diagnostics` 只返回 `configured`、`source`、`masked`、验证状态和中文说明，不返回完整 key。`settings/secrets` 只写入本机用户目录，不写入前端、不写入 Git、不写入安装目录。

私有发行版可能显示 `source=private_bundle`，含义是 key 已由发行版预配置并导入本机用户目录。设置页仍可替换为用户自定义 key，也可 reset 后恢复发行方默认 key。

## Alpha Vantage 验证

Alpha Vantage 只用于在线 cross-market 数据：

- `CURRENCY_EXCHANGE_RATE`：USD/CNY 即时汇率。
- `FX_DAILY`：USD/CNY 日线。
- `TREASURY_YIELD`：10 年期美债收益率。
- `COPPER`：可选宏观代理，字段名为 `copper_global_proxy`。

Alpha Vantage 不用于沪锡主行情、现货、基差、库存或 LME tin。返回 `Note`、`Information` 或限流提示时，状态记为 `rate_limited`；无效 key 记为 `key_invalid`；字段不匹配记为 `schema_mismatch`。

## NewsAPI 验证

NewsAPI 使用 `/v2/everything`，key 通过 `X-Api-Key` header 发送，不拼到 URL，也不写入日志。验证查询使用低成本锡相关 query：

`("tin" OR "SHFE tin" OR "LME tin" OR "Shanghai tin") AND (futures OR inventory OR supply OR demand)`

请求使用 `searchIn=title,description`、`sortBy=publishedAt`、`pageSize=10`，默认最近 7 天；如果 0 结果，刷新链路会回退最近 30 天。返回：

- `configured`
- `success`
- `returned_count`
- `rate_limited`
- `key_invalid`
- `last_success_time`
- `request_params_sanitized`

NewsAPI 成功但没有高相关新闻时，不会伪造事件因子；前端显示“没有符合沪锡相关性门槛的新闻”。

## 安全边界

- 不把完整 key 返回给 API 调用方。
- 不把完整 key 写入前端、localStorage、URL、日志或 release 包。
- 不把 `.env`、`secrets.json`、`packaging/private_release_keys.json` 或真实 token 提交到 Git。
- 诊断导出只允许脱敏状态。
- 公开 GitHub release 不应包含 private bundle seed；私有/offline release 可以内置发行方默认 key，但只适合内部交付。

## 当前限制

如果 Alpha Vantage 返回限流，系统会显示 `rate_limited`，不会再误显示 `key_missing`。如果 NewsAPI 未在用户目录或环境变量中配置，仍会显示未配置；用户可在设置页重新保存 key 后验证。
