from __future__ import annotations

import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from .runtime import resource_path
from .user_data import initialize_user_data_dir, secrets_path
from .services.api_key_resolver import SECRET_KEYS, mask_key


PRIVATE_BUNDLE_SEED_NAME = "private_bundle_seed.json"
PRIVATE_BUNDLE_SOURCE = "private_bundle"


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists() or not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def private_bundle_seed_candidates() -> list[Path]:
    candidates: list[Path] = []
    if os.environ.get("SN_PRIVATE_BUNDLE_SEED"):
        candidates.append(Path(os.environ["SN_PRIVATE_BUNDLE_SEED"]).expanduser())
    if getattr(sys, "frozen", False):
        candidates.extend(
            [
                resource_path("private", PRIVATE_BUNDLE_SEED_NAME),
                resource_path("_internal", "private", PRIVATE_BUNDLE_SEED_NAME),
            ]
        )
    elif os.environ.get("SN_ALLOW_PROJECT_PRIVATE_BUNDLE_SEED") == "1":
        candidates.extend(
            [
                _project_root() / "build" / PRIVATE_BUNDLE_SEED_NAME,
                _project_root() / "packaging" / "private_bundle" / PRIVATE_BUNDLE_SEED_NAME,
            ]
        )
    seen: set[str] = set()
    out: list[Path] = []
    for candidate in candidates:
        key = str(candidate)
        if key not in seen:
            seen.add(key)
            out.append(candidate)
    return out


def load_private_bundle_seed() -> dict[str, Any]:
    for path in private_bundle_seed_candidates():
        payload = _read_json(path)
        secrets = payload.get("secrets") if isinstance(payload, dict) else None
        if not isinstance(secrets, dict):
            continue
        values = {name: str(secrets.get(name, "") or "").strip() for name in SECRET_KEYS}
        values = {name: value for name, value in values.items() if value}
        if values:
            return {
                "schema_version": payload.get("schema_version", 1),
                "source": PRIVATE_BUNDLE_SOURCE,
                "path": str(path),
                "secrets": values,
            }
    return {"source": "none", "secrets": {}}


def _read_user_secret_payload() -> dict[str, Any]:
    path = secrets_path()
    payload = _read_json(path)
    return payload if isinstance(payload, dict) else {}


def _secret_sources(payload: dict[str, Any]) -> dict[str, str]:
    raw = payload.get("_sources")
    if isinstance(raw, dict):
        return {str(key): str(value) for key, value in raw.items()}
    return {}


def import_private_bundle_keys_if_needed() -> dict[str, Any]:
    initialize_user_data_dir()
    seed = load_private_bundle_seed()
    seed_secrets = seed.get("secrets") if isinstance(seed, dict) else {}
    if not isinstance(seed_secrets, dict) or not seed_secrets:
        return {
            "success": True,
            "available": False,
            "imported": [],
            "skipped_existing": [],
            "message_zh": "未发现发行方预配置 key seed。",
        }

    payload = _read_user_secret_payload()
    sources = _secret_sources(payload)
    imported: list[dict[str, str]] = []
    skipped_existing: list[str] = []
    now = datetime.now().isoformat(timespec="seconds")

    for name in SECRET_KEYS:
        existing = str(payload.get(name, "") or "").strip()
        if existing:
            skipped_existing.append(name)
            continue
        value = str(seed_secrets.get(name, "") or "").strip()
        if not value:
            continue
        payload[name] = value
        sources[name] = PRIVATE_BUNDLE_SOURCE
        imported.append({"name": name, "masked": mask_key(value), "source": PRIVATE_BUNDLE_SOURCE})

    if imported:
        payload["_sources"] = sources
        payload["_private_bundle_imported_at"] = now
        payload["updated_at"] = now
        path = secrets_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        for item in imported:
            value = str(payload.get(item["name"], "") or "")
            if value:
                os.environ[item["name"]] = value

    return {
        "success": True,
        "available": True,
        "imported": imported,
        "skipped_existing": skipped_existing,
        "message_zh": "发行方预配置 key 已导入到本机用户目录。" if imported else "用户已配置 key，发行方默认 key 未覆盖。",
    }


def restore_private_bundle_defaults() -> dict[str, Any]:
    path = secrets_path()
    if path.exists():
        path.unlink()
    for name in SECRET_KEYS:
        os.environ.pop(name, None)
    return import_private_bundle_keys_if_needed()
