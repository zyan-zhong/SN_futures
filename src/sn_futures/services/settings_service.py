from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping

from ..config import mask_secret
from ..private_bundle_keys import import_private_bundle_keys_if_needed, restore_private_bundle_defaults
from ..user_data import get_user_data_root, initialize_user_data_dir, secrets_path, user_path
from .api_key_resolver import SECRET_KEYS, resolve_secret


ALLOWED_SECRET_KEYS = SECRET_KEYS


def _read_secrets() -> dict[str, Any]:
    path = secrets_path()
    if not path.exists():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return raw if isinstance(raw, dict) else {}


def _provider_label(source: str) -> str:
    if source == "private_bundle":
        return "已预配置"
    if source == "user_secrets":
        return "用户自定义"
    if source == "env":
        return "环境变量"
    if source == ".env":
        return "开发环境"
    return "未配置"


def _provider_message(source: str, configured: bool) -> str:
    if source == "private_bundle":
        return "已由发行版预配置，可直接使用；如过期可在此替换。"
    if source == "user_secrets":
        return "已使用用户自定义 key；用户配置优先于发行版默认 key。"
    if source == "env":
        return "已从本机环境变量读取；不会返回完整 key。"
    if source == ".env":
        return "已从开发环境 .env 读取；仅用于本机开发。"
    if configured:
        return "已配置。"
    return "未配置；可在设置页填写，也可使用私有发行版默认 key。"


def get_terminal_settings_status() -> dict[str, Any]:
    initialize_user_data_dir()
    import_private_bundle_keys_if_needed()
    stored = _read_secrets()
    alpha_resolved = resolve_secret("SN_ALPHA_VANTAGE_KEY")
    news_resolved = resolve_secret("SN_NEWSAPI_KEY")
    managed_resolved = resolve_secret("SN_MANAGED_DATA_PROXY_TOKEN")
    alpha = str(alpha_resolved.get("value") or "")
    news = str(news_resolved.get("value") or "")
    managed_token = str(managed_resolved.get("value") or "")
    alpha_source = str(alpha_resolved.get("source") or "none")
    news_source = str(news_resolved.get("source") or "none")
    managed_source = str(managed_resolved.get("source") or "none")
    host = os.environ.get("SN_TERMINAL_HOST", "127.0.0.1")
    port = os.environ.get("SN_TERMINAL_PORT", "8765")
    api_base_url = os.environ.get("SN_TERMINAL_API_BASE_URL") or f"http://{host}:{port}"
    user_root = get_user_data_root()
    return {
        "success": True,
        "alpha_vantage_configured": bool(alpha),
        "newsapi_configured": bool(news),
        "managed_data_proxy_configured": bool(managed_token),
        "alpha_vantage_masked": mask_secret(alpha) if alpha else "",
        "newsapi_masked": mask_secret(news) if news else "",
        "managed_data_proxy_masked": mask_secret(managed_token) if managed_token else "",
        "alpha_vantage_source": alpha_source,
        "newsapi_source": news_source,
        "managed_data_proxy_source": managed_source,
        "alpha_vantage_source_label_zh": _provider_label(alpha_source),
        "newsapi_source_label_zh": _provider_label(news_source),
        "managed_data_proxy_source_label_zh": _provider_label(managed_source),
        "alpha_vantage_ui_message_zh": _provider_message(alpha_source, bool(alpha)),
        "newsapi_ui_message_zh": _provider_message(news_source, bool(news)),
        "managed_data_proxy_ui_message_zh": _provider_message(managed_source, bool(managed_token)),
        "config_path": str(secrets_path().parent),
        "user_data_dir": str(user_root),
        "logs_dir": str(user_path("logs")),
        "reports_dir": str(user_path("reports")),
        "api_base_url": api_base_url,
        "terminal_url": f"{api_base_url}/terminal",
        "last_update_time": str(stored.get("updated_at") or ""),
        "message_zh": "密钥仅保存在本机用户目录，不会写入前端，不会上传。",
    }


