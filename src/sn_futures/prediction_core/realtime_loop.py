from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

from ..data_layer.stores import atomic_write_json, read_json
from ..runtime import get_user_output_dir
from ..resource_manager.worker_pool import WorkerPoolSnapshot, worker_pool_gate
from .contracts import DOWNSTREAM_FALSE_FLAGS
from .gates import assert_no_prediction_values, dirty_reasons, safe_payload
from .readiness import build_public_prediction_core_readiness


REALTIME_LOOP_SCHEMA_VERSION = "realtime-prediction-loop-dry-run-v1"
PUBLIC_PREDICTION_STATUS_SCHEMA_VERSION = "public-prediction-status-v1"


def _output_dir(output_dir: Path | None = None) -> Path:
    return output_dir or get_user_output_dir()


def _state_path(output_dir: Path) -> Path:
    return output_dir / "prediction_core" / "realtime_loop_state.json"


def _parse_time(value: Any) -> datetime:
    text = str(value or "").strip()
    if text:
        try:
            if text.endswith("Z"):
                text = text[:-1] + "+00:00"
            return datetime.fromisoformat(text)
        except Exception:
            pass
    return datetime.now(timezone.utc)


def _format_time(value: datetime) -> str:
    return value.isoformat(timespec="seconds")


def load_realtime_loop_state(*, output_dir: Path | None = None) -> dict[str, Any]:
    out = _output_dir(output_dir)
    path = _state_path(out)
    payload = read_json(path, {})
    if isinstance(payload, Mapping) and payload:
        return safe_payload({**dict(payload), "state_path": str(path)})
    return safe_payload(
        {
            "schema_version": REALTIME_LOOP_SCHEMA_VERSION,
            "state_path": str(path),
            "last_status": "not_run",
            "attempt_count": 0,
            "last_checked_at": "",
            "last_attempted_at": "",
            "next_allowed_at": "",
            "blocking_reasons": [],
            "prediction_generated": False,
            "customer_prediction_generated": False,
        }
    )


def _persist_state(
    *,
    output_dir: Path,
    previous: Mapping[str, Any],
    payload: Mapping[str, Any],
    now_text: str,
    checked: bool,
    next_allowed_at: str,
) -> dict[str, Any]:
    state = {
        "schema_version": REALTIME_LOOP_SCHEMA_VERSION,
        "state_path": str(_state_path(output_dir)),
        "last_status": str(payload.get("status") or "blocked"),
        "attempt_count": int(previous.get("attempt_count") or 0) + 1,
        "last_checked_at": now_text if checked else str(previous.get("last_checked_at") or ""),
        "last_attempted_at": now_text,
        "next_allowed_at": next_allowed_at,
        "blocking_reasons": list(payload.get("blocking_reasons") or []),
        "prediction_generated": False,
        "customer_prediction_generated": False,
    }
    atomic_write_json(_state_path(output_dir), state)
    return safe_payload(state)


def _quote_metadata(latest_quote: Mapping[str, Any] | None) -> dict[str, Any]:
    quote = dict(latest_quote or {})
    return safe_payload(
        {
            "received": bool(quote),
            "symbol": str(quote.get("symbol") or ""),
            "quote_time": str(quote.get("quote_time") or quote.get("source_published_at") or quote.get("time") or ""),
        }
    )


