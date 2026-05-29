from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Mapping

SAMPLE_MESSAGE_ZH = "这是样例数据，仅用于演示界面结构，不代表真实行情或预测。"
SAMPLE_BANNER_ZH = "当前为样例数据模式，请点击一键刷新数据获取真实数据。"


def _candidate_roots() -> list[Path]:
    roots: list[Path] = []
    if getattr(sys, "frozen", False):
        roots.append(Path(getattr(sys, "_MEIPASS", Path.cwd())))
        roots.append(Path(sys.executable).resolve().parent)
    here = Path(__file__).resolve()
    roots.extend([here.parents[3], here.parents[2], Path.cwd()])
    return roots


def sample_data_dir() -> Path:
    for root in _candidate_roots():
        candidate = root / "sample_data"
        if candidate.exists():
            return candidate
    return _candidate_roots()[0] / "sample_data"


def read_sample_json(name: str) -> dict[str, Any]:
    path = sample_data_dir() / name
    if not path.exists():
        return {"sample": True, "message_zh": SAMPLE_MESSAGE_ZH}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {"sample": True, "message_zh": SAMPLE_MESSAGE_ZH}
    return payload if isinstance(payload, dict) else {"sample": True, "message_zh": SAMPLE_MESSAGE_ZH}


def read_sample_report(report_type: str) -> str:
    name = "sample_event_report.md" if report_type == "event" else "sample_daily_report.md"
    path = sample_data_dir() / "sample_reports" / name
    if not path.exists():
        return f"# 样例报告\n\n样例报告，不构成投资建议。\n\n{SAMPLE_MESSAGE_ZH}\n"
    return path.read_text(encoding="utf-8", errors="replace")


def sample_predictions() -> list[dict[str, Any]]:
    payload = read_sample_json("sample_predictions.json")
    rows = payload.get("predictions", [])
    if not isinstance(rows, list):
        return []
    out: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        item = dict(row)
        item["sample"] = True
        item["sample_mode"] = True
        item["message_zh"] = SAMPLE_MESSAGE_ZH
        item["signal"] = "观望"
        item["entry"] = None
        item["stop_loss"] = None
        item["take_profit"] = None
        item["trade_point_note"] = "暂无交易点位"
        out.append(item)
    return out


def sample_price_history() -> dict[str, Any]:
    payload = read_sample_json("sample_market_history.json")
    points = payload.get("points", [])
    return {
        "sample": True,
        "sample_mode": True,
        "sample_banner_zh": SAMPLE_BANNER_ZH,
        "message_zh": SAMPLE_MESSAGE_ZH,
        "symbol": payload.get("symbol", "SN"),
        "contract": payload.get("contract", "SN_SAMPLE"),
        "source": "sample_data",
        "data_quality_score": 0.0,
        "points": points if isinstance(points, list) else [],
        "disclaimer": "仅供沪锡期货量化投研参考，不构成投资建议，不承诺收益，不接实盘交易。",
    }


def sample_forecast_path() -> dict[str, Any]:
    payload = read_sample_json("sample_predictions.json")
    rows = payload.get("forecast_points", [])
    points = [dict(row, sample=True) for row in rows if isinstance(row, Mapping)] if isinstance(rows, list) else []
    return {
        "sample": True,
        "sample_mode": True,
        "sample_banner_zh": SAMPLE_BANNER_ZH,
        "horizons": sorted({str(row.get("horizon")) for row in points if row.get("horizon")}),
        "points": points,
        "message_zh": SAMPLE_MESSAGE_ZH,
        "disclaimer": "仅供沪锡期货量化投研参考，不构成投资建议，不承诺收益，不接实盘交易。",
    }


def sample_news_events() -> dict[str, Any]:
    payload = read_sample_json("sample_news_events.json")
    events = payload.get("events", [])
    return {
        "sample": True,
        "sample_mode": True,
        "sample_banner_zh": SAMPLE_BANNER_ZH,
        "events": events if isinstance(events, list) else [],
        "provider_status": {"name": "sample_data", "success": True, "sample": True},
        "message_zh": SAMPLE_MESSAGE_ZH,
        "disclaimer": "仅供沪锡期货量化投研参考，不构成投资建议，不承诺收益，不接实盘交易。",
    }


def sample_report_full(report_type: str = "daily") -> dict[str, Any]:
    report_type = report_type if report_type in {"daily", "weekly", "monthly", "event"} else "daily"
    markdown = read_sample_report("event" if report_type == "event" else "daily")
    title_map = {"daily": "样例日报", "weekly": "样例周报", "monthly": "样例月报", "event": "样例事件报告"}
    return {
        "sample": True,
        "sample_mode": True,
        "sample_banner_zh": SAMPLE_BANNER_ZH,
        "type": report_type,
        "title": title_map.get(report_type, "样例报告"),
        "generated_at": "样例时间",
        "data_cutoff": "样例数据，无真实截止时间",
        "markdown": markdown,
        "message_zh": SAMPLE_MESSAGE_ZH,
        "disclaimer": "仅供沪锡期货量化投研参考，不构成投资建议，不承诺收益，不接实盘交易。",
    }
