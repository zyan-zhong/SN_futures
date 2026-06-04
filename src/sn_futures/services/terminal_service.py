from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Mapping

from ..api.json_utils import clean_trade_points, sanitize_for_json
from ..api.schemas import (
    DISCLAIMER,
    BacktestDiagnostics,
    DataSourceStatus,
    LearningStatus,
    ModelHealth,
    PositionScenario,
    PredictionCard,
    SystemHealth,
    TerminalSummary,
)
from ..config import load_environment_config
from ..runtime import get_user_output_dir


HORIZON_LABELS = {
    "next_5m": "未来5分钟",
    "next_15m": "未来15分钟",
    "next_30m": "未来30分钟",
    "next_hour": "下一小时",
    "tomorrow": "下一交易日",
    "one_to_two_weeks": "未来1-2周",
    "one_to_three_months": "未来1-3个月",
}


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _safe_call(name: str, fn: Callable[[], Any], fallback: Any) -> Any:
    try:
        return fn()
    except Exception as exc:
        return {"ok": False, "module": name, "message_zh": f"{name} 暂不可用：{exc}", "error": str(exc), **(fallback or {})}


def _read_json(path: Path) -> Any:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _tushare_subinterfaces() -> list[dict[str, Any]]:
    payload = _read_json(get_user_output_dir() / "fundamentals" / "tushare_provider_status.json")
    results = payload.get("results") if isinstance(payload, Mapping) and isinstance(payload.get("results"), Mapping) else {}
    rows: list[dict[str, Any]] = []
    for key, label in (
        ("tushare_contracts", "contract info"),
        ("tushare_daily", "daily"),
        ("tushare_warehouse", "warehouse"),
        ("tushare_settlement", "settlement"),
        ("tushare_holding", "holding"),
    ):
        item = results.get(key) if isinstance(results, Mapping) else None
        if not isinstance(item, Mapping):
            rows.append({"source_name": key, "label": label, "status": "missing", "row_count": 0, "selected_params": {}, "last_success_time": ""})
            continue
        rows.append(
            {
                "source_name": key,
                "label": label,
                "status": item.get("status") or "unknown",
                "success": bool(item.get("success")),
                "row_count": int(item.get("row_count") or 0),
                "selected_params": item.get("selected_params") or item.get("params_sanitized") or {},
                "last_success_time": item.get("last_success_time") or ((payload.get("generated_at") if isinstance(payload, Mapping) else "") if item.get("success") else "") or "",
                "error_message_zh": item.get("error_message_zh") or "",
            }
        )
    return rows


def _as_float(value: Any, default: float | None = None) -> float | None:
    try:
        parsed = float(value)
    except Exception:
        return default
    return parsed if parsed == parsed and parsed not in {float("inf"), float("-inf")} else default


def _text(value: Any, default: str = "数据暂缺") -> str:
    if value is None:
        return default
    text = str(value).strip()
    if not text or text.lower() in {"nan", "none", "null"}:
        return default
    return text


def _price_range(card: Mapping[str, Any]) -> list[float | None]:
    low = _as_float(card.get("range_low", card.get("price_lower")))
    high = _as_float(card.get("range_high", card.get("price_upper")))
    return [low, high]


def _list_text(value: Any, default: str) -> list[str]:
    if isinstance(value, list):
        out: list[str] = []
        for item in value:
            if isinstance(item, Mapping):
                title = item.get("title") or item.get("summary") or item.get("name")
                if title:
                    out.append(str(title))
            elif item:
                out.append(str(item))
        return out[:8] or [default]
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return [default]


def _failure_reasons(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value if item] or ["暂无失败原因"]
    if isinstance(value, str) and value:
        return [value]
    return ["暂无失败原因"]


def build_terminal_predictions() -> list[dict[str, Any]]:
    from .. import v2_api

    live = _safe_call("预测服务", v2_api.get_live_predictions, {"cards": {}})
    watermark = live.get("data_watermark", {}) if isinstance(live, Mapping) else {}
    global_quality = _as_float(watermark.get("quality_score"), 0.0) or 0.0
    cards = live.get("cards", {}) if isinstance(live, Mapping) and isinstance(live.get("cards"), Mapping) else {}

    out: list[dict[str, Any]] = []
    for horizon, raw_card in cards.items():
        if not isinstance(raw_card, Mapping):
            continue
        p_up = _as_float(raw_card.get("p_up", raw_card.get("prob_up")))
        card_quality = _as_float(raw_card.get("data_quality_score"), global_quality)
        decision = raw_card.get("决策说明")
        if isinstance(decision, Mapping):
            explanation = _text(decision.get("摘要"), "方向优势不足，维持研究观察。")
        else:
            explanation = _text(decision, "方向优势不足，维持研究观察。")

        prediction = PredictionCard(
            horizon=str(horizon),
            horizon_zh=_text(raw_card.get("horizon_label") or raw_card.get("周期") or HORIZON_LABELS.get(str(horizon)), str(horizon)),
            direction=_text(raw_card.get("方向") or raw_card.get("direction_label") or raw_card.get("direction"), "观望"),
            signal=_text(raw_card.get("信号") or raw_card.get("signal"), "观望"),
            calibrated_prob_up=_as_float(raw_card.get("calibrated_prob_up", p_up)),
            raw_prob_up=_as_float(raw_card.get("raw_prob_up", raw_card.get("prob_up", p_up))),
            expected_return=_as_float(raw_card.get("expected_return", raw_card.get("predicted_return"))),
            predicted_range=_price_range(raw_card),
            confidence_score=_as_float(raw_card.get("confidence_score", raw_card.get("confidence"))),
            decision_explanation=explanation,
            top_factors=_list_text(raw_card.get("核心因子") or raw_card.get("top_factors") or raw_card.get("core_drivers"), "核心因子仍在积累"),
            event_evidence=_list_text(raw_card.get("事件依据") or raw_card.get("top_bullish_events"), "暂无高权重入模事件"),
            risk_notes=_list_text(raw_card.get("风险提示") or raw_card.get("risk_notes"), "预测可能误差、延迟或失效"),
            data_quality=card_quality,
            model_status=_text(raw_card.get("模型状态") or raw_card.get("model_status") or raw_card.get("promotion_result"), "模型状态待验证"),
            backtest_summary=raw_card.get("回测摘要") if isinstance(raw_card.get("回测摘要"), dict) else {},
            path_guard_summary=_text(raw_card.get("路径守门结果") or raw_card.get("path_guard_status"), "路径守门待验证"),
            entry=_as_float(raw_card.get("entry")),
            stop_loss=_as_float(raw_card.get("stop_loss")),
            take_profit=_as_float(raw_card.get("take_profit")),
        )
        out.append(clean_trade_points(sanitize_for_json(prediction)))

    return sanitize_for_json(out)


def build_terminal_summary() -> dict[str, Any]:
    from .. import v2_api

    live = _safe_call("预测服务", v2_api.get_live_predictions, {"cards": {}})
    health = _safe_call("模型健康", v2_api.get_models_health, {})
    watermark = _safe_call("数据水位", v2_api.get_data_watermark, {})
    quote = watermark.get("live_quote", {}) if isinstance(watermark.get("live_quote"), Mapping) else {}
    cards = live.get("cards", {}) if isinstance(live.get("cards"), Mapping) else {}
    first_card = next((card for card in cards.values() if isinstance(card, Mapping)), {})
    quality = _as_float(watermark.get("quality_score"), 0.0)
    quality_label = "较可靠" if quality is not None and quality >= 0.75 else "需谨慎" if quality is not None and quality >= 0.55 else "数据质量不足"

    summary = TerminalSummary(
        system_status="运行中" if live else "部分模块不可用",
        data_quality_score=quality,
        data_quality_label=quality_label,
        main_contract=_text(watermark.get("active_contract") or watermark.get("target_contract"), "SN"),
        latest_price=_as_float(watermark.get("latest_price") or quote.get("latest")),
        price_change=_as_float(quote.get("change")),
        price_change_pct=_as_float(quote.get("change_pct")),
        current_signal=_text(first_card.get("信号") or first_card.get("signal"), "观望"),
        model_status=_text(health.get("validation_mode") or health.get("health_reason"), "模型状态待验证"),
        backtest_status=_text(health.get("validation_mode"), "回测状态待验证"),
        risk_level="高" if quality is not None and quality < 0.55 else "中" if quality is not None and quality < 0.75 else "低",
        last_update_time=_text(watermark.get("fetch_timestamp") or watermark.get("source_timestamp") or live.get("generated_at"), "本周期未更新"),
        disclaimer=DISCLAIMER,
    )


    return sanitize_for_json(summary)


def build_terminal_model_health() -> dict[str, Any]:
    from .. import v2_api

    health = _safe_call("模型健康", v2_api.get_models_health, {})
    per = health.get("per_horizon", {}) if isinstance(health.get("per_horizon"), Mapping) else {}
    active = ", ".join(str(row.get("active_model")) for row in per.values() if isinstance(row, Mapping) and row.get("active_model"))
    candidate = ", ".join(str(row.get("candidate_model")) for row in per.values() if isinstance(row, Mapping) and row.get("candidate_model"))
    failures: list[str] = []
    degraded: list[str] = []
    for horizon, row in per.items():
        if not isinstance(row, Mapping):
            continue
        failures.extend(_failure_reasons(row.get("failure_reasons")) if row.get("failure_reasons") else [])
        deg = row.get("degradation_gate_status")
        if isinstance(deg, Mapping) and deg.get("degraded"):
            degraded.append(str(horizon))
    model_health = ModelHealth(
        active_model=active or "暂无可用 active 模型",
        candidate_model=candidate or "暂未运行",
        degraded_models=degraded,
        promotion_status=_text(health.get("validation_mode"), "待验证"),
        degradation_status="已触发" if degraded else "未触发",
        metrics_by_horizon=per,
        failure_reasons=list(dict.fromkeys(failures)) or ["暂无失败原因"],
        last_check_time=_text(health.get("updated_at"), _now()),
    )
    return sanitize_for_json(model_health)


def build_terminal_learning_status() -> dict[str, Any]:
    from .. import v2_api

    status = _safe_call("学习状态", v2_api.get_learning_status, {})
    learning = LearningStatus(
        latest_market_refresh=_text(status.get("last_market_refresh"), "暂未运行"),
        latest_prediction=_text(status.get("last_prediction") or status.get("last_prediction_refresh"), "暂未运行"),
        latest_validation=_text(status.get("last_verification"), "暂未运行"),
        latest_calibration=_text(status.get("last_calibration"), "暂未运行"),
        latest_candidate_training=_text(status.get("last_candidate_training") or status.get("last_training"), "暂未运行"),
        latest_walk_forward=_text(status.get("last_walk_forward"), "暂未运行"),
        latest_event_ablation=_text(status.get("last_event_ablation"), "暂未运行"),
        latest_promotion_check=_text(status.get("last_promotion_check"), "暂未运行"),
        next_task=_text(status.get("next_task") or status.get("next_prediction_at"), "暂未计划"),
        active_candidate_state=_text(status.get("message"), "学习状态待验证"),
        failure_reasons=_failure_reasons(status.get("failure_reasons")),
    )
    return sanitize_for_json(learning)


