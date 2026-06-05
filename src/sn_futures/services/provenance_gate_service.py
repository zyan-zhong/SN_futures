from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Mapping
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from ..api.json_utils import sanitize_for_json
from ..runtime import get_user_output_dir


PROVENANCE_SCHEMA_VERSION = "provenance-gate-v1"
MIN_DAILY_ROWS_FOR_RESEARCH = 60
DATA_KINDS = {
    "realtime_quote",
    "daily_bar",
    "inventory",
    "warehouse_receipt",
    "settlement",
    "positions",
    "news",
    "policy",
    "macro",
}
CACHE_STATUSES = {"remote", "cache", "last_good_cache", "missing"}
STALE_STATUSES = {"fresh", "recent", "stale", "missing"}
RESEARCH_PURPOSES = {"feature_store", "training", "prediction", "backtest"}

SENSITIVE_QUERY_NAMES = {
    "apikey",
    "api_key",
    "key",
    "token",
    "access_token",
    "authorization",
    "auth",
    "secret",
}


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        if value is None or value == "":
            return default
        return int(value)
    except Exception:
        return default


def _bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y"}
    return bool(value)


def sanitize_source_url(url: str | None) -> str:
    raw = str(url or "").strip()
    if not raw:
        return ""
    try:
        parts = urlsplit(raw)
        safe_query: list[tuple[str, str]] = []
        for key, value in parse_qsl(parts.query, keep_blank_values=True):
            if key.strip().lower() in SENSITIVE_QUERY_NAMES:
                safe_query.append((key, "***"))
            else:
                safe_query.append((key, value))
        return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(safe_query), ""))
    except Exception:
        return raw.split("?")[0]


def _hash_file(path: str | Path | None) -> str:
    if not path:
        return ""
    try:
        candidate = Path(path)
        if not candidate.exists() or not candidate.is_file():
            return ""
        digest = hashlib.sha256()
        with candidate.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()
    except Exception:
        return ""


