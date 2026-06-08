from __future__ import annotations

import json
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping

from ..api.json_utils import sanitize_for_json
from ..runtime import get_user_output_dir
from ..utils.secret_sanitizer import sanitize_mapping


CANONICAL_FILE = "provider_status_canonical.json"


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _output_dir() -> Path:
    return get_user_output_dir()


def _canonical_path() -> Path:
    return _output_dir() / CANONICAL_FILE


def _read_json(path: Path) -> Any:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(sanitize_for_json(sanitize_mapping(dict(payload))), ensure_ascii=False, indent=2), encoding="utf-8")


def _safe_int(value: Any) -> int:
    try:
        return int(value or 0)
    except Exception:
        return 0


def _first_str(*values: Any) -> str:
    for value in values:
        if value not in (None, ""):
            return str(value)
    return ""


def _sanitize_visible_path(value: str) -> str:
    return re.sub(r"[A-Za-z]:\\Users\\[^\\]+", "%USERPROFILE%", value)


def _first_bool(payload: Mapping[str, Any], keys: tuple[str, ...], default: bool = False) -> bool:
    for key in keys:
        if key in payload and payload.get(key) is not None:
            return bool(payload.get(key))
    return default


def _row_count(payload: Mapping[str, Any], fallback: int = 0) -> int:
    for key in ("row_count", "inserted_count", "fetched_count", "returned_count", "count"):
        if key in payload:
            count = _safe_int(payload.get(key))
            if count:
                return count
    rows = payload.get("rows") or payload.get("articles") or payload.get("events") or payload.get("inputs")
    if isinstance(rows, list):
        return len(rows)
    return fallback


def _providers(payload: Any) -> list[Mapping[str, Any]]:
    if isinstance(payload, Mapping) and isinstance(payload.get("providers"), list):
        return [item for item in payload["providers"] if isinstance(item, Mapping)]
    if isinstance(payload, Mapping):
        return [payload]
    return []


def _best_provider(payloads: list[Any], *, prefer_success: bool = True) -> tuple[Mapping[str, Any], Mapping[str, Any], Path | None]:
    candidates: list[tuple[Mapping[str, Any], Mapping[str, Any], Path | None]] = []
    for payload, path in payloads:
        if not isinstance(payload, Mapping):
            continue
        providers = _providers(payload)
        if providers:
            for provider in providers:
                candidates.append((payload, provider, path))
        else:
            candidates.append((payload, payload, path))
    if not candidates:
        return {}, {}, None
    if prefer_success:
        for top, provider, path in candidates:
            if bool(provider.get("success")) or str(provider.get("status") or "").lower() == "success":
                return top, provider, path
        for top, provider, path in candidates:
            if bool(top.get("from_cache")) or bool(provider.get("from_cache")):
                return top, provider, path
    return candidates[0]


def _event_cache_count(output_dir: Path) -> tuple[int, str]:
    event_payload = _read_json(output_dir / "events" / "news_events.json")
    raw_payload = _read_json(output_dir / "events" / "news_raw.json")
    if isinstance(event_payload, Mapping):
        events = event_payload.get("events")
        if isinstance(events, list) and events:
            return len(events), _first_str(event_payload.get("generated_at"), event_payload.get("updated_at"))
    if isinstance(raw_payload, Mapping):
        articles = raw_payload.get("articles")
        if isinstance(articles, list) and articles:
            return len(articles), _first_str(raw_payload.get("generated_at"), raw_payload.get("updated_at"))
    return 0, ""


def _data_generated_at(path: Path) -> str:
    payload = _read_json(path)
    if isinstance(payload, Mapping):
        return _first_str(payload.get("data_generated_at"), payload.get("generated_at"), payload.get("updated_at"), payload.get("last_success_time"))
    return ""


def _status_from_payload(top: Mapping[str, Any], provider: Mapping[str, Any], *, cache_available: bool = False) -> str:
    explicit = _first_str(provider.get("status"), top.get("status"), provider.get("error_code"), top.get("error_code"), top.get("final_status"))
    explicit_l = explicit.lower()
    from_cache = bool(top.get("from_cache") or provider.get("from_cache"))
    if explicit_l in {"using_cache", "using_cache_rate_limited"}:
        return explicit_l
    if (from_cache or cache_available) and explicit_l in {"failed", "error", "rate_limited", "request_failed"}:
        return "using_cache"
    if bool(provider.get("success")) or bool(top.get("success")):
        return "success"
    if (from_cache or cache_available) and not (bool(provider.get("success")) or bool(top.get("success"))):
        return "using_cache"
    if explicit_l:
        return explicit_l
    return "unknown"


