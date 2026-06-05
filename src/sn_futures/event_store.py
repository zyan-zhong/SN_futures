from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any, Iterable

import pandas as pd

from .event_taxonomy import build_event_from_article, safe_url
from .event_url_resolver import is_external_open_allowed
from .runtime import get_user_data_dir


EVENT_COLUMNS = (
    "event_id", "title", "summary", "raw_text", "source", "source_tier", "provider", "raw_url", "canonical_url",
    "url_status", "url_sanitized", "region", "language", "published_at", "source_published_at", "fetched_at",
    "available_at", "event_time_confidence", "updated_at", "category", "event_type",
    "entity_tags", "symbol_tags", "commodity_tags", "horizon_tags", "direction_bias", "direction_confidence",
    "impact_score", "sentiment_score", "supply_score", "demand_score", "inventory_score", "policy_score",
    "macro_score", "volatility_score", "risk_score", "time_decay_weight", "source_confidence",
    "source_reliability_score", "final_event_weight", "used_in_model", "rejected_reason", "feature_window",
    "content_hash", "dedupe_key", "batch_id", "relevance_score", "event_group_id",
)


def event_db_path() -> Path:
    target = get_user_data_dir() / "data"
    target.mkdir(parents=True, exist_ok=True)
    return target / "event_store.sqlite"