def build_terminal_backtest_diagnostics(horizon: str | None = None) -> dict[str, Any]:
    from .. import v2_api

    raw = _safe_call("回测诊断", lambda: v2_api.get_backtest_diagnostics(horizon or ""), {})
    diagnostics = BacktestDiagnostics(
        horizon=_text(raw.get("horizon") or horizon, "all"),
        walk_forward_metrics=raw.get("walk_forward_metrics") if isinstance(raw.get("walk_forward_metrics"), dict) else {},
        baseline_comparison=raw.get("baseline_comparison") if isinstance(raw.get("baseline_comparison"), dict) else {},
        cost_sensitivity=raw.get("cost_sensitivity") if isinstance(raw.get("cost_sensitivity"), dict) else {},
        by_regime=raw.get("by_regime_performance") if isinstance(raw.get("by_regime_performance"), dict) else {},
        by_signal_strength=raw.get("by_signal_strength_performance") if isinstance(raw.get("by_signal_strength_performance"), dict) else {},
        drawdown_periods=raw.get("drawdown_periods") if isinstance(raw.get("drawdown_periods"), list) else [],
        promotion_gate_result=_text(raw.get("promotion_gate_conclusion") or raw.get("promotion_result"), "待验证"),
        failure_reasons=_failure_reasons(raw.get("failure_reasons")),
    )
    return sanitize_for_json(diagnostics)


def build_terminal_position_scenario(payload: Mapping[str, Any]) -> dict[str, Any]:
    from .. import v2_api

    adapted = {
        "direction": payload.get("direction"),
        "quantity": payload.get("contracts", payload.get("quantity")),
        "avg_price": payload.get("entry_price", payload.get("avg_price")),
        "account_equity": payload.get("account_equity"),
        "max_loss": payload.get("max_acceptable_loss", payload.get("max_loss")),
        "plan_horizon": payload.get("horizon", payload.get("plan_horizon")),
    }
    raw = _safe_call("持仓情景", lambda: v2_api.evaluate_position_scenario_api(adapted), {})
    scenario = PositionScenario(
        input=dict(payload),
        notional_exposure=_as_float(raw.get("名义敞口") or raw.get("鍚嶄箟鏁炲彛")),
        margin_required=_as_float(raw.get("保证金占用") or raw.get("淇濊瘉閲戝崰鐢?")),
        var_95=_as_float(raw.get("VaR 95")),
        stress_var=_as_float(raw.get("压力 VaR") or raw.get("鍘嬪姏 VaR")),
        max_loss_ratio=_as_float(raw.get("最大可承受亏损占比") or raw.get("鏈€澶у彲鎵垮彈浜忔崯鍗犳瘮")),
        observation_zone=raw.get("观察区") or raw.get("瑙傚療鍖?") or raw.get("zones") or [],
        risk_zone=raw.get("风险区") or raw.get("椋庨櫓鍖?") or [],
        horizon_resonance=_text(raw.get("周期共振") or raw.get("鍛ㄦ湡鍏辨尟"), "周期共振待验证"),
        event_evidence=_list_text(raw.get("事件依据") or raw.get("浜嬩欢渚濇嵁"), "暂无高权重入模事件"),
        uncertainty_notes=_list_text(raw.get("不确定性提示") or raw.get("涓嶇‘瀹氭€ф彁绀?"), "仅供投研参考，需独立决策"),
        disclaimer=DISCLAIMER,
    )
    return sanitize_for_json(scenario)


def build_terminal_reports() -> dict[str, Any]:
    from .. import v2_api

    reports: list[dict[str, Any]] = []
    for report_type, name in (("daily", "日报"), ("weekly", "周报"), ("monthly", "月报"), ("event", "事件报告")):
        raw = _safe_call(f"{name}报告", lambda report_type=report_type: v2_api.get_report_content(report_type), {})
        reports.append(
            {
                "type": report_type,
                "name": name,
                "title": _text(raw.get("title"), name),
                "generated_at": _text(raw.get("generated_at"), "本周期未更新"),
                "data_cutoff": _text(raw.get("data_cutoff"), "数据暂缺"),
                "summary": _text(str(raw.get("markdown", ""))[:240], "报告暂未生成"),
                "disclaimer": DISCLAIMER,
            }
        )
    return sanitize_for_json({"reports": reports, "disclaimer": DISCLAIMER})


def build_terminal_data_status() -> dict[str, Any]:
    from .. import v2_api

    settings = load_environment_config()
    watermark = _safe_call("数据水位", v2_api.get_data_watermark, {})
    provider_status = _safe_call("事件源状态", v2_api.get_events_provider_status, {})
    event_sources = provider_status.get("providers", []) if isinstance(provider_status.get("providers"), list) else []
    sources = [
        DataSourceStatus(
            source_name="本地行情缓存",
            enabled=True,
            success=bool(watermark.get("latest_price") or watermark.get("latest_daily")),
            from_cache=bool(watermark.get("using_fallback")),
            message_zh=_text(watermark.get("source_mode"), "本周期未更新"),
            last_update=_text(watermark.get("fetch_timestamp") or watermark.get("source_timestamp"), "本周期未更新"),
            stale=bool(watermark.get("data_quality_report", {}).get("stale_data_flag")) if isinstance(watermark.get("data_quality_report"), Mapping) else False,
        ),
        DataSourceStatus(
            source_name="Alpha Vantage",
            enabled=bool(settings.alpha_vantage.enabled),
            success=False,
            from_cache=False,
            message_zh="已配置，等待数据任务验证" if settings.alpha_vantage.enabled else "未配置 SN_ALPHA_VANTAGE_KEY",
            last_update="本周期未更新",
            stale=True,
        ),
        DataSourceStatus(
            source_name="NewsAPI",
            enabled=bool(settings.newsapi.enabled),
            success=False,
            from_cache=False,
            message_zh="已配置，等待新闻任务验证" if settings.newsapi.enabled else "未配置 SN_NEWSAPI_KEY",
            last_update="本周期未更新",
            stale=True,
        ),
    ]
    for item in event_sources[:10]:
        if isinstance(item, Mapping):
            sources.append(
                DataSourceStatus(
                    source_name=_text(item.get("provider") or item.get("source"), "事件源"),
                    enabled=True,
                    success=bool(item.get("success", item.get("last_success_time"))),
                    from_cache=bool(item.get("from_cache", False)),
                    message_zh=_text(item.get("message") or item.get("last_error"), "状态待验证"),
                    last_update=_text(item.get("last_success_time") or item.get("updated_at"), "本周期未更新"),
                    stale=not bool(item.get("success", item.get("last_success_time"))),
                )
            )
    return sanitize_for_json({"sources": sources, "tushare_subinterfaces": _tushare_subinterfaces(), "data_watermark": watermark, "disclaimer": DISCLAIMER})


def build_terminal_system_health() -> dict[str, Any]:
    from .. import v2_api

    warnings: list[str] = []
    env = load_environment_config()
    storage_status = "可写" if Path(env.data_dir).exists() else "数据目录待创建"
    truth = _safe_call("系统真实性审计", v2_api.get_system_truth_audit, {})
    if truth.get("status") == "fail":
        warnings.append("系统真实性审计存在失败项")
    health = SystemHealth(
        api_status="正常",
        data_status="待验证" if warnings else "正常",
        model_status="待验证",
        storage_status=storage_status,
        report_status="正常",
        frontend_status="legacy UI 可用；新 React 终端待建设",
        warnings=warnings or ["暂无阻断告警"],
        last_check_time=_now(),
    )
    return sanitize_for_json({"health": health, "truth_audit": truth, "disclaimer": DISCLAIMER})


def build_terminal_snapshot() -> dict[str, Any]:
    from .refresh_service import get_refresh_status

    snapshot = {
        "summary": build_terminal_summary(),
        "predictions": build_terminal_predictions(),
        "model_health": build_terminal_model_health(),
        "learning_status": build_terminal_learning_status(),
        "backtest_diagnostics": build_terminal_backtest_diagnostics(None),
        "data_status": build_terminal_data_status(),
        "system_health": build_terminal_system_health(),
        "refresh_status": get_refresh_status(),
        "disclaimer": DISCLAIMER,
    }
    return sanitize_for_json(snapshot)


def _runtime_output_dir() -> Path:
    from ..runtime import get_user_output_dir

    return get_user_output_dir()


def _runtime_reports_dir() -> Path:
    from ..user_data import user_path

    path = user_path("reports")
    path.mkdir(parents=True, exist_ok=True)
    return path


def _read_json_file(path: Path) -> Any:
    import json

    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _to_float(value: Any) -> float | None:
    return _as_float(value)


def build_terminal_price_history() -> dict[str, Any]:
    """Return real cached market history for charting; never fabricates bars."""
    from .. import v2_api

    out = _runtime_output_dir()
    history_payload = _read_json_file(out / "sn_market_history.json")
    snapshot = _read_json_file(out / "sn_live_snapshot.json")
    rows = history_payload.get("history", []) if isinstance(history_payload, Mapping) else []
    points: list[dict[str, Any]] = []
    for row in rows if isinstance(rows, list) else []:
        if not isinstance(row, Mapping):
            continue
        close = _to_float(row.get("close") or row.get("price") or row.get("latest"))
        if close is None:
            continue
        points.append(
            {
                "time": _text(row.get("time") or row.get("ts") or row.get("date") or row.get("datetime"), "本周期未更新"),
                "open": _to_float(row.get("open")) if row.get("open") is not None else close,
                "high": _to_float(row.get("high")) if row.get("high") is not None else close,
                "low": _to_float(row.get("low")) if row.get("low") is not None else close,
                "close": close,
                "volume": _to_float(row.get("volume")),
                "open_interest": _to_float(row.get("open_interest")),
            }
        )

    if not points:
        try:
            chart = v2_api.get_price_forecast_chart("tomorrow")
            for row in chart.get("history", []) if isinstance(chart.get("history"), list) else []:
                if not isinstance(row, Mapping):
                    continue
                close = _to_float(row.get("close") or row.get("price"))
                if close is None:
                    continue
                points.append(
                    {
                        "time": _text(row.get("ts") or row.get("date"), "本周期未更新"),
                        "open": close,
                        "high": close,
                        "low": close,
                        "close": close,
                        "volume": None,
                        "open_interest": None,
                    }
                )
        except Exception:
            points = []

    data_quality = 0.0
    contract = "SN"
    source = "运行期行情缓存"
    if isinstance(snapshot, Mapping):
        data_quality = _as_float(snapshot.get("data_quality_score"), 0.0) or 0.0
        contract = _text(snapshot.get("active_contract"), "SN")
        source_status = snapshot.get("source_status")
        if isinstance(source_status, list) and source_status and isinstance(source_status[0], Mapping):
            source = _text(source_status[0].get("provider"), source)
    message = "行情历史可用于图表展示。" if points else "暂无行情历史数据，请先运行一键刷新数据。"
    return sanitize_for_json(
        {
            "symbol": "SN",
            "contract": contract,
            "source": source,
            "data_quality_score": data_quality,
            "points": points[-500:],
            "message_zh": message,
            "disclaimer": DISCLAIMER,
        }
    )