def _validate_secret(name: str, value: Any) -> str | None:
    text = str(value or "").strip()
    if not text:
        return None
    if len(text) < 8:
        raise ValueError(f"{name} 过短，请检查输入。")
    return text


def save_terminal_secrets(payload: Mapping[str, Any]) -> dict[str, Any]:
    initialize_user_data_dir()
    existing = _read_secrets()
    updates: dict[str, str] = {}
    for name in ALLOWED_SECRET_KEYS:
        if name not in payload:
            continue
        value = _validate_secret(name, payload.get(name))
        if value is not None:
            updates[name] = value
    if not updates:
        return {
            **get_terminal_settings_status(),
            "success": False,
            "message_zh": "没有可保存的密钥；空字符串不会写入配置。",
        }

    sources = existing.get("_sources") if isinstance(existing.get("_sources"), dict) else {}
    sources = {str(key): str(value) for key, value in sources.items()}
    for name in updates:
        sources[name] = "user_secrets"

    merged = {
        **existing,
        **updates,
        "_sources": sources,
        "updated_at": datetime.now().isoformat(timespec="seconds"),
    }
    path = secrets_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(merged, ensure_ascii=False, indent=2), encoding="utf-8")
    for name, value in updates.items():
        os.environ[name] = value
    return {**get_terminal_settings_status(), "success": True, "message_zh": "密钥已保存到本机用户目录。"}


def reset_terminal_secrets() -> dict[str, Any]:
    initialize_user_data_dir()
    for name in ALLOWED_SECRET_KEYS:
        os.environ.pop(name, None)
    restored = restore_private_bundle_defaults()
    status = get_terminal_settings_status()
    if restored.get("available") and restored.get("imported"):
        message = "本机密钥已重置，并已恢复发行方默认 key；其他用户数据未删除。"
    else:
        message = "密钥已重置，其他用户数据未删除。"
    return {**status, "success": True, "message_zh": message}


def _read_status_file(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _validation_status(provider: str) -> str:
    root = get_user_data_root()
    if provider == "alpha_vantage":
        item = _read_status_file(root / "outputs" / "fundamentals" / "fx_macro_provider_status.json")
        code = str(item.get("status") or "")
    elif provider == "newsapi":
        status = _read_status_file(root / "outputs" / "events" / "provider_status.json")
        providers = status.get("providers")
        item = providers[0] if isinstance(providers, list) and providers and isinstance(providers[0], dict) else status
        code = str(item.get("error_code") or item.get("status") or "")
        if item.get("success"):
            code = "success"
    elif provider == "managed_proxy":
        code = "not_tested"
    else:
        code = ""
    if not code:
        return "not_tested"
    lower = code.lower()
    if code in {"success", "rate_limited", "key_invalid", "key_missing", "not_tested"}:
        return code
    if "limit" in lower or "rate" in lower or "note" in lower:
        return "rate_limited"
    if "invalid" in lower or "forbidden" in lower or "401" in lower:
        return "key_invalid"
    return "failed"


def get_key_diagnostics() -> dict[str, Any]:
    initialize_user_data_dir()
    import_private_bundle_keys_if_needed()

    def row(name: str, provider: str) -> dict[str, Any]:
        resolved = resolve_secret(name)
        configured = bool(resolved.get("configured"))
        source = str(resolved.get("source") or "none")
        return {
            "configured": configured,
            "source": source,
            "source_label_zh": _provider_label(source),
            "masked": str(resolved.get("masked") or ""),
            "can_read": configured,
            "last_validation_status": _validation_status(provider) if configured else "not_tested",
            "ui_message_zh": _provider_message(source, configured),
            "message_zh": "已读取本机配置，仅返回脱敏信息。" if configured else "未配置该数据源 key。",
        }

    return {
        "success": True,
        "alpha_vantage": row("SN_ALPHA_VANTAGE_KEY", "alpha_vantage"),
        "newsapi": row("SN_NEWSAPI_KEY", "newsapi"),
        "managed_proxy": row("SN_MANAGED_DATA_PROXY_TOKEN", "managed_proxy"),
        "message_zh": "key 诊断只返回来源和脱敏状态，不返回完整 key。",
    }
