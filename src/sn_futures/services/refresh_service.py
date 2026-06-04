from __future__ import annotations

import json
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Callable

from ..api.json_utils import sanitize_for_json
from ..config import load_environment_config
from ..data_providers.newsapi_provider import NewsApiProvider
from ..event_store import ingest_articles, load_events, update_provider_status
from ..runtime import get_user_output_dir
from ..user_data import initialize_user_data_dir, user_path
from ..utils.secret_sanitizer import sanitize_mapping


DISCLAIMER = "仅供沪锡期货量化投研参考，不构成投资建议，不承诺收益，不接实盘交易。"
_LOCK = threading.Lock()
HORIZONS = (
    "next_5m",
    "next_15m",
    "next_30m",
    "next_hour",
    "tomorrow",
    "one_to_two_weeks",
    "one_to_three_months",
)


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _outputs_dir() -> Path:
    initialize_user_data_dir()
    path = get_user_output_dir()
    path.mkdir(parents=True, exist_ok=True)
    return path


def _events_dir() -> Path:
    path = _outputs_dir() / "events"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _reports_dir() -> Path:
    path = user_path("reports")
    path.mkdir(parents=True, exist_ok=True)
    return path


def _status_path() -> Path:
    return _outputs_dir() / "refresh_status.json"


def _history_path() -> Path:
    return _outputs_dir() / "refresh_history.json"


def _refresh_log_path() -> Path:
    path = user_path("logs") / f"refresh_{datetime.now().strftime('%Y%m%d')}.log"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(sanitize_for_json(sanitize_mapping(payload)), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _read_json(path: Path) -> Any:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _append_history(run: dict[str, Any]) -> None:
    path = _history_path()
    history = _read_json(path)
    rows = history if isinstance(history, list) else []
    rows.append(run)
    _write_json(path, rows[-50:])


def _append_refresh_log(record: dict[str, Any]) -> None:
    try:
        with _refresh_log_path().open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(sanitize_for_json(record), ensure_ascii=False) + "\n")
    except Exception:
        return


def _default_next_actions(step_name: str, step_status: str) -> list[str]:
    if step_status == "success":
        return ["查看数据源状态", "继续生成预测或报告"]
    if step_name == "market":
        return ["检查网络连接", "确认是否处于非交易时段", "查看行情 provider 明细", "如有缓存可继续使用缓存"]
    if step_name == "news":
        return ["检查 NewsAPI 是否配置", "检查 key 是否有效或被限流", "稍后重试新闻刷新"]
    if step_name == "reports":
        return ["先运行一键刷新数据", "确认预测或行情缓存是否存在"]
    return ["查看刷新日志", "运行运行期诊断", "稍后重试"]


def _enrich_step_observability(step_name: str, status: dict[str, Any]) -> dict[str, Any]:
    provider_attempts = status.get("provider_attempts")
    if provider_attempts is None:
        provider_attempts = status.get("provider_chain_status") or status.get("query_attempts") or []
    if not isinstance(provider_attempts, list):
        provider_attempts = []
    step_status = str(status.get("status") or "unknown")
    row_count = status.get("row_count") or status.get("fetched_count") or status.get("inserted_count") or 0
    status.setdefault("provider_attempts", provider_attempts)
    status.setdefault("used_symbol", status.get("symbol_used") or "")
    status.setdefault("request_params_sanitized", {})
    status.setdefault("status_code", step_status)
    status.setdefault("row_count", int(row_count or 0))
    status.setdefault("cache_hit", bool(status.get("from_cache")))
    status.setdefault("cache_age", None)
    status.setdefault("last_success_time", status.get("finished_at") if step_status == "success" else "")
    status.setdefault("last_error_time", status.get("finished_at") if step_status == "failed" else "")
    status.setdefault("error_type", "none" if step_status == "success" else step_status)
    status.setdefault("error_message_zh", str(status.get("error") or ""))
    status.setdefault("next_actions_zh", _default_next_actions(step_name, step_status))
    return status