def build_terminal_forecast_path() -> dict[str, Any]:
    """Return forecast paths from existing prediction cache only."""
    from .. import v2_api

    out = _runtime_output_dir()
    payload = _read_json_file(out / "sn_unified_forecast.json") or _read_json_file(out / "sn_live_predictions.json")
    cards = payload.get("cards", {}) if isinstance(payload, Mapping) and isinstance(payload.get("cards"), Mapping) else {}
    points: list[dict[str, Any]] = []
    horizons: list[str] = []
    for horizon, card in cards.items():
        if not isinstance(card, Mapping):
            continue
        horizons.append(str(horizon))
        try:
            forecast = v2_api.get_price_forecast_chart(str(horizon)).get("forecast", [])
        except Exception:
            forecast = card.get("forecast", [])
        for row in forecast if isinstance(forecast, list) else []:
            if not isinstance(row, Mapping):
                continue
            center = _to_float(row.get("center") or row.get("pred_center"))
            lower = _to_float(row.get("lower") or row.get("pred_low"))
            upper = _to_float(row.get("upper") or row.get("pred_high"))
            if center is None and lower is None and upper is None:
                continue
            points.append(
                {
                    "horizon": str(horizon),
                    "time": row.get("ts") or row.get("date"),
                    "center": center,
                    "lower": lower,
                    "upper": upper,
                    "prob_up": _to_float(row.get("p_up") or row.get("prob_up") or card.get("p_up") or card.get("prob_up")),
                    "signal": _text(card.get("signal") or card.get("信号"), "观望"),
                }
            )
    return sanitize_for_json(
        {
            "horizons": horizons,
            "points": points,
            "message_zh": "预测路径已读取。" if points else "暂无预测路径数据，请先运行预测刷新；系统不会生成伪预测。",
            "disclaimer": DISCLAIMER,
        }
    )


def build_terminal_equity_curve() -> dict[str, Any]:
    diagnostics = build_terminal_backtest_diagnostics(None)
    equity = diagnostics.get("equity_curve") if isinstance(diagnostics, Mapping) else None
    points = equity if isinstance(equity, list) else []
    return sanitize_for_json(
        {
            "points": points,
            "message_zh": "权益曲线已读取。" if points else "暂无权益曲线数据，请先运行 walk-forward 或回测诊断。",
            "disclaimer": DISCLAIMER,
        }
    )


def build_terminal_drawdown() -> dict[str, Any]:
    diagnostics = build_terminal_backtest_diagnostics(None)
    periods = diagnostics.get("drawdown_periods") if isinstance(diagnostics, Mapping) else None
    return sanitize_for_json(
        {
            "points": periods if isinstance(periods, list) else [],
            "message_zh": "回撤数据已读取。" if periods else "暂无回撤数据，请先运行回测诊断。",
            "disclaimer": DISCLAIMER,
        }
    )


def _normalise_news_event(row: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "title": _text(row.get("title"), "未命名新闻"),
        "source": _text(row.get("source"), "数据暂缺"),
        "published_at": _text(row.get("published_at") or row.get("publishedAt"), "本周期未更新"),
        "url": _text(row.get("url") or row.get("canonical_url") or row.get("raw_url"), ""),
        "category": _text(row.get("category"), "other"),
        "sentiment_score": _to_float(row.get("sentiment_score")),
        "impact_score": _to_float(row.get("impact_score") or row.get("final_event_weight")),
        "relevance_score": _to_float(row.get("relevance_score")),
        "allowed_for_event_factor": bool(row.get("allowed_for_event_factor", row.get("used_in_model", False))),
        "used_in_model": bool(row.get("used_in_model", False)),
        "exclusion_reason": _text(row.get("exclusion_reason"), ""),
        "summary_zh": _text(row.get("summary") or row.get("description"), "暂无摘要"),
    }


def _normalise_news_event(row: Mapping[str, Any]) -> dict[str, Any]:  # type: ignore[no-redef]
    return {
        "title": _text(row.get("title"), "未命名新闻"),
        "source": _text(row.get("source"), "数据暂缺"),
        "published_at": _text(row.get("published_at") or row.get("publishedAt"), "本周期未更新"),
        "url": _text(row.get("url") or row.get("canonical_url") or row.get("raw_url"), ""),
        "category": _text(row.get("category"), "other"),
        "sentiment_score": _to_float(row.get("sentiment_score")),
        "impact_score": _to_float(row.get("impact_score") or row.get("final_event_weight")),
        "relevance_score": _to_float(row.get("relevance_score")),
        "hard_evidence_score": _to_float(row.get("hard_evidence_score")),
        "source_reliability_score": _to_float(row.get("source_reliability_score")),
        "source_domain": _text(row.get("source_domain"), ""),
        "domain_blacklist_penalty": _to_float(row.get("domain_blacklist_penalty")),
        "allowed_for_event_factor": bool(row.get("allowed_for_event_factor", row.get("used_in_model", False))),
        "used_in_model": bool(row.get("used_in_model", False)),
        "inclusion_reason": _text(row.get("inclusion_reason"), ""),
        "exclusion_reason": _text(row.get("exclusion_reason"), ""),
        "keyword_hits": row.get("keyword_hits") if isinstance(row.get("keyword_hits"), list) else [],
        "negative_keyword_hits": row.get("negative_keyword_hits") if isinstance(row.get("negative_keyword_hits"), list) else [],
        "summary_zh": _text(row.get("summary") or row.get("summary_zh") or row.get("description"), "暂无摘要"),
    }


def build_terminal_news_events() -> dict[str, Any]:
    env = load_environment_config()
    events_dir = _runtime_output_dir() / "events"
    news_payload = _read_json_file(events_dir / "news_events.json")
    store_payload = _read_json_file(events_dir / "event_store.json")
    provider_status = _read_json_file(events_dir / "provider_status.json") or {}
    rows = news_payload.get("events", []) if isinstance(news_payload, Mapping) and isinstance(news_payload.get("events"), list) else []
    if not rows and isinstance(store_payload, Mapping) and isinstance(store_payload.get("events"), list):
        rows = store_payload.get("events", [])
    events = [_normalise_news_event(row) for row in rows if isinstance(row, Mapping)]
    if not env.newsapi.enabled and not events:
        message = "未配置 NewsAPI，无法拉取外部新闻。"
    elif events:
        message = "新闻事件已读取。"
    else:
        message = "暂无新闻事件，请先运行新闻刷新。"
    return sanitize_for_json(
        {
            "events": events,
            "provider_status": provider_status,
            "message_zh": message,
            "disclaimer": DISCLAIMER,
        }
    )


def build_terminal_event_evidence(horizon: str | None = None) -> dict[str, Any]:
    from .. import v2_api

    key = horizon or "tomorrow"
    evidence_path = _runtime_output_dir() / "events" / "event_evidence_by_horizon.json"
    payload = _read_json_file(evidence_path)
    if isinstance(payload, Mapping) and key in payload:
        result = dict(payload.get(key) or {})
        result.setdefault("horizon", key)
        result.setdefault("message_zh", "事件证据已读取。")
        result.setdefault("disclaimer", DISCLAIMER)
        return sanitize_for_json(result)
    try:
        result = v2_api.get_events_evidence(key)
        result.setdefault("message_zh", "事件证据已读取。")
        return sanitize_for_json(result)
    except Exception as exc:
        return sanitize_for_json(
            {
                "horizon": key,
                "events": [],
                "message_zh": f"暂无事件证据：{exc}",
                "disclaimer": DISCLAIMER,
            }
        )


def _report_file_for_type(report_type: str) -> Path:
    name = {
        "daily": "sn_daily_report.md",
        "weekly": "sn_weekly_report.md",
        "monthly": "sn_monthly_report.md",
        "event": "sn_event_report.md",
    }.get(report_type, "sn_daily_report.md")
    return _runtime_reports_dir() / name


def build_terminal_report_full(report_type: str = "daily") -> dict[str, Any]:
    from .. import v2_api

    report_type = report_type if report_type in {"daily", "weekly", "monthly", "event"} else "daily"
    path = _report_file_for_type(report_type)
    markdown = ""
    if path.exists():
        markdown = path.read_text(encoding="utf-8", errors="replace")
    if not markdown:
        try:
            markdown = str(v2_api.get_report_content(report_type).get("markdown") or "")
        except Exception:
            markdown = ""
    title_map = {"daily": "日报", "weekly": "周报", "monthly": "月报", "event": "事件报告"}
    return sanitize_for_json(
        {
            "type": report_type,
            "title": f"沪锡期货{title_map.get(report_type, '报告')}",
            "generated_at": _now(),
            "data_cutoff": "数据暂缺" if not markdown else "见报告正文",
            "markdown": markdown.replace("nan", "数据暂缺") if markdown else "",
            "message_zh": "报告全文已读取。" if markdown else "暂无报告全文，请先运行报告刷新。",
            "disclaimer": DISCLAIMER,
        }
    )


def build_terminal_reports() -> dict[str, Any]:  # type: ignore[override]
    reports: list[dict[str, Any]] = []
    for report_type, name in (("daily", "日报"), ("weekly", "周报"), ("monthly", "月报"), ("event", "事件报告")):
        full = build_terminal_report_full(report_type)
        markdown = str(full.get("markdown") or "")
        reports.append(
            {
                "type": report_type,
                "name": name,
                "title": full.get("title") or name,
                "generated_at": full.get("generated_at") or "本周期未更新",
                "data_cutoff": full.get("data_cutoff") or "数据暂缺",
                "summary": markdown[:240] if markdown else "报告暂未生成",
                "markdown": markdown,
                "markdown_available": bool(markdown),
                "disclaimer": DISCLAIMER,
            }
        )
    return sanitize_for_json({"reports": reports, "disclaimer": DISCLAIMER})


def build_terminal_factor_diagnostics() -> dict[str, Any]:
    import csv

    out = _runtime_output_dir()
    candidates = [
        out / "sn_factor_diagnostics.json",
        out / "factor_diagnostics.json",
        out / "sn_factor_diagnostics.csv",
        out / "factor_diagnostics.csv",
    ]
    rows: list[dict[str, Any]] = []
    missing_report: dict[str, Any] = {}
    for path in candidates:
        if not path.exists():
            continue
        if path.suffix.lower() == ".json":
            payload = _read_json_file(path)
            if isinstance(payload, Mapping):
                raw_rows = payload.get("features") or payload.get("factors") or payload.get("rows") or []
                if isinstance(raw_rows, list):
                    rows = [dict(item) for item in raw_rows if isinstance(item, Mapping)]
                missing_report = payload.get("missing_feature_report", {}) if isinstance(payload.get("missing_feature_report"), Mapping) else {}
            elif isinstance(payload, list):
                rows = [dict(item) for item in payload if isinstance(item, Mapping)]
        else:
            try:
                with path.open("r", encoding="utf-8-sig", newline="") as fh:
                    rows = [dict(item) for item in csv.DictReader(fh)]
            except Exception:
                rows = []
        if rows:
            break

    groups_map: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        group = _text(row.get("group") or row.get("group_zh"), "其他")
        groups_map.setdefault(group, []).append(
            {
                "name": _text(row.get("feature") or row.get("name"), "未命名因子"),
                "value": _to_float(row.get("value")),
                "ic": _to_float(row.get("ic")),
                "missing": bool(row.get("missing", False)),
                "direction_hint": _text(row.get("direction_hint"), "方向提示待验证"),
            }
        )
    groups = [{"group": group, "features": features[:50]} for group, features in groups_map.items()]
    return sanitize_for_json(
        {
            "groups": groups,
            "missing_feature_report": missing_report,
            "message_zh": "因子诊断已读取。" if groups else "暂无完整因子诊断数据，请先运行刷新任务。",
            "disclaimer": DISCLAIMER,
        }
    )

