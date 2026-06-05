from __future__ import annotations

import re
from typing import Any, Iterable, Mapping
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


SENSITIVE_KEY_HINTS = ("key", "token", "secret", "password", "authorization", "apikey", "api_key")
SENSITIVE_ENV_NAMES = (
    "SN_ALPHA_VANTAGE_KEY",
    "SN_ALPHA_VANTAGE_API_KEY",
    "SN_NEWSAPI_KEY",
    "SN_LOCAL_API_PROVIDER_TOKEN",
    "SN_MANAGED_DATA_PROXY_TOKEN",
    "SN_MANAGED_PROXY_TOKEN",
    "SN_TUSHARE_TOKEN",
    "SN_TWELVEDATA_API_KEY",
    "SN_FRED_API_KEY",
)
SAFE_SENSITIVE_METADATA_KEYS = {
    "base_url_configured",
    "enabled_configured",
    "endpoint_configured",
    "api_key_configured",
    "api_key_masked",
    "gitignore_secret_coverage",
    "key_configured",
    "key_masked",
    "key_source",
    "missing_provider_credentials",
    "no_raw_token_in_artifacts",
    "no_secret_echo_allowed",
    "token_configured",
    "token_masked",
}
SECRET_LIKE_RE = re.compile(
    r"(?i)(apikey|apiKey|api_key|x-api-key|x-sn-license-token|authorization|bearer|token|secret|password)(\s*[:=]\s*|%3D)[^&\s,;\"']+"
)
BEARER_RE = re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._\-]{8,}")
PROVIDER_ECHOED_KEY_RE = re.compile(
    r"(?i)(\bapi\s+key\s+(?:as|is|was detected as)\s+)([A-Za-z0-9._\-]{8,})"
)


def _apply_extra_secret_redaction(value: str, extra_secrets: Iterable[str] | None = None) -> str:
    cleaned = value
    for secret in extra_secrets or ():
        text = str(secret or "").strip()
        if len(text) >= 8:
            cleaned = cleaned.replace(text, "***")
    return cleaned


def sanitize_text(text: Any, extra_secrets: Iterable[str] | None = None) -> str:
    value = str(text or "")
    value = _apply_extra_secret_redaction(value, extra_secrets)
    for name in SENSITIVE_ENV_NAMES:
        value = re.sub(rf"(?i){re.escape(name)}\s*=\s*[^&\s,;\"']+", f"{name}=***", value)
    value = PROVIDER_ECHOED_KEY_RE.sub(lambda match: f"{match.group(1)}***", value)
    value = BEARER_RE.sub("Bearer ***", value)
    value = SECRET_LIKE_RE.sub(lambda match: f"{match.group(1)}{match.group(2)}***", value)
    return value


def sanitize_url(url: Any, extra_secrets: Iterable[str] | None = None) -> str:
    value = sanitize_text(url, extra_secrets=extra_secrets)
    try:
        parts = urlsplit(value)
    except Exception:
        return value
    if not parts.query:
        return value
    pairs = []
    for key, item in parse_qsl(parts.query, keep_blank_values=True):
        if any(hint in key.lower() for hint in SENSITIVE_KEY_HINTS):
            pairs.append((key, "***"))
        else:
            pairs.append((key, item))
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(pairs), parts.fragment))


def sanitize_mapping(obj: Any, extra_secrets: Iterable[str] | None = None) -> Any:
    if isinstance(obj, Mapping):
        cleaned: dict[str, Any] = {}
        for key, value in obj.items():
            lower = str(key).lower()
            if lower in SAFE_SENSITIVE_METADATA_KEYS:
                cleaned[str(key)] = sanitize_mapping(value, extra_secrets=extra_secrets)
            elif any(hint in lower for hint in SENSITIVE_KEY_HINTS):
                cleaned[str(key)] = "***" if value else ""
            elif "url" in lower:
                cleaned[str(key)] = sanitize_url(value, extra_secrets=extra_secrets)
            else:
                cleaned[str(key)] = sanitize_mapping(value, extra_secrets=extra_secrets)
        return cleaned
    if isinstance(obj, list):
        return [sanitize_mapping(item, extra_secrets=extra_secrets) for item in obj]
    if isinstance(obj, str):
        return sanitize_text(obj, extra_secrets=extra_secrets)
    return obj


def contains_secret_like_value(text: Any) -> bool:
    value = str(text or "")
    if SECRET_LIKE_RE.search(value) or BEARER_RE.search(value):
        return True
    return any(name in value for name in SENSITIVE_ENV_NAMES)
