# NewsAPI 新闻相关性门控

## Private bundle refresh validation

`refresh/news` 必须生成以下运行期文件：

- `outputs/events/news_raw.json`
- `outputs/events/news_events_filtered.json`
- `outputs/events/event_factor_inputs.json`
- `outputs/events/news_relevance_report.json`
- `outputs/events/news_provider_status.json`

`event_factor_inputs.json` 只允许包含 `used_in_model=true` 的高相关新闻。Macworld、PyPI、generic software、Apple、sports、entertainment 等低相关新闻可在 UI 中作为“已排除新闻”或折叠区展示，但不能进入事件因子。

本说明对应 Prompt 54S。目标是让 NewsAPI 新闻只作为事件研究输入，不把无关科技、软件、体育或娱乐新闻误送入事件因子。

## Key 与请求方式

- NewsAPI key 通过统一 key resolver 读取。
- 读取优先级：用户目录 `config/secrets.json`、环境变量 `SN_NEWSAPI_KEY`、private bundle seed、开发 `.env`。
- 请求使用 `X-Api-Key` header，不把 key 拼到 URL。
- 诊断、日志、cache 和 API 响应只允许返回脱敏状态。

## 查询策略

默认查询覆盖：

- English core: `("tin" OR "SHFE tin" OR "LME tin" OR "Shanghai tin") AND (price OR futures OR inventory OR supply OR demand)`
- Supply: `(tin AND (Indonesia OR Myanmar OR "Wa State" OR smelter OR mining OR export OR quota))`
- Demand: `(tin AND (semiconductor OR solder OR photovoltaic OR solar OR electronics))`
- Chinese: `("沪锡" OR "锡期货" OR "上期所锡" OR "锡库存" OR "锡供应" OR "锡升贴水")`

请求参数：

- endpoint: `/v2/everything`
- `searchIn=title,description`
- `sortBy=publishedAt`，无结果时回退 `relevancy`
- 默认最近 7 天，无结果时回退最近 30 天
- `pageSize <= 100`

每组 query 记录 `totalResults`、`returned_count`、`error` 和 sanitized request params。

## 相关性评分

每条新闻计算：

- `tin_entity_score`
- `shfe_lme_score`
- `supply_chain_score`
- `demand_chain_score`
- `inventory_score`
- `macro_score`
- `negative_keyword_penalty`
- `relevance_score`
- `category`
- `sentiment_score`
- `impact_score`
- `used_in_model`
- `exclusion_reason`

门控规则：

- `relevance_score >= 0.60` 且 `category != irrelevant` 才允许 `used_in_model=true`。
- `0.25 <= relevance_score < 0.60` 仅前端展示，不进入事件因子。
- `relevance_score < 0.25` 默认折叠或排除。
- Macworld、PyPI、generic software、Apple、DAC、sports、entertainment 等不得入模。
- 中文“沪锡 / 锡期货 / 上期所锡 / 锡库存 / 锡供应”会提高相关性。

## 输出文件

刷新和过滤后写入：

- `outputs/events/news_raw.json`
- `outputs/events/news_events.json`
- `outputs/events/news_events_filtered.json`
- `outputs/events/event_factor_inputs.json`
- `outputs/events/news_relevance_report.json`

`event_factor_inputs.json` 只包含 `used_in_model=true` 的新闻。

## 边界

- NewsAPI 不生成预测。
- NewsAPI 不发布 active model。
- 无 key 时不伪造新闻或事件因子。
- 有 key 但无相关新闻时，显示“无高相关新闻”，不是系统错误。
# Prompt 58S Update

The NewsAPI event gate now records query-group diagnostics and keyword evidence for every candidate article.

- High-relevance event factor input requires `used_in_model=true`.
- The threshold is `relevance_score >= 0.55`, plus a positive tin-entity score, non-irrelevant category, low negative-keyword penalty, and keyword evidence.
- Low-relevance articles can be shown in the UI but do not enter `event_factor_inputs.json`.
- Macworld, PyPI, generic software, Apple accessories, sports, entertainment, and generic tin-can/food-packaging articles remain excluded.
- If no high-relevance news passes the gate, the event factor input stays empty and the UI states that the system will not fabricate event factors.