# ---------------------------------------------------------------------------
# Prompt 28 sample-mode overlays.
#
# Real runtime cache always wins. Sample data is only returned before the first
# refresh task writes a refresh_status file, so sample payloads never become
# real predictions, model inputs, or training artifacts.
# ---------------------------------------------------------------------------

_REAL_BUILD_TERMINAL_SUMMARY = build_terminal_summary
_REAL_BUILD_TERMINAL_PREDICTIONS = build_terminal_predictions
_REAL_BUILD_TERMINAL_SNAPSHOT = build_terminal_snapshot
_REAL_BUILD_TERMINAL_PRICE_HISTORY = build_terminal_price_history
_REAL_BUILD_TERMINAL_FORECAST_PATH = build_terminal_forecast_path
_REAL_BUILD_TERMINAL_NEWS_EVENTS = build_terminal_news_events
_REAL_BUILD_TERMINAL_REPORT_FULL = build_terminal_report_full
_REAL_BUILD_TERMINAL_REPORTS = build_terminal_reports
_REAL_BUILD_TERMINAL_EVENT_EVIDENCE = build_terminal_event_evidence


def _refresh_has_run() -> bool:
    payload = _read_json_file(_runtime_output_dir() / "refresh_status.json")
    return isinstance(payload, Mapping) and bool(payload.get("run_id") or payload.get("started_at"))


def _is_empty_sequence_payload(payload: Any, key: str) -> bool:
    return isinstance(payload, Mapping) and not payload.get(key)


def build_terminal_predictions() -> list[dict[str, Any]]:  # type: ignore[override]
    real = _REAL_BUILD_TERMINAL_PREDICTIONS()
    if real or _refresh_has_run():
        return real
    from .sample_data_service import sample_predictions

    return sanitize_for_json(sample_predictions())


def build_terminal_summary() -> dict[str, Any]:  # type: ignore[override]
    real = _REAL_BUILD_TERMINAL_SUMMARY()
    if _refresh_has_run() or real.get("latest_price"):
        return real
    history = build_terminal_price_history()
    points = history.get("points", []) if isinstance(history, Mapping) else []
    latest = points[-1].get("close") if points and isinstance(points[-1], Mapping) else None
    real.update(
        {
            "sample": True,
            "sample_mode": True,
            "sample_banner_zh": "当前为样例数据模式，请点击一键刷新数据获取真实数据。",
            "system_status": "样例数据模式",
            "data_quality_score": 0.0,
            "data_quality_label": "样例数据",
            "main_contract": "SN_SAMPLE",
            "latest_price": latest,
            "current_signal": "观望",
            "model_status": "样例模式",
            "risk_level": "数据不足",
            "last_update_time": "样例时间",
        }
    )
    return sanitize_for_json(real)


def build_terminal_price_history() -> dict[str, Any]:  # type: ignore[override]
    real = _REAL_BUILD_TERMINAL_PRICE_HISTORY()
    if not _is_empty_sequence_payload(real, "points") or _refresh_has_run():
        return real
    from .sample_data_service import sample_price_history

    return sanitize_for_json(sample_price_history())


def build_terminal_forecast_path() -> dict[str, Any]:  # type: ignore[override]
    real = _REAL_BUILD_TERMINAL_FORECAST_PATH()
    if not _is_empty_sequence_payload(real, "points") or _refresh_has_run():
        return real
    from .sample_data_service import sample_forecast_path

    return sanitize_for_json(sample_forecast_path())


def build_terminal_news_events() -> dict[str, Any]:  # type: ignore[override]
    real = _REAL_BUILD_TERMINAL_NEWS_EVENTS()
    if not _is_empty_sequence_payload(real, "events") or _refresh_has_run():
        return real
    from .sample_data_service import sample_news_events

    return sanitize_for_json(sample_news_events())


def build_terminal_event_evidence(horizon: str | None = None) -> dict[str, Any]:  # type: ignore[override]
    real = _REAL_BUILD_TERMINAL_EVENT_EVIDENCE(horizon)
    if not _is_empty_sequence_payload(real, "events") or _refresh_has_run():
        return real
    news = build_terminal_news_events()
    events = news.get("events", []) if isinstance(news, Mapping) else []
    count = len(events) if isinstance(events, list) else 0
    return sanitize_for_json(
        {
            "sample": True,
            "sample_mode": True,
            "sample_banner_zh": "当前为样例数据模式，请点击一键刷新数据获取真实数据。",
            "horizon": horizon or "tomorrow",
            "events": events if isinstance(events, list) else [],
            "event_count": count,
            "recognized_event_count": count,
            "used_in_model_event_count": 0,
            "rejected_event_count": count,
            "rejected_reason_breakdown": {"sample_data": count},
            "message_zh": "这是样例事件证据，仅用于演示界面结构，不进入模型。",
            "disclaimer": DISCLAIMER,
        }
    )


def build_terminal_report_full(report_type: str = "daily") -> dict[str, Any]:  # type: ignore[override]
    real = _REAL_BUILD_TERMINAL_REPORT_FULL(report_type)
    if real.get("markdown") or _refresh_has_run():
        return real
    from .sample_data_service import sample_report_full

    return sanitize_for_json(sample_report_full(report_type))


def build_terminal_reports() -> dict[str, Any]:  # type: ignore[override]
    real = _REAL_BUILD_TERMINAL_REPORTS()
    reports = real.get("reports", []) if isinstance(real, Mapping) else []
    has_markdown = any(isinstance(item, Mapping) and item.get("markdown") for item in reports)
    if has_markdown or _refresh_has_run():
        return real
    sample_reports: list[dict[str, Any]] = []
    for report_type in ("daily", "weekly", "monthly", "event"):
        full = build_terminal_report_full(report_type)
        markdown = str(full.get("markdown") or "")
        sample_reports.append(
            {
                "sample": True,
                "sample_mode": True,
                "type": report_type,
                "name": full.get("title"),
                "title": full.get("title"),
                "generated_at": full.get("generated_at"),
                "data_cutoff": full.get("data_cutoff"),
                "summary": markdown[:240],
                "markdown": markdown,
                "markdown_available": bool(markdown),
                "disclaimer": DISCLAIMER,
            }
        )
    return sanitize_for_json(
        {
            "sample": True,
            "sample_mode": True,
            "sample_banner_zh": "当前为样例数据模式，请点击一键刷新数据获取真实数据。",
            "reports": sample_reports,
            "disclaimer": DISCLAIMER,
        }
    )


def build_terminal_snapshot() -> dict[str, Any]:  # type: ignore[override]
    from .refresh_service import get_refresh_status

    summary = build_terminal_summary()
    refresh_status = get_refresh_status()
    now = _now()
    snapshot = {
        "summary": summary,
        "predictions": build_terminal_predictions(),
        # Keep the first-screen snapshot lightweight for PyInstaller cold starts.
        # Full details are still available from the dedicated model/learning/backtest APIs.
        "model_health": {
            "active_model": summary.get("model_status") if isinstance(summary, Mapping) else "模型状态待验证",
            "candidate_model": "请进入模型治理页查看候选模型",
            "degraded_models": [],
            "promotion_status": "请进入模型治理页查看完整晋级结果",
            "degradation_status": "未发现安装后启动阻断",
            "metrics_by_horizon": {},
            "failure_reasons": [],
            "last_check_time": now,
            "message_zh": "首页快照使用轻量模型健康摘要；完整信息请打开模型治理页。",
        },
        "learning_status": {
            "latest_market_refresh": refresh_status.get("updated_at") or refresh_status.get("finished_at"),
            "latest_prediction": "本周期未更新",
            "latest_validation": "暂未运行",
            "latest_calibration": "暂未运行",
            "latest_candidate_training": "暂未运行",
            "latest_walk_forward": "暂未运行",
            "latest_event_ablation": "暂未运行",
            "latest_promotion_check": "暂未运行",
            "next_task": "可点击一键刷新数据",
            "active_candidate_state": "首页轻量状态；完整学习状态请打开模型治理页。",
            "failure_reasons": [],
        },
        "backtest_diagnostics": {
            "message_zh": "首页快照不执行完整回测诊断；请进入回测与 Walk-forward 页面查看。",
            "walk_forward_metrics": {},
            "baseline_comparison": {},
            "cost_sensitivity": {},
            "promotion_gate_result": "未在首页快照运行",
            "failure_reasons": [],
        },
        "data_status": build_terminal_data_status(),
        "system_health": {
            "api_status": "正常",
            "data_status": "请查看数据源状态页",
            "model_status": summary.get("model_status") if isinstance(summary, Mapping) else "模型状态待验证",
            "storage_status": "用户数据目录可用",
            "report_status": "请查看报告中心",
            "frontend_status": "专业终端已构建",
            "warnings": [],
            "last_check_time": now,
        },
        "refresh_status": refresh_status,
        "disclaimer": DISCLAIMER,
    }
    predictions = snapshot.get("predictions", [])
    if (isinstance(summary, Mapping) and summary.get("sample_mode")) or any(
        isinstance(item, Mapping) and item.get("sample_mode") for item in predictions
    ):
        snapshot["sample"] = True
        snapshot["sample_mode"] = True
        snapshot["sample_banner_zh"] = "当前为样例数据模式，请点击一键刷新数据获取真实数据。"
        snapshot["message_zh"] = "这是样例数据，仅用于演示界面结构，不代表真实行情或预测。"
    return sanitize_for_json(snapshot)

# Prompt 28 stricter first-run sample fallback: bundled legacy fallbacks do not
# count as real user runtime cache. Actual refresh output files always win.
def _runtime_file_exists(*names: str) -> bool:
    out = _runtime_output_dir()
    return any((out / name).exists() for name in names)


def _runtime_report_exists(report_type: str = "daily") -> bool:
    try:
        return _report_file_for_type(report_type).exists()
    except Exception:
        return False


def build_terminal_predictions() -> list[dict[str, Any]]:  # type: ignore[override]
    if not _refresh_has_run() and not _runtime_file_exists("sn_unified_forecast.json", "sn_live_predictions.json"):
        from .sample_data_service import sample_predictions

        return sanitize_for_json(sample_predictions())
    return _REAL_BUILD_TERMINAL_PREDICTIONS()


def build_terminal_summary() -> dict[str, Any]:  # type: ignore[override]
    if not _refresh_has_run() and not _runtime_file_exists("sn_live_snapshot.json", "sn_market_history.json"):
        history = build_terminal_price_history()
        points = history.get("points", []) if isinstance(history, Mapping) else []
        latest = points[-1].get("close") if points and isinstance(points[-1], Mapping) else None
        return sanitize_for_json(
            {
                "sample": True,
                "sample_mode": True,
                "sample_banner_zh": "当前为样例数据模式，请点击一键刷新数据获取真实数据。",
                "system_status": "样例数据模式",
                "data_quality_score": 0.0,
                "data_quality_label": "样例数据",
                "main_contract": "SN_SAMPLE",
                "latest_price": latest,
                "price_change": None,
                "price_change_pct": None,
                "current_signal": "观望",
                "model_status": "样例模式",
                "backtest_status": "样例模式",
                "risk_level": "数据不足",
                "last_update_time": "样例时间",
                "disclaimer": DISCLAIMER,
            }
        )
    return _REAL_BUILD_TERMINAL_SUMMARY()


