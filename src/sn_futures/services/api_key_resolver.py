from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from ..user_data import initialize_user_data_dir, secrets_path


SECRET_KEYS = ("SN_ALPHA_VANTAGE_KEY", "SN_NEWSAPI_KEY", "SN_MANAGED_DATA_PROXY_TOKEN")
PLACEHOLDER_VALUES = {
    "***",
    "****",
    "masked",
    "[masked]",
    "your_alpha_vantage_api_key_here",
    "your_newsapi_key_here",
}


def _project_root() -> Path:
    return Path(__file__).resolve().parents[3]


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
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def read_user_secrets() -> dict[str, str]:
    initialize_user_data_dir()
    raw = _read_json(secrets_path())
    values = {key: str(raw.get(key, "") or "").strip() for key in SECRET_KEYS}
    return {key: ("" if value in PLACEHOLDER_VALUES else value) for key, value in values.items()}


def read_user_secret_records() -> dict[str, dict[str, str]]:
    initialize_user_data_dir()
    raw = _read_json(secrets_path())
    sources = raw.get("_sources") if isinstance(raw.get("_sources"), dict) else {}
    records: dict[str, dict[str, str]] = {}
    for key in SECRET_KEYS:
        value = str(raw.get(key, "") or "").strip()
        if value in PLACEHOLDER_VALUES:
            value = ""
        if not value:
            continue
        source = str(sources.get(key) or "user_secrets")
        records[key] = {"value": value, "source": source}
    return records


def read_private_bundle_secrets() -> dict[str, str]:
    candidates = []
    if os.environ.get("SN_PRIVATE_BUNDLE_SECRETS"):
        candidates.append(Path(os.environ["SN_PRIVATE_BUNDLE_SECRETS"]).expanduser())
    root = _project_root()
    candidates.extend(
        [
            root / "private_bundle" / "secrets.json",
            root / "private_bundle" / "secrets.seed.json",
            root / "packaging" / "private_bundle" / "secrets.json",
        ]
    )
    for path in candidates:
        raw = _read_json(path)
        if raw:
            return {key: str(raw.get(key, "") or "").strip() for key in SECRET_KEYS}
    return {}


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
        value = value.strip().strip("\"'")
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

    env_value = str(os.environ.get(name, "") or "").strip()
    if env_value:
        return {"name": name, "configured": True, "source": "env", "value": env_value, "masked": mask_key(env_value)}

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