def _freshness_label(status: str, from_cache: bool, stale: bool) -> str:
    if status == "success":
        return "fresh"
    if status.startswith("using_cache") or from_cache:
        return "cache"
    if status in {"disabled", "token_missing", "key_missing", "not_configured"}:
        return status
    if stale:
        return "stale"
    return status or "unknown"


def _canonical_row(
    provider_id: str,
    *,
    source_file: Path | None,
    top: Mapping[str, Any],
    provider: Mapping[str, Any],
    data_generated_at: str = "",
    fallback_row_count: int = 0,
    cache_available: bool = False,
    default_enabled: bool = True,
    default_configured: bool = False,
) -> dict[str, Any]:
    status = _status_from_payload(top, provider, cache_available=cache_available)
    configured = _first_bool(provider, ("configured", "can_read"), _first_bool(top, ("configured", "can_read"), default_configured or status in {"success", "using_cache", "using_cache_rate_limited"}))
    if status == "unknown" and not configured:
        status = "not_configured"
    from_cache = bool(top.get("from_cache") or provider.get("from_cache") or status.startswith("using_cache"))
    row_count = _row_count(provider, _row_count(top, fallback_row_count))
    if from_cache and not row_count:
        row_count = fallback_row_count
    last_attempt = _first_str(provider.get("last_attempt_time"), top.get("last_attempt_time"), provider.get("updated_at"), top.get("updated_at"), provider.get("generated_at"), top.get("generated_at"))
    last_success = _first_str(provider.get("last_success_time"), top.get("last_success_time"), provider.get("last_success_at"), top.get("last_success_at"))
    if status == "success" and not last_success:
        last_success = last_attempt
    if from_cache and not last_success:
        last_success = data_generated_at or last_attempt
    enabled = _first_bool(provider, ("enabled",), _first_bool(top, ("enabled",), default_enabled))
    stale = bool(top.get("stale") or provider.get("stale"))
    return {
        "provider_id": provider_id,
        "status": status,
        "success": status in {"success", "usable"},
        "configured": configured,
        "enabled": enabled,
        "row_count": row_count,
        "from_cache": from_cache,
        "stale": stale,
        "last_attempt_time": last_attempt,
        "last_success_time": last_success,
        "source_file": str(source_file) if source_file else "",
        "status_generated_at": _first_str(top.get("updated_at"), top.get("generated_at"), provider.get("updated_at"), provider.get("generated_at"), last_attempt),
        "data_generated_at": data_generated_at or last_success or last_attempt,
        "status_time": last_attempt,
        "data_time": data_generated_at or last_success or last_attempt,
        "report_time": _now(),
        "freshness_label": _freshness_label(status, from_cache, stale),
        "message_zh": _first_str(provider.get("message_zh"), top.get("message_zh"), provider.get("message"), top.get("message"), provider.get("error_message_zh"), top.get("error_message_zh")),
    }


def _newsapi_status(output_dir: Path) -> dict[str, Any]:
    news_path = output_dir / "events" / "news_provider_status.json"
    legacy_path = output_dir / "events" / "provider_status.json"
    cache_count, cache_time = _event_cache_count(output_dir)
    news_payload = _read_json(news_path)
    if isinstance(news_payload, Mapping):
        top, provider, path = _best_provider([(news_payload, news_path)], prefer_success=False)
    else:
        top, provider, path = _best_provider([(_read_json(legacy_path), legacy_path)], prefer_success=False)
    return _canonical_row(
        "newsapi",
        source_file=path,
        top=top,
        provider=provider,
        data_generated_at=cache_time,
        fallback_row_count=cache_count,
        cache_available=cache_count > 0,
        default_enabled=True,
        default_configured=bool(os.environ.get("SN_NEWSAPI_KEY")) or bool(top or provider),
    )


