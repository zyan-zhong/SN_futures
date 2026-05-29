# News Source Quality Profile

本轮新增 `config/news_source_profiles.json`，用于把 NewsAPI 返回的候选新闻按来源质量做诊断。白名单只提高可信度，不会绕过沪锡相关性门槛；黑名单会阻止 Macworld、PyPI、Apple、泛软件、体育和娱乐类新闻进入事件因子。

白名单示例：
- `mining.com`
- `kitco.com`
- `reuters.com`
- `argusmedia.com`
- `fastmarkets.com`
- `lme.com`
- `shfe.com.cn`

黑名单示例：
- `macworld.com`
- `pypi.org`
- `apple.com`
- 泛软件、体育、娱乐、食品罐头、家居装饰类域名或关键词

输出与 API：
- `GET /api/terminal/events/source-quality-report`
- `outputs/events/news_source_quality_report.json`
- 前端“行情与新闻”页显示 source reliability 和 hard evidence 诊断。

边界：
- 不爬付费墙。
- 如果 NewsAPI 只返回标题和摘要，只使用标题和摘要。
- source quality 不能替代 `relevance_score >= 0.60`、`hard_evidence_score >= 0.30` 和锡产业关键词证据。
