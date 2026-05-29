from __future__ import annotations

from typing import Any, Mapping


COMPONENT_WEIGHTS = {
    "market_latest_score": 30,
    "market_history_score": 20,
    "news_score": 15,
    "event_score": 10,
    "report_score": 10,
    "prediction_score": 10,
    "model_health_score": 5,
}


def _as_float(value: Any, default: float = 0.0) -> float:
    try:
        parsed = float(value)
    except Exception:
        return default
    if parsed != parsed or parsed in {float("inf"), float("-inf")}:
        return default
    return parsed


def _truthy_count(value: Any) -> int:
    if isinstance(value, Mapping):
        return len(value)
    if isinstance(value, (list, tuple, set)):
        return len(value)
    try:
        return int(value or 0)
    except Exception:
        return 0


def compute_data_quality_score(context: Mapping[str, Any] | None) -> dict[str, Any]:
    """Compute an explainable 0-1 quality score. No fixed 0.60 fallback."""
    ctx = dict(context or {})
    if ctx.get("sample_mode"):
        return {
            "score": 0.0,
            "label": "样例数据",
            "components": {"sample_quality": {"score": 0.0, "weight": 0, "reason_zh": "样例数据不计入真实数据质量。"}},
            "blocking_reasons": ["当前为样例数据模式。"],
            "degradation_reasons": ["请点击一键刷新数据获取真实数据。"],
            "next_actions_zh": ["点击一键刷新数据", "配置外部数据源密钥（可选）"],
        }

    latest_price = _as_float(ctx.get("latest_price"), 0.0)
    has_quote_time = bool(ctx.get("quote_time") or ctx.get("latest_time") or ctx.get("source_timestamp"))
    from_cache = bool(ctx.get("from_cache"))
    history_rows = _truthy_count(ctx.get("history_rows", ctx.get("history_count", ctx.get("history", []))))
    news_configured = bool(ctx.get("news_configured"))
    news_count = _truthy_count(ctx.get("news_count", ctx.get("news_events", [])))
    event_count = _truthy_count(ctx.get("event_count", ctx.get("events", [])))
    report_count = _truthy_count(ctx.get("report_count", ctx.get("reports", [])))
    prediction_count = _truthy_count(ctx.get("prediction_count", ctx.get("predictions", [])))
    model_status = str(ctx.get("model_status") or "").lower()

    components: dict[str, dict[str, Any]] = {}
    blocking: list[str] = []
    degradation: list[str] = []
    actions: list[str] = []

    if latest_price > 0 and has_quote_time and not from_cache:
        market_latest = 1.0
        latest_reason = "最新价和行情时间均可用。"
    elif latest_price > 0 and from_cache:
        market_latest = 0.55
        latest_reason = "仅有最近成功缓存，行情新鲜度打折。"
        degradation.append("行情来自缓存。")
    elif latest_price > 0:
        market_latest = 0.7
        latest_reason = "有最新价但行情时间不完整。"
        degradation.append("行情时间缺失。")
    else:
        market_latest = 0.0
        latest_reason = "未取得可用最新价。"
        blocking.append("缺少最新行情。")
        actions.append("刷新行情")

    if history_rows >= 60:
        market_history = 1.0
        history_reason = f"历史行情 {history_rows} 条，满足基础展示和特征计算。"
    elif history_rows >= 20:
        market_history = 0.55
        history_reason = f"历史行情 {history_rows} 条，短周期可参考但特征覆盖不足。"
        degradation.append("历史行情点数不足 60。")
    elif history_rows > 0:
        market_history = 0.25
        history_reason = f"历史行情仅 {history_rows} 条。"
        degradation.append("历史行情点数严重不足。")
        actions.append("刷新行情")
    else:
        market_history = 0.0
        history_reason = "未取得历史行情。"
        blocking.append("缺少历史行情。")
        actions.append("刷新行情")

    if news_count > 0:
        news_score = 1.0
        news_reason = f"近期新闻/事件 {news_count} 条。"
    elif news_configured:
        news_score = 0.35
        news_reason = "NewsAPI 已配置但暂无可用新闻。"
        degradation.append("新闻源暂无返回。")
        actions.append("刷新新闻")
    else:
        news_score = 0.2
        news_reason = "NewsAPI 未配置；未配置不等于请求失败，但事件因子覆盖下降。"
        degradation.append("NewsAPI 未配置。")
        actions.append("可在设置页配置 NewsAPI")

    if event_count > 0:
        event_score = 1.0
        event_reason = f"事件证据 {event_count} 条。"
    else:
        event_score = 0.25
        event_reason = "暂无事件证据，事件解释会降级。"
        degradation.append("事件证据为空。")

    if report_count > 0:
        report_score = 1.0
        report_reason = f"报告文件 {report_count} 份。"
    else:
        report_score = 0.25
        report_reason = "暂无真实报告，可生成数据不足版报告。"
        actions.append("生成报告")

    if prediction_count > 0:
        prediction_score = 1.0
        prediction_reason = f"预测卡片 {prediction_count} 个。"
    else:
        prediction_score = 0.0
        prediction_reason = "暂无真实预测卡片。"
        blocking.append("缺少真实预测。")
        actions.append("生成预测")

    if "degraded" in model_status or "降级" in model_status:
        model_health_score = 0.35
        model_reason = "模型处于降级状态。"
        degradation.append("模型健康下降。")
    elif "active" in model_status or "正常" in model_status or "可用" in model_status:
        model_health_score = 1.0
        model_reason = "模型状态可用。"
    else:
        model_health_score = 0.55
        model_reason = "模型状态待验证。"
        degradation.append("模型状态待验证。")

    raw_scores = {
        "market_latest_score": (market_latest, latest_reason),
        "market_history_score": (market_history, history_reason),
        "news_score": (news_score, news_reason),
        "event_score": (event_score, event_reason),
        "report_score": (report_score, report_reason),
        "prediction_score": (prediction_score, prediction_reason),
        "model_health_score": (model_health_score, model_reason),
    }
    weighted = 0.0
    for key, (score, reason) in raw_scores.items():
        weight = COMPONENT_WEIGHTS[key]
        weighted += score * weight
        components[key] = {"score": round(score, 4), "weight": weight, "reason_zh": reason}

    final_score = round(max(0.0, min(1.0, weighted / 100.0)), 4)
    if final_score >= 0.85:
        label = "优秀"
    elif final_score >= 0.70:
        label = "可用"
    elif final_score >= 0.45:
        label = "需谨慎"
    else:
        label = "数据不足"

    return {
        "score": final_score,
        "label": label,
        "components": components,
        "blocking_reasons": list(dict.fromkeys(blocking)),
        "degradation_reasons": list(dict.fromkeys(degradation)),
        "next_actions_zh": list(dict.fromkeys(actions or ["查看运行期诊断"])),
    }

