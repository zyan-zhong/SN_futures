from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import urlparse

from ..api.json_utils import sanitize_for_json
from ..runtime import get_user_output_dir, resource_path


DEFAULT_PROFILE: dict[str, Any] = {
    "whitelist_domains": [
        "mining.com",
        "kitco.com",
        "reuters.com",
        "argusmedia.com",
        "fastmarkets.com",
        "lme.com",
        "shfe.com.cn",
        "metalbulletin.com",
        "spglobal.com",
        "smm.cn",
        "mysteel.net",
    ],
    "blacklist_domains": [
        "macworld.com",
        "pypi.org",
        "apple.com",
        "github.com",
        "medium.com",
        "substack.com",
        "espn.com",
        "sports.yahoo.com",
        "variety.com",
        "entertainmentweekly.com",
    ],
    "generic_blacklist_terms": [
        "software",
        "python package",
        "app store",
        "sports",
        "entertainment",
        "tin can",
        "canned food",
        "home decor",
        "audio dac",
    ],
    "legal_note": "Profiles are used only for relevance filtering and source diagnostics.",
}


def _normalise_domain(value: str) -> str:
    text = value.strip().lower()
    if not text:
        return ""
    parsed = urlparse(text if "://" in text else f"https://{text}")
    host = parsed.netloc or parsed.path
    host = host.split("@")[-1].split(":")[0].strip(".")
    if host.startswith("www."):
        host = host[4:]
    return host


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


def load_news_source_profiles() -> dict[str, Any]:
    profile_path = resource_path("config", "news_source_profiles.json")
    payload = _read_json(profile_path)
    if not isinstance(payload, Mapping):
        payload = DEFAULT_PROFILE
    profile = dict(DEFAULT_PROFILE)
    for key in ("whitelist_domains", "blacklist_domains", "generic_blacklist_terms"):
        values = payload.get(key) if isinstance(payload.get(key), list) else profile.get(key, [])
        profile[key] = sorted({_normalise_domain(str(item)) if "domain" in key else str(item).strip().lower() for item in values if str(item).strip()})
    profile["legal_note"] = str(payload.get("legal_note") or profile["legal_note"])
    return profile


def _source_name(source: Any) -> str:
    if isinstance(source, Mapping):
        return str(source.get("name") or "")
    return str(source or "")


def domain_from_article(article: Mapping[str, Any]) -> str:
    url = str(article.get("url") or article.get("canonical_url") or article.get("raw_url") or "")
    domain = _normalise_domain(url)
    if domain:
        return domain
    source = _source_name(article.get("source"))
    source_lower = source.lower().strip()
    if "reuters" in source_lower:
        return "reuters.com"
    if "mining" in source_lower:
        return "mining.com"
    if "kitco" in source_lower:
        return "kitco.com"
    if "lme" in source_lower:
        return "lme.com"
    if "shfe" in source_lower or "上海期货" in source:
        return "shfe.com.cn"
    return _normalise_domain(source_lower)


def _matches_domain(domain: str, candidates: list[str]) -> bool:
    return any(domain == item or domain.endswith(f".{item}") for item in candidates if item)


def score_source_quality(article: Mapping[str, Any]) -> dict[str, Any]:
    profile = load_news_source_profiles()
    domain = domain_from_article(article)
    text = " ".join(
        [
            str(article.get("title") or ""),
            str(article.get("description") or ""),
            str(article.get("content") or ""),
            _source_name(article.get("source")),
            domain,
        ]
    ).lower()
    whitelist = profile["whitelist_domains"]
    blacklist = profile["blacklist_domains"]
    generic_terms = profile["generic_blacklist_terms"]
    whitelisted = _matches_domain(domain, whitelist)
    blacklisted = _matches_domain(domain, blacklist)
    generic_penalty = 0.25 if any(term in text for term in generic_terms) else 0.0
    domain_blacklist_penalty = 0.75 if blacklisted else generic_penalty
    domain_whitelist_score = 0.75 if whitelisted else 0.0
    source_reliability_score = 0.5 + domain_whitelist_score - domain_blacklist_penalty
    source_reliability_score = max(0.0, min(1.0, source_reliability_score))
    if domain_blacklist_penalty >= 0.5:
        label = "blacklisted"
    elif domain_whitelist_score > 0:
        label = "whitelisted"
    else:
        label = "neutral"
    return {
        "source_domain": domain,
        "source_reliability_score": round(source_reliability_score, 4),
        "domain_whitelist_score": round(domain_whitelist_score, 4),
        "domain_blacklist_penalty": round(domain_blacklist_penalty, 4),
        "source_quality_label": label,
    }


def _events_from_report(report: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for key in ("high_relevance_events", "low_relevance_events", "rejected_events"):
        values = report.get(key)
        if isinstance(values, list):
            rows.extend(dict(item) for item in values if isinstance(item, Mapping))
    return rows


def build_source_quality_report() -> dict[str, Any]:
    report_payload = _read_json(_events_dir() / "news_relevance_report.json")
    if not isinstance(report_payload, Mapping):
        return sanitize_for_json(
            {
                "article_count": 0,
                "used_in_model_count": 0,
                "domains": [],
                "source_reliability": {"avg_score": 0.0},
                "message_zh": "暂无新闻源质量报告，请先刷新新闻。",
            }
        )
    events = _events_from_report(report_payload)
    domain_rows: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for event in events:
        domain = str(event.get("source_domain") or domain_from_article(event) or "unknown")
        domain_rows[domain].append(event)
    domains: list[dict[str, Any]] = []
    for domain in sorted(domain_rows):
        rows = domain_rows[domain]
        reliability = [float(row.get("source_reliability_score") or score_source_quality(row).get("source_reliability_score") or 0.0) for row in rows]
        domains.append(
            {
                "domain": domain,
                "article_count": len(rows),
                "used_in_model_count": sum(1 for row in rows if row.get("used_in_model")),
                "avg_source_reliability": round(sum(reliability) / len(reliability) if reliability else 0.0, 4),
            }
        )
    reliability_values = [float(row.get("avg_source_reliability") or 0.0) for row in domains]
    return sanitize_for_json(
        {
            "article_count": len(events),
            "used_in_model_count": sum(1 for row in events if row.get("used_in_model")),
            "domains": domains,
            "source_reliability": {
                "avg_score": round(sum(reliability_values) / len(reliability_values) if reliability_values else 0.0, 4)
            },
            "message_zh": "新闻源质量报告已生成；白名单只提高可信度，不会绕过相关性门槛。",
        }
    )