def _step(name: str, fn: Callable[[], dict[str, Any]]) -> dict[str, Any]:
    started = time.perf_counter()
    status: dict[str, Any] = {
        "step_name": name,
        "status": "running",
        "started_at": _now(),
        "finished_at": "",
        "duration_seconds": None,
        "message_zh": "正在执行",
        "output_files": [],
        "error": "",
    }
    try:
        result = fn()
        status.update(result)
        status.setdefault("status", "success")
    except Exception as exc:
        status.update(
            {
                "status": "failed",
                "message_zh": f"{name} 刷新失败，已保留可用缓存。",
                "error": str(exc),
            }
        )
    status["finished_at"] = _now()
    status["duration_seconds"] = round(time.perf_counter() - started, 3)
    status = _enrich_step_observability(name, status)
    _append_refresh_log(status)
    return sanitize_for_json(status)


def _data_quality_from_history(history: list[dict[str, Any]], latest_price: float | None) -> float:
    score = 0.0
    if latest_price and latest_price > 0:
        score += 0.45
    if history:
        score += min(0.45, len(history) / 120.0)
    return round(min(1.0, score), 4)


def refresh_market_data(force: bool = False) -> dict[str, Any]:
    """Refresh market data from the existing v2 API/cache path without fabricating quotes."""
    from .. import v2_api

    out = _outputs_dir()
    latest = v2_api.get_market_latest(force_refresh=force)
    history_payload = v2_api.get_market_history()
    history = history_payload.get("history") if isinstance(history_payload.get("history"), list) else []
    quote = latest.get("latest_quote") if isinstance(latest.get("latest_quote"), dict) else {}
    latest_price = latest.get("price") or quote.get("latest") or quote.get("price")
    active_contract = (
        (latest.get("data_watermark") or {}).get("active_contract")
        if isinstance(latest.get("data_watermark"), dict)
        else None
    )
    quality = _data_quality_from_history(history, float(latest_price or 0) if latest_price else None)

    snapshot = {
        "generated_at": _now(),
        "latest_quote": quote,
        "active_contract": active_contract or latest.get("symbol") or "SN",
        "latest_price": latest_price or None,
        "quote_time": latest.get("source_timestamp") or quote.get("quote_time") or "",
        "history": history,
        "source_status": [
            {
                "provider": "本地行情缓存",
                "success": bool(latest_price or history),
                "message": "行情缓存可用" if (latest_price or history) else "未找到可用行情缓存",
            }
        ],
        "data_quality_score": quality,
        "disclaimer": DISCLAIMER,
    }
    history_file = out / "sn_market_history.json"
    snapshot_file = out / "sn_live_snapshot.json"
    watermark_file = out / "data_watermark.json"
    _write_json(history_file, {"history": history, "generated_at": _now(), "disclaimer": DISCLAIMER})
    _write_json(snapshot_file, snapshot)
    _write_json(
        watermark_file,
        {
            "generated_at": _now(),
            "latest_price": latest_price or None,
            "quote_time": snapshot["quote_time"],
            "data_quality_score": quality,
            "source": "本地行情缓存",
        },
    )

    if not latest_price and not history:
        return {
            "status": "failed",
            "message_zh": "未找到可用行情缓存，未生成假行情。",
            "output_files": [str(snapshot_file), str(history_file), str(watermark_file)],
        }
    return {
        "status": "success",
        "message_zh": "行情刷新完成。",
        "output_files": [str(snapshot_file), str(history_file), str(watermark_file)],
    }


def _classify_article(article: dict[str, Any]) -> dict[str, Any]:
    text = " ".join(str(article.get(key) or "") for key in ("title", "description", "content")).lower()
    if any(word in text for word in ("myanmar", "wa state", "indonesia", "export permit", "smelter")):
        category = "supply"
        impact = 0.55
    elif any(word in text for word in ("semiconductor", "photovoltaic", "solder")):
        category = "demand"
        impact = 0.45
    elif "inventory" in text:
        category = "inventory"
        impact = 0.45
    elif any(word in text for word in ("fomc", "rate", "dollar", "treasury")):
        category = "macro"
        impact = 0.40
    else:
        category = "other"
        impact = 0.25
    return {
        "title": article.get("title", ""),
        "source": (article.get("source") or {}).get("name", "")
        if isinstance(article.get("source"), dict)
        else article.get("source", ""),
        "published_at": article.get("publishedAt") or article.get("published_at") or "",
        "url": article.get("url", ""),
        "description": article.get("description", ""),
        "sentiment_score": 0.0,
        "impact_score": impact,
        "category": category,
        "query_group": article.get("query_group", "unknown"),
        "query_language": article.get("query_language", ""),
        "query_sort_by": article.get("query_sort_by", ""),
        "query_window_days": article.get("query_window_days", ""),
    }


