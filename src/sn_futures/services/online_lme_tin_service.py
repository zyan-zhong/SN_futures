from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from ..api.json_utils import sanitize_for_json
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


def refresh_online_lme_tin_data(force: bool = False) -> dict[str, Any]:
    _ = force
    out = _fundamentals_dir()
    data_path = out / "sn_lme_tin.json"
    status_path = out / "lme_tin_provider_status.json"
    status = {
        "source_name": "online_lme_tin",
        "status": "paid_or_unavailable",
        "success": False,
        "enabled": True,
        "configured": False,
        "row_count": 0,
        "missing_fields": ["lme_tin_close", "lme_tin_inventory"],
        "generated_at": _now(),
        "message_zh": "当前未发现可靠免费结构化 LME tin 数据源；不使用铜/铝替代，不从新闻价格入结构化因子。",
        "next_actions_zh": ["如需 LME tin close 或库存，请接入正式数据供应商或发行方托管数据服务。"],
        "client_upload_required": False,
        "paid_required": True,
    }
    _write_json(
        data_path,
        {
            "generated_at": _now(),
            "sample": False,
            "rows": [],
            "missing_fields": ["lme_tin_close", "lme_tin_inventory"],
            "message_zh": status["message_zh"],
        },
    )
    _write_json(status_path, status)
    return sanitize_for_json({"status": "paid_or_unavailable", "success": False, "output_files": [str(data_path), str(status_path)], **status})
