# 在线数据源自动扩展策略

本策略说明 SNInsightTerminal 如何在客户不提供 CSV/Excel 的前提下，自动尝试公开在线源、API key 源和可选托管源。系统获取不到数据时只展示真实不可用原因，不伪造库存、仓单、基差、LME 或宏观字段。

## 数据源分层

1. 免费公开 / AKShare 源：用于沪锡主行情、交易所日线和部分期货基础数据探测。函数不存在、字段变动或没有锡相关行时，状态显示 `function_unavailable`、`missing_required_columns` 或 `no_tin_rows`。
2. API key 源：Alpha Vantage 用于 USD/CNY、US10Y 和 copper 宏观代理；NewsAPI 用于事件新闻。Alpha Vantage 不用于沪锡主行情、现货、库存或基差。
3. NewsAPI 事件源：用于海外锡、SHFE tin、LME tin、沪锡、库存、供应和需求相关新闻。key 使用 `X-Api-Key` header，不拼 URL；低相关新闻只展示，不进入事件因子。
4. LME tin 探测层：没有可靠免费结构化源时，状态为 `paid_or_unavailable`。系统不会用铜、铝或新闻文本价格替代 LME tin。
5. 托管数据代理：默认关闭。正式客户可由发行方服务器统一维护第三方数据源和 API key，客户端只配置 license token。

## Registry 合同

`GET /api/terminal/online-data-sources/status` 返回统一 registry：

- `source_id`
- `category`
- `provider`
- `enabled`
- `requires_key`
- `requires_paid_account`
- `client_upload_required=false`
- `priority`
- `ttl_seconds`
- `legal_note`
- `fields_provided`
- `status`
- `last_success_time`
- `next_actions_zh`

所有默认 registry 项必须满足 `client_upload_required=false`。需要客户本地文件的路径不能作为客户主流程。

## API Key 运行期验证

Prompt 53S 后，Alpha Vantage / NewsAPI 通过统一 key resolver 读取：

1. 用户目录 `config/secrets.json`。
2. 环境变量。
3. private bundle seed。
4. 开发 `.env`。

`GET /api/terminal/settings/key-diagnostics` 只返回脱敏 key、来源和验证状态。Alpha Vantage 成功、限流、无效 key 和字段不匹配会分别显示 `success`、`rate_limited`、`key_invalid`、`schema_mismatch`，不再把已配置但限流的状态误显示为 `key_missing`。

## Prompt 52S/53S 因子准备度

`GET /api/terminal/factors/online-readiness` 读取在线 registry、fundamentals 输出和 feature coverage，生成字段级准备度：

- Alpha Vantage key 缺失时，USD/CNY 和 US10Y 显示 `key_missing`。
- Alpha Vantage 已配置但限流时，显示 `rate_limited`。
- LME tin 免费结构化源不可用时，`lme_tin_close` 显示 `paid_or_unavailable`。
- basis/inventory 没有真实沪锡行时，不提升覆盖率。
- `copper_global_proxy` 只作为宏观代理，不冒充 `lme_tin_close`。
- 新闻文本中的价格不进入结构化 LME price 字段。

## 边界

- 不接实盘交易。
- 不生成 active model。
- 不生成客户预测。
- 不使用 baseline。
- 不伪造库存、仓单、基差、LME tin、汇率或宏观数据。
- 获取不到数据时只显示真实原因和下一步建议。
