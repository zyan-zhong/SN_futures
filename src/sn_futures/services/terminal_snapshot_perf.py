from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from ..api.json_utils import sanitize_for_json
from ..api.schemas import DISCLAIMER
from ..runtime import get_user_output_dir
from .terminal_service import (
    build_terminal_backtest_diagnostics,
    build_terminal_data_status,
    build_terminal_learning_status,
    build_terminal_model_health,
    build_terminal_predictions,
    build_terminal_summary,
    build_terminal_system_health,
    _now,
)


def _build_lite_summary() -> dict[str, Any]:
    def read_json(path: Path) -> Mapping[str, Any]:
        if not path.exists():
            return {}
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return {}
        return payload if isinstance(payload, Mapping) else {}

    out = get_user_output_dir()
    watermark = read_json(out / "data_watermark.json")
    snapshot = read_json(out / "sn_live_snapshot.json")
    latest_price = watermark.get("latest_price") or snapshot.get("latest_price")
    return {
        "system_status": "connected",
        "data_quality_score": 0.0 if latest_price in (None, "") else 0.7,
        "data_quality_label": "waiting" if latest_price in (None, "") else "available",
        "main_contract": watermark.get("active_contract") or snapshot.get("active_contract") or "SN",
        "latest_price": latest_price,
        "price_change": None,
        "price_change_pct": None,
        "current_signal": "观望",
        "model_status": "research_only",
        "backtest_status": "research_only",
        "risk_level": "unknown",
        "last_update_time": watermark.get("quote_time") or watermark.get("generated_at") or snapshot.get("generated_at") or "",
        "disclaimer": DISCLAIMER,
    }


def _build_lite_refresh_status() -> dict[str, Any]:
    path = get_user_output_dir() / "refresh_status.json"
    if not path.exists():
        return {"status": "idle", "message_zh": "暂无刷新任务记录。", "steps": []}
    try:
        modified_at = path.stat().st_mtime
    except OSError:
        modified_at = 0.0
    return {
        "status": "available",
        "message_zh": "刷新任务详情请打开任务页或调用 /api/terminal/refresh/status。",
        "steps": [],
        "last_update_epoch": modified_at,
    }


def build_terminal_snapshot_lite() -> dict[str, Any]:
    summary = _build_lite_summary()
    snapshot = {
        "snapshot_mode": "lite",
        "generated_at": _now(),
        "cache_age_seconds": 0.0,
        "summary": summary,
        "refresh_status": _build_lite_refresh_status(),
        "omitted_components": [
            "predictions",
            "model_health",
            "learning_status",
            "backtest_diagnostics",
            "data_status",
            "system_health",
        ],
        "message_zh": "轻量快照只服务首屏连接；重模块由各页面独立加载或通过任务 API 执行。",
        "customer_prediction_generated": False,
        "disclaimer": DISCLAIMER,
    }
    if isinstance(summary, Mapping) and summary.get("sample_mode"):
        snapshot["sample"] = True
        snapshot["sample_mode"] = True
        snapshot["sample_banner_zh"] = summary.get("sample_banner_zh")
    return sanitize_for_json(snapshot)


def build_terminal_snapshot() -> dict[str, Any]:
    from .refresh_service import get_refresh_status

    summary = build_terminal_summary()
    snapshot = {
        "snapshot_mode": "heavy_cached",
        "generated_at": _now(),
        "summary": summary,
        "predictions": build_terminal_predictions(),
        "model_health": build_terminal_model_health(),
        "learning_status": build_terminal_learning_status(),
        "backtest_diagnostics": build_terminal_backtest_diagnostics(None),
        "data_status": build_terminal_data_status(),
        "system_health": build_terminal_system_health(),
        "refresh_status": get_refresh_status(),
        "customer_prediction_generated": False,
        "disclaimer": DISCLAIMER,
    }
    if isinstance(summary, Mapping) and summary.get("sample_mode"):
        snapshot["sample"] = True
        snapshot["sample_mode"] = True
        snapshot["sample_banner_zh"] = summary.get("sample_banner_zh")
    return sanitize_for_json(snapshot)
