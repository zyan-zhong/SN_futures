from __future__ import annotations

from typing import Any, Mapping

from .payload_utils import DISCLAIMER, fmt_num, fmt_pct, label, sanitize_for_json


def _report_title(report_type: str) -> str:
    return {
        "daily": "沪锡期货多周期方向预测与事件驱动分析日报",
        "weekly": "沪锡期货周度方向与风险报告",
        "monthly": "沪锡期货月度产业链与模型报告",
        "event": "沪锡重大事件专项分析报告",
    }.get(report_type, "沪锡期货多周期方向预测与事件驱动分析报告")


def build_report_content(
    *,
    report_type: str,
    generated_at: str,
    data_watermark: Mapping[str, Any],
    live_predictions: Mapping[str, Any],
    model_health: Mapping[str, Any],
    learning_status: Mapping[str, Any],
    news_policy: Mapping[str, Any],
) -> dict[str, Any]:
    title = _report_title(report_type)
    data_cutoff = data_watermark.get("latest_realtime") or data_watermark.get("latest_daily") or data_watermark.get("source_timestamp") or "数据暂缺"
    cards = live_predictions.get("cards", {}) if isinstance(live_predictions.get("cards"), Mapping) else {}
    per = model_health.get("per_horizon", {}) if isinstance(model_health.get("per_horizon"), Mapping) else {}
    lines = [
        f"# {title}",
        "",
        f"- 报告生成时间：{generated_at}",
        f"- 数据截止时间：{data_cutoff}",
        f"- 当前主力合约：{data_watermark.get('active_contract') or data_watermark.get('target_contract') or '数据暂缺'}",
        f"- 数据质量评分：{fmt_num(data_watermark.get('quality_score'), 2)}",
        f"- 展望周期：{label(report_type, report_type)}",
        "",
        "## 核心观点摘要",
        "本报告围绕方向优先模型、价格中枢、预测区间、事件证据和模型治理状态展开。候选模型未通过 promotion gate 前不会替换现行模型。",
        "",
        "## 多周期方向预测表",
    ]
    for horizon, card in cards.items():
        if not isinstance(card, Mapping):
            continue
        health = per.get(horizon, {}) if isinstance(per.get(horizon), Mapping) else {}
        lines.append(
            "- "
            f"{card.get('周期', horizon)}：方向 {card.get('方向', '数据暂缺')}，"
            f"信号 {card.get('信号', '观望')}，上涨 {card.get('上涨概率', '数据暂缺')}，"
            f"下跌 {card.get('下跌概率', '数据暂缺')}，预测区间 {card.get('预测区间', '数据暂缺')}，"
            f"模型 {card.get('model_version', '数据暂缺')}，晋级 {label(card.get('promotion_result'), '待验证')}，"
            f"方向命中 {fmt_pct(health.get('direction_hit_rate'))}。"
        )
    lines.extend(
        [
            "",
            "## 新闻政策与事件影响",
            f"- 识别事件：{news_policy.get('recognized_event_count', 0)}",
            f"- 入模事件：{news_policy.get('used_in_model_event_count', 0)}",
            f"- 过滤事件：{news_policy.get('rejected_event_count', 0)}",
            "- 事件解释用于辅助方向判断；若事件消融无稳定增益，系统不会夸大新闻政策效果。",
            "",
            "## 模型健康与回测口径",
            f"- 验证口径：{model_health.get('validation_mode', '待验证')}",
            f"- 平均中性率：{fmt_pct(model_health.get('neutral_rate'))}",
            f"- 强方向覆盖：{fmt_pct(model_health.get('strong_signal_rate'))}",
            f"- 说明：{model_health.get('health_reason', '真实样本不足时不伪造指标。')}",
            "",
            "## 学习与模型治理状态",
            f"- 最近行情刷新：{learning_status.get('last_market_refresh', '暂未运行')}",
            f"- 最近预测：{learning_status.get('last_prediction', learning_status.get('last_prediction_refresh', '暂未运行'))}",
            f"- 最近候选训练：{learning_status.get('last_candidate_training', learning_status.get('last_training', '暂未运行'))}",
            f"- 最近 walk-forward：{learning_status.get('last_walk_forward', '暂未运行')}",
            f"- 最近事件消融：{learning_status.get('last_event_ablation', '暂未运行')}",
            "",
            "## 风险提示",
            "- 免费公开数据可能存在延迟、缺失或源间差异。",
            "- 模型预测基于历史数据与公开信息，可能出现误差、失效和极端行情偏离。",
            "- 若数据质量不足、模型降级或方向价格分歧，应降低解读强度。",
            "",
            "## 重要声明",
            DISCLAIMER,
            "本系统不接入实盘交易，不构成投资建议、交易建议、收益承诺或风险承诺；期货交易具有高杠杆和高风险，用户需独立判断并自行承担风险。",
        ]
    )
    markdown = "\n".join(lines)
    return sanitize_for_json(
        {
            "type": report_type,
            "title": title,
            "generated_at": generated_at,
            "data_cutoff": data_cutoff,
            "markdown": markdown,
            "html": markdown.replace("\n", "<br>"),
            "disclaimer": DISCLAIMER,
        },
        text_for_nan=True,
    )
