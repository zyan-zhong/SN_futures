from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from ..api.json_utils import sanitize_for_json
from ..config import load_environment_config
from ..runtime import get_user_data_dir, get_user_output_dir
from ..user_data import initialize_user_data_dir, secrets_path, user_path


FORECAST_FILES = (
    "sn_unified_forecast.json",
    "sn_live_predictions.json",
    "sn_live_snapshot.json",
)
REPORT_FILES = (
    "sn_daily_report.md",
    "sn_weekly_report.md",
    "sn_monthly_report.md",
    "sn_event_report.md",
)
EVENT_DB_CANDIDATES = (
    ("event_store.sqlite", "event_store"),
    ("news_events.sqlite", "news_events"),
    ("events.sqlite", "event_store"),
)


def _iso_from_mtime(path: Path) -> str | None:
    try:
        return datetime.fromtimestamp(path.stat().st_mtime).isoformat(timespec="seconds")
    except Exception:
        return None


def _extract_cards(payload: Any) -> tuple[bool, int]:
    if not isinstance(payload, dict):
        return False, 0
    cards = payload.get("cards") or payload.get("predictions") or payload.get("prediction_cards")
    if isinstance(cards, dict):
        return bool(cards), len(cards)
    if isinstance(cards, list):
        return bool(cards), len(cards)
    return False, 0


def _extract_latest_price(payload: Any) -> tuple[bool, float | int | str | None]:
    if not isinstance(payload, dict):
        return False, None
    candidates = [
        payload.get("latest_price"),
        payload.get("last_price"),
        payload.get("price"),
        (payload.get("quote") or {}).get("latest_price") if isinstance(payload.get("quote"), dict) else None,
        (payload.get("latest_quote") or {}).get("latest_price") if isinstance(payload.get("latest_quote"), dict) else None,
        (payload.get("data_watermark") or {}).get("latest_price") if isinstance(payload.get("data_watermark"), dict) else None,
    ]
    for value in candidates:
        if value not in (None, "", "nan", "NaN"):
            return True, value
    return False, None


def _inspect_json(path: Path) -> dict[str, Any]:
    result: dict[str, Any] = {
        "json_valid": False,
        "has_cards": False,
        "card_count": 0,
        "has_quote": False,
        "latest_price": None,
    }
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        result["json_error"] = str(exc)
        return result
    has_cards, card_count = _extract_cards(payload)
    has_quote, latest_price = _extract_latest_price(payload)
    result.update(
        {
            "json_valid": True,
            "has_cards": has_cards,
            "card_count": card_count,
            "has_quote": has_quote,
            "latest_price": latest_price,
        }
    )
    return result


def _inspect_file(path: Path, *, relative_name: str) -> dict[str, Any]:
    status: dict[str, Any] = {
        "name": path.name,
        "relative_name": relative_name,
        "path": str(path),
        "exists": path.exists(),
        "size": 0,
        "modified_time": None,
    }
    if not path.exists():
        if path.suffix.lower() == ".json":
            status.update({"json_valid": False, "has_cards": False, "card_count": 0, "has_quote": False, "latest_price": None})
        if path.suffix.lower() == ".md":
            status["report_length"] = 0
        return status

    try:
        status["size"] = path.stat().st_size
        status["modified_time"] = _iso_from_mtime(path)
    except Exception:
        pass

    if path.suffix.lower() == ".json":
        status.update(_inspect_json(path))
    elif path.suffix.lower() == ".md":
        try:
            status["report_length"] = len(path.read_text(encoding="utf-8", errors="replace"))
        except Exception:
            status["report_length"] = 0
    return status


def _count_sqlite_table(path: Path, table: str) -> int:
    if not path.exists():
        return 0
    try:
        with sqlite3.connect(str(path)) as conn:
            cursor = conn.execute(f"select count(*) from {table}")
            row = cursor.fetchone()
            return int(row[0]) if row else 0
    except Exception:
        return 0


def _inspect_event_store(data_dir: Path) -> dict[str, Any]:
    stores: list[dict[str, Any]] = []
    total = 0
    for filename, table in EVENT_DB_CANDIDATES:
        path = data_dir / filename
        count = _count_sqlite_table(path, table)
        total += count
        stores.append(
            {
                "name": filename,
                "path": str(path),
                "exists": path.exists(),
                "table": table,
                "event_count": count,
            }
        )
    return {"stores": stores, "news_event_count": total, "has_news_events": total > 0}


def _service_status(path: str, fn: Callable[[], Any]) -> dict[str, Any]:
    try:
        payload = fn()
        return {
            "path": path,
            "success": True,
            "message_zh": "内部服务可调用",
            "payload_type": type(payload).__name__,
        }
    except Exception as exc:
        return {
            "path": path,
            "success": False,
            "message_zh": f"内部服务调用失败：{exc.__class__.__name__}",
        }