def refresh_news_data(force: bool = False, provider: NewsApiProvider | None = None) -> dict[str, Any]:
    """Refresh NewsAPI articles when configured; otherwise record a skipped step."""
    _ = force
    events_dir = _events_dir()
    provider_status_path = events_dir / "provider_status.json"
    news_provider_status_path = events_dir / "news_provider_status.json"
    raw_path = events_dir / "news_raw.json"
    news_events_path = events_dir / "news_events.json"
    provider = provider or NewsApiProvider()
    result = provider.fetch_tin_news(page_size=50)
    if result.get("configured") is False or (not result.get("configured") and result.get("enabled") is False):
        status = result
        provider_payload = {"providers": [status], "updated_at": _now()}
        _write_json(provider_status_path, provider_payload)
        _write_json(news_provider_status_path, provider_payload)
        return {
            "status": "skipped",
            "message_zh": "未配置 NewsAPI，已跳过新闻刷新。",
            "output_files": [str(provider_status_path), str(news_provider_status_path)],
        }
    articles = result.get("articles") if isinstance(result.get("articles"), list) else []
    events = [_classify_article(row) for row in articles if isinstance(row, dict)]
    _write_json(
        raw_path,
        {
            "articles": articles,
            "query_attempts": result.get("query_attempts", []),
            "provider": "newsapi",
            "generated_at": _now(),
            "disclaimer": DISCLAIMER,
        },
    )
    _write_json(news_events_path, {"events": events, "generated_at": _now(), "disclaimer": DISCLAIMER})
    provider_payload = {"providers": [result], "updated_at": _now()}
    _write_json(provider_status_path, provider_payload)
    _write_json(news_provider_status_path, provider_payload)
    update_provider_status(
        [
            {
                "provider": "newsapi",
                "source_tier": "tier2",
                "success": bool(result.get("success")),
                "message": result.get("message", ""),
                "fetched_count": len(articles),
                "inserted_count": len(events),
                "updated_at": _now(),
            }
        ]
    )
    if not result.get("success"):
        return {
            "status": "failed",
            "message_zh": f"NewsAPI 刷新失败：{result.get('message', '未知错误')}",
            "output_files": [str(raw_path), str(news_events_path), str(provider_status_path), str(news_provider_status_path)],
        }
    return {
        "status": "success",
        "message_zh": str(result.get("message_zh") or f"新闻刷新完成，返回 {len(articles)} 条。"),
        "output_files": [str(raw_path), str(news_events_path), str(provider_status_path), str(news_provider_status_path)],
    }


def refresh_event_store() -> dict[str, Any]:
    events_dir = _events_dir()
    news_events_path = events_dir / "news_events.json"
    event_store_path = events_dir / "event_store.json"
    evidence_path = events_dir / "event_evidence_by_horizon.json"
    payload = _read_json(news_events_path)
    rows = payload.get("events", []) if isinstance(payload, dict) and isinstance(payload.get("events"), list) else []
    rows = [
        row for row in rows
        if isinstance(row, dict) and row.get("used_in_model", row.get("allowed_for_event_factor", True)) is True
    ]
    if rows:
        articles = [
            {
                "title": row.get("title", ""),
                "description": row.get("description", ""),
                "url": row.get("url", ""),
                "publishedAt": row.get("published_at", ""),
                "source": {"name": row.get("source", "NewsAPI")},
            }
            for row in rows
            if isinstance(row, dict)
        ]
        inserted = ingest_articles(articles, batch_id=_now())
    else:
        inserted = 0

    recent_events = load_events(limit=200)
    _write_json(
        event_store_path,
        {
            "events": recent_events,
            "generated_at": _now(),
            "message_zh": "暂无新闻事件" if not recent_events else "事件 store 已更新",
            "disclaimer": DISCLAIMER,
        },
    )
    evidence_by_horizon = {
        horizon: {"events": recent_events[:20], "event_count": len(recent_events), "message_zh": "事件证据已刷新"}
        for horizon in HORIZONS
    }
    _write_json(evidence_path, evidence_by_horizon)
    return {
        "status": "success",
        "message_zh": f"事件 store 刷新完成，写入或更新 {inserted} 条；当前可读事件 {len(recent_events)} 条。",
        "output_files": [str(event_store_path), str(evidence_path)],
    }


