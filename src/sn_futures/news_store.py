from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urlparse

import pandas as pd

from .event_url_resolver import is_external_open_allowed, resolve_canonical_url
from .runtime import get_user_data_dir


TRUSTED_URL_SCHEMES = {"http", "https"}


def news_db_path() -> Path:
    target = get_user_data_dir() / "data"
    target.mkdir(parents=True, exist_ok=True)
    return target / "news_events.sqlite"


def _connect(path: Path | None = None) -> sqlite3.Connection:
    conn = sqlite3.connect(str(path or news_db_path()))
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS news_events (
            event_id TEXT PRIMARY KEY,
            title TEXT,
            source TEXT,
            canonical_url TEXT,
            published_at TEXT,
            available_at TEXT,
            fetched_at TEXT,
            summary TEXT,
            category TEXT,
            impact_score REAL,
            sentiment_score REAL,
            related_symbols TEXT,
            entity_tags TEXT,
            source_tier TEXT,
            is_authoritative INTEGER,
            url_status TEXT,
            open_mode TEXT,
            content_hash TEXT,
            fetch_batch_id TEXT,
            used_in_model INTEGER,
            created_at TEXT,
            updated_at TEXT
        )
        """
    )
    return conn


def _safe_url(url: str) -> str:
    text = str(url or "").strip()
    parsed = urlparse(text)
    if parsed.scheme.lower() not in TRUSTED_URL_SCHEMES or not parsed.netloc:
        return ""
    return text


def _event_id(title: str, source: str, published_at: str, url: str) -> str:
    domain = urlparse(url).netloc.lower()
    bucket = str(published_at or "")[:13]
    normalized = " ".join(str(title or "").lower().split())
    return hashlib.sha256(f"{normalized}|{source}|{bucket}|{domain}".encode("utf-8")).hexdigest()[:24]


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


def normalize_article(article: dict[str, Any], *, fetch_batch_id: str = "") -> dict[str, Any] | None:
    title = str(article.get("title") or article.get("summary") or "").strip()
    if not title:
        return None
    source_obj = article.get("source")
    source = str(source_obj.get("name") if isinstance(source_obj, dict) else source_obj or article.get("provider") or "公开来源")
    raw_url = str(article.get("url") or article.get("source_url") or article.get("canonical_url") or "")
    resolved = resolve_canonical_url(raw_url, network=False)
    url = resolved.canonical_url or _safe_url(raw_url)
    published_at = str(article.get("publishedAt") or article.get("published_at") or article.get("time_published") or "")
    now = pd.Timestamp.now(tz="Asia/Hong_Kong").isoformat()
    summary = str(article.get("summary") or article.get("description") or article.get("content") or title)[:1000]
    content_hash = hashlib.sha256(f"{title}|{summary}|{url}".encode("utf-8")).hexdigest()
    return {
        "event_id": _event_id(title, source, published_at, url),
        "title": title[:240],
        "source": source,
        "canonical_url": url,
        "published_at": published_at,
        "available_at": str(article.get("available_at") or now),
        "fetched_at": now,
        "summary": summary,
        "category": str(article.get("category") or article.get("event_type") or ""),
        "impact_score": _safe_float(article.get("impact_score"), 0.0),
        "sentiment_score": _safe_float(article.get("sentiment_score", article.get("sentiment")), 0.0),
        "related_symbols": json.dumps(article.get("related_symbols") or ["SN", "沪锡", "锡"], ensure_ascii=False),
        "entity_tags": json.dumps(article.get("entity_tags") or article.get("extracted_entities") or [], ensure_ascii=False),
        "source_tier": str(article.get("source_tier") or article.get("provider") or ""),
        "is_authoritative": 1 if str(article.get("provider") or source).lower().startswith("shfe") else 0,
        "url_status": resolved.url_status if url else "missing",
        "open_mode": "external_browser" if url and is_external_open_allowed(url) else "unavailable",
        "content_hash": content_hash,
        "fetch_batch_id": fetch_batch_id,
        "used_in_model": 1 if article.get("used_in_model") or article.get("enters_model") else 0,
        "created_at": now,
        "updated_at": now,
    }


def upsert_articles(articles: Iterable[dict[str, Any]], *, fetch_batch_id: str = "") -> int:
    rows = [row for article in articles if isinstance(article, dict) and (row := normalize_article(article, fetch_batch_id=fetch_batch_id))]
    if not rows:
        return 0
    conn = _connect()
    try:
        with conn:
            for row in rows:
                conn.execute(
                    """
                    INSERT INTO news_events (
                        event_id,title,source,canonical_url,published_at,available_at,fetched_at,summary,category,
                        impact_score,sentiment_score,related_symbols,entity_tags,source_tier,is_authoritative,url_status,
                        open_mode,content_hash,fetch_batch_id,used_in_model,created_at,updated_at
                    ) VALUES (
                        :event_id,:title,:source,:canonical_url,:published_at,:available_at,:fetched_at,:summary,:category,
                        :impact_score,:sentiment_score,:related_symbols,:entity_tags,:source_tier,:is_authoritative,:url_status,
                        :open_mode,:content_hash,:fetch_batch_id,:used_in_model,:created_at,:updated_at
                    )
                    ON CONFLICT(event_id) DO UPDATE SET
                        fetched_at=excluded.fetched_at,
                        summary=excluded.summary,
                        impact_score=max(news_events.impact_score, excluded.impact_score),
                        sentiment_score=excluded.sentiment_score,
                        url_status=excluded.url_status,
                        canonical_url=COALESCE(NULLIF(excluded.canonical_url,''), news_events.canonical_url),
                        open_mode=excluded.open_mode,
                        updated_at=excluded.updated_at
                    """,
                    row,
                )
    finally:
        conn.close()
    return len(rows)


def load_recent_articles(limit: int = 100, *, min_impact_score: float = 0.0, category: str = "") -> list[dict[str, Any]]:
    conn = _connect()
    try:
        query = "SELECT * FROM news_events WHERE impact_score >= ?"
        params: list[Any] = [float(min_impact_score)]
        if category:
            query += " AND category LIKE ?"
            params.append(f"%{category}%")
        query += " ORDER BY COALESCE(published_at, fetched_at) DESC, impact_score DESC LIMIT ?"
        params.append(int(limit))
        conn.row_factory = sqlite3.Row
        rows = conn.execute(query, params).fetchall()
    finally:
        conn.close()
    articles: list[dict[str, Any]] = []
    for row in rows:
        item = dict(row)
        articles.append(
            {
                "title": item.get("title", ""),
                "summary": item.get("summary", ""),
                "content": item.get("summary", ""),
                "url": item.get("canonical_url", ""),
                "publishedAt": item.get("published_at", ""),
                "published_at": item.get("published_at", ""),
                "available_at": item.get("available_at", ""),
                "source": {"name": item.get("source", "")},
                "provider": item.get("source_tier") or item.get("source", ""),
                "impact_score": item.get("impact_score", 0.0),
                "sentiment_score": item.get("sentiment_score", 0.0),
                "event_id": item.get("event_id", ""),
                "canonical_url": item.get("canonical_url", ""),
                "source_tier": item.get("source_tier", ""),
            }
        )
    return articles


def resolve_event_url(event_id: str) -> dict[str, Any]:
    conn = _connect()
    try:
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT event_id,title,canonical_url,url_status FROM news_events WHERE event_id=?", (event_id,)).fetchone()
    finally:
        conn.close()
    if not row:
        return {"ok": False, "event_id": event_id, "reason": "event_not_found", "blocked_reason": "event_not_found"}
    url = _safe_url(str(row["canonical_url"] or ""))
    if not url:
        return {"ok": False, "event_id": event_id, "reason": "url_missing", "blocked_reason": "url_missing", "final_open_url": ""}
    if not is_external_open_allowed(url):
        return {
            "ok": False,
            "event_id": event_id,
            "title": row["title"],
            "canonical_url": url,
            "final_open_url": "",
            "url_status": "blocked",
            "reason": "unsafe_or_private_url",
            "blocked_reason": "unsafe_or_private_url",
        }
    return {
        "ok": True,
        "event_id": event_id,
        "title": row["title"],
        "url": url,
        "canonical_url": url,
        "final_open_url": url,
        "url_status": row["url_status"] or "ok",
        "blocked_reason": "",
        "open_mode": "external_browser",
    }