def _base_payload(
    *,
    output_dir: Path,
    now_text: str,
    status: str,
    dry_run_status: str | None = None,
    reason: str,
    blocking_reasons: list[str],
    readiness: Mapping[str, Any] | None = None,
    latest_quote: Mapping[str, Any] | None = None,
    next_allowed_at: str = "",
    worker_pool: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    ready = status == "ready_to_predict"
    payload = {
        "schema_version": REALTIME_LOOP_SCHEMA_VERSION,
        "status": status,
        "dry_run_status": dry_run_status or status,
        "dry_run": True,
        "can_predict": ready,
        "ready_to_generate_prediction": ready,
        "reason": reason,
        "checked_at": now_text,
        "next_allowed_at": next_allowed_at,
        "state_path": str(_state_path(output_dir)),
        "blocking_reasons": sorted(set(blocking_reasons)),
        "missing_evidence": list((readiness or {}).get("missing_evidence") or []),
        "active_release_safe": bool((readiness or {}).get("active_release_safe")) and ready,
        "readiness_status": str((readiness or {}).get("status") or ""),
        "latest_quote": _quote_metadata(latest_quote),
        "worker_pool": dict(worker_pool or {}),
        "sample_data_used": False,
        "fake_data_used": False,
        "demo_data_used": False,
        "baseline_used": False,
        **DOWNSTREAM_FALSE_FLAGS,
    }
    guarded = assert_no_prediction_values(payload)
    if guarded.get("status") == "blocked" and "prediction_value_output_forbidden" in guarded.get("blocking_reasons", []):
        return safe_payload({**payload, **guarded, **DOWNSTREAM_FALSE_FLAGS})
    return safe_payload(payload)


def _rate_limit_payload(
    *,
    output_dir: Path,
    previous: Mapping[str, Any],
    now_dt: datetime,
    min_interval_seconds: int,
) -> dict[str, Any] | None:
    previous_dt = _parse_time(previous.get("last_checked_at")) if previous.get("last_checked_at") else None
    if previous_dt is None or min_interval_seconds <= 0:
        return None
    next_allowed = previous_dt + timedelta(seconds=min_interval_seconds)
    if now_dt >= next_allowed:
        return None
    return _base_payload(
        output_dir=output_dir,
        now_text=_format_time(now_dt),
        status="skipped",
        reason="rate_limited",
        blocking_reasons=["rate_limited"],
        next_allowed_at=_format_time(next_allowed),
    )


def run_realtime_prediction_dry_run(
    *,
    output_dir: Path | None = None,
    latest_quote: Mapping[str, Any] | None = None,
    worker_pool: WorkerPoolSnapshot | Mapping[str, Any] | None = None,
    now: str = "",
    min_interval_seconds: int = 0,
    horizons: Iterable[int | str] = ("tomorrow",),
) -> dict[str, Any]:
    out = _output_dir(output_dir)
    now_dt = _parse_time(now)
    now_text = _format_time(now_dt)
    previous = load_realtime_loop_state(output_dir=out)

    rate_limited = _rate_limit_payload(
        output_dir=out,
        previous=previous,
        now_dt=now_dt,
        min_interval_seconds=min_interval_seconds,
    )
    if rate_limited is not None:
        state = _persist_state(
            output_dir=out,
            previous=previous,
            payload=rate_limited,
            now_text=now_text,
            checked=False,
            next_allowed_at=str(rate_limited.get("next_allowed_at") or ""),
        )
        return safe_payload({**rate_limited, "loop_state": state})

    pool_gate = worker_pool_gate(worker_pool, now=now_text)
    if pool_gate.get("status") != "ready":
        payload = _base_payload(
            output_dir=out,
            now_text=now_text,
            status="skipped",
            dry_run_status="resource_busy",
            reason="resource_busy",
            blocking_reasons=[str(reason) for reason in pool_gate.get("blocking_reasons") or ["resource_busy"]],
            latest_quote=latest_quote,
            worker_pool=pool_gate,
        )
        state = _persist_state(output_dir=out, previous=previous, payload=payload, now_text=now_text, checked=False, next_allowed_at="")
        return safe_payload({**payload, "loop_state": state})

    quote_reasons = dirty_reasons(dict(latest_quote or {}), "latest_quote") if latest_quote else []
    if quote_reasons:
        payload = _base_payload(
            output_dir=out,
            now_text=now_text,
            status="blocked",
            reason=quote_reasons[0],
            blocking_reasons=quote_reasons,
            latest_quote=latest_quote,
            worker_pool=pool_gate,
        )
        state = _persist_state(output_dir=out, previous=previous, payload=payload, now_text=now_text, checked=True, next_allowed_at="")
        return safe_payload({**payload, "loop_state": state})

    readiness = build_public_prediction_core_readiness(output_dir=out, horizons=horizons)
    reasons = [str(reason) for reason in readiness.get("blocking_reasons") or [] if str(reason)]
    stale = any(reason in {"data_watermark_stale", "data_watermark_prediction_not_allowed"} for reason in reasons)
    status = "ready_to_predict" if readiness.get("can_predict") is True and not reasons else "blocked"
    payload = _base_payload(
        output_dir=out,
        now_text=now_text,
        status=status,
        dry_run_status="stale_data" if stale else status,
        reason="" if status == "ready_to_predict" else ("stale_data" if stale else (reasons[0] if reasons else "blocked")),
        blocking_reasons=reasons,
        readiness=readiness,
        latest_quote=latest_quote,
        worker_pool=pool_gate,
    )
    state = _persist_state(output_dir=out, previous=previous, payload=payload, now_text=now_text, checked=True, next_allowed_at="")
    return safe_payload({**payload, "loop_state": state})


def build_public_prediction_status_payload(*, output_dir: Path | None = None) -> dict[str, Any]:
    status = run_realtime_prediction_dry_run(output_dir=output_dir, min_interval_seconds=0)
    return safe_payload(
        {
            "schema_version": PUBLIC_PREDICTION_STATUS_SCHEMA_VERSION,
            "prediction_status": status,
            **DOWNSTREAM_FALSE_FLAGS,
        }
    )
