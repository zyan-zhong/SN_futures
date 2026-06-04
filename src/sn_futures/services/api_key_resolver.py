from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from ..user_data import initialize_user_data_dir, secrets_path


SECRET_KEYS = ("SN_ALPHA_VANTAGE_KEY", "SN_NEWSAPI_KEY", "SN_MANAGED_DATA_PROXY_TOKEN", "SN_TUSHARE_TOKEN")
PLACEHOLDER_VALUES = {
    "***",
    "****",
    "masked",
    "[masked]",
    "your_alpha_vantage_api_key_here",
    "your_newsapi_key_here",
    "your_tushare_token_here",
    "<本机真实 Tushare token>",
    "<本机真实 tushare token>",
    "<your_tushare_token>",
}


def _project_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _has_explicit_data_dir() -> bool:
    return bool(str(os.environ.get("SN_DATA_DIR") or "").strip())


def mask_key(value: str | None) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    if len(text) <= 8:
        return "***"
    return f"{text[:2]}***{text[-2:]}"


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _is_placeholder_secret(value: Any) -> bool:
    text = str(value or "").strip()
    if not text:
        return True
    lower = text.lower()
    if lower in {item.lower() for item in PLACEHOLDER_VALUES}:
        return True
    if set(text) <= {"*"}:
        return True
    if lower in {"configured", "not_configured", "source", "masked", "redacted"}:
        return True
    return False


def _clean_secret_value(value: Any) -> str:
    text = str(value or "").strip()
    return "" if _is_placeholder_secret(text) else text


def read_user_secrets() -> dict[str, str]:
    initialize_user_data_dir()
    raw = _read_json(secrets_path())
    return {key: _clean_secret_value(raw.get(key, "")) for key in SECRET_KEYS}


def read_user_secret_records() -> dict[str, dict[str, str]]:
    initialize_user_data_dir()
    raw = _read_json(secrets_path())
    sources = raw.get("_sources") if isinstance(raw.get("_sources"), dict) else {}
    records: dict[str, dict[str, str]] = {}
    for key in SECRET_KEYS:
        value = _clean_secret_value(raw.get(key, ""))
        if not value:
            continue
        source = str(sources.get(key) or "user_secrets")
        records[key] = {"value": value, "source": source}
    return records


def _private_secret_candidates() -> list[tuple[Path, str]]:
    candidates: list[tuple[Path, str]] = []
    if os.environ.get("SN_PRIVATE_RELEASE_KEYS"):
        candidates.append((Path(os.environ["SN_PRIVATE_RELEASE_KEYS"]).expanduser(), "private_release_keys"))
    if os.environ.get("SN_PRIVATE_BUNDLE_SECRETS"):
        candidates.append((Path(os.environ["SN_PRIVATE_BUNDLE_SECRETS"]).expanduser(), "private_bundle"))
    root = _project_root()
    if not _has_explicit_data_dir():
        candidates.extend(
            [
                (root / "packaging" / "private_release_keys.json", "private_release_keys"),
                (root / "private_bundle" / "secrets.json", "private_bundle"),
                (root / "private_bundle" / "secrets.seed.json", "private_bundle"),
                (root / "packaging" / "private_bundle" / "secrets.json", "private_bundle"),
            ]
        )
    return candidates


def read_private_secret_records() -> dict[str, dict[str, str]]:
    project_private_keys = _project_root() / "packaging" / "private_release_keys.json"
    for path, source in _private_secret_candidates():
        raw = _read_json(path)
        if not raw:
            continue
        secrets = raw.get("secrets") if isinstance(raw.get("secrets"), dict) else raw
        allowed_keys = ("SN_TUSHARE_TOKEN",) if source == "private_release_keys" and path == project_private_keys else SECRET_KEYS
        values = {key: _clean_secret_value(secrets.get(key, "")) for key in allowed_keys}
        records = {key: {"value": value, "source": source} for key, value in values.items() if value}
        if records:
            return records
    return {}


def read_private_bundle_secrets() -> dict[str, str]:
    records = read_private_secret_records()
    return {key: record["value"] for key, record in records.items()}


def read_project_env_values() -> dict[str, str]:
    path = _project_root() / ".env"
    if not path.exists():
        return {}
    values: dict[str, str] = {}
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except Exception:
        return {}
    for line in lines:
        text = line.strip()
        if not text or text.startswith("#") or "=" not in text:
            continue
        key, value = text.split("=", 1)
        key = key.strip()
        if key not in SECRET_KEYS:
            continue
        value = _clean_secret_value(value.strip().strip("\"'"))
        values[key] = value
    return values


def resolve_secret(name: str) -> dict[str, Any]:
    """Resolve one sensitive setting without returning it to public API callers.

    Priority is intentionally runtime-first:
    user secrets (including imported private bundle defaults) -> environment -> development .env.
    The bundled seed is only a first-run import source and is not read directly by providers.
    """

    if name not in SECRET_KEYS:
        return {"name": name, "configured": False, "source": "none", "value": "", "masked": ""}

    user_record = read_user_secret_records().get(name, {})
    user_value = str(user_record.get("value") or "")
    if user_value:
        source = str(user_record.get("source") or "user_secrets")
        return {"name": name, "configured": True, "source": source, "value": user_value, "masked": mask_key(user_value)}

    private_record = read_private_secret_records().get(name, {})
    private_value = str(private_record.get("value") or "")
    if private_value:
        source = str(private_record.get("source") or "private_bundle")
        return {"name": name, "configured": True, "source": source, "value": private_value, "masked": mask_key(private_value)}

    env_value = _clean_secret_value(os.environ.get(name, ""))
    if env_value:
        return {"name": name, "configured": True, "source": "env", "value": env_value, "masked": mask_key(env_value)}

    if not _has_explicit_data_dir():
        env_file_value = read_project_env_values().get(name, "")
        if env_file_value:
            return {"name": name, "configured": True, "source": ".env", "value": env_file_value, "masked": mask_key(env_file_value)}

    return {"name": name, "configured": False, "source": "none", "value": "", "masked": ""}


def resolved_secret_value(name: str) -> str:
    return str(resolve_secret(name).get("value") or "")


def inject_resolved_secrets_into_environment() -> dict[str, str]:
    loaded: dict[str, str] = {}
    for name in SECRET_KEYS:
        resolved = resolve_secret(name)
        value = str(resolved.get("value") or "")
        if value:
            os.environ[name] = value
            loaded[name] = value
    return loaded