def build_terminal_price_history() -> dict[str, Any]:  # type: ignore[override]
    if not _refresh_has_run() and not _runtime_file_exists("sn_market_history.json", "sn_live_snapshot.json"):
        from .sample_data_service import sample_price_history

        return sanitize_for_json(sample_price_history())
    return _REAL_BUILD_TERMINAL_PRICE_HISTORY()


def build_terminal_forecast_path() -> dict[str, Any]:  # type: ignore[override]
    if not _refresh_has_run() and not _runtime_file_exists("sn_unified_forecast.json", "sn_live_predictions.json"):
        from .sample_data_service import sample_forecast_path

        return sanitize_for_json(sample_forecast_path())
    return _REAL_BUILD_TERMINAL_FORECAST_PATH()


def build_terminal_report_full(report_type: str = "daily") -> dict[str, Any]:  # type: ignore[override]
    if not _refresh_has_run() and not _runtime_report_exists(report_type):
        from .sample_data_service import sample_report_full

        return sanitize_for_json(sample_report_full(report_type))
    return _REAL_BUILD_TERMINAL_REPORT_FULL(report_type)


# ---------------------------------------------------------------------------
# Prompt 31 data-quality and provider-status overrides.
# ---------------------------------------------------------------------------

def _p31_read_json(path: Path) -> Any:
    try:
        if path.exists():
            import json

            return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return None


def _p31_market_paths() -> dict[str, Path]:
    out = _runtime_output_dir()
    return {
        "watermark": out / "data_watermark.json",
        "snapshot": out / "sn_live_snapshot.json",
        "history": out / "sn_market_history.json",
        "provider_status": out / "market_provider_status.json",
        "last_good": out / "last_good_market.json",
    }


def _p31_history_count(payload: Any) -> int:
    if isinstance(payload, Mapping):
        history = payload.get("history") or payload.get("points")
        return len(history) if isinstance(history, list) else 0
    if isinstance(payload, list):
        return len(payload)
    return 0


def _p31_report_count() -> int:
    names = ("daily", "weekly", "monthly", "event")
    return sum(1 for name in names if _runtime_report_exists(name))


def _p31_prediction_count() -> int:
    payload = _p31_read_json(_runtime_output_dir() / "sn_live_predictions.json") or _p31_read_json(_runtime_output_dir() / "sn_unified_forecast.json")
    if isinstance(payload, Mapping):
        cards = payload.get("cards")
        if isinstance(cards, Mapping):
            return len(cards)
        if isinstance(cards, list):
            return len(cards)
    return 0


def _p31_event_count() -> int:
    payload = _p31_read_json(_runtime_output_dir() / "events" / "event_store.json")
    if isinstance(payload, Mapping):
        events = payload.get("events")
        return len(events) if isinstance(events, list) else 0
    return 0


def _p31_source_status(
    *,
    source_name: str,
    enabled: bool,
    success: bool,
    from_cache: bool = False,
    last_update: str = "",
    message_zh: str = "",
    source_key: str = "daily_market",
    error_message_zh: str = "",
    suggested_action_zh: str = "查看运行期诊断",
) -> DataSourceStatus:
    from .freshness_policy import classify_freshness

    freshness = classify_freshness(source_key, last_update, None, enabled=enabled, success=success, from_cache=from_cache)
    status = DataSourceStatus(
        source_name=source_name,
        enabled=enabled,
        success=success,
        from_cache=from_cache,
        message_zh=message_zh or str(freshness.get("message_zh") or "状态待验证"),
        last_update=last_update or "本周期未更新",
        stale=bool(freshness.get("stale")),
        status_code=str(freshness.get("status_code") or "not_updated"),
        status_zh=str(freshness.get("status_zh") or "本周期未更新"),
        last_success_time=last_update if success else "本周期未更新",
        last_attempt_time=last_update or "本周期未更新",
        ttl_seconds=freshness.get("ttl_seconds"),
        ttl_zh=str(freshness.get("ttl_zh") or "本周期未更新"),
        next_expected_update_time=freshness.get("next_expected_update_time"),
        error_message_zh=error_message_zh,
        suggested_action_zh=suggested_action_zh,
    )
    return status


def build_terminal_data_status() -> dict[str, Any]:  # type: ignore[override]
    env = load_environment_config()
    paths = _p31_market_paths()
    watermark = _p31_read_json(paths["watermark"]) if paths["watermark"].exists() else {}
    provider_status = _p31_read_json(paths["provider_status"]) if paths["provider_status"].exists() else {}
    last_good = _p31_read_json(paths["last_good"]) if paths["last_good"].exists() else {}
    reports = _p31_report_count()

    sources: list[DataSourceStatus] = []
    latest_market_time = ""
    if isinstance(watermark, Mapping):
        latest_market_time = str(watermark.get("quote_time") or watermark.get("generated_at") or "")
    elif isinstance(last_good, Mapping):
        latest_market_time = str(last_good.get("quote_time") or last_good.get("generated_at") or "")

    if isinstance(last_good, Mapping) or isinstance(watermark, Mapping):
        has_market = bool((isinstance(watermark, Mapping) and watermark.get("latest_price")) or (isinstance(last_good, Mapping) and last_good.get("latest_price")))
        sources.append(
            _p31_source_status(
                source_name="本地行情缓存",
                enabled=True,
                success=has_market,
                from_cache=bool(isinstance(watermark, Mapping) and watermark.get("from_cache")),
                last_update=latest_market_time,
                message_zh="使用最近成功缓存。" if bool(isinstance(watermark, Mapping) and watermark.get("from_cache")) else "行情缓存可用。" if has_market else "尚未写入可用行情缓存。",
                source_key="local_market_cache",
                error_message_zh="" if has_market else "未找到 latest_price。",
                suggested_action_zh="点击刷新行情",
            )
        )
    else:
        sources.append(
            _p31_source_status(
                source_name="本地行情缓存",
                enabled=True,
                success=False,
                last_update="",
                message_zh="尚未生成行情缓存，请点击刷新行情。",
                source_key="local_market_cache",
                error_message_zh="last_good_market.json 不存在。",
                suggested_action_zh="点击刷新行情",
            )
        )

    providers = provider_status.get("providers", []) if isinstance(provider_status, Mapping) and isinstance(provider_status.get("providers"), list) else []
    for item in providers:
        if not isinstance(item, Mapping):
            continue
        name = str(item.get("provider_name") or item.get("provider") or "行情源")
        last_update = str(item.get("latest_time") or item.get("finished_at") or item.get("last_success_time") or "")
        sources.append(
            _p31_source_status(
                source_name=name,
                enabled=True,
                success=bool(item.get("success")),
                from_cache=bool(item.get("from_cache")),
                last_update=last_update,
                message_zh=str(item.get("error_message_zh") or ("行情源可用。" if item.get("success") else "行情源请求失败。")),
                source_key=name,
                error_message_zh=str(item.get("error_message_zh") or ""),
                suggested_action_zh="稍后重试或查看运行期诊断",
            )
        )

    sources.append(
        _p31_source_status(
            source_name="Alpha Vantage",
            enabled=bool(env.alpha_vantage.enabled),
            success=False,
            from_cache=False,
            last_update="",
            message_zh="已配置，等待宏观/外盘任务验证。" if env.alpha_vantage.enabled else "未配置 SN_ALPHA_VANTAGE_KEY。",
            source_key="daily_market",
            suggested_action_zh="前往设置配置 Alpha Vantage（可选）",
        )
    )
    sources.append(
        _p31_source_status(
            source_name="NewsAPI",
            enabled=bool(env.newsapi.enabled),
            success=False,
            from_cache=False,
            last_update="",
            message_zh="已配置，等待新闻刷新验证。" if env.newsapi.enabled else "未配置 SN_NEWSAPI_KEY。",
            source_key="newsapi",
            suggested_action_zh="前往设置配置 NewsAPI（可选）",
        )
    )
    sources.append(
        _p31_source_status(
            source_name="报告输出",
            enabled=True,
            success=reports > 0,
            last_update=_now() if reports > 0 else "",
            message_zh=f"已生成 {reports} 份报告。" if reports > 0 else "暂无报告，请点击生成报告。",
            source_key="reports",
            suggested_action_zh="生成报告",
        )
    )
    return sanitize_for_json({"sources": sources, "data_watermark": watermark or {}, "provider_status": provider_status or {}, "disclaimer": DISCLAIMER})


def build_terminal_summary() -> dict[str, Any]:  # type: ignore[override]
    from .data_quality_service import compute_data_quality_score

    if not _refresh_has_run() and not _runtime_file_exists("sn_live_snapshot.json", "sn_market_history.json"):
        history = build_terminal_price_history()
        points = history.get("points", []) if isinstance(history, Mapping) else []
        latest = points[-1].get("close") if points and isinstance(points[-1], Mapping) else None
        return sanitize_for_json(
            {
                "sample": True,
                "sample_mode": True,
                "sample_banner_zh": "当前为样例数据模式，请点击一键刷新数据获取真实数据。",
                "system_status": "样例数据模式",
                "data_quality_score": 0.0,
                "data_quality_label": "样例数据",
                "data_quality_components": {"sample_quality": {"score": 0.0, "reason_zh": "样例数据不计入真实质量。"}},
                "data_quality_blocking_reasons": ["当前为样例数据模式。"],
                "data_quality_degradation_reasons": ["请点击一键刷新数据。"],
                "data_quality_next_actions_zh": ["点击一键刷新数据"],
                "main_contract": "SN_SAMPLE",
                "latest_price": latest,
                "price_change": None,
                "price_change_pct": None,
                "current_signal": "观望",
                "model_status": "样例模式",
                "backtest_status": "样例模式",
                "risk_level": "数据不足",
                "last_update_time": "样例时间",
                "disclaimer": DISCLAIMER,
            }
        )

    paths = _p31_market_paths()
    watermark = _p31_read_json(paths["watermark"]) if paths["watermark"].exists() else {}
    snapshot = _p31_read_json(paths["snapshot"]) if paths["snapshot"].exists() else {}
    history_payload = _p31_read_json(paths["history"]) if paths["history"].exists() else {}
    data_status = build_terminal_data_status()
    sources = data_status.get("sources", []) if isinstance(data_status, Mapping) else []
    history_rows = _p31_history_count(history_payload)
    quality = compute_data_quality_score(
        {
            "latest_price": (watermark or {}).get("latest_price") if isinstance(watermark, Mapping) else None,
            "quote_time": (watermark or {}).get("quote_time") if isinstance(watermark, Mapping) else None,
            "from_cache": bool((watermark or {}).get("from_cache")) if isinstance(watermark, Mapping) else False,
            "history_rows": history_rows,
            "news_configured": bool(load_environment_config().newsapi.enabled),
            "news_count": _p31_event_count(),
            "event_count": _p31_event_count(),
            "report_count": _p31_report_count(),
            "prediction_count": _p31_prediction_count(),
            "model_status": "待验证",
        }
    )
    latest_price = (watermark or {}).get("latest_price") if isinstance(watermark, Mapping) else None
    if latest_price is None and isinstance(snapshot, Mapping):
        latest_price = snapshot.get("latest_price")
    latest_update = ""
    if isinstance(watermark, Mapping):
        latest_update = str(watermark.get("quote_time") or watermark.get("generated_at") or "")
    return sanitize_for_json(
        {
            "system_status": "数据不足" if quality["score"] < 0.45 else "降级" if quality["score"] < 0.70 else "正常",
            "data_quality_score": quality["score"],
            "data_quality_label": quality["label"],
            "data_quality_components": quality["components"],
            "data_quality_blocking_reasons": quality["blocking_reasons"],
            "data_quality_degradation_reasons": quality["degradation_reasons"],
            "data_quality_next_actions_zh": quality["next_actions_zh"],
            "main_contract": (watermark or {}).get("active_contract") if isinstance(watermark, Mapping) else "SN",
            "latest_price": latest_price,
            "price_change": None,
            "price_change_pct": None,
            "current_signal": "观望",
            "model_status": "待验证",
            "backtest_status": "待验证",
            "risk_level": "高" if quality["score"] < 0.45 else "中" if quality["score"] < 0.70 else "低",
            "last_update_time": latest_update or "本周期未更新",
            "data_source_available_count": sum(1 for source in sources if isinstance(source, Mapping) and source.get("success")),
            "disclaimer": DISCLAIMER,
        }
    )


