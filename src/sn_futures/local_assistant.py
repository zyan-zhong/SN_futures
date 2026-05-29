from __future__ import annotations

from pathlib import Path

import pandas as pd

from .compliance import with_disclaimer
from .text_tables import dataframe_to_text


def answer_question(
    question: str,
    current_result: dict[str, object] | None,
    docs: dict[str, Path] | None = None,
) -> str:
    q = (question or "").strip().lower()
    if not q:
        return with_disclaimer(
            [
                "本地智能问答已就绪。",
                "你可以询问最新预测、风险预警、因子驱动、投研报告、实时新闻影响或压力测试结果。",
            ]
        )

    lines: list[str] = [f"问题：{question}", "", "回答："]
    result = current_result or {}
    predictions = result.get("predictions")
    metrics = result.get("metrics")
    selected_features = result.get("selected_features")
    trades = result.get("trades")
    report_manifest = result.get("report_manifest")
    live_snapshot = result.get("live_snapshot")
    scenario_matrix = result.get("scenario_matrix")
    position_risk = result.get("position_risk")

    if any(token in q for token in ("predict", "forecast", "signal", "预测", "信号", "走势", "价格")):
        if isinstance(predictions, pd.DataFrame) and not predictions.empty:
            latest = predictions.iloc[-1]
            lines.extend(
                [
                    f"- 最新市场状态：{latest['regime']}",
                    f"- 预测收益：{latest['predicted_return']:.2%}",
                    f"- 上涨概率：{latest.get('prob_up_multimodal', latest['prob_up']):.2%}",
                    f"- 置信度：{latest.get('confidence_multimodal', latest['confidence']):.1f}",
                    f"- 预测区间：[{latest['pred_low']:.0f}, {latest['pred_high']:.0f}]",
                    f"- 驱动摘要：{latest['driver_summary']}",
                    "- 解读：该结果仅作为量化投研参考，需要结合你自己的风险约束使用。",
                ]
            )
        else:
            lines.append("- 当前还没有加载预测输出，请先刷新实时预测。")
        return with_disclaimer(lines)

    if any(token in q for token in ("risk", "drawdown", "风险", "回撤", "预警")):
        if isinstance(metrics, dict) and metrics:
            lines.extend(
                [
                    f"- 胜率：{metrics.get('win_rate', 0.0):.2%}",
                    f"- 盈亏比：{metrics.get('reward_risk_ratio', 0.0):.2f}",
                    f"- 夏普比率：{metrics.get('sharpe', 0.0):.2f}",
                    f"- 最大回撤：{metrics.get('max_drawdown', 0.0):.2%}",
                    "- 风险说明：终端仅用于投研分析，不连接任何实盘交易接口。",
                ]
            )
        else:
            lines.append("- 当前还没有风险指标，请先运行预测/回测流水线。")
        return with_disclaimer(lines)

    if any(token in q for token in ("factor", "driver", "因子", "驱动", "归因")):
        if isinstance(selected_features, list) and selected_features:
            lines.append("- 当前高优先级因子：" + ", ".join(selected_features[:10]))
        elif isinstance(predictions, pd.DataFrame) and not predictions.empty:
            lines.append(f"- 最新驱动摘要：{predictions.iloc[-1]['driver_summary']}")
        else:
            lines.append("- 当前还没有因子输出。")
        return with_disclaimer(lines)

    if any(token in q for token in ("report", "报告", "投研")):
        if isinstance(report_manifest, list) and report_manifest:
            lines.append("- 已生成报告：")
            for item in report_manifest[:8]:
                lines.append(f"  {item['report_type']}: {item['title']} -> {item['path']}")
        else:
            lines.append("- 当前还没有生成报告。")
        return with_disclaimer(lines)

    if any(token in q for token in ("trade", "backtest", "交易", "回测", "绩效")):
        if isinstance(trades, pd.DataFrame) and not trades.empty:
            latest_trade = trades.iloc[-1]
            lines.extend(
                [
                    f"- 最新信号：{latest_trade['signal_label']}",
                    f"- 最新回测盈亏：{latest_trade['pnl']:.2f}",
                    f"- 最新置信度：{latest_trade['confidence']:.1f}",
                    f"- 所属市场状态：{latest_trade['regime']}",
                ]
            )
        else:
            lines.append("- 当前还没有加载回测交易记录。")
        return with_disclaimer(lines)

    if any(token in q for token in ("live", "news", "macro", "policy", "实时", "新闻", "宏观", "政策", "舆情")):
        if isinstance(live_snapshot, dict) and live_snapshot:
            text_summary = live_snapshot.get("text_summary", {})
            lines.extend(
                [
                    f"- 实时快照时间：{live_snapshot.get('generated_at', 'n/a')}",
                    f"- 主导文本维度：{text_summary.get('dominant_dimension', 'n/a')}",
                    f"- 平均情绪得分：{float(text_summary.get('sentiment_mean', 0.0) or 0.0):.2f}",
                    f"- 平均影响得分：{float(text_summary.get('impact_mean', 0.0) or 0.0):.2f}",
                    f"- 新闻热点热度：{float(text_summary.get('topic_heat_score', 0.0) or 0.0):.2f}",
                ]
            )
            hot_topics = text_summary.get("hot_topics", [])
            if isinstance(hot_topics, (list, tuple)) and hot_topics:
                lines.append("- 热点关键词：" + " / ".join(str(item) for item in hot_topics[:6]))
            headlines = text_summary.get("top_headlines", [])
            if isinstance(headlines, (list, tuple)) and headlines:
                lines.append("- 核心新闻：" + " | ".join(str(item) for item in headlines[:3]))
        else:
            lines.append("- 当前还没有实时快照，请先刷新实时预测。")
        return with_disclaimer(lines)

    if any(token in q for token in ("scenario", "stress", "var", "情景", "压力", "持仓")):
        if isinstance(scenario_matrix, pd.DataFrame) and not scenario_matrix.empty:
            show = scenario_matrix[["scenario_label", "expected_return", "prob_up", "risk_level"]].copy()
            show["expected_return"] = show["expected_return"].map(lambda v: f"{v:.2%}")
            show["prob_up"] = show["prob_up"].map(lambda v: f"{v:.2%}")
            lines.append(dataframe_to_text(show, index=False))
        else:
            lines.append("- 当前还没有加载情景矩阵。")
        if isinstance(position_risk, dict) and position_risk:
            lines.extend(
                [
                    f"- VaR 95：{position_risk.get('var_95', 0.0):.0f}",
                    f"- 压力VaR：{position_risk.get('stressed_var', 0.0):.0f}",
                    f"- 保证金占用率：{position_risk.get('margin_usage_ratio', 0.0):.2%}",
                ]
            )
        return with_disclaimer(lines)

    if docs:
        for name, path in docs.items():
            if name.lower() in q and path.exists():
                content = path.read_text(encoding="utf-8", errors="ignore")
                excerpt = "\n".join(content.splitlines()[:10])
                lines.extend([f"- 匹配文档：{name}", excerpt])
                return with_disclaimer(lines)

    lines.extend(
        [
            "- 我可以总结最新预测、风险画像、因子驱动、投研报告、实时快照或压力测试。",
            "- 你可以试试：'最新沪锡预测是什么？' 或 '当前风险指标如何？'",
        ]
    )
    return with_disclaimer(lines)