def refresh_features() -> dict[str, Any]:
    events_dir = _events_dir()
    path = events_dir / "feature_refresh_status.json"
    event_payload = _read_json(events_dir / "event_store.json")
    event_count = (
        len(event_payload.get("events", []))
        if isinstance(event_payload, dict) and isinstance(event_payload.get("events"), list)
        else 0
    )
    payload = {
        "generated_at": _now(),
        "status": "success",
        "event_feature_nonzero_possible": event_count > 0,
        "event_count": event_count,
        "message_zh": "特征刷新状态已记录；实际模型特征在训练/预测链路中构建。",
        "disclaimer": DISCLAIMER,
    }
    _write_json(path, payload)
    return {"status": "success", "message_zh": payload["message_zh"], "output_files": [str(path)]}


def refresh_predictions() -> dict[str, Any]:
    """Refresh prediction cache. Empty predictions are explicit and never replaced with fake cards."""
    from .. import v2_api

    out = _outputs_dir()
    market_status = _read_json(out / "market_provider_status.json")
    history_payload = _read_json(out / "sn_market_history.json")
    history_rows = 0
    if isinstance(history_payload, dict):
        rows = history_payload.get("points") or history_payload.get("history")
        history_rows = len(rows) if isinstance(rows, list) else int(history_payload.get("row_count") or 0)
    final_status = str(market_status.get("final_status") or "") if isinstance(market_status, dict) else ""
    skip_reason = ""
    if final_status == "cache_only":
        skip_reason = "当前仅有缓存行情，未生成新的真实预测。"
    elif history_rows < 60:
        skip_reason = "数据不足，未生成预测：真实历史行情不足 60 条，未生成预测/回测。"
    if skip_reason:
        cards = {}
        payload = {
            "cards": {},
            "generated_at": _now(),
            "data_watermark": v2_api.get_data_watermark(out),
            "market_final_status": final_status,
            "history_rows": history_rows,
            "message_zh": skip_reason,
            "disclaimer": DISCLAIMER,
        }
    else:
        payload = v2_api.get_live_predictions(out)
        cards = payload.get("cards") if isinstance(payload.get("cards"), dict) else {}
        if not cards:
            skip_reason = "暂无可用 active 模型或有效预测结果，未生成预测。"
        elif payload.get("sample_mode") or payload.get("sample"):
            skip_reason = "当前为样例模式，未生成真实预测。"
        if skip_reason:
            cards = {}
            payload = {
                "cards": {},
                "generated_at": _now(),
                "data_watermark": v2_api.get_data_watermark(out),
                "market_final_status": final_status,
                "history_rows": history_rows,
                "message_zh": skip_reason,
                "disclaimer": DISCLAIMER,
            }
    unified_path = out / "sn_unified_forecast.json"
    live_path = out / "sn_live_predictions.json"
    _write_json(unified_path, payload)
    _write_json(live_path, payload)
    if not cards:
        return {
            "status": "skipped",
            "message_zh": skip_reason or "数据不足，未生成预测。",
            "output_files": [str(unified_path), str(live_path)],
            "history_rows": history_rows,
            "market_final_status": final_status,
        }
    return {
        "status": "success",
        "message_zh": f"预测刷新完成，生成 {len(cards)} 个周期卡片。",
        "output_files": [str(unified_path), str(live_path)],
    }