def build_terminal_snapshot() -> dict[str, Any]:  # type: ignore[override]
    from .refresh_service import get_refresh_status

    summary = build_terminal_summary()
    snapshot = {
        "summary": summary,
        "predictions": build_terminal_predictions(),
        "model_health": build_terminal_model_health(),
        "learning_status": build_terminal_learning_status(),
        "backtest_diagnostics": build_terminal_backtest_diagnostics(None),
        "data_status": build_terminal_data_status(),
        "system_health": build_terminal_system_health(),
        "refresh_status": get_refresh_status(),
        "disclaimer": DISCLAIMER,
    }
    if isinstance(summary, Mapping) and summary.get("sample_mode"):
        snapshot["sample"] = True
        snapshot["sample_mode"] = True
        snapshot["sample_banner_zh"] = summary.get("sample_banner_zh")
    return sanitize_for_json(snapshot)

def _final_canonical_duplicate_source(source: Mapping[str, Any], canonical_ids: set[str]) -> bool:
    provider_id = str(source.get("provider_id") or "").strip().lower()
    source_key = str(source.get("source_key") or "").strip().lower()
    source_name = str(source.get("source_name") or "").strip().lower()
    if provider_id and provider_id in canonical_ids:
        return True
    canonical_aliases = {
        "market",
        "market_data",
        "alpha",
        "alpha_vantage",
        "cross_market",
        "fx_macro",
        "news",
        "newsapi",
        "event",
        "events",
        "tushare",
        "managed_proxy",
        "managed",
        "shfe_public",
        "lme_tin",
    }
    if source_key in canonical_aliases:
        return True
    return any(
        token in source_name
        for token in (
            "alpha",
            "newsapi",
            "tushare",
            "managed proxy",
            "managed_proxy",
            "market data",
            "lme tin",
        )
    )

_CANONICAL_PREVIOUS_BUILD_TERMINAL_DATA_STATUS = build_terminal_data_status


def _canonical_source_row(row: Mapping[str, Any]) -> dict[str, Any]:
    provider_id = str(row.get("provider_id") or "")
    label = {
        "market": "Market data",
        "alpha_vantage": "Alpha Vantage",
        "newsapi": "NewsAPI",
        "tushare": "Tushare",
        "managed_proxy": "Managed Proxy",
        "shfe_public": "SHFE 公共数据",
        "lme_tin": "LME tin",
        "akshare_history": "AKShare history",
    }.get(provider_id, provider_id or "provider")
    status = str(row.get("status") or "unknown")
    success = status == "success"
    from_cache = bool(row.get("from_cache"))
    freshness = {
        "success": "正常",
        "not_configured": "未配置",
        "token_missing": "未配置",
        "key_missing": "未配置",
        "disabled": "未启用",
        "using_cache": "使用缓存",
        "using_cache_rate_limited": "使用缓存",
        "optional_failed": "可选源不可用",
    }.get(status, str(row.get("freshness_label") or status))
    stale = bool(row.get("stale")) and status not in {"not_configured", "token_missing", "key_missing", "disabled"}
    next_actions = ["去设置页配置"] if status in {"not_configured", "token_missing", "key_missing"} else ["查看运行期诊断"]
    return {
        "source_name": label,
        "source_key": provider_id,
        "provider_id": provider_id,
        "enabled": bool(row.get("enabled")),
        "configured": bool(row.get("configured")),
        "attempted": bool(row.get("last_attempt_time")),
        "status": status,
        "success": success,
        "from_cache": from_cache,
        "message_zh": str(row.get("message_zh") or ""),
        "last_update": str(row.get("last_success_time") or row.get("last_attempt_time") or ""),
        "stale": stale,
        "status_code": status,
        "status_zh": status,
        "freshness_label": freshness,
        "last_success_time": str(row.get("last_success_time") or ""),
        "last_attempt_time": str(row.get("last_attempt_time") or ""),
        "ttl_seconds": None,
        "ttl_zh": "按数据源更新",
        "next_expected_update": "",
        "next_expected_update_time": "",
        "row_count": int(row.get("row_count") or 0),
        "error_code": "" if success or from_cache else status,
        "error_message_zh": "" if success or from_cache else str(row.get("message_zh") or ""),
        "next_actions_zh": next_actions,
        "suggested_action_zh": "；".join(next_actions),
        "provider_status_source": "provider_status_canonical.json",
        "source_file": str(row.get("source_file") or ""),
        "status_time": str(row.get("status_time") or row.get("last_attempt_time") or ""),
        "data_time": str(row.get("data_time") or row.get("last_success_time") or ""),
        "report_time": str(row.get("report_time") or ""),
    }


def build_terminal_data_status() -> dict[str, Any]:  # type: ignore[override]
    previous = _CANONICAL_PREVIOUS_BUILD_TERMINAL_DATA_STATUS()
    try:
        from .provider_status_canonical_service import build_canonical_provider_status

        canonical = build_canonical_provider_status()
    except Exception:
        return previous
    provider_list = canonical.get("provider_list") if isinstance(canonical, Mapping) else []
    sources = [_canonical_source_row(row) for row in provider_list if isinstance(row, Mapping)]
    payload = dict(previous) if isinstance(previous, Mapping) else {}
    payload["sources"] = sanitize_for_json(sources)
    payload["provider_status_canonical"] = canonical
    payload["provider_status_source"] = "provider_status_canonical.json"
    payload["report_time"] = canonical.get("generated_at") if isinstance(canonical, Mapping) else _now()
    return sanitize_for_json(payload)


def build_terminal_summary() -> dict[str, Any]:  # type: ignore[override]
    """Connection-time summary; avoid slow provider and model checks."""
    paths = _p31_market_paths()
    watermark = _p31_read_json(paths["watermark"]) if paths["watermark"].exists() else {}
    snapshot = _p31_read_json(paths["snapshot"]) if paths["snapshot"].exists() else {}
    has_real_data = any(paths[name].exists() for name in ("watermark", "snapshot", "history", "last_good"))

    if not has_real_data and not _refresh_has_run():
        return sanitize_for_json(
            {
                "sample": True,
                "sample_mode": True,
                "sample_banner_zh": "当前为样例数据模式，请点击一键刷新数据获取真实数据。",
                "system_status": "样例数据模式",
                "data_quality_score": 0.0,
                "data_quality_label": "样例数据",
                "data_quality_components": {},
                "data_quality_blocking_reasons": ["当前为样例数据模式。"],
                "data_quality_degradation_reasons": ["请点击一键刷新数据。"],
                "data_quality_next_actions_zh": ["刷新市场数据"],
                "main_contract": "SN_SAMPLE",
                "latest_price": None,
                "price_change": None,
                "price_change_pct": None,
                "current_signal": "观望",
                "model_status": "无 active",
                "backtest_status": "研究观察",
                "risk_level": "数据不足",
                "last_update_time": _now(),
                "customer_prediction_generated": False,
                "active_updated": False,
                "baseline_used": False,
                "fake_prediction_generated": False,
                "disclaimer": DISCLAIMER,
            }
        )

    latest_price = None
    quote_time = ""
    active_contract = "SN"
    from_cache = False
    if isinstance(watermark, Mapping):
        latest_price = watermark.get("latest_price")
        quote_time = str(watermark.get("quote_time") or watermark.get("generated_at") or "")
        active_contract = str(watermark.get("active_contract") or watermark.get("target_contract") or active_contract)
        from_cache = bool(watermark.get("from_cache"))
    if latest_price is None and isinstance(snapshot, Mapping):
        latest_price = snapshot.get("latest_price") or snapshot.get("close")
        quote_time = quote_time or str(snapshot.get("quote_time") or snapshot.get("generated_at") or "")
        active_contract = str(snapshot.get("active_contract") or snapshot.get("contract") or active_contract)

    has_price = latest_price is not None
    quality = 0.72 if has_price and from_cache else 0.82 if has_price else 0.35
    return sanitize_for_json(
        {
            "system_status": "缓存可用" if from_cache else "正常" if has_price else "数据不足",
            "data_quality_score": quality,
            "data_quality_label": "缓存可用" if from_cache else "较可靠" if has_price else "数据质量不足",
            "data_quality_components": {},
            "data_quality_blocking_reasons": [] if has_price else ["暂无最新行情价格。"],
            "data_quality_degradation_reasons": ["当前使用缓存。"] if from_cache else [],
            "data_quality_next_actions_zh": ["如需更新，请刷新市场数据。"] if from_cache else [],
            "main_contract": active_contract,
            "latest_price": _as_float(latest_price),
            "price_change": None,
            "price_change_pct": None,
            "current_signal": "观望",
            "model_status": "无 active",
            "backtest_status": "研究观察",
            "risk_level": "中" if has_price else "高",
            "last_update_time": quote_time or _now(),
            "customer_prediction_generated": False,
            "active_updated": False,
            "baseline_used": False,
            "fake_prediction_generated": False,
            "disclaimer": DISCLAIMER,
        }
    )

# Prompt 32 override: normalize news/policy provider statuses so optional or
# cached sources are not mislabeled as expired.
_P32_PREVIOUS_BUILD_TERMINAL_DATA_STATUS = build_terminal_data_status


def _p32_events_provider_status() -> list[Mapping[str, Any]]:
    payload = _p31_read_json(_runtime_output_dir() / "events" / "provider_status.json")
    providers = payload.get("providers", []) if isinstance(payload, Mapping) else []
    return [item for item in providers if isinstance(item, Mapping)]


def _p32_find_provider(name: str) -> Mapping[str, Any] | None:
    target = name.lower()
    for item in _p32_events_provider_status():
        candidates = (
            item.get("name"),
            item.get("provider"),
            item.get("source_name"),
            item.get("provider_name"),
        )
        if any(str(value or "").lower() == target for value in candidates):
            return item
    return None


def _p32_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value if item]
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return []