def _alpha_status(output_dir: Path) -> dict[str, Any]:
    path = output_dir / "fundamentals" / "fx_macro_provider_status.json"
    payload = _read_json(path)
    top, provider, source = _best_provider([(payload, path)], prefer_success=False)
    return _canonical_row(
        "alpha_vantage",
        source_file=source,
        top=top,
        provider=provider,
        data_generated_at=_data_generated_at(output_dir / "fundamentals" / "sn_cross_market.json"),
        default_enabled=True,
        default_configured=bool(os.environ.get("SN_ALPHA_VANTAGE_KEY")) or bool(top.get("configured") if isinstance(top, Mapping) else False),
    )


def _simple_provider(
    provider_id: str,
    path: Path,
    *,
    default_enabled: bool = True,
    default_configured: bool = False,
    data_file: Path | None = None,
) -> dict[str, Any]:
    payload = _read_json(path)
    top, provider, source = _best_provider([(payload, path)], prefer_success=False)
    return _canonical_row(
        provider_id,
        source_file=source,
        top=top,
        provider=provider,
        data_generated_at=_data_generated_at(data_file) if data_file else "",
        default_enabled=default_enabled,
        default_configured=default_configured,
    )


def _provider_result_bridge_status(
    canonical_provider_id: str,
    bridge_provider_id: str,
    *,
    output_dir: Path,
    default_enabled: bool = True,
    default_configured: bool = True,
) -> dict[str, Any] | None:
    path = output_dir / "provider_results" / bridge_provider_id / "latest_status.json"
    payload = _read_json(path)
    if not isinstance(payload, Mapping):
        return None
    top: Mapping[str, Any] = payload
    manifest = payload.get("manifest") if isinstance(payload.get("manifest"), Mapping) else {}
    provider: Mapping[str, Any] = {
        "success": bool(payload.get("success")),
        "status": "success" if payload.get("success") else str(payload.get("error_code") or "blocked"),
        "row_count": _safe_int(payload.get("normalized_row_count") or payload.get("row_count")),
        "from_cache": bool(payload.get("from_cache")),
        "stale": bool(payload.get("stale")),
        "last_attempt_time": _first_str(payload.get("fetched_at"), manifest.get("fetched_at")),
        "last_success_time": _first_str(payload.get("as_of"), payload.get("source_timestamp")) if payload.get("success") else "",
        "message_zh": _first_str(payload.get("sanitized_error"), manifest.get("sanitized_error"), payload.get("error_code")),
        "error_code": str(payload.get("error_code") or ""),
        "configured": default_configured,
        "enabled": default_enabled,
    }
    row = _canonical_row(
        canonical_provider_id,
        source_file=path,
        top=top,
        provider=provider,
        data_generated_at=_first_str(payload.get("as_of"), payload.get("source_timestamp"), manifest.get("as_of")),
        default_enabled=default_enabled,
        default_configured=default_configured,
    )
    row["provider_status_source"] = "provider_result_bridge"
    row["provider_interface_schema_version"] = str(payload.get("schema_version") or manifest.get("provider_interface_schema_version") or "")
    row["bridge_provider_id"] = bridge_provider_id
    row["manifest_hash"] = str(manifest.get("content_hash") or "")
    return row


def _market_status(output_dir: Path) -> dict[str, Any]:
    path = output_dir / "market_provider_status.json"
    payload = _read_json(path)
    providers = _providers(payload)
    success_rows = [_row_count(item) for item in providers if bool(item.get("success"))]
    top: Mapping[str, Any] = payload if isinstance(payload, Mapping) else {}
    provider: Mapping[str, Any] = {
        "success": bool(success_rows) or str(top.get("final_status") or "").lower() == "success",
        "row_count": sum(success_rows),
    }
    row = _canonical_row(
        "market",
        source_file=path if path.exists() else None,
        top=top,
        provider=provider,
        data_generated_at=_data_generated_at(output_dir / "sn_market_history.json"),
        fallback_row_count=sum(success_rows),
        default_enabled=True,
        default_configured=True,
    )
    if top.get("market_status"):
        row["status"] = str(top.get("market_status"))
        row["success"] = row["status"] == "usable"
        row["freshness_label"] = row["status"]
    return row