def _insufficient_report(report_type: str, reason: str) -> str:
    return "\n".join(
        [
            f"# 沪锡期货{report_type}报告",
            "",
            f"- 报告生成时间：{_now()}",
            "- 数据截止时间：数据暂缺",
            "- 报告状态：数据不足版报告",
            "",
            "## 当前状态",
            reason,
            "",
            "## 下一步",
            "- 请先运行一键刷新数据。",
            "- 如需外部新闻和宏观数据，请在设置页配置 API key。",
            "- 若行情缓存仍为空，请检查数据源或本地日志。",
            "",
            "## 合规声明",
            DISCLAIMER,
        ]
    )


def refresh_reports() -> dict[str, Any]:
    from .. import v2_api

    report_dir = _reports_dir()
    outputs: list[str] = []
    cards = v2_api.get_live_predictions().get("cards", {})
    insufficient = not bool(cards)
    for report_type, filename in {
        "daily": "sn_daily_report.md",
        "weekly": "sn_weekly_report.md",
        "monthly": "sn_monthly_report.md",
        "event": "sn_event_report.md",
    }.items():
        if insufficient:
            markdown = _insufficient_report(report_type, "数据不足，未生成有效预测；本报告不包含方向或收益结论。")
        else:
            try:
                markdown = str(v2_api.get_report_content(report_type).get("markdown") or "")
            except Exception:
                markdown = ""
            if not markdown:
                markdown = _insufficient_report(report_type, "报告服务暂未返回正文。")
        path = report_dir / filename
        path.write_text(markdown.replace("nan", "数据暂缺"), encoding="utf-8")
        outputs.append(str(path))
    return {
        "status": "success",
        "message_zh": "报告刷新完成。" if not insufficient else "已生成数据不足版报告。",
        "output_files": outputs,
    }


def _run_steps(step_names: list[str], *, force: bool = False) -> dict[str, Any]:
    funcs: dict[str, Callable[[], dict[str, Any]]] = {
        "market": lambda: refresh_market_data(force=force),
        "news": lambda: refresh_news_data(force=force),
        "events": refresh_event_store,
        "features": refresh_features,
        "predictions": refresh_predictions,
        "reports": refresh_reports,
    }
    run: dict[str, Any] = {
        "run_id": f"refresh-{int(time.time())}",
        "started_at": _now(),
        "finished_at": "",
        "status": "running",
        "steps": [],
        "message_zh": "刷新任务执行中",
    }
    _write_json(_status_path(), run)
    for name in step_names:
        if name not in funcs:
            run["steps"].append(
                {
                    "step_name": name,
                    "status": "failed",
                    "started_at": _now(),
                    "finished_at": _now(),
                    "duration_seconds": 0,
                    "message_zh": "未知刷新步骤",
                    "output_files": [],
                    "error": name,
                }
            )
        else:
            run["steps"].append(_step(name, funcs[name]))
        _write_json(_status_path(), run)
    failed = [step for step in run["steps"] if step.get("status") == "failed"]
    run["status"] = "failed" if failed else "success"
    run["message_zh"] = "部分刷新步骤失败，已保留可用缓存。" if failed else "刷新任务完成。"
    run["finished_at"] = _now()
    _write_json(_status_path(), run)
    _append_history(run)
    return sanitize_for_json(run)


def run_refresh_all(force: bool = False) -> dict[str, Any]:
    if not _LOCK.acquire(blocking=False):
        return {"status": "running", "message_zh": "已有刷新任务正在执行，请稍后再试。", "steps": []}
    try:
        return _run_steps(["market", "news", "events", "features", "predictions", "reports"], force=force)
    finally:
        _LOCK.release()


def run_refresh_steps(step_names: list[str], *, force: bool = False) -> dict[str, Any]:
    if not _LOCK.acquire(blocking=False):
        return {"status": "running", "message_zh": "已有刷新任务正在执行，请稍后再试。", "steps": []}
    try:
        return _run_steps(step_names, force=force)
    finally:
        _LOCK.release()


def get_refresh_status() -> dict[str, Any]:
    payload = _read_json(_status_path())
    if isinstance(payload, dict):
        return sanitize_for_json(payload)
    return {"status": "idle", "message_zh": "暂无刷新任务记录。", "steps": []}


