# 新闻与政策数据源可靠性说明

本文记录 0.3.2-beta.1 前的专项修复：避免 `akshare_news`、`NewsAPI`、`miit_policy`、`shfe_public` 被长期误判为“已过期”。

## NewsAPI 查询策略

- 请求接口：`https://newsapi.org/v2/everything`
- 密钥传递：仅使用 `X-Api-Key` HTTP header，不拼入 URL。
- 默认窗口：最近 7 天。
- 回退窗口：7 天无结果时回退最近 30 天。
- 排序策略：优先 `publishedAt`，无结果时补充 `relevancy`。
- 英文关键词组：
  - `tin OR "SHFE tin" OR "LME tin"`
  - `tin supply OR tin inventory OR tin smelter`
  - `Indonesia tin OR Myanmar tin OR Wa State tin`
  - `semiconductor tin demand OR solder tin`
  - `photovoltaic tin demand OR solar solder`
- 中文关键词组：
  - `锡 期货 OR 沪锡 OR 上期所 锡`
  - `锡 库存 OR 锡 供应 OR 锡 冶炼`
  - `印尼 锡 OR 缅甸 锡 OR 佤邦 锡`
  - `半导体 锡需求 OR 光伏 焊料 锡`

每组查询都会记录 `query / language / from / to / sortBy / status / totalResults / returned_count / error`，用于前端诊断和刷新日志。

## AKShare 新闻源

当前版本未启用可靠的 AKShare 新闻自动源时，前端状态显示为“未启用”，不再显示“已过期”。这表示该源不是当前生产链路的一部分，不会影响 NewsAPI 的刷新结果。

## 工信部政策源

政策源不是实时行情源，不能使用 15 分钟或 24 小时行情 TTL。

- 7 天内成功：正常。
- 7 到 30 天：较旧但可参考。
- 超过 30 天：已过期。
- 请求失败但有缓存：使用缓存。
- 当前版本未启用自动抓取：未启用。

## SHFE 公共数据源

SHFE 公共数据主要对应日线、库存、仓单、结算等公开数据，不是 tick 级实时行情。

- 默认 TTL：36 小时。
- 周末、节假日或非交易时段：不直接判定失败，显示“非交易时段等待更新”。
- 请求失败但有可用缓存：显示“使用缓存”。
- 无缓存且请求失败：显示“请求失败”，并提供下一步建议。

## 统一状态字段

前端数据源状态页使用以下字段展示：

- `freshness_label`：正常、使用缓存、未配置、已过期、请求失败、未启用、非交易时段等待更新。
- `last_attempt_time`：最近尝试时间。
- `last_success_time`：最近成功时间。
- `ttl_seconds`：当前源 TTL。
- `next_expected_update`：下一次建议更新时间。
- `row_count`：返回条数。
- `error_code`：错误代码。
- `message_zh`：中文说明。
- `next_actions_zh`：下一步建议。

## 合规边界

新闻与政策数据仅用于沪锡期货量化投研参考，不构成投资建议，不承诺收益，不接实盘交易。
