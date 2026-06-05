from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping

from ..config import mask_secret
from ..private_bundle_keys import import_private_bundle_keys_if_needed, restore_private_bundle_defaults
from ..user_data import get_user_data_root, initialize_user_data_dir, secrets_path, user_path
from .api_key_resolver import CANONICAL_SECRET_KEYS, LEGACY_SECRET_KEYS, resolve_secret


ALLOWED_SECRET_KEYS = (*CANONICAL_SECRET_KEYS, *LEGACY_SECRET_KEYS)
ALLOWED_CONFIG_KEYS = (
    "SN_LOCAL_API_PROVIDER_ENABLED",
    "SN_LOCAL_API_PROVIDER_ID",
    "SN_LOCAL_API_PROVIDER_BASE_URL",
    "SN_MANAGED_DATA_PROXY_URL",
    "SN_MANAGED_DATA_PROXY_ENABLED",
    "SN_MANAGED_PROXY_BASE_URL",
    "SN_MANAGED_PROXY_ENABLED",
)
SECRET_KEY_CANONICAL: dict[str, str] = {
    "SN_MANAGED_DATA_PROXY_TOKEN": "SN_LOCAL_API_PROVIDER_TOKEN",
    "SN_MANAGED_PROXY_TOKEN": "SN_LOCAL_API_PROVIDER_TOKEN",
}
CONFIG_KEY_CANONICAL: dict[str, str] = {
    "SN_MANAGED_DATA_PROXY_URL": "SN_LOCAL_API_PROVIDER_BASE_URL",
    "SN_MANAGED_PROXY_BASE_URL": "SN_LOCAL_API_PROVIDER_BASE_URL",
    "SN_MANAGED_DATA_PROXY_ENABLED": "SN_LOCAL_API_PROVIDER_ENABLED",
    "SN_MANAGED_PROXY_ENABLED": "SN_LOCAL_API_PROVIDER_ENABLED",
}
FORBIDDEN_PAYLOAD_KEYS = {
    "authorization",
    "auth_header",
    "authorization_header",
    "endpoint_secret",
    "raw_endpoint_secret",
    "raw_secret",
    "raw_token",
    "bearer",
}
LOCAL_PROVIDER_CONFIG_ALIASES: dict[str, tuple[str, ...]] = {
    "SN_LOCAL_API_PROVIDER_BASE_URL": (
        "SN_LOCAL_API_PROVIDER_BASE_URL",
        "SN_MANAGED_DATA_PROXY_URL",
        "SN_MANAGED_PROXY_BASE_URL",
    ),
    "SN_LOCAL_API_PROVIDER_ENABLED": (
        "SN_LOCAL_API_PROVIDER_ENABLED",
        "SN_MANAGED_DATA_PROXY_ENABLED",
        "SN_MANAGED_PROXY_ENABLED",
    ),
    "SN_LOCAL_API_PROVIDER_ID": ("SN_LOCAL_API_PROVIDER_ID",),
}


def _read_secrets() -> dict[str, Any]:
    path = secrets_path()
    if not path.exists():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return raw if isinstance(raw, dict) else {}


def _clean_text(value: Any) -> str:
    return str(value or "").strip()


def _is_truthy(value: Any) -> bool:
    return _clean_text(value).lower() in {"1", "true", "yes", "on", "enabled"}


def _canonical_secret_key(name: str) -> str:
    return SECRET_KEY_CANONICAL.get(name, name)


def _canonical_config_key(name: str) -> str:
    return CONFIG_KEY_CANONICAL.get(name, name)


def _deprecated_warning(legacy_name: str, canonical_name: str) -> str:
    return f"{legacy_name} is deprecated; use {canonical_name} for Local API Provider configuration."


def _config_value(stored: Mapping[str, Any], canonical_name: str) -> dict[str, Any]:
    for name in LOCAL_PROVIDER_CONFIG_ALIASES.get(canonical_name, (canonical_name,)):
        value = _clean_text(stored.get(name))
        if value:
            return {
                "value": value,
                "source": "user_secrets",
                "resolved_name": name,
                "deprecated": name != canonical_name,
                "deprecated_warning": _deprecated_warning(name, canonical_name) if name != canonical_name else "",
            }
    for name in LOCAL_PROVIDER_CONFIG_ALIASES.get(canonical_name, (canonical_name,)):
        value = _clean_text(os.environ.get(name))
        if value:
            return {
                "value": value,
                "source": "env",
                "resolved_name": name,
                "deprecated": name != canonical_name,
                "deprecated_warning": _deprecated_warning(name, canonical_name) if name != canonical_name else "",
            }
    return {
        "value": "",
        "source": "none",
        "resolved_name": canonical_name,
        "deprecated": False,
        "deprecated_warning": "",
    }


