from __future__ import annotations

import base64
import json
import os
import shutil
import zipfile
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from hashlib import sha256

from .config import AppSettings, ProjectPaths, load_project_env, resolve_app_settings
from .runtime import APP_NAME


def load_settings() -> AppSettings:
    paths = ProjectPaths()
    if not paths.settings_path.exists():
        return AppSettings()
    try:
        raw = json.loads(paths.settings_path.read_text(encoding="utf-8"))
    except Exception:
        return AppSettings()
    return resolve_app_settings(raw)


def save_settings(settings: AppSettings) -> Path:
    paths = ProjectPaths()
    paths.user_data_dir.mkdir(parents=True, exist_ok=True)
    paths.settings_path.write_text(
        json.dumps(asdict(settings), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return paths.settings_path


def _encryption_key() -> bytes:
    seed = f"{APP_NAME}|{Path.home()}|{os.environ.get('USERNAME', '')}"
    return sha256(seed.encode("utf-8")).digest()


def _xor_bytes(data: bytes, key: bytes) -> bytes:
    return bytes(value ^ key[idx % len(key)] for idx, value in enumerate(data))


def encrypt_secret(secret: str) -> str:
    if not secret:
        return ""
    encoded = _xor_bytes(secret.encode("utf-8"), _encryption_key())
    return base64.urlsafe_b64encode(encoded).decode("ascii")


def decrypt_secret(payload: str) -> str:
    if not payload:
        return ""
    try:
        raw = base64.urlsafe_b64decode(payload.encode("ascii"))
        return _xor_bytes(raw, _encryption_key()).decode("utf-8")
    except Exception:
        return ""


def load_api_keys() -> dict[str, str]:
    load_project_env()
    paths = ProjectPaths()
    if not paths.api_keys_path.exists():
        return {
            "SN_ALPHA_VANTAGE_KEY": os.environ.get("SN_ALPHA_VANTAGE_KEY", ""),
            "SN_NEWSAPI_KEY": os.environ.get("SN_NEWSAPI_KEY", ""),
            "SN_TUSHARE_TOKEN": os.environ.get("SN_TUSHARE_TOKEN", ""),
        }
    try:
        raw = json.loads(paths.api_keys_path.read_text(encoding="utf-8"))
    except Exception:
        raw = {}

    keys: dict[str, str] = {}
    for name in ("SN_ALPHA_VANTAGE_KEY", "SN_NEWSAPI_KEY", "SN_TUSHARE_TOKEN"):
        stored = str(raw.get(name, "") or "")
        decoded = decrypt_secret(stored) or stored
        keys[name] = os.environ.get(name, "") or decoded
    for name, value in keys.items():
        if value:
            os.environ[name] = value
        elif os.environ.get(name):
            keys[name] = os.environ.get(name, "")
    return keys


def save_api_keys(alpha_vantage_key: str, newsapi_key: str) -> Path:
    paths = ProjectPaths()
    paths.user_data_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "SN_ALPHA_VANTAGE_KEY": alpha_vantage_key.strip(),
        "SN_NEWSAPI_KEY": newsapi_key.strip(),
        "updated_at": datetime.now().isoformat(),
    }
    paths.api_keys_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    if alpha_vantage_key.strip():
        os.environ["SN_ALPHA_VANTAGE_KEY"] = alpha_vantage_key.strip()
    if newsapi_key.strip():
        os.environ["SN_NEWSAPI_KEY"] = newsapi_key.strip()
    return paths.api_keys_path


def missing_api_keys() -> list[str]:
    keys = load_api_keys()
    missing = [name for name, value in keys.items() if not value.strip()]
    return missing


def create_backup(label: str | None = None) -> Path:
    paths = ProjectPaths()
    paths.backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    suffix = f"_{label}" if label else ""
    archive_path = paths.backup_dir / f"sn_terminal_backup_{stamp}{suffix}.zip"
    exclude_roots = {paths.backup_dir.resolve()}
    with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        for file in paths.user_data_dir.rglob("*"):
            if not file.is_file():
                continue
            try:
                resolved = file.resolve()
            except OSError:
                continue
            if any(root in resolved.parents or resolved == root for root in exclude_roots):
                continue
            relative = resolved.relative_to(paths.user_data_dir.resolve())
            zf.write(resolved, arcname=str(relative))
    for stale in list_backups(limit=999)[5:]:
        try:
            stale.unlink()
        except OSError:
            pass
    return archive_path


def list_backups(limit: int = 10) -> list[Path]:
    paths = ProjectPaths()
    if not paths.backup_dir.exists():
        return []
    files = sorted(paths.backup_dir.glob("sn_terminal_backup_*.zip"), key=lambda p: p.stat().st_mtime, reverse=True)
    return files[:limit]
