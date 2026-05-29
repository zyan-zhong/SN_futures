from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Any, Mapping

from ..api.json_utils import sanitize_for_json
from ..runtime import get_user_output_dir


def _events_dir() -> Path:
    path = get_user_output_dir() / "events"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _read_json(path: Path) -> Any:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _source_name(source: Any) -> str:
    if isinstance(source, Mapping):
        return str(source.get("name") or "")
    return str(source or "")


def _events_from_payload(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, Mapping) and isinstance(payload.get("events"), list):
        return [dict(item) for item in payload["events"] if isinstance(item, Mapping)]
    if isinstance(payload, list):
        return [dict(item) for item in payload if isinstance(item, Mapping)]
    return []


def _query_group_summary(articles: list[Mapping[str, Any]], attempts: list[Mapping[str, Any]]) -> dict[str, dict[str, Any]]:
    grouped: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for article in articles:
        grouped[str(article.get("query_group") or "unknown")].append(article)
    attempt_grouped: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for attempt in attempts:
        attempt_grouped[str(attempt.get("query_group") or "unknown")].append(attempt)
    summary: dict[str, dict[str, Any]] = {}
    for group in sorted(attempt_grouped):
        rows = attempt_grouped[group]
        summary[group] = {
            "attempt_count": len(rows),
            "returned_count": sum(int(row.get("returned_count") or row.get("returnedCount") or 0) for row in rows),
            "used_in_model_count": 0,
            "avg_relevance": 0.0,
            "statuses": sorted({str(row.get("status") or "unknown") for row in rows}),
        }
    for group in sorted(grouped):
        rows = grouped[group]
        relevance = [float(row.get("relevance_score") or 0.0) for row in rows]
        current = summary.setdefault(group, {"attempt_count": 0, "returned_count": len(rows), "statuses": []})
        current["candidate_count"] = len(rows)
        current["used_in_model_count"] = sum(1 for row in rows if row.get("used_in_model"))
        current["avg_relevance"] = round(sum(relevance) / len(relevance) if relevance else 0.0, 4)
    return summary


def build_news_relevance_diagnostics() -> dict[str, Any]:
    events_dir = _events_dir()
    raw_payload = _read_json(events_dir / "news_raw.json")
    events_payload = _read_json(events_dir / "news_events.json")
    report_payload = _read_json(events_dir / "news_relevance_report.json")

    raw_articles = []
    query_attempts: list[Mapping[str, Any]] = []
    if isinstance(raw_payload, Mapping):
        raw_articles = [item for item in raw_payload.get("articles", []) if isinstance(item, Mapping)]
        query_attempts = [item for item in raw_payload.get("query_attempts", []) if isinstance(item, Mapping)]
    elif isinstance(raw_payload, list):
        raw_articles = [item for item in raw_payload if isinstance(item, Mapping)]

    scored_events = _events_from_payload(events_payload)
    if not scored_events and isinstance(report_payload, Mapping):
        scored_events = [
            *[dict(item) for item in report_payload.get("high_relevance_events", []) if isinstance(item, Mapping)],
            *[dict(item) for item in report_payload.get("low_relevance_events", []) if isinstance(item, Mapping)],
            *[dict(item) for item in report_payload.get("rejected_events", []) if isinstance(item, Mapping)],
        ]

    articles: list[dict[str, Any]] = []
    for item in scored_events:
        articles.append(
            {
                "title": str(item.get("title") or ""),
                "source": _source_name(item.get("source")),
                "query_group": str(item.get("query_group") or "unknown"),
                "relevance_score": float(item.get("relevance_score") or 0.0),
                "tin_entity_score": float(item.get("tin_entity_score") or 0.0),
                "hard_evidence_score": float(item.get("hard_evidence_score") or 0.0),
                "source_reliability_score": float(item.get("source_reliability_score") or 0.0),
                "source_domain": str(item.get("source_domain") or ""),
                "category": str(item.get("category") or "irrelevant"),
                "used_in_model": bool(item.get("used_in_model")),
                "inclusion_reason": str(item.get("inclusion_reason") or ""),
                "exclusion_reason": str(item.get("exclusion_reason") or ""),
                "keyword_hits": item.get("keyword_hits") if isinstance(item.get("keyword_hits"), list) else [],
                "negative_keyword_hits": item.get("negative_keyword_hits")
                if isinstance(item.get("negative_keyword_hits"), list)
                else [],
            }
        )

    used_count = sum(1 for item in scored_events if item.get("used_in_model"))
    excluded_count = len(scored_events) - used_count
    query_groups = _query_group_summary(scored_events, query_attempts)
    recommendations = []
    if not scored_events:
        recommendations.append("当前没有可诊断新闻，请先运行刷新新闻。")
    elif used_count == 0:
        recommendations.append("当前候选新闻均未达到锡产业相关性门槛，系统不会伪造事件因子。")
        recommendations.append("优先检查 query_group 的 returned_count，并扩大锡供应、交易所和中文沪锡查询窗口。")
    else:
        recommendations.append("仅 used_in_model=true 的新闻进入事件因子；继续观察被排除新闻是否存在误杀。")

    return sanitize_for_json(
        {
            "raw_article_count": len(raw_articles),
            "candidate_count": len(scored_events),
            "used_in_model_count": used_count,
            "excluded_count": excluded_count,
            "articles": articles,
            "query_groups": query_groups,
            "recommendations_zh": recommendations,
            "message_zh": "新闻相关性诊断已生成。",
        }
    )