def _deprecated_warnings(*records: Mapping[str, Any]) -> list[str]:
    warnings: list[str] = []
    for record in records:
        warning = str(record.get("deprecated_warning") or "")
        if warning:
            warnings.append(warning)
    return list(dict.fromkeys(warnings))


def _validate_payload_keys(payload: Mapping[str, Any]) -> None:
    allowed = set(ALLOWED_SECRET_KEYS) | set(ALLOWED_CONFIG_KEYS)
    for key in payload:
        normalized = str(key or "").strip()
        lowered = normalized.lower()
        if lowered in FORBIDDEN_PAYLOAD_KEYS or "authorization" in lowered:
            raise ValueError("Forbidden secret field is not allowed in settings payload.")
        if normalized not in allowed:
            raise ValueError("Unsupported settings key is not allowed.")


def _validate_config_value(name: str, value: Any) -> str | None:
    text = _clean_text(value)
    if not text:
        return None
    lowered = text.lower()
    if any(marker in lowered for marker in ("authorization=", "access_token=", "api_key=", "apikey=", "token=", "secret=")):
        raise ValueError(f"{name} must not contain raw endpoint secrets or token query parameters.")
    return text


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
    local_provider_resolved = resolve_secret("SN_LOCAL_API_PROVIDER_TOKEN")
    tushare_resolved = resolve_secret("SN_TUSHARE_TOKEN")
    alpha = str(alpha_resolved.get("value") or "")
    news = str(news_resolved.get("value") or "")
    local_provider_token = str(local_provider_resolved.get("value") or "")
    local_provider_base_url_record = _config_value(stored, "SN_LOCAL_API_PROVIDER_BASE_URL")
    local_provider_enabled_record = _config_value(stored, "SN_LOCAL_API_PROVIDER_ENABLED")
    local_provider_id_record = _config_value(stored, "SN_LOCAL_API_PROVIDER_ID")
    local_provider_base_url = str(local_provider_base_url_record.get("value") or "")
    local_provider_enabled_value = str(local_provider_enabled_record.get("value") or "")
    local_provider_id = str(local_provider_id_record.get("value") or "custom_http_provider")
    tushare_token = str(tushare_resolved.get("value") or "")
    alpha_source = str(alpha_resolved.get("source") or "none")
    news_source = str(news_resolved.get("source") or "none")
    local_provider_source = str(local_provider_resolved.get("source") or "none")
    tushare_source = str(tushare_resolved.get("source") or "none")
    local_provider_warnings = _deprecated_warnings(
        local_provider_resolved,
        local_provider_base_url_record,
        local_provider_enabled_record,
        local_provider_id_record,
    )
    local_provider_enabled = bool(
        _is_truthy(local_provider_enabled_value)
        or local_provider_token
        or local_provider_base_url
    )
    local_provider_configured = bool(local_provider_token and local_provider_base_url)
    host = os.environ.get("SN_TERMINAL_HOST", "127.0.0.1")
    port = os.environ.get("SN_TERMINAL_PORT", "8765")
    api_base_url = os.environ.get("SN_TERMINAL_API_BASE_URL") or f"http://{host}:{port}"
    user_root = get_user_data_root()
    return {
        "success": True,
        "alpha_vantage_configured": bool(alpha),
        "newsapi_configured": bool(news),
        "local_api_provider_enabled": local_provider_enabled,
        "local_api_provider_configured": local_provider_configured,
        "local_api_provider_token_configured": bool(local_provider_token),
        "local_api_provider_base_url_configured": bool(local_provider_base_url),
        "local_api_provider_id": local_provider_id,
        "local_api_provider_id_source": str(local_provider_id_record.get("source") or "none"),
        "local_api_provider_base_url": local_provider_base_url,
        "local_api_provider_base_url_source": str(local_provider_base_url_record.get("source") or "none"),
        "local_api_provider_token_masked": mask_secret(local_provider_token) if local_provider_token else "",
        "local_api_provider_source": local_provider_source,
        "local_api_provider_deprecated": bool(local_provider_warnings),
        "local_api_provider_deprecated_warnings": local_provider_warnings,
        "managed_data_proxy_configured": bool(local_provider_token),
        "managed_data_proxy_endpoint_configured": bool(local_provider_base_url),
        "tushare_configured": bool(tushare_token),
        "alpha_vantage_masked": mask_secret(alpha) if alpha else "",
        "newsapi_masked": mask_secret(news) if news else "",
        "managed_data_proxy_masked": mask_secret(local_provider_token) if local_provider_token else "",
        "managed_data_proxy_endpoint": local_provider_base_url,
        "tushare_masked": mask_secret(tushare_token) if tushare_token else "",
        "alpha_vantage_source": alpha_source,
        "newsapi_source": news_source,
        "managed_data_proxy_source": local_provider_source,
        "tushare_source": tushare_source,
        "alpha_vantage_source_label_zh": _provider_label(alpha_source),
        "newsapi_source_label_zh": _provider_label(news_source),
        "local_api_provider_source_label_zh": _provider_label(local_provider_source),
        "managed_data_proxy_source_label_zh": _provider_label(local_provider_source),
        "tushare_source_label_zh": _provider_label(tushare_source),
        "alpha_vantage_ui_message_zh": _provider_message(alpha_source, bool(alpha)),
        "newsapi_ui_message_zh": _provider_message(news_source, bool(news)),
        "local_api_provider_ui_message_zh": _provider_message(local_provider_source, bool(local_provider_token)),
        "managed_data_proxy_ui_message_zh": _provider_message(local_provider_source, bool(local_provider_token)),
        "tushare_ui_message_zh": _provider_message(tushare_source, bool(tushare_token)),
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
    _validate_payload_keys(payload)
    existing = _read_secrets()
    updates: dict[str, str] = {}
    for name in ALLOWED_SECRET_KEYS:
        if name not in payload:
            continue
        value = _validate_secret(name, payload.get(name))
        if value is not None:
            updates[_canonical_secret_key(name)] = value
    config_updates: dict[str, str] = {}
    for name in ALLOWED_CONFIG_KEYS:
        if name not in payload:
            continue
        text = _validate_config_value(name, payload.get(name))
        if text:
            config_updates[_canonical_config_key(name)] = text
    if not updates and not config_updates:
        return {
            **get_terminal_settings_status(),
            "success": False,
            "message_zh": "没有可保存的密钥；空字符串不会写入配置。",
        }

    sources = existing.get("_sources") if isinstance(existing.get("_sources"), dict) else {}
    sources = {str(key): str(value) for key, value in sources.items()}
    for name in updates:
        sources[name] = "user_secrets"
    for name in config_updates:
        sources[name] = "user_secrets"

    merged = {
        **existing,
        **updates,
        **config_updates,
        "_sources": sources,
        "updated_at": datetime.now().isoformat(timespec="seconds"),
    }
    path = secrets_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(merged, ensure_ascii=False, indent=2), encoding="utf-8")
    for name, value in updates.items():
        os.environ[name] = value
    for name, value in config_updates.items():
        os.environ[name] = value
    return {**get_terminal_settings_status(), "success": True, "message_zh": "密钥已保存到本机用户目录。"}