def _connect(path: Path | None = None) -> sqlite3.Connection:
    conn = sqlite3.connect(str(path or event_db_path()))
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS event_store (
            event_id TEXT PRIMARY KEY,
            title TEXT,
            summary TEXT,
            raw_text TEXT,
            source TEXT,
            source_tier TEXT,
            provider TEXT,
            raw_url TEXT,
            canonical_url TEXT,
            url_status TEXT,
            url_sanitized TEXT,
            region TEXT,
            language TEXT,
            published_at TEXT,
            source_published_at TEXT,
            fetched_at TEXT,
            available_at TEXT,
            event_time_confidence REAL,
            updated_at TEXT,
            category TEXT,
            event_type TEXT,
            entity_tags TEXT,
            symbol_tags TEXT,
            commodity_tags TEXT,
            horizon_tags TEXT,
            direction_bias TEXT,
            direction_confidence REAL,
            impact_score REAL,
            sentiment_score REAL,
            supply_score REAL,
            demand_score REAL,
            inventory_score REAL,
            policy_score REAL,
            macro_score REAL,
            volatility_score REAL,
            risk_score REAL,
            time_decay_weight REAL,
            source_confidence REAL,
            source_reliability_score REAL,
            final_event_weight REAL,
            used_in_model INTEGER,
            rejected_reason TEXT,
            feature_window TEXT,
            content_hash TEXT,
            dedupe_key TEXT,
            batch_id TEXT,
            relevance_score REAL,
            event_group_id TEXT
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS event_provider_status (
            provider TEXT PRIMARY KEY,
            source_tier TEXT,
            last_success_time TEXT,
            last_error TEXT,
            fetched_count INTEGER,
            inserted_count INTEGER,
            updated_count INTEGER,
            rejected_count INTEGER,
            latency_ms REAL,
            updated_at TEXT
        )
        """
    )
    existing = {row[1] for row in conn.execute("PRAGMA table_info(event_store)").fetchall()}
    for col, ddl in {
        "raw_url": "TEXT",
        "event_group_id": "TEXT",
        "url_sanitized": "TEXT",
        "region": "TEXT",
        "language": "TEXT",
        "source_published_at": "TEXT",
        "event_time_confidence": "REAL",
        "source_reliability_score": "REAL",
    }.items():
        if col not in existing:
            conn.execute(f"ALTER TABLE event_store ADD COLUMN {col} {ddl}")
    return conn


def _json(value: Any) -> str:
    return json.dumps(value if value is not None else [], ensure_ascii=False, default=str)


def _row_for_db(event: dict[str, Any]) -> dict[str, Any]:
    row = {col: event.get(col) for col in EVENT_COLUMNS}
    for key in ("entity_tags", "symbol_tags", "commodity_tags", "horizon_tags"):
        row[key] = _json(row.get(key))
    raw_url = str(row.get("raw_url") or row.get("canonical_url") or "")
    canonical_url = safe_url(str(row.get("canonical_url") or raw_url))
    row["raw_url"] = raw_url
    row["canonical_url"] = canonical_url
    row["url_sanitized"] = str(row.get("url_sanitized") or canonical_url or raw_url)
    row["source_published_at"] = str(row.get("source_published_at") or row.get("published_at") or "")
    row["event_time_confidence"] = float(row.get("event_time_confidence") or 0.0)
    row["source_reliability_score"] = float(row.get("source_reliability_score") or row.get("source_confidence") or 0.0)
    if canonical_url and not row.get("url_status"):
        row["url_status"] = "ok"
    row["used_in_model"] = 1 if bool(row.get("used_in_model")) else 0
    return row


def upsert_events(events: Iterable[dict[str, Any]]) -> int:
    rows = [_row_for_db(event) for event in events if isinstance(event, dict) and event.get("event_id")]
    if not rows:
        return 0
    cols = ",".join(EVENT_COLUMNS)
    placeholders = ",".join(f":{col}" for col in EVENT_COLUMNS)
    update_cols = ",".join(
        f"{col}=excluded.{col}" for col in EVENT_COLUMNS if col not in {"event_id", "used_in_model", "rejected_reason", "feature_window"}
    )
    conn = _connect()
    try:
        with conn:
            for row in rows:
                conn.execute(
                    f"""
                    INSERT INTO event_store ({cols}) VALUES ({placeholders})
                    ON CONFLICT(event_id) DO UPDATE SET
                        {update_cols},
                        used_in_model=max(event_store.used_in_model, excluded.used_in_model),
                        rejected_reason=CASE WHEN excluded.rejected_reason!='' THEN excluded.rejected_reason ELSE event_store.rejected_reason END,
                        feature_window=CASE WHEN excluded.feature_window!='' THEN excluded.feature_window ELSE event_store.feature_window END
                    """,
                    row,
                )
    finally:
        conn.close()
    return len(rows)


def update_provider_status(rows: Iterable[dict[str, Any]]) -> None:
    now = pd.Timestamp.now(tz="Asia/Hong_Kong").isoformat()
    conn = _connect()
    try:
        with conn:
            for row in rows:
                if not isinstance(row, dict):
                    continue
                name = str(row.get("name") or row.get("provider") or "unknown")
                success = bool(row.get("success", row.get("ok", False)))
                conn.execute(
                    """
                    INSERT INTO event_provider_status (
                        provider, source_tier, last_success_time, last_error, fetched_count, inserted_count,
                        updated_count, rejected_count, latency_ms, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(provider) DO UPDATE SET
                        source_tier=excluded.source_tier,
                        last_success_time=CASE WHEN excluded.last_success_time!='' THEN excluded.last_success_time ELSE event_provider_status.last_success_time END,
                        last_error=excluded.last_error,
                        fetched_count=excluded.fetched_count,
                        inserted_count=excluded.inserted_count,
                        updated_count=excluded.updated_count,
                        rejected_count=excluded.rejected_count,
                        latency_ms=excluded.latency_ms,
                        updated_at=excluded.updated_at
                    """,
                    (
                        name,
                        str(row.get("source_tier") or ""),
                        str(row.get("fetched_at") or row.get("updated_at") or now) if success else "",
                        "" if success else str(row.get("message") or row.get("error") or ""),
                        int(row.get("fetched_count", 0) or 0),
                        int(row.get("inserted_count", 0) or 0),
                        int(row.get("updated_count", 0) or 0),
                        int(row.get("rejected_count", 0) or 0),
                        float(row.get("latency_ms", 0.0) or 0.0),
                        now,
                    ),
                )
    finally:
        conn.close()


def ingest_articles(articles: Iterable[dict[str, Any]], *, batch_id: str = "") -> int:
    events = []
    for article in articles:
        if not isinstance(article, dict):
            continue
        event = build_event_from_article(article, batch_id=batch_id)
        if event:
            events.append(event)
    return upsert_events(events)


def load_events(limit: int = 500, *, min_impact_score: float = 0.0, category: str = "") -> list[dict[str, Any]]:
    conn = _connect()
    conn.row_factory = sqlite3.Row
    try:
        query = "SELECT * FROM event_store WHERE impact_score >= ?"
        params: list[Any] = [float(min_impact_score)]
        if category:
            query += " AND category LIKE ?"
            params.append(f"%{category}%")
        query += " ORDER BY COALESCE(available_at, published_at, fetched_at) DESC, final_event_weight DESC LIMIT ?"
        params.append(int(limit))
        rows = [dict(row) for row in conn.execute(query, params).fetchall()]
    finally:
        conn.close()
    for row in rows:
        for key in ("entity_tags", "symbol_tags", "commodity_tags", "horizon_tags"):
            try:
                row[key] = json.loads(row.get(key) or "[]")
            except Exception:
                row[key] = []
        if not row.get("raw_url"):
            row["raw_url"] = row.get("canonical_url", "")
        row["final_open_url"] = row.get("canonical_url") or row.get("raw_url", "")
        row["blocked_reason"] = "" if is_external_open_allowed(row["final_open_url"]) else "unsafe_or_private_url"
    return rows


def load_provider_status() -> list[dict[str, Any]]:
    conn = _connect()
    conn.row_factory = sqlite3.Row
    try:
        rows = [dict(row) for row in conn.execute("SELECT * FROM event_provider_status ORDER BY provider").fetchall()]
    finally:
        conn.close()
    return rows


def mark_event_usage(event_ids: set[str], *, horizon: str, rejected: dict[str, str]) -> None:
    if not event_ids and not rejected:
        return
    conn = _connect()
    try:
        with conn:
            for event_id in event_ids:
                conn.execute(
                    "UPDATE event_store SET used_in_model=1, rejected_reason='', feature_window=? WHERE event_id=?",
                    (horizon, event_id),
                )
            for event_id, reason in rejected.items():
                conn.execute(
                    "UPDATE event_store SET rejected_reason=? WHERE event_id=? AND used_in_model=0",
                    (reason, event_id),
                )
    finally:
        conn.close()


def resolve_event_url(event_id: str) -> dict[str, Any]:
    """Resolve an event URL for external opening through one backend safety gate."""
    conn = _connect()
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute(
            "SELECT event_id,title,raw_url,canonical_url,url_status FROM event_store WHERE event_id=?",
            (event_id,),
        ).fetchone()
    finally:
        conn.close()
    if not row:
        return {"ok": False, "event_id": event_id, "reason": "event_not_found", "blocked_reason": "event_not_found"}
    raw_url = safe_url(str(row["raw_url"] or ""))
    canonical_url = safe_url(str(row["canonical_url"] or ""))
    final_open_url = canonical_url or raw_url
    if not final_open_url:
        return {
            "ok": False,
            "event_id": event_id,
            "reason": "url_missing",
            "blocked_reason": "url_missing",
            "raw_url": raw_url,
            "canonical_url": canonical_url,
            "final_open_url": "",
            "url_status": "missing",
        }
    if not is_external_open_allowed(final_open_url):
        return {
            "ok": False,
            "event_id": event_id,
            "title": row["title"],
            "raw_url": raw_url,
            "canonical_url": canonical_url,
            "final_open_url": "",
            "url_status": "blocked",
            "reason": "unsafe_or_private_url",
            "blocked_reason": "unsafe_or_private_url",
        }
    return {
        "ok": True,
        "event_id": event_id,
        "title": row["title"],
        "raw_url": raw_url,
        "canonical_url": canonical_url or final_open_url,
        "url": final_open_url,
        "final_open_url": final_open_url,
        "url_status": row["url_status"] or "ok",
        "blocked_reason": "",
        "open_mode": "external_browser",
    }