def _build_api_status() -> list[dict[str, Any]]:
    # Import lazily to avoid a circular import through terminal_api.
    from .terminal_service import (
        build_terminal_data_status,
        build_terminal_predictions,
        build_terminal_reports,
        build_terminal_summary,
        build_terminal_system_health,
    )

    return [
        _service_status("/api/terminal/summary", build_terminal_summary),
        _service_status("/api/terminal/predictions", lambda: {"predictions": build_terminal_predictions()}),
        _service_status("/api/terminal/data-status", build_terminal_data_status),
        _service_status("/api/terminal/reports", build_terminal_reports),
        _service_status("/api/terminal/system-health", build_terminal_system_health),
    ]


def _next_actions(conclusions: dict[str, bool], alpha_configured: bool, news_configured: bool) -> list[str]:
    actions: list[str] = []
    if not alpha_configured or not news_configured:
        actions.append("配置 API key，未配置时系统仍可启动但外部数据源会显示未配置")
    if conclusions.get("no_cache_files") or conclusions.get("no_predictions"):
        actions.append("运行数据刷新和预测生成任务，生成 sn_unified_forecast.json 或 sn_live_predictions.json")
    if conclusions.get("no_news_events"):
        actions.append("运行新闻/事件刷新任务，确认 NewsAPI 或本地事件库是否可用")
    if conclusions.get("no_reports"):
        actions.append("运行报告生成任务，生成日报、周报、月报或事件报告 Markdown")
    if conclusions.get("frontend_only_shell"):
        actions.append("当前更像是前端壳已启动但运行期数据尚未生成，请先完成数据刷新闭环")
    return actions or ["当前运行期数据文件存在，请进一步检查 provider 请求日志和模型任务日志"]


def build_runtime_data_diagnostics() -> dict[str, Any]:
    """Diagnose why the terminal may render without data, charts, news, or reports.

    This function is intentionally read-only. It does not fetch quotes, create
    predictions, synthesize news, or generate reports. It only inspects runtime
    files and service callability so the empty-terminal root cause is visible.
    """

    initialize_user_data_dir()
    env = load_environment_config()
    user_data_dir = get_user_data_dir()
    output_dir = get_user_output_dir()
    data_dir = user_path("data")
    report_dir = user_path("reports")
    cache_dir = user_path("cache")
    config_dir = user_path("config")

    expected_files: list[dict[str, Any]] = []
    for name in FORECAST_FILES:
        expected_files.append(_inspect_file(output_dir / name, relative_name=name))
    for name in REPORT_FILES:
        expected_files.append(_inspect_file(report_dir / name, relative_name=f"reports/{name}"))

    json_files = [item for item in expected_files if str(item.get("relative_name", "")).endswith(".json")]
    report_files = [item for item in expected_files if str(item.get("relative_name", "")).endswith(".md")]
    event_store = _inspect_event_store(data_dir)

    no_cache_files = not any(bool(item.get("exists")) for item in json_files)
    no_predictions = not any(bool(item.get("has_cards")) and int(item.get("card_count") or 0) > 0 for item in json_files)
    no_reports = not any(bool(item.get("exists")) and int(item.get("report_length") or 0) > 0 for item in report_files)
    no_news_events = not bool(event_store.get("has_news_events"))
    conclusions = {
        "no_cache_files": no_cache_files,
        "no_predictions": no_predictions,
        "no_reports": no_reports,
        "no_news_events": no_news_events,
        "no_provider_validation": True,
        "frontend_only_shell": no_predictions and no_reports and no_news_events,
    }

    payload = {
        "user_data_dir": str(user_data_dir),
        "output_dir": str(output_dir),
        "report_dir": str(report_dir),
        "cache_dir": str(cache_dir),
        "config_dir": str(config_dir),
        "secrets_path_exists": secrets_path().exists(),
        "alpha_vantage_configured": bool(os.environ.get("SN_ALPHA_VANTAGE_KEY") or env.alpha_vantage.enabled),
        "newsapi_configured": bool(os.environ.get("SN_NEWSAPI_KEY") or env.newsapi.enabled),
        "expected_output_files": expected_files,
        "event_store": event_store,
        "api_status": _build_api_status(),
        "data_gap_conclusion": conclusions,
        "next_actions_zh": _next_actions(conclusions, bool(env.alpha_vantage.enabled), bool(env.newsapi.enabled)),
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "disclaimer": "仅供沪锡期货量化投研参考，不构成投资建议，不承诺收益，不接实盘交易。",
    }
    return sanitize_for_json(payload)
