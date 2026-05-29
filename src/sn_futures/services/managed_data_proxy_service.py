from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any

from ..api.json_utils import sanitize_for_json
from ..config import mask_secret
from ..runtime import get_user_output_dir


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _fundamentals_dir() -> Path:
    path = get_user_output_dir() / "fundamentals"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(sanitize_for_json(payload), ensure_ascii=False, indent=2), encoding="utf-8")


def managed_proxy_status() -> dict[str, Any]:
    enabled = os.getenv("SN_MANAGED_DATA_PROXY_ENABLED", "").strip().lower() in {"1", "true", "yes", "on"}
    token = os.getenv("SN_MANAGED_DATA_PROXY_TOKEN", "").strip()
    base_url = os.getenv("SN_MANAGED_DATA_PROXY_URL", "").strip()
    if not enabled:
        status = "disabled"
        message = "托管数据服务默认关闭；客户不需要 CSV/Excel。"
    elif not token:
        status = "token_missing"
        message = "托管数据服务已启用但缺 license token。"
    elif not base_url:
        status = "unavailable"
        message = "托管数据服务缺少服务器地址，本轮只实现客户端状态和接口。"
    else:
        status = "unavailable"
        message = "托管数据服务客户端已配置，但本轮未连接真实发行方服务器。"
    return {
        "source_name": "managed_data_proxy",
        "status": status,
        "success": False,
        "enabled": enabled,
        "configured": bool(token and base_url),
        "token_masked": mask_secret(token) if token else "",
        "base_url_configured": bool(base_url),
        "client_upload_required": False,
        "message_zh": message,
        "next_actions_zh": ["正式客户免配置推荐方案；第三方 API key 由发行方服务器维护，不写入公开安装包。"],
    }


def refresh_managed_data_proxy(force: bool = False) -> dict[str, Any]:
    _ = force
    out = _fundamentals_dir()
    status = managed_proxy_status()
    path = out / "managed_data_proxy_status.json"
    status["generated_at"] = _now()
    _write_json(path, status)
    return sanitize_for_json({"status": status["status"], "success": False, "output_files": [str(path)], **status})
