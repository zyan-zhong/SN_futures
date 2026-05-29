# Event Factor Inputs

`outputs/events/event_factor_inputs.json` 只允许聚合 `used_in_model=true` 的新闻。仅展示新闻和已排除新闻可以出现在 UI 中，但不能进入事件因子。

每个交易日聚合字段：
- `news_count`
- `used_in_model_count`
- `supply_shock_score`
- `demand_shock_score`
- `inventory_shock_score`
- `exchange_event_score`
- `macro_risk_score`
- `source_reliability_weighted_score`
- `max_relevance_score`
- `avg_relevance_score`
- `event_recency_decay_score`

如果没有入模新闻：
- `inputs=[]`
- `message_zh="无通过相关性门槛的沪锡新闻，系统未构造事件因子。"`
- 不填假值，不生成客户预测，不训练模型。

入模条件：
- `relevance_score >= 0.60`
- `hard_evidence_score >= 0.30`
- `commodity_entity_score > 0`
- `category != irrelevant`
- `domain_blacklist_penalty < 0.5`
- `negative_keyword_penalty < 0.4`
- 必须有 `keyword_hits`