def reset_terminal_secrets() -> dict[str, Any]:
    initialize_user_data_dir()
    for name in ALLOWED_SECRET_KEYS:
        os.environ.pop(name, None)
    for name in ALLOWED_CONFIG_KEYS:
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
    elif provider == "tushare":
        item = _read_status_file(root / "outputs" / "fundamentals" / "tushare_provider_status.json")
        code = str(item.get("status") or "")
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
            "deprecated": bool(resolved.get("deprecated")),
            "deprecated_warning": str(resolved.get("deprecated_warning") or ""),
            "can_read": configured,
            "last_validation_status": _validation_status(provider) if configured else "not_tested",
            "ui_message_zh": _provider_message(source, configured),
            "message_zh": "已读取本机配置，仅返回脱敏信息。" if configured else "未配置该数据源 key。",
        }

    return {
        "success": True,
            "alpha_vantage": row("SN_ALPHA_VANTAGE_KEY", "alpha_vantage"),
            "newsapi": row("SN_NEWSAPI_KEY", "newsapi"),
            "local_api_provider": row("SN_LOCAL_API_PROVIDER_TOKEN", "managed_proxy"),
            "managed_proxy": row("SN_MANAGED_DATA_PROXY_TOKEN", "managed_proxy"),
            "tushare": row("SN_TUSHARE_TOKEN", "tushare"),
        "message_zh": "key 诊断只返回来源和脱敏状态，不返回完整 key。",
    }