def get_refresh_history() -> dict[str, Any]:
    payload = _read_json(_history_path())
    rows = payload if isinstance(payload, list) else []
    return {"history": sanitize_for_json(rows), "count": len(rows)}


# Prompt 31 override: route market refresh through the explainable provider
# chain.  The original implementation only read the old v2 cache path, which
# made repeated refreshes look like failures when no cache existed.
def refresh_market_data(force: bool = False) -> dict[str, Any]:  # type: ignore[override]
    from .market_data_service import refresh_sn_market_data

    result = refresh_sn_market_data(force=force)
    output_files = result.get("output_files") if isinstance(result.get("output_files"), list) else []
    if not result.get("success"):
        return {
            "status": "failed",
            "final_status": result.get("final_status"),
            "message_zh": result.get("message_zh") or "行情刷新失败，未生成假行情。",
            "output_files": output_files,
            "error": result.get("message_zh") or "",
            "provider_chain_status": result.get("provider_chain_status", []),
            "market_provider_status": result.get("market_provider_status", {}),
            "history_rows": result.get("history_rows", 0),
        }
    return {
        "status": "success",
        "final_status": result.get("final_status"),
        "message_zh": result.get("message_zh") or "行情刷新完成。",
        "output_files": output_files,
        "from_cache": bool(result.get("from_cache")),
        "stale": bool(result.get("stale")),
        "data_quality": result.get("data_quality", {}),
        "provider_chain_status": result.get("provider_chain_status", []),
        "market_provider_status": result.get("market_provider_status", {}),
        "history_rows": result.get("history_rows", 0),
    }


