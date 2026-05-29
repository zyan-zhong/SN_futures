from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any


APP_DIR_NAME = "SNInsightTerminal"
USER_SUBDIRS = ("data", "cache", "logs", "reports", "models", "config", "registry", "outputs")
DEFAULT_SETTINGS = {
    "created_by": "SNInsightTerminal",
    "created_at": "",
    "theme": "dark",
    "language": "zh-CN",
    "default_entry": "/terminal",
    "auto_open_browser": True,
}
DEFAULT_USER_CONFIG = {
    "market": "SHFE",
    "symbol": "SN",
    "contract_type": "main",
    "terminal_port_start": 8765,
    "terminal_port_end": 8769,
}
SECRETS_EXAMPLE = {
    "SN_ALPHA_VANTAGE_KEY": "your_alpha_vantage_api_key_here",
    "SN_NEWSAPI_KEY": "your_newsapi_key_here",
    "_note": "复制为 secrets.json 并填写本机密钥；不要提交真实密钥。",
}


def _safe_child(root: Path, *parts: str) -> Path:
    root_resolved = root.resolve()
    candidate = root_resolved.joinpath(*parts).resolve()
    try:
        candidate.relative_to(root_resolved)
    except ValueError as exc:
        raise ValueError("用户数据路径不合法") from exc
    return candidate


def get_user_data_root() -> Path:
    override = os.environ.get("SN_DATA_DIR") or os.environ.get("SN_INSIGHT_DATA_DIR")
    if override:
        root = Path(override).expanduser()
    elif os.name == "nt":
        base = Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local")
        root = base / APP_DIR_NAME
    else:
        root = Path.home() / ".sninsightterminal"
    root.mkdir(parents=True, exist_ok=True)
    return root


def user_path(*parts: str) -> Path:
    return _safe_child(get_user_data_root(), *parts)


def _write_json_if_missing(path: Path, payload: dict[str, Any]) -> None:
    if path.exists():
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    data = dict(payload)
    if not data.get("created_at"):
        data["created_at"] = datetime.now().isoformat(timespec="seconds")
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def initialize_user_data_dir() -> dict[str, Any]:
    root = get_user_data_root()
    created_dirs: list[str] = []
    for name in USER_SUBDIRS:
        target = _safe_child(root, name)
        target.mkdir(parents=True, exist_ok=True)
        created_dirs.append(str(target))

    settings_path = _safe_child(root, "config", "settings.json")
    user_config_path = _safe_child(root, "config", "user_config.json")
    secrets_example_path = _safe_child(root, "config", "secrets.example.json")
    _write_json_if_missing(settings_path, DEFAULT_SETTINGS)
    _write_json_if_missing(user_config_path, DEFAULT_USER_CONFIG)
    _write_json_if_missing(secrets_example_path, SECRETS_EXAMPLE)

    return {
        "root": str(root),
        "created_dirs": created_dirs,
        "settings_path": str(settings_path),
        "user_config_path": str(user_config_path),
        "secrets_example_path": str(secrets_example_path),
    }


def secrets_path() -> Path:
    return user_path("config", "secrets.json")


def settings_path() -> Path:
    return user_path("config", "settings.json")


def user_config_path() -> Path:
    return user_path("config", "user_config.json")