def _p32_status(
    *,
    source_name: str,
    source_key: str,
    enabled: bool,
    configured: bool,
    attempted: bool = False,
    success: bool = False,
    from_cache: bool = False,
    last_attempt_time: str = "",
    last_success_time: str = "",
    row_count: int = 0,
    error_code: str = "",
    error_message_zh: str = "",
    message_zh: str = "",
    next_actions_zh: list[str] | None = None,
) -> dict[str, Any]:
    from .freshness_policy import classify_freshness

    status = classify_freshness(
        source_key,
        last_success_time or last_attempt_time,
        success=success,
        enabled=enabled,
        from_cache=from_cache,
    )
    if not configured and not enabled:
        status.update(
            {
                "status_code": "unconfigured",
                "status_zh": "未配置",
                "freshness_label": "未配置",
                "stale": False,
            }
        )
    if enabled is False and configured is False and source_key in {"akshare_news", "miit_policy"}:
        status.update(
            {
                "status_code": "disabled",
                "status_zh": "未启用",
                "freshness_label": "未启用",
                "stale": False,
            }
        )
    label = str(status.get("freshness_label") or status.get("status_zh") or "本周期未更新")
    return {
        "source_name": source_name,
        "enabled": enabled,
        "configured": configured,
        "attempted": attempted,
        "success": success,
        "from_cache": from_cache,
        "stale": bool(status.get("stale")),
        "freshness_label": label,
        "status_code": str(status.get("status_code") or ""),
        "status_zh": label,
        "last_attempt_time": last_attempt_time or "本周期未更新",
        "last_success_time": last_success_time or "本周期未更新",
        "last_update": last_success_time or last_attempt_time or "本周期未更新",
        "ttl_seconds": status.get("ttl_seconds"),
        "ttl_zh": str(status.get("ttl_zh") or "本周期未更新"),
        "next_expected_update": status.get("next_expected_update"),
        "next_expected_update_time": status.get("next_expected_update_time"),
        "row_count": int(row_count or 0),
        "error_code": error_code,
        "error_message_zh": error_message_zh,
        "message_zh": message_zh or label,
        "next_actions_zh": next_actions_zh or [],
        "suggested_action_zh": "；".join(next_actions_zh or []) or "查看运行期诊断",
    }


def _p32_status_from_provider(source_name: str, source_key: str, fallback_message: str) -> dict[str, Any]:
    item = _p32_find_provider(source_key)
    if not item:
        return _p32_status(
            source_name=source_name,
            source_key=source_key,
            enabled=False,
            configured=False,
            attempted=False,
            success=False,
            message_zh=fallback_message,
            next_actions_zh=["当前版本未启用该自动源", "可使用 NewsAPI、SHFE 公共数据或本地缓存补位"],
        )
    return _p32_status(
        source_name=source_name,
        source_key=source_key,
        enabled=bool(item.get("enabled", True)),
        configured=bool(item.get("configured", True)),
        attempted=bool(item.get("attempted", True)),
        success=bool(item.get("success")),
        from_cache=bool(item.get("from_cache")),
        last_attempt_time=str(item.get("last_attempt_time") or item.get("updated_at") or item.get("finished_at") or ""),
        last_success_time=str(item.get("last_success_time") or item.get("latest_time") or ""),
        row_count=int(item.get("row_count") or item.get("fetched_count") or item.get("returned_count") or 0),
        error_code=str(item.get("error_code") or ""),
        error_message_zh=str(item.get("error_message_zh") or item.get("error") or ""),
        message_zh=str(item.get("message_zh") or item.get("message") or fallback_message),
        next_actions_zh=_p32_list(item.get("next_actions_zh")),
    )


def _p32_newsapi_status() -> dict[str, Any]:
    env = load_environment_config()
    item = _p32_find_provider("newsapi")
    if not env.newsapi.enabled:
        return _p32_status(
            source_name="NewsAPI",
            source_key="newsapi",
            enabled=False,
            configured=False,
            attempted=False,
            success=False,
            message_zh="未配置 NewsAPI，新闻刷新会跳过。",
            next_actions_zh=["去设置页配置 NewsAPI", "配置后点击刷新新闻"],
        )
    if not item:
        return _p32_status(
            source_name="NewsAPI",
            source_key="newsapi",
            enabled=True,
            configured=True,
            attempted=False,
            success=False,
            message_zh="NewsAPI 已配置，尚未运行新闻刷新。",
            next_actions_zh=["点击刷新新闻", "查看最近错误"],
        )
    return _p32_status(
        source_name="NewsAPI",
        source_key="newsapi",
        enabled=True,
        configured=True,
        attempted=bool(item.get("attempted", True)),
        success=bool(item.get("success")),
        from_cache=bool(item.get("from_cache")),
        last_attempt_time=str(item.get("last_attempt_time") or item.get("updated_at") or ""),
        last_success_time=str(item.get("last_success_time") or ""),
        row_count=int(item.get("row_count") or (len(item.get("articles") or []) if isinstance(item.get("articles"), list) else 0)),
        error_code=str(item.get("error_code") or ""),
        error_message_zh=str(item.get("error_message_zh") or ""),
        message_zh=str(item.get("message_zh") or item.get("message") or "NewsAPI 状态已记录。"),
        next_actions_zh=_p32_list(item.get("next_actions_zh")),
    )


def _p32_shfe_public_status(existing: Mapping[str, Any] | None) -> dict[str, Any]:
    if existing:
        return _p32_status(
            source_name="SHFE 公共数据",
            source_key="shfe_public",
            enabled=bool(existing.get("enabled", True)),
            configured=bool(existing.get("configured", True)),
            attempted=bool(existing.get("attempted", True)),
            success=bool(existing.get("success")),
            from_cache=bool(existing.get("from_cache")),
            last_attempt_time=str(existing.get("last_attempt_time") or existing.get("last_update") or ""),
            last_success_time=str(existing.get("last_success_time") or existing.get("last_update") or ""),
            row_count=int(existing.get("row_count") or 0),
            error_code=str(existing.get("error_code") or ""),
            error_message_zh=str(existing.get("error_message_zh") or ""),
            message_zh=str(existing.get("message_zh") or "SHFE 公共数据状态已记录。"),
            next_actions_zh=_p32_list(existing.get("next_actions_zh")),
        )
    return _p32_status(
        source_name="SHFE 公共数据",
        source_key="shfe_public",
        enabled=True,
        configured=True,
        attempted=False,
        success=False,
        message_zh="SHFE 公共数据尚未刷新；该源按日线/库存/仓单节奏更新，不按 tick 级判定过期。",
        next_actions_zh=["点击刷新行情", "非交易日可等待下一交易日更新"],
    )


def build_terminal_data_status() -> dict[str, Any]:  # type: ignore[override]
    previous = _P32_PREVIOUS_BUILD_TERMINAL_DATA_STATUS()
    previous_sources = previous.get("sources", []) if isinstance(previous, Mapping) and isinstance(previous.get("sources"), list) else []
    normalized: list[dict[str, Any]] = []
    shfe_existing: Mapping[str, Any] | None = None
    skip_names = {"NewsAPI", "akshare_news", "AKShare 新闻", "miit_policy", "工信部政策", "shfe_public", "SHFE 公共数据"}
    for source in previous_sources:
        if not isinstance(source, Mapping):
            continue
        name = str(source.get("source_name") or "")
        if name.lower() == "shfe_public" or "shfe" in name.lower():
            shfe_existing = source
            continue
        if name in skip_names:
            continue
        normalized.append(dict(source))

    normalized.append(_p32_newsapi_status())
    normalized.append(
        _p32_status_from_provider(
            "AKShare 新闻",
            "akshare_news",
            "当前版本未启用 AKShare 新闻源；不会再将其误判为已过期。",
        )
    )
    normalized.append(
        _p32_status_from_provider(
            "工信部政策",
            "miit_policy",
            "当前版本未启用工信部政策自动抓取；政策源按周/月级别更新。",
        )
    )
    normalized.append(_p32_shfe_public_status(shfe_existing))
    previous = dict(previous) if isinstance(previous, Mapping) else {}
    previous["sources"] = sanitize_for_json(normalized)
    previous["provider_status_schema_version"] = "p32-news-policy-freshness"
    return sanitize_for_json(previous)


_P51_PREVIOUS_BUILD_TERMINAL_DATA_STATUS = build_terminal_data_status


def _p51_registry_sources() -> tuple[list[dict[str, Any]], Mapping[str, Any]]:
    from .online_data_source_registry import build_online_data_source_registry

    registry = build_online_data_source_registry()
    sources: list[dict[str, Any]] = []
    for item in registry.get("sources", []) if isinstance(registry.get("sources"), list) else []:
        if not isinstance(item, Mapping):
            continue
        status = str(item.get("status") or "unavailable")
        success = status in {"success", "available", "正常"}
        sources.append(
            {
                "source_name": f"在线源：{item.get('source_id')}",
                "source_key": str(item.get("source_id") or ""),
                "enabled": bool(item.get("enabled")),
                "configured": not bool(item.get("requires_key")) or status not in {"key_missing", "token_missing"},
                "attempted": True,
                "success": success,
                "from_cache": False,
                "stale": False,
                "freshness_label": status,
                "status_code": status,
                "status_zh": status,
                "last_attempt_time": str(registry.get("generated_at") or ""),
                "last_success_time": str(item.get("last_success_time") or ""),
                "last_update": str(item.get("last_success_time") or registry.get("generated_at") or ""),
                "ttl_seconds": item.get("ttl_seconds"),
                "ttl_zh": "在线源自动刷新",
                "next_expected_update": "",
                "next_expected_update_time": "",
                "row_count": 0,
                "error_code": "" if success else status,
                "error_message_zh": "",
                "message_zh": "客户不需要 CSV/Excel；系统自动尝试该在线源。",
                "next_actions_zh": _p32_list(item.get("next_actions_zh")),
                "suggested_action_zh": "；".join(_p32_list(item.get("next_actions_zh"))),
                "online_category": item.get("category"),
                "provider": item.get("provider"),
                "requires_key": bool(item.get("requires_key")),
                "client_upload_required": False,
                "fields_provided": item.get("fields_provided") or [],
            }
        )
    return sources, registry


def build_terminal_data_status() -> dict[str, Any]:  # type: ignore[override]
    previous = _P51_PREVIOUS_BUILD_TERMINAL_DATA_STATUS()
    sources = previous.get("sources", []) if isinstance(previous, Mapping) and isinstance(previous.get("sources"), list) else []
    normalized = [dict(source) for source in sources if isinstance(source, Mapping)]
    registry_sources, registry = _p51_registry_sources()
    normalized.extend(registry_sources)
    previous = dict(previous) if isinstance(previous, Mapping) else {}
    previous["sources"] = sanitize_for_json(normalized)
    previous["online_data_source_registry"] = registry
    previous["client_upload_required"] = False
    previous["online_source_message_zh"] = "客户不需要 CSV/Excel；系统会自动尝试公开在线源、API key 源和可选托管源。"
    return sanitize_for_json(previous)


_P45_PREVIOUS_BUILD_TERMINAL_DATA_STATUS = build_terminal_data_status


