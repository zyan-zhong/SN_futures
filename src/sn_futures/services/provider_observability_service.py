from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping

from ..api.json_utils import sanitize_for_json
from ..config import mask_secret
from ..user_data import get_user_data_root, user_path
from ..utils.secret_sanitizer import sanitize_mapping
from .refresh_service import get_refresh_history, get_refresh_status
from .runtime_diagnostics_service import build_runtime_data_diagnostics
from .settings_service import get_terminal_settings_status
from .terminal_service import build_terminal_data_status
from .provider_status_canonical_service import build_canonical_provider_status


SENSITIVE_KEYS = ("key", "token", "secret", "password", "authorization", "apikey")
SUPPORTED_PROVIDERS = {"market", "newsapi", "alpha_vantage", "alphavantage", "managed_proxy", "managed", "tushare", "shfe_public", "akshare_news", "miit_policy"}


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _scrub(value: Any) -> Any:
    if isinstance(value, Mapping):
        cleaned: dict[str, Any] = {}
        for key, item in value.items():
            lower = str(key).lower()
            if any(secret in lower for secret in SENSITIVE_KEYS):
                cleaned[str(key)] = mask_secret(str(item or "")) if item else ""
            else:
                cleaned[str(key)] = _scrub(item)
        return cleaned
    if isinstance(value, list):
        return [_scrub(item) for item in value]
    return value


def _read_json(path: Path) -> Any:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(sanitize_for_json(sanitize_mapping(_scrub(payload))), ensure_ascii=False, indent=2), encoding="utf-8")


def _failed_steps_from_run(run: Mapping[str, Any]) -> list[dict[str, Any]]:
    steps = run.get("steps", [])
    if not isinstance(steps, list):
        return []
    failed: list[dict[str, Any]] = []
    for step in steps:
        if not isinstance(step, Mapping):
            continue
        if str(step.get("status")) in {"failed", "skipped"} or step.get("error_message_zh"):
            failed.append(dict(step))
    return failed


def get_refresh_last_error() -> dict[str, Any]:
    status = get_refresh_status()
    errors = _failed_steps_from_run(status if isinstance(status, Mapping) else {})
    if not errors:
        history = get_refresh_history()
        rows = history.get("history", []) if isinstance(history, Mapping) else []
        for run in reversed(rows if isinstance(rows, list) else []):
            if isinstance(run, Mapping):
                errors = _failed_steps_from_run(run)
                if errors:
                    break
    latest = errors[-1] if errors else None
    return sanitize_for_json(
        {
            "success": True,
            "has_error": bool(latest),
            "latest_error": latest or {},
            "errors": errors,
            "message_zh": "已找到最近刷新错误。" if latest else "暂无刷新错误记录。",
            "next_actions_zh": (latest or {}).get("next_actions_zh", ["如页面无数据，请先运行一键刷新数据。"]),
            "generated_at": _now(),
        }
    )


def get_provider_status_detail() -> dict[str, Any]:
    data_status = build_terminal_data_status()
    refresh_status = get_refresh_status()
    canonical = build_canonical_provider_status()
    market_chain = _read_json(get_user_data_root() / "outputs" / "market_provider_status.json") or {}
    news_status = _read_json(get_user_data_root() / "outputs" / "events" / "provider_status.json") or {}
    return sanitize_for_json(
        sanitize_mapping(
        {
            "success": True,
            "data_status": data_status,
            "refresh_status": refresh_status,
            "provider_status_canonical": canonical,
            "market_provider_status": market_chain,
            "news_provider_status": (canonical.get("providers", {}) or {}).get("newsapi", news_status) if isinstance(canonical, Mapping) else news_status,
            "message_zh": "数据源明细已汇总，所有敏感字段已脱敏。",
            "generated_at": _now(),
        }
        )
    )


def test_provider(provider: str) -> dict[str, Any]:
    provider = str(provider or "").strip().lower()
    if provider not in SUPPORTED_PROVIDERS:
        return {
            "success": False,
            "provider": provider,
            "message_zh": "不支持的数据源测试类型。",
            "next_actions_zh": ["请选择 market、newsapi、shfe_public、akshare_news 或 miit_policy"],
        }
    data_status = build_terminal_data_status()
    sources = data_status.get("sources", []) if isinstance(data_status, Mapping) else []
    matched = [
        source for source in sources
        if isinstance(source, Mapping)
        and (
            provider in str(source.get("source_name", "")).lower()
            or (provider == "market" and "行情" in str(source.get("source_name", "")))
            or (provider == "newsapi" and str(source.get("source_name", "")).lower() == "newsapi")
            or (provider == "akshare_news" and "akshare" in str(source.get("source_name", "")).lower())
            or (provider == "miit_policy" and "工信部" in str(source.get("source_name", "")))
            or (provider == "shfe_public" and "shfe" in str(source.get("source_name", "")).lower())
        )
    ]
    if provider == "market":
        from .market_data_service import get_market_provider_chain_status

        detail = get_market_provider_chain_status()
    elif provider in {"alpha_vantage", "alphavantage"}:
        from .online_cross_market_service import test_alpha_vantage_connection

        detail = test_alpha_vantage_connection()
        provider = "alpha_vantage"
    elif provider == "newsapi":
        from ..data_providers.newsapi_provider import test_newsapi_connection

        detail = test_newsapi_connection()
    elif provider == "tushare":
        from .tushare_futures_service import test_tushare_connection

        detail = test_tushare_connection()
    elif provider in {"managed_proxy", "managed"}:
        from .managed_data_proxy_service import test_managed_proxy_connection

        detail = test_managed_proxy_connection()
        provider = "managed_proxy"
    else:
        detail = matched[0] if matched else {}
    status_payload = detail if provider in {"alpha_vantage", "newsapi", "tushare", "managed_proxy"} else (matched[0] if matched else detail)
    label = str(status_payload.get("freshness_label") or status_payload.get("status") or "")
    return sanitize_for_json(
        sanitize_mapping(
        {
            "success": bool(status_payload),
            "provider": provider,
            "request_params_sanitized": {"provider": provider},
            "status": status_payload,
            "message_zh": f"{provider} 测试完成：{label or '已返回状态明细'}。",
            "next_actions_zh": status_payload.get("next_actions_zh", ["查看数据源状态", "复制诊断信息"]),
            "generated_at": _now(),
        }
        )
    )


def export_diagnostics_bundle() -> dict[str, Any]:
    bundle = {
        "version": _read_text(Path("VERSION")),
        "generated_at": _now(),
        "settings_status": get_terminal_settings_status(),
        "data_source_status": build_terminal_data_status(),
        "refresh_status": get_refresh_status(),
        "last_errors": get_refresh_last_error(),
        "file_inventory": build_runtime_data_diagnostics(),
        "message_zh": "诊断包已生成，敏感字段已脱敏，不包含完整 key。",
    }
    path = user_path("logs", "diagnostics_bundle.json")
    _write_json(path, bundle)
    return sanitize_for_json(sanitize_mapping({"success": True, "path": str(path), "bundle": _scrub(bundle), "message_zh": "诊断信息已导出。"}))


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8").strip()
    except Exception:
        return "unknown"
