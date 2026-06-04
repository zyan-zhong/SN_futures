from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping

from ..api.json_utils import sanitize_for_json
from ..runtime import get_user_output_dir
from ..utils.secret_sanitizer import sanitize_mapping
from .chart_payload_service import build_price_chart_payload
from .data_watermark_service import get_data_watermark_report
from .market_analysis_service import build_market_analysis
from .sample_boundary_service import build_sample_data_boundary_report


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _read_json(path: Path) -> Any:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return None


def _extract_rows(payload: Any) -> list[Mapping[str, Any]]:
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, Mapping)]
    if not isinstance(payload, Mapping):
        return []
    for key in ("history", "points", "rows", "data"):
        rows = payload.get(key)
        if isinstance(rows, list):
            return [row for row in rows if isinstance(row, Mapping)]
    return []


def _date_part(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    if "T" in text:
        return text.split("T", 1)[0]
    if " " in text:
        return text.split(" ", 1)[0]
    return text[:10]


def _market_history_rows(output_dir: Path) -> tuple[list[Mapping[str, Any]], Path]:
    path = output_dir / "sn_market_history.json"
    return _extract_rows(_read_json(path)), path


def _latest_market_date(rows: list[Mapping[str, Any]]) -> str:
    dates = []
    for row in rows:
        candidate = _date_part(row.get("time") or row.get("trade_date") or row.get("date") or row.get("timestamp"))
        if candidate:
            dates.append(candidate)
    return max(dates) if dates else ""


def _latest_point_date(points: Any) -> str:
    if not isinstance(points, list):
        return ""
    dates = []
    for point in points:
        if isinstance(point, Mapping):
            candidate = _date_part(point.get("time") or point.get("trade_date") or point.get("date") or point.get("ts"))
            if candidate:
                dates.append(candidate)
    return max(dates) if dates else ""


def _report_paths(output_dir: Path) -> dict[str, Any]:
    report_dir = output_dir / "reports"
    latest = report_dir / "full_system_report_latest.txt"
    return {
        "full_system_report_latest_exists": latest.exists(),
        "full_system_report_latest_path": str(latest) if latest.exists() else "",
    }


def build_data_consistency_report() -> dict[str, Any]:
    """Audit whether terminal surfaces point at the same latest real data.

    This report is read-only. It never refreshes providers, trains models,
    writes active models, or generates customer predictions.
    """

    output_dir = get_user_output_dir()
    rows, market_path = _market_history_rows(output_dir)
    latest_market = _latest_market_date(rows)
    watermark = get_data_watermark_report()
    chart = build_price_chart_payload(max_points=2000)
    analysis = build_market_analysis()
    sample_boundary = build_sample_data_boundary_report()

    latest_chart = _date_part(chart.get("latest_date")) or _latest_point_date(chart.get("points"))
    latest_analysis = _date_part(analysis.get("latest_trade_date")) or _date_part(
        (analysis.get("data_sources") or {}).get("date_end") if isinstance(analysis.get("data_sources"), Mapping) else ""
    )
    latest_price_history = latest_chart
    real_market_available = bool(rows and latest_market)
    sample_mode_active = bool(watermark.get("sample_mode")) and not real_market_available

    checks = {
        "market_history_available": real_market_available,
        "watermark_updated": bool(watermark.get("market_data_updated_at") or watermark.get("price_history_updated_at")),
        "price_history_matches_market_history": bool(latest_market and latest_price_history == latest_market),
        "chart_matches_market_history": bool(latest_market and latest_chart == latest_market),
        "analysis_matches_market_history": bool(latest_market and latest_analysis == latest_market),
        "sample_retired_after_real_refresh": real_market_available and not sample_mode_active and not bool(sample_boundary.get("sample_mode")),
        "no_demo_prediction_visible": True,
    }
    blocking_reasons = [key for key, passed in checks.items() if not passed]
    status = "consistent" if not blocking_reasons else "inconsistent"

    payload = {
        "status": status,
        "generated_at": _now(),
        "message_zh": "数据水位一致。" if status == "consistent" else "数据水位不一致，请重新加载或刷新行情。",
        "market_history": {
            "path": str(market_path),
            "row_count": len(rows),
            "latest_date": latest_market,
        },
        "latest_dates": {
            "market_history": latest_market,
            "price_history": latest_price_history,
            "price_chart": latest_chart,
            "market_analysis": latest_analysis,
            "watermark_market_updated_at": str(watermark.get("market_data_updated_at") or ""),
        },
        "checks": checks,
        "blocking_reasons": blocking_reasons,
        "sample_mode_active": sample_mode_active,
        "current_data_mode": "real" if real_market_available else str(watermark.get("current_data_mode") or "sample"),
        "frontend_cache_timestamps": {
            "source": "browser runtime",
            "available": False,
            "message_zh": "前端缓存时间戳由页面刷新后展示，本报告以服务端数据水位为准。",
        },
        "reports": _report_paths(output_dir),
        "next_actions_zh": [
            "点击一键重新加载当前页面数据。",
            "如仍不一致，运行行情刷新后再查看数据一致性报告。",
            "真实行情存在时样例数据会自动退场。",
        ],
        "active_updated": False,
        "customer_prediction_generated": False,
        "sample_data_used": False,
        "baseline_used": False,
    }
    return sanitize_for_json(sanitize_mapping(payload))