def _hash_payload(payload: Mapping[str, Any]) -> str:
    encoded = json.dumps(sanitize_for_json(dict(payload)), ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _normalise_data_kind(value: Any) -> str:
    data_kind = str(value or "daily_bar").strip().lower()
    return data_kind if data_kind in DATA_KINDS else "daily_bar"


def _normalise_cache_status(value: Any) -> str:
    status = str(value or "missing").strip().lower()
    return status if status in CACHE_STATUSES else "missing"


def _normalise_stale_status(value: Any) -> str:
    status = str(value or "missing").strip().lower()
    return status if status in STALE_STATUSES else "missing"


def _append_unique(items: list[str], reason: str) -> None:
    if reason and reason not in items:
        items.append(reason)


def build_watermark_record(
    *,
    symbol: str = "SN",
    exchange: str = "SHFE",
    active_contract: str = "SN",
    data_kind: str,
    provider: str = "",
    source_path: str | Path | None = "",
    source_url: str | None = "",
    source_url_sanitized: str | None = None,
    fetched_at: str = "",
    source_published_at: str = "",
    as_of: str = "",
    trading_date: str = "",
    row_count: int | str = 0,
    schema_version: str = PROVENANCE_SCHEMA_VERSION,
    content_hash: str = "",
    sample_data_used: bool = False,
    baseline_used: bool = False,
    cache_status: str = "missing",
    stale_status: str = "missing",
    blocking_reasons: Iterable[str] | None = None,
) -> dict[str, Any]:
    source_path_str = str(source_path or "")
    data_kind_norm = _normalise_data_kind(data_kind)
    cache_status_norm = _normalise_cache_status(cache_status)
    stale_status_norm = _normalise_stale_status(stale_status)
    rows = max(0, _safe_int(row_count))
    sample = _bool(sample_data_used)
    baseline = _bool(baseline_used)
    reasons = [str(reason) for reason in (blocking_reasons or []) if str(reason)]

    if rows <= 0 or cache_status_norm == "missing" or stale_status_norm == "missing":
        _append_unique(reasons, f"缺少 {data_kind_norm} 数据或 row_count=0")
    if sample:
        _append_unique(reasons, "sample_data_used=true，禁止用于训练、预测和回测")
    if baseline:
        _append_unique(reasons, "baseline_used=true，禁止用于训练、预测和回测")
    if cache_status_norm == "last_good_cache":
        _append_unique(reasons, "cache_status=last_good_cache，仅允许标记为缓存展示")
    if stale_status_norm == "stale":
        _append_unique(reasons, "stale_status=stale，禁止用于预测和回测")
    if data_kind_norm in {"news", "policy"} and rows > 0 and not str(source_published_at or "").strip():
        _append_unique(reasons, "news/policy 缺少 source_published_at，禁止用于高权重事件因子")

    usable_real_data = rows > 0 and not sample and not baseline
    display_allowed = usable_real_data and cache_status_norm != "missing" and stale_status_norm != "missing"
    research_allowed = (
        data_kind_norm == "daily_bar"
        and rows >= MIN_DAILY_ROWS_FOR_RESEARCH
        and usable_real_data
        and cache_status_norm in {"remote", "cache"}
        and stale_status_norm in {"fresh", "recent"}
    )
    high_weight_event_allowed = (
        data_kind_norm in {"news", "policy"} and usable_real_data and bool(str(source_published_at or "").strip())
    )

    record = {
        "symbol": str(symbol or "SN"),
        "exchange": str(exchange or "SHFE"),
        "active_contract": str(active_contract or "SN"),
        "data_kind": data_kind_norm,
        "provider": str(provider or ""),
        "source_path": source_path_str,
        "source_url_sanitized": sanitize_source_url(source_url_sanitized if source_url_sanitized is not None else source_url),
        "fetched_at": str(fetched_at or ""),
        "source_published_at": str(source_published_at or ""),
        "as_of": str(as_of or ""),
        "trading_date": str(trading_date or ""),
        "row_count": rows,
        "schema_version": str(schema_version or PROVENANCE_SCHEMA_VERSION),
        "content_hash": str(content_hash or _hash_file(source_path_str)),
        "sample_data_used": sample,
        "baseline_used": baseline,
        "cache_status": cache_status_norm,
        "stale_status": stale_status_norm,
        "blocking_reasons": reasons,
        "allowed_for_display": bool(display_allowed),
        "allowed_for_feature_store": bool(research_allowed),
        "allowed_for_training": bool(research_allowed),
        "allowed_for_prediction": bool(research_allowed),
        "allowed_for_backtest": bool(research_allowed),
        "allowed_for_high_weight_event_factor": bool(high_weight_event_allowed),
    }
    if not record["content_hash"]:
        record["content_hash"] = _hash_payload({k: v for k, v in record.items() if k != "content_hash"})
    return sanitize_for_json(record)


def normalise_watermark_record(record: Mapping[str, Any]) -> dict[str, Any]:
    return build_watermark_record(
        symbol=str(record.get("symbol") or "SN"),
        exchange=str(record.get("exchange") or "SHFE"),
        active_contract=str(record.get("active_contract") or "SN"),
        data_kind=str(record.get("data_kind") or "daily_bar"),
        provider=str(record.get("provider") or ""),
        source_path=str(record.get("source_path") or ""),
        source_url_sanitized=str(record.get("source_url_sanitized") or ""),
        fetched_at=str(record.get("fetched_at") or ""),
        source_published_at=str(record.get("source_published_at") or ""),
        as_of=str(record.get("as_of") or ""),
        trading_date=str(record.get("trading_date") or ""),
        row_count=_safe_int(record.get("row_count")),
        schema_version=str(record.get("schema_version") or PROVENANCE_SCHEMA_VERSION),
        content_hash=str(record.get("content_hash") or ""),
        sample_data_used=_bool(record.get("sample_data_used")),
        baseline_used=_bool(record.get("baseline_used")),
        cache_status=str(record.get("cache_status") or "missing"),
        stale_status=str(record.get("stale_status") or "missing"),
        blocking_reasons=record.get("blocking_reasons") if isinstance(record.get("blocking_reasons"), list) else [],
    )


def _read_json(path: Path) -> Any:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _rows_from_payload(payload: Any) -> list[Mapping[str, Any]]:
    if isinstance(payload, Mapping):
        rows = payload.get("history") or payload.get("points") or payload.get("rows") or payload.get("data") or []
    elif isinstance(payload, list):
        rows = payload
    else:
        rows = []
    return [row for row in rows if isinstance(row, Mapping)]


def _max_trade_date(rows: list[Mapping[str, Any]]) -> str:
    values = [
        str(row.get("trade_date") or row.get("date") or row.get("time") or row.get("timestamp") or "").strip()
        for row in rows
    ]
    values = [value[:10] for value in values if value]
    return max(values) if values else ""


def _infer_daily_bar_record(output_dir: Path, watermark: Mapping[str, Any]) -> dict[str, Any] | None:
    path = output_dir / "sn_market_history.json"
    payload = _read_json(path)
    rows = _rows_from_payload(payload)
    if not rows:
        return None
    sample = _bool(payload.get("sample") if isinstance(payload, Mapping) else False) or any(_bool(row.get("sample")) for row in rows)
    baseline = _bool(payload.get("baseline_used") if isinstance(payload, Mapping) else False)
    trading_date = _max_trade_date(rows)
    return build_watermark_record(
        data_kind="daily_bar",
        provider=str((payload.get("provider") if isinstance(payload, Mapping) else "") or "runtime_market_history"),
        source_path=path,
        fetched_at=str((payload.get("fetched_at") if isinstance(payload, Mapping) else "") or watermark.get("price_history_updated_at") or ""),
        source_published_at=str((payload.get("source_published_at") if isinstance(payload, Mapping) else "") or ""),
        as_of=str((payload.get("as_of") if isinstance(payload, Mapping) else "") or trading_date),
        trading_date=trading_date,
        row_count=len(rows),
        sample_data_used=sample,
        baseline_used=baseline,
        cache_status=str((payload.get("cache_status") if isinstance(payload, Mapping) else "") or "cache"),
        stale_status=str((payload.get("stale_status") if isinstance(payload, Mapping) else "") or "recent"),
    )


def _infer_realtime_quote_record(output_dir: Path, watermark: Mapping[str, Any]) -> dict[str, Any] | None:
    path = output_dir / "sn_live_snapshot.json"
    payload = _read_json(path)
    if not isinstance(payload, Mapping):
        return None
    quotes = payload.get("quotes") if isinstance(payload.get("quotes"), list) else []
    row_count = len([row for row in quotes if isinstance(row, Mapping)]) or (1 if payload.get("latest") else 0)
    if row_count <= 0:
        return None
    quote_time = str(payload.get("generated_at") or payload.get("quote_time") or watermark.get("latest_realtime") or "")
    return build_watermark_record(
        data_kind="realtime_quote",
        provider=str(payload.get("provider") or "runtime_live_snapshot"),
        source_path=path,
        fetched_at=quote_time,
        source_published_at=quote_time,
        as_of=quote_time,
        trading_date=quote_time[:10],
        row_count=row_count,
        sample_data_used=_bool(payload.get("sample") or payload.get("sample_mode")),
        baseline_used=_bool(payload.get("baseline_used")),
        cache_status=str(payload.get("cache_status") or "cache"),
        stale_status=str(payload.get("stale_status") or "recent"),
    )


def _infer_event_records(output_dir: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for data_kind, path in (
        ("news", output_dir / "event_factor_inputs.json"),
        ("news", output_dir / "events" / "event_factor_inputs.json"),
        ("policy", output_dir / "events" / "policy_events.json"),
    ):
        payload = _read_json(path)
        if not isinstance(payload, Mapping):
            continue
        rows = payload.get("inputs") or payload.get("events") or payload.get("rows") or []
        if not isinstance(rows, list) or not rows:
            continue
        published_values = [
            str(row.get("source_published_at") or row.get("published_at") or "").strip()
            for row in rows
            if isinstance(row, Mapping)
        ]
        records.append(
            build_watermark_record(
                data_kind=data_kind,
                provider=str(payload.get("provider") or "runtime_event_store"),
                source_path=path,
                fetched_at=str(payload.get("fetched_at") or payload.get("generated_at") or ""),
                source_published_at=max([value for value in published_values if value], default=""),
                as_of=str(payload.get("as_of") or payload.get("generated_at") or ""),
                trading_date=str(payload.get("trading_date") or ""),
                row_count=len([row for row in rows if isinstance(row, Mapping)]),
                sample_data_used=_bool(payload.get("sample") or payload.get("sample_mode")),
                baseline_used=_bool(payload.get("baseline_used")),
                cache_status=str(payload.get("cache_status") or "cache"),
                stale_status=str(payload.get("stale_status") or "recent"),
            )
        )
    return records


def load_provenance_records(output_dir: Path | None = None, aggregate_watermark: Mapping[str, Any] | None = None) -> list[dict[str, Any]]:
    root = output_dir or get_user_output_dir()
    watermark_path = root / "data_watermark.json"
    watermark = dict(aggregate_watermark or {})
    persisted = _read_json(watermark_path)
    if isinstance(persisted, Mapping):
        watermark = {**persisted, **watermark}
        rows = persisted.get("provenance_records")
        if isinstance(rows, list):
            return [normalise_watermark_record(row) for row in rows if isinstance(row, Mapping)]
    rows = watermark.get("provenance_records")
    if isinstance(rows, list):
        return [normalise_watermark_record(row) for row in rows if isinstance(row, Mapping)]

    records: list[dict[str, Any]] = []
    daily = _infer_daily_bar_record(root, watermark)
    quote = _infer_realtime_quote_record(root, watermark)
    if daily:
        records.append(daily)
    if quote:
        records.append(quote)
    records.extend(_infer_event_records(root))
    return records


def _collect_record_reasons(records: Iterable[Mapping[str, Any]]) -> list[str]:
    reasons: list[str] = []
    for record in records:
        record_reasons = record.get("blocking_reasons")
        if not isinstance(record_reasons, list):
            continue
        for reason in record_reasons:
            _append_unique(reasons, str(reason))
    return reasons


def evaluate_provenance_gate(records: Iterable[Mapping[str, Any]], *, purpose: str) -> dict[str, Any]:
    purpose_norm = str(purpose or "prediction").strip().lower()
    normalised = [normalise_watermark_record(record) for record in records if isinstance(record, Mapping)]
    daily_records = [record for record in normalised if record.get("data_kind") == "daily_bar"]
    quote_records = [record for record in normalised if record.get("data_kind") == "realtime_quote"]
    event_records = [record for record in normalised if record.get("data_kind") in {"news", "policy"}]

    display_allowed = any(_bool(record.get("allowed_for_display")) for record in normalised)
    feature_store_allowed = any(_bool(record.get("allowed_for_feature_store")) for record in daily_records)
    training_allowed = any(_bool(record.get("allowed_for_training")) for record in daily_records)
    prediction_allowed = any(_bool(record.get("allowed_for_prediction")) for record in daily_records)
    backtest_allowed = any(_bool(record.get("allowed_for_backtest")) for record in daily_records)
    high_weight_event_allowed = bool(event_records) and all(
        _bool(record.get("allowed_for_high_weight_event_factor")) for record in event_records
    )

    reasons = _collect_record_reasons(normalised)
    if purpose_norm in RESEARCH_PURPOSES and not daily_records:
        _append_unique(reasons, "缺少 daily_bar 历史行情，禁止生成预测、训练或回测结果")
    if purpose_norm == "high_weight_event_factor":
        if not event_records:
            _append_unique(reasons, "缺少 news/policy 事件水位，禁止用于高权重事件因子")
        elif not high_weight_event_allowed:
            _append_unique(reasons, "news/policy 缺少 source_published_at，禁止用于高权重事件因子")

    allowed_by_purpose = {
        "display": display_allowed,
        "feature_store": feature_store_allowed,
        "training": training_allowed,
        "prediction": prediction_allowed,
        "backtest": backtest_allowed,
        "high_weight_event_factor": high_weight_event_allowed,
    }
    required = {
        "display": ["daily_bar or realtime_quote"],
        "feature_store": ["daily_bar"],
        "training": ["daily_bar"],
        "prediction": ["daily_bar"],
        "backtest": ["daily_bar"],
        "high_weight_event_factor": ["news or policy", "source_published_at"],
    }.get(purpose_norm, ["daily_bar"])
    gate = {
        "schema_version": PROVENANCE_SCHEMA_VERSION,
        "purpose": purpose_norm,
        "allowed": bool(allowed_by_purpose.get(purpose_norm, False)),
        "allowed_for_display": bool(display_allowed),
        "allowed_for_feature_store": bool(feature_store_allowed),
        "allowed_for_training": bool(training_allowed),
        "allowed_for_prediction": bool(prediction_allowed),
        "allowed_for_backtest": bool(backtest_allowed),
        "allowed_for_high_weight_event_factor": bool(high_weight_event_allowed),
        "display_latest_only": bool(quote_records and not daily_records),
        "required_data_kinds": required,
        "record_count": len(normalised),
        "blocking_reasons": reasons if reasons else ([] if bool(allowed_by_purpose.get(purpose_norm, False)) else ["数据水位未通过"]),
    }
    return sanitize_for_json(gate)


def _aggregate_gate_reasons(gates: Mapping[str, Mapping[str, Any]]) -> list[str]:
    reasons: list[str] = []
    for gate in gates.values():
        if not isinstance(gate, Mapping):
            continue
        for reason in gate.get("blocking_reasons") or []:
            _append_unique(reasons, str(reason))
    return reasons


def build_runtime_provenance_report(
    output_dir: Path | None = None,
    aggregate_watermark: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    root = output_dir or get_user_output_dir()
    records = load_provenance_records(root, aggregate_watermark=aggregate_watermark)
    gates = {
        purpose: evaluate_provenance_gate(records, purpose=purpose)
        for purpose in ("display", "feature_store", "training", "prediction", "backtest", "high_weight_event_factor")
    }
    return sanitize_for_json(
        {
            "schema_version": PROVENANCE_SCHEMA_VERSION,
            "runtime_root": str(root),
            "records": records,
            "gates": gates,
            "provenance_gate": gates["prediction"],
            "blocking_reasons": _aggregate_gate_reasons(gates),
            "sample_data_used": any(_bool(record.get("sample_data_used")) for record in records),
            "baseline_used": any(_bool(record.get("baseline_used")) for record in records),
        }
    )
