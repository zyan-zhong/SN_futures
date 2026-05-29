# News Relevance Diagnostics

Prompt 58S fixes the case where NewsAPI refresh succeeds but all articles are excluded from event-factor inputs.

## What Changed

- NewsAPI now uses profile-based queries: core English, Asia supply, exchange, demand, and Chinese tin-market queries.
- The first pass checks a narrow 7-day window; if it finds no candidates, the provider falls back to a 30-day window.
- Each article keeps its `query_group`, keyword evidence, negative keyword hits, relevance score, category, and exclusion reason.
- `event_factor_inputs.json` is built only from `used_in_model=true` articles.
- If no article passes the gate, the event-factor input stays empty with a clear Chinese message. No fake event score is created.

## Diagnostics API

- `GET /api/terminal/events/relevance-diagnostics`
- `GET /api/terminal/events/relevance-report`
- `GET /api/terminal/events/news`

The diagnostics payload reports raw count, candidate count, used-in-model count, excluded count, per-article evidence, and per-query-group performance.

## Gate Rules

- `relevance_score >= 0.55`
- `tin_entity_score > 0`
- `category != irrelevant`
- `negative_keyword_penalty < 0.4`
- Each model event must have keyword evidence.

The lower threshold is only to reduce false negatives for real tin news. It does not allow Macworld, PyPI, generic software, Apple accessory, sports, entertainment, or tin-can/food-packaging articles into event factors.

## No-Fake Policy

If NewsAPI returns no high-relevance tin industry news, the system writes:

`本周期无通过相关性门槛的锡产业新闻。`

The event input remains empty and downstream feature coverage should report that no real event increment is available.