def _market_child_status(output_dir: Path, provider_id: str, provider_name: str) -> dict[str, Any] | None:
    path = output_dir / "market_provider_status.json"
    payload = _read_json(path)
    top: Mapping[str, Any] = payload if isinstance(payload, Mapping) else {}
    for provider in _providers(payload):
        name = str(provider.get("provider_name") or provider.get("provider") or provider.get("name") or "").lower()
        if name == provider_name.lower():
            row = _canonical_row(
                provider_id,
                source_file=path if path.exists() else None,
                top=top,
                provider=provider,
                data_generated_at=_data_generated_at(output_dir / "sn_market_history.json"),
                fallback_row_count=_row_count(provider),
                default_enabled=True,
                default_configured=True,
            )
            if str(provider.get("status_code") or provider.get("status") or "") == "optional_failed":
                message = _sanitize_visible_path(_first_str(provider.get("error_message_zh"), provider.get("message_zh"), provider.get("message")))
                row.update(
                    {
                        "status": "optional_failed",
                        "severity": "optional_failed",
                        "optional": True,
                        "blocks_market": False,
                        "stale": False,
                        "message_zh": "可选源失败，不影响主行情。" + (f" {message}" if message else ""),
                    }
                )
            return row
    return None


def build_canonical_provider_status() -> dict[str, Any]:
    output_dir = _output_dir()
    fundamentals = output_dir / "fundamentals"
    shfe_public = _simple_provider("shfe_public", fundamentals / "shfe_public_provider_status.json", default_configured=True)
    shfe_bridge = _provider_result_bridge_status("shfe_public", "shfe_public", output_dir=output_dir)
    if shfe_bridge is not None:
        shfe_public = shfe_bridge
    market_shfe_public = _market_child_status(output_dir, "shfe_public", "shfe_public")
    if market_shfe_public is not None and not shfe_public.get("source_file"):
        shfe_public = market_shfe_public
    tushare = _provider_result_bridge_status("tushare", "tushare_futures", output_dir=output_dir, default_configured=bool(os.environ.get("SN_TUSHARE_TOKEN")) or True)
    if tushare is None:
        tushare = _simple_provider("tushare", fundamentals / "tushare_provider_status.json", default_configured=bool(os.environ.get("SN_TUSHARE_TOKEN")))
    policy_rss = _provider_result_bridge_status("public_policy_rss", "public_policy_rss", output_dir=output_dir, default_configured=True)
    if policy_rss is None:
        policy_rss = _simple_provider("public_policy_rss", output_dir / "events" / "public_policy_rss_provider_status.json", default_configured=False)
    providers = {
        "market": _market_status(output_dir),
        "alpha_vantage": _alpha_status(output_dir),
        "newsapi": _newsapi_status(output_dir),
        "tushare": tushare,
        "managed_proxy": _simple_provider("managed_proxy", fundamentals / "managed_proxy_status.json", default_enabled=False, default_configured=bool(os.environ.get("SN_MANAGED_DATA_PROXY_TOKEN"))),
        "shfe_public": shfe_public,
        "public_policy_rss": policy_rss,
        "lme_tin": _simple_provider("lme_tin", fundamentals / "lme_tin_provider_status.json", default_configured=False),
    }
    akshare_history = _market_child_status(output_dir, "akshare_history", "akshare_history")
    if akshare_history is not None:
        providers["akshare_history"] = akshare_history
    generated_at = _now()
    for item in providers.values():
        item["report_time"] = generated_at
    payload = {
        "status": "success",
        "generated_at": generated_at,
        "provider_count": len(providers),
        "providers": providers,
        "provider_list": list(providers.values()),
        "source_files": sorted({item["source_file"] for item in providers.values() if item.get("source_file")}),
        "active_updated": False,
        "customer_prediction_generated": False,
    }
    try:
        from ..data_providers.provider_registry import list_provider_registry

        payload["provider_interface_schema_version"] = "provider-result-v1"
        payload["provider_registry"] = list_provider_registry()
    except Exception:
        payload["provider_interface_schema_version"] = ""
        payload["provider_registry"] = []
    _write_json(_canonical_path(), payload)
    return sanitize_for_json(payload)


def get_canonical_provider_status() -> dict[str, Any]:
    payload = _read_json(_canonical_path())
    if isinstance(payload, Mapping):
        return sanitize_for_json(dict(payload))
    return build_canonical_provider_status()