def _p45_status_file_to_source(path: Path, source_name: str, source_key: str) -> dict[str, Any] | None:
    payload = _read_json_file(path)
    if not isinstance(payload, Mapping):
        return None
    return _p32_status(
        source_name=source_name,
        source_key=source_key,
        enabled=bool(payload.get("enabled", True)),
        configured=bool(payload.get("configured", False)),
        attempted=bool(payload.get("attempted", True)),
        success=bool(payload.get("success")),
        from_cache=bool(payload.get("from_cache")),
        last_attempt_time=str(payload.get("last_attempt_time") or payload.get("generated_at") or ""),
        last_success_time=str(payload.get("last_success_time") or ""),
        row_count=int(payload.get("row_count") or 0),
        error_code=str(payload.get("error_code") or ""),
        error_message_zh=str(payload.get("error_message_zh") or ""),
        message_zh=str(payload.get("message_zh") or "机构级因子数据源状态已记录。"),
        next_actions_zh=_p32_list(payload.get("next_actions_zh")),
    )


def build_terminal_data_status() -> dict[str, Any]:  # type: ignore[override]
    previous = _P45_PREVIOUS_BUILD_TERMINAL_DATA_STATUS()
    sources = previous.get("sources", []) if isinstance(previous, Mapping) and isinstance(previous.get("sources"), list) else []
    normalized = [dict(source) for source in sources if isinstance(source, Mapping)]
    output_dir = _runtime_output_dir()
    for source in (
        _p45_status_file_to_source(output_dir / "fundamentals" / "term_structure_status.json", "期限结构", "term_structure"),
        _p45_status_file_to_source(output_dir / "fundamentals" / "fundamental_status.json", "基差/库存/仓单", "fundamentals"),
        _p45_status_file_to_source(output_dir / "fundamentals" / "cross_market_status.json", "外盘/汇率/宏观", "cross_market"),
        _p45_status_file_to_source(output_dir / "events" / "news_relevance_status.json", "新闻相关性", "news_relevance"),
    ):
        if source is not None:
            normalized.append(source)
    previous = dict(previous) if isinstance(previous, Mapping) else {}
    previous["sources"] = sanitize_for_json(normalized)
    previous["institutional_factor_sources"] = True
    return sanitize_for_json(previous)


_P50_PREVIOUS_BUILD_TERMINAL_DATA_STATUS = build_terminal_data_status


def _p50_load_shfe_provider_status() -> Mapping[str, Any]:
    payload = _read_json_file(_runtime_output_dir() / "fundamentals" / "shfe_public_provider_status.json")
    return payload if isinstance(payload, Mapping) else {}


def _p50_result(provider_status: Mapping[str, Any], key: str) -> Mapping[str, Any]:
    results = provider_status.get("results")
    if isinstance(results, Mapping):
        value = results.get(key)
        if isinstance(value, Mapping):
            return value
    return {}


def _p50_label_for_status(status: str, success: bool) -> str:
    if status == "blocked_by_waf":
        return "blocked_by_waf"
    if success:
        return "正常"
    if status == "function_unavailable":
        return "函数不可用"
    if status == "no_tin_rows":
        return "无锡数据"
    if status == "missing_required_columns":
        return "字段不匹配"
    if status == "request_failed":
        return "请求失败"
    return status or "未刷新"


def _p50_result_source(
    *,
    source_name: str,
    source_key: str,
    result: Mapping[str, Any],
    fallback_message: str,
) -> dict[str, Any]:
    status = str(result.get("status") or "")
    success = bool(result.get("success"))
    label = _p50_label_for_status(status, success)
    attempts = result.get("attempts") if isinstance(result.get("attempts"), list) else []
    row_count = int(result.get("row_count") or 0)
    return {
        "source_name": source_name,
        "source_key": source_key,
        "enabled": True,
        "configured": True,
        "attempted": bool(result) and bool(result.get("attempted", True)),
        "success": success,
        "from_cache": bool(result.get("from_cache") or result.get("cache_used")),
        "stale": False,
        "freshness_label": label,
        "status_code": status,
        "status_zh": label,
        "last_attempt_time": str(result.get("last_attempt_time") or result.get("generated_at") or ""),
        "last_success_time": str(result.get("last_success_time") or ""),
        "last_update": str(result.get("last_success_time") or result.get("last_attempt_time") or result.get("generated_at") or ""),
        "ttl_seconds": None,
        "ttl_zh": "按交易所日频/辅助数据源更新",
        "next_expected_update": "",
        "next_expected_update_time": "",
        "row_count": row_count,
        "error_code": status if not success else "",
        "error_message_zh": str(result.get("error_message_zh") or ""),
        "message_zh": str(result.get("message_zh") or result.get("error_message_zh") or fallback_message),
        "next_actions_zh": _p32_list(result.get("next_actions_zh"))
        or ["检查 AKShare 版本和网络；如无锡数据，不要用其它品种替代。"],
        "suggested_action_zh": "；".join(_p32_list(result.get("next_actions_zh"))) or "查看 SHFE/AKShare 辅助源诊断",
        "attempt_count": len(attempts),
    }


def _p50_shfe_sources(provider_status: Mapping[str, Any]) -> list[dict[str, Any]]:
    direct = _p50_result(provider_status, "shfe_direct_probe")
    direct_message = (
        "SHFE 官网直连被人机验证阻断；系统已尝试 AKShare/缓存辅助源。"
        "该状态不影响主行情链路。"
    )
    direct_source = _p50_result_source(
        source_name="SHFE 官网直连",
        source_key="shfe_direct",
        result=direct,
        fallback_message=direct_message,
    )
    if direct_source["status_code"] == "blocked_by_waf":
        direct_source.update(
            {
                "freshness_label": "blocked_by_waf",
                "status_zh": "blocked_by_waf",
                "message_zh": direct_message,
                "error_message_zh": direct_message,
                "next_actions_zh": ["无需反复重试官网直连；优先查看 AKShare 库存、仓单、基差和缓存辅助源。"],
                "suggested_action_zh": "无需反复重试官网直连；优先查看 AKShare/缓存辅助源。",
            }
        )

    return [
        direct_source,
        _p50_result_source(
            source_name="AKShare SHFE 库存",
            source_key="akshare_shfe_inventory",
            result=_p50_result(provider_status, "shfe_inventory"),
            fallback_message="尚未获取到真实 SHFE 锡库存；不会用其它品种冒充。",
        ),
        _p50_result_source(
            source_name="AKShare 仓单",
            source_key="akshare_shfe_warehouse_receipts",
            result=_p50_result(provider_status, "shfe_warehouse_receipts"),
            fallback_message="尚未获取到真实 SHFE 锡注册仓单；不会伪造仓单数据。",
        ),
        _p50_result_source(
            source_name="现货基差",
            source_key="spot_basis",
            result=_p50_result(provider_status, "spot_basis"),
            fallback_message="尚未获取到真实现货锡价格或升贴水；基差因子保持不可用。",
        ),
        _p50_result_source(
            source_name="交易所日线 / 持仓",
            source_key="exchange_daily",
            result=_p50_result(provider_status, "exchange_daily"),
            fallback_message="尚未获取到真实交易所日线或持仓数据。",
        ),
        _p50_result_source(
            source_name="会员持仓排名",
            source_key="member_positions",
            result=_p50_result(provider_status, "member_positions"),
            fallback_message="尚未获取到真实会员持仓排名；该辅助源不影响主行情链路。",
        ),
    ]


def build_terminal_data_status() -> dict[str, Any]:  # type: ignore[override]
    previous = _P50_PREVIOUS_BUILD_TERMINAL_DATA_STATUS()
    sources = previous.get("sources", []) if isinstance(previous, Mapping) and isinstance(previous.get("sources"), list) else []
    normalized: list[dict[str, Any]] = []
    for source in sources:
        if not isinstance(source, Mapping):
            continue
        name = str(source.get("source_name") or "")
        key = str(source.get("source_key") or source.get("status_code") or "")
        lower = name.lower()
        if "shfe" in lower or "shfe_public" in key or name in {"SHFE 公共数据"}:
            if bool(source.get("success")) or bool(source.get("from_cache")):
                normalized.append(dict(source))
            continue
        normalized.append(dict(source))

    provider_status = _p50_load_shfe_provider_status()
    normalized.extend(_p50_shfe_sources(provider_status))
    previous = dict(previous) if isinstance(previous, Mapping) else {}
    previous["sources"] = sanitize_for_json(normalized)
    previous["shfe_public_split_sources"] = True
    previous["shfe_public_message_zh"] = (
        "SHFE 官网直连、AKShare 库存、仓单、现货基差、交易所日线和会员持仓已拆分显示；"
        "blocked_by_waf 不等于主行情失败。"
    )
    return sanitize_for_json(previous)


# Performance override: keep connection-time APIs lightweight. Heavy research,
# backtest, refresh and validation payloads are available through their own
# pages or task APIs and should not block the terminal shell.
def build_terminal_system_health() -> dict[str, Any]:  # type: ignore[override]
    env = load_environment_config()
    storage_status = "可写" if Path(env.data_dir).exists() else "数据目录待创建"
    health = SystemHealth(
        api_status="正常",
        data_status="待验证",
        model_status="待验证",
        storage_status=storage_status,
        report_status="正常",
        frontend_status="React 终端可用",
        warnings=["lightweight system-health 未调用慢 provider；深度诊断请使用 runtime-diagnostics。"],
        last_check_time=_now(),
    )
    return sanitize_for_json(
        {
            "mode": "lightweight",
            "generated_at": _now(),
            "cache_age_seconds": 0.0,
            "health": health,
            "truth_audit": {"status": "skipped", "message_zh": "轻量健康检查不调用慢 provider。"},
            "disclaimer": DISCLAIMER,
        }
    )


def build_terminal_snapshot() -> dict[str, Any]:  # type: ignore[override]
    from .refresh_service import get_refresh_status

    summary = build_terminal_summary()
    snapshot = {
        "snapshot_mode": "lite",
        "generated_at": _now(),
        "cache_age_seconds": 0.0,
        "summary": summary,
        "refresh_status": get_refresh_status(),
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


_TERMINAL_DATA_STATUS_CANONICAL_EXPORT_PREVIOUS = build_terminal_data_status


def build_terminal_data_status() -> dict[str, Any]:  # type: ignore[override]
    previous = _TERMINAL_DATA_STATUS_CANONICAL_EXPORT_PREVIOUS()
    try:
        from .provider_status_canonical_service import build_canonical_provider_status

        canonical = build_canonical_provider_status()
    except Exception:
        return sanitize_for_json(previous)

    provider_list = canonical.get("provider_list") if isinstance(canonical, Mapping) else []
    canonical_sources = [_canonical_source_row(row) for row in provider_list if isinstance(row, Mapping)]
    canonical_ids = {str(row.get("provider_id") or "").strip().lower() for row in canonical_sources}
    previous_sources = (
        previous.get("sources", []) if isinstance(previous, Mapping) and isinstance(previous.get("sources"), list) else []
    )
    preserved_sources = [
        dict(source)
        for source in previous_sources
        if isinstance(source, Mapping) and not _final_canonical_duplicate_source(source, canonical_ids)
    ]
    payload = dict(previous) if isinstance(previous, Mapping) else {}
    payload["sources"] = sanitize_for_json(canonical_sources + preserved_sources)
    payload["tushare_subinterfaces"] = _tushare_subinterfaces()
    payload["provider_status_canonical"] = canonical
    payload["provider_status_source"] = "provider_status_canonical.json"
    payload["report_time"] = canonical.get("generated_at") if isinstance(canonical, Mapping) else _now()
    return sanitize_for_json(payload)