# Prompt 33 override: keep NewsAPI refresh observable and explainable.
def refresh_news_data(force: bool = False, provider: NewsApiProvider | None = None) -> dict[str, Any]:  # type: ignore[override]
    _ = force
    events_dir = _events_dir()
    provider_status_path = events_dir / "provider_status.json"
    news_provider_status_path = events_dir / "news_provider_status.json"
    raw_path = events_dir / "news_raw.json"
    news_events_path = events_dir / "news_events.json"
    provider = provider or NewsApiProvider()
    result = provider.fetch_tin_news(page_size=50)
    if result.get("configured") is False or (not result.get("configured") and result.get("enabled") is False):
        provider_payload = {"providers": [result], "updated_at": _now()}
        _write_json(provider_status_path, provider_payload)
        _write_json(news_provider_status_path, provider_payload)
        return {
            "status": "skipped",
            "message_zh": "未配置 NewsAPI，已跳过新闻刷新。",
            "output_files": [str(provider_status_path), str(news_provider_status_path)],
            "provider_attempts": result.get("query_attempts", []),
            "status_code": "not_configured",
            "row_count": 0,
            "error_type": "not_configured",
            "error_message_zh": result.get("error_message_zh", "未配置 NewsAPI"),
            "next_actions_zh": result.get("next_actions_zh", ["前往设置页配置 NewsAPI"]),
        }

    articles = result.get("articles") if isinstance(result.get("articles"), list) else []
    events = [_classify_article(row) for row in articles if isinstance(row, dict)]
    cached_raw = _read_json(raw_path)
    cached_news_events = _read_json(news_events_path)
    cached_articles = cached_raw.get("articles") if isinstance(cached_raw, dict) and isinstance(cached_raw.get("articles"), list) else []
    cached_events = cached_news_events.get("events") if isinstance(cached_news_events, dict) and isinstance(cached_news_events.get("events"), list) else []
    if not result.get("success") and (cached_events or cached_articles):
        cache_time = ""
        if isinstance(cached_news_events, dict):
            cache_time = str(cached_news_events.get("generated_at") or cached_news_events.get("updated_at") or "")
        if not cache_time and isinstance(cached_raw, dict):
            cache_time = str(cached_raw.get("generated_at") or cached_raw.get("updated_at") or "")
        provider_payload = {"providers": [result], "updated_at": _now(), "from_cache": True}
        _write_json(provider_status_path, provider_payload)
        _write_json(news_provider_status_path, provider_payload)
        try:
            from .data_watermark_service import update_provider_watermark

            update_provider_watermark(
                "newsapi",
                status="using_cache",
                last_attempt_time=str(provider_payload["updated_at"]),
                last_success_time=cache_time,
                row_count=len(cached_events) or len(cached_articles),
                from_cache=True,
            )
        except Exception:
            pass
        update_provider_status(
            [
                {
                    "provider": "newsapi",
                    "source_tier": "tier2",
                    "success": False,
                    "from_cache": True,
                    "message": result.get("message", "") or result.get("message_zh", ""),
                    "fetched_count": len(cached_articles),
                    "inserted_count": len(cached_events),
                    "updated_at": _now(),
                }
            ]
        )
        return {
            "status": "using_cache",
            "success": True,
            "from_cache": True,
            "message_zh": "NewsAPI 当前不可刷新，已保留最近成功新闻缓存；缓存不会冒充新数据。",
            "output_files": [str(raw_path), str(news_events_path), str(provider_status_path), str(news_provider_status_path)],
            "provider_attempts": result.get("query_attempts", []),
            "status_code": result.get("error_code") or "request_failed",
            "row_count": len(cached_events) or len(cached_articles),
            "last_success_time": cache_time,
            "cache_hit": True,
            "error_type": result.get("error_code") or "request_failed",
            "error_message_zh": result.get("error_message_zh") or result.get("message_zh") or result.get("message", ""),
            "next_actions_zh": result.get("next_actions_zh") or ["等待 NewsAPI quota 冷却后重试", "继续使用最近成功新闻缓存"],
        }
    _write_json(
        raw_path,
        {
            "articles": articles,
            "query_attempts": result.get("query_attempts", []),
            "provider": "newsapi",
            "generated_at": _now(),
            "disclaimer": DISCLAIMER,
        },
    )
    _write_json(news_events_path, {"events": events, "generated_at": _now(), "disclaimer": DISCLAIMER})
    provider_payload = {"providers": [result], "updated_at": _now()}
    _write_json(provider_status_path, provider_payload)
    _write_json(news_provider_status_path, provider_payload)
    if result.get("success"):
        try:
            from .data_watermark_service import update_provider_watermark

            success_time = str(result.get("last_success_time") or provider_payload["updated_at"])
            update_provider_watermark(
                "newsapi",
                status="success",
                last_attempt_time=str(provider_payload["updated_at"]),
                last_success_time=success_time,
                row_count=len(articles),
                from_cache=bool(result.get("from_cache")),
            )
        except Exception:
            pass
    update_provider_status(
        [
            {
                "provider": "newsapi",
                "source_tier": "tier2",
                "success": bool(result.get("success")),
                "message": result.get("message", ""),
                "fetched_count": len(articles),
                "inserted_count": len(events),
                "updated_at": _now(),
            }
        ]
    )
    if not result.get("success"):
        return {
            "status": "failed",
            "message_zh": f"NewsAPI 刷新失败：{result.get('message', '未知错误')}",
            "output_files": [str(raw_path), str(news_events_path), str(provider_status_path), str(news_provider_status_path)],
            "provider_attempts": result.get("query_attempts", []),
            "status_code": result.get("error_code") or "request_failed",
            "row_count": len(articles),
            "error_type": result.get("error_code") or "request_failed",
            "error_message_zh": result.get("error_message_zh") or result.get("message_zh") or result.get("message", ""),
            "next_actions_zh": result.get("next_actions_zh") or ["检查 NewsAPI key", "稍后重试"],
        }
    return {
        "status": "success",
        "message_zh": str(result.get("message_zh") or f"新闻刷新完成，返回 {len(articles)} 条。"),
        "output_files": [str(raw_path), str(news_events_path), str(provider_status_path), str(news_provider_status_path)],
        "provider_attempts": result.get("query_attempts", []),
        "status_code": "success",
        "row_count": len(articles),
        "cache_hit": bool(result.get("from_cache")),
        "last_success_time": result.get("last_success_time", ""),
        "next_actions_zh": result.get("next_actions_zh") or ["查看事件监控", "生成报告"],
    }
