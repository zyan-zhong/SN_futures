from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from pathlib import Path

import pandas as pd

from .compliance import with_disclaimer
from .text_tables import dataframe_to_text


@dataclass
class ReportArtifact:
    report_type: str
    title: str
    path: str
    generated_at: str


def _latest(predictions: pd.DataFrame | None) -> pd.Series | None:
    if isinstance(predictions, pd.DataFrame) and not predictions.empty:
        return predictions.iloc[-1]
    return None


def _table(df: pd.DataFrame, columns: list[str], rows: int = 8) -> str:
    if df.empty:
        return "暂无数据。"
    safe_cols = [col for col in columns if col in df.columns]
    if not safe_cols:
        return "暂无数据。"
    return dataframe_to_text(df[safe_cols], index=True, rows=rows)


def _fmt_num(value: object, digits: int = 0) -> str:
    try:
        numeric = float(value)
    except Exception:
        return "暂无"
    if pd.isna(numeric):
        return "暂无"
    return f"{numeric:.{digits}f}"


def _fmt_pct(value: object) -> str:
    try:
        numeric = float(value)
    except Exception:
        return "暂无"
    if pd.isna(numeric):
        return "暂无"
    return f"{numeric:.2%}"


def _metrics_block(metrics: dict[str, float]) -> list[str]:
    return [
        f"- 累计收益：{metrics.get('cumulative_return', 0.0):.2%}",
        f"- 年化收益：{metrics.get('annual_return', 0.0):.2%}",
        f"- 夏普比率：{metrics.get('sharpe', 0.0):.2f}",
        f"- Sortino：{metrics.get('sortino', 0.0):.2f}",
        f"- Calmar：{metrics.get('calmar', 0.0):.2f}",
        f"- 最大回撤：{metrics.get('max_drawdown', 0.0):.2%}",
        f"- 胜率：{metrics.get('win_rate', 0.0):.2%}",
        f"- 盈亏比：{metrics.get('reward_risk_ratio', 0.0):.2f}",
        f"- 交易次数：{metrics.get('trade_count', 0.0):.0f}",
    ]


def _scenario_block(scenario_matrix: pd.DataFrame | None) -> list[str]:
    if not isinstance(scenario_matrix, pd.DataFrame) or scenario_matrix.empty:
        return ["暂无情景矩阵。"]
    show = scenario_matrix[
        ["scenario_label", "expected_return", "prob_up", "confidence", "range_low", "range_high", "risk_level"]
    ].copy()
    show["expected_return"] = show["expected_return"].map(lambda v: f"{v:.2%}")
    show["prob_up"] = show["prob_up"].map(lambda v: f"{v:.2%}")
    show["confidence"] = show["confidence"].map(lambda v: f"{v:.1f}")
    show["range_low"] = show["range_low"].map(lambda v: f"{v:.0f}")
    show["range_high"] = show["range_high"].map(lambda v: f"{v:.0f}")
    return [dataframe_to_text(show, index=False)]


def _live_block(live_snapshot: dict[str, object] | None) -> list[str]:
    if not isinstance(live_snapshot, dict) or not live_snapshot:
        return ["暂无实时快照。"]
    text_summary = live_snapshot.get("text_summary", {})
    source_status = pd.DataFrame(live_snapshot.get("source_status", []))
    quotes = pd.DataFrame(live_snapshot.get("quotes", []))
    lines = [
        f"- 生成时间：{live_snapshot.get('generated_at', 'n/a')}",
        f"- 主导文本维度：{text_summary.get('dominant_dimension', 'n/a')}",
        f"- 平均情绪得分：{float(text_summary.get('sentiment_mean', 0.0) or 0.0):.2f}",
        f"- 平均影响得分：{float(text_summary.get('impact_mean', 0.0) or 0.0):.2f}",
        f"- 新闻热点热度：{float(text_summary.get('topic_heat_score', 0.0) or 0.0):.2f}",
        f"- 情绪一致性：{float(text_summary.get('news_consensus', 0.0) or 0.0):.2f}",
    ]
    hot_topics = text_summary.get("hot_topics", [])
    if isinstance(hot_topics, (list, tuple)) and hot_topics:
        lines.append("- 热点关键词：" + " / ".join(str(item) for item in hot_topics[:6]))
    top_headlines = text_summary.get("top_headlines", [])
    if isinstance(top_headlines, (list, tuple)) and top_headlines:
        lines.append("- 重点新闻：" + " | ".join(str(item) for item in top_headlines[:3]))
    if not quotes.empty:
        lines.append("")
        lines.append("报价：")
        lines.append(dataframe_to_text(quotes, index=False, columns=["symbol", "latest", "high", "low", "volume"]))
    if not source_status.empty:
        lines.append("")
        lines.append("数据源状态：")
        lines.append(dataframe_to_text(source_status, index=False, columns=["name", "enabled", "success", "from_cache", "message"]))
    return lines


def _position_risk_block(position_risk: dict[str, float] | None) -> list[str]:
    if not isinstance(position_risk, dict) or not position_risk:
        return ["暂无持仓风险快照。"]
    return [
        f"- 手数：{position_risk.get('contracts', 0.0):.0f}",
        f"- 名义敞口：{position_risk.get('notional', 0.0):.0f}",
        f"- 保证金占用：{position_risk.get('margin_required', 0.0):.0f}",
        f"- VaR 95：{position_risk.get('var_95', 0.0):.0f}",
        f"- 压力 VaR：{position_risk.get('stressed_var', 0.0):.0f}",
        f"- 保证金占用率：{position_risk.get('margin_usage_ratio', 0.0):.2%}",
    ]


def build_daily_report(
    raw: pd.DataFrame,
    predictions: pd.DataFrame,
    metrics: dict[str, float],
    diagnostics: pd.DataFrame,
    signals: pd.DataFrame,
    trades: pd.DataFrame,
    selected_features: list[str],
    live_snapshot: dict[str, object] | None = None,
    scenario_matrix: pd.DataFrame | None = None,
    position_risk: dict[str, float] | None = None,
) -> str:
    latest_pred = _latest(predictions)
    latest_raw = raw.iloc[-1]
    latest_signal = signals.iloc[-1] if not signals.empty else None
    diagnostics_table = diagnostics.head(8)[["factor", "group", "ic", "icir", "vif"]] if not diagnostics.empty else pd.DataFrame()

    lines = [
        "# 沪锡日度投研跟踪报告",
        "",
        "## 封面",
        f"- 报告日期：{raw.index[-1].date()}",
        f"- 主力合约收盘：{_fmt_num(latest_raw['close'])}",
        f"- 日内区间：[{_fmt_num(latest_raw['low'])}, {_fmt_num(latest_raw['high'])}]",
        f"- 成交量：{_fmt_num(latest_raw['volume'])}",
        f"- 持仓量：{_fmt_num(latest_raw['open_interest'])}",
        "",
        "## 当日行情全景",
        f"- 现货升贴水：{_fmt_num(latest_raw['spot_premium'])}",
        f"- 上期所库存：{_fmt_num(latest_raw['shfe_inventory'])}",
        f"- LME库存：{_fmt_num(latest_raw['lme_inventory'])}",
        f"- 隔夜联动因子：{_fmt_pct(latest_raw['lme_overnight_return'])}",
        "",
        "## 当日驱动归因",
    ]

    if latest_pred is not None:
        lines.extend(
            [
                f"- 市场状态：{latest_pred['regime']}",
                f"- 预测收益：{latest_pred['predicted_return']:.2%}",
                f"- 上涨概率：{latest_pred.get('prob_up_multimodal', latest_pred['prob_up']):.2%}",
                f"- 置信度：{latest_pred.get('confidence_multimodal', latest_pred['confidence']):.1f}",
                f"- 预测区间：[{latest_pred['pred_low']:.0f}, {latest_pred['pred_high']:.0f}]",
                f"- 驱动摘要：{latest_pred['driver_summary']}",
            ]
        )
    else:
        lines.append("- 当前没有可用的预测输出。")

    lines.extend(
        [
            "",
            "## 多周期预测结论",
            "- 日内关注：隔夜伦锡传导、交割月基差动量、量仓背离。",
            "- 波段关注：库存消费比、仓单注销代理指标、下游订单变化。",
            "- 趋势关注：矿端扰动、冶炼端检修预期、宏观事件扩散。",
            "",
            "## 信号跟踪与验证",
        ]
    )
    if latest_signal is not None:
        lines.extend(
            [
                f"- 最新信号：{latest_signal['signal_label']}",
                f"- 参考开仓：{latest_signal['entry_reference']:.0f}",
                f"- 止损位：{latest_signal['stop_loss']:.0f}",
                f"- 止盈位：{latest_signal['take_profit']:.0f}",
            ]
        )
    lines.extend(
        [
            _table(
                trades if isinstance(trades, pd.DataFrame) else pd.DataFrame(),
                ["signal_label", "confidence", "pnl", "regime"],
                rows=6,
            ),
            "",
            "## 下一交易日关注点",
            f"- 核心因子关注：{', '.join(selected_features[:8])}",
            f"- 事件分数：{_fmt_num(latest_raw['event_score'], 2)}",
            f"- 下游订单指数：{_fmt_num(latest_raw['downstream_orders_idx'], 1)}",
            f"- 缅甸通关量：{_fmt_num(latest_raw['myanmar_clearance_tons'])}",
            "",
            "## 核心因子诊断",
            dataframe_to_text(diagnostics_table, index=False) if not diagnostics_table.empty else "暂无诊断结果。",
            "",
            "## 策略指标快照",
            *_metrics_block(metrics),
            "",
            "## 实时多模态快照",
            *_live_block(live_snapshot),
            "",
            "## 情景矩阵",
            *_scenario_block(scenario_matrix),
            "",
            "## 持仓风险快照",
            *_position_risk_block(position_risk),
        ]
    )
    return with_disclaimer(lines)


def build_weekly_report(
    raw: pd.DataFrame,
    predictions: pd.DataFrame,
    metrics: dict[str, float],
    diagnostics: pd.DataFrame,
    trades: pd.DataFrame,
    selected_features: list[str],
    live_snapshot: dict[str, object] | None = None,
    scenario_matrix: pd.DataFrame | None = None,
    position_risk: dict[str, float] | None = None,
) -> str:
    weekly = raw.resample("W-FRI").agg(
        {
            "open": "first",
            "high": "max",
            "low": "min",
            "close": "last",
            "volume": "sum",
            "open_interest": "last",
            "shfe_inventory": "last",
            "lme_inventory": "last",
            "spot_premium": "last",
            "tc_rc": "last",
            "smelter_runrate": "last",
            "pv_demand_yoy": "last",
            "semi_demand_yoy": "last",
        }
    )
    latest_week = weekly.iloc[-1]
    week_ret = latest_week["close"] / latest_week["open"] - 1
    lines = [
        "# 沪锡周度策略报告",
        "",
        "## 封面",
        f"- 截止日期：{weekly.index[-1].date()}",
        f"- 周度涨跌幅：{_fmt_pct(week_ret)}",
        f"- 周度区间：[{_fmt_num(latest_week['low'])}, {_fmt_num(latest_week['high'])}]",
        "",
        "## 周度行情复盘",
        f"- 周度成交量：{_fmt_num(latest_week['volume'])}",
        f"- 周末持仓量：{_fmt_num(latest_week['open_interest'])}",
        f"- 周末现货升贴水：{_fmt_num(latest_week['spot_premium'])}",
        "",
        "## 供需全景",
        f"- 上期所库存：{_fmt_num(latest_week['shfe_inventory'])}",
        f"- LME库存：{_fmt_num(latest_week['lme_inventory'])}",
        f"- 锡矿TC/RC：{_fmt_num(latest_week['tc_rc'])}",
        f"- 冶炼开工率：{_fmt_pct(latest_week['smelter_runrate'])}",
        f"- 光伏需求同比：{_fmt_pct(latest_week['pv_demand_yoy'])}",
        f"- 半导体需求同比：{_fmt_pct(latest_week['semi_demand_yoy'])}",
        "",
        "## 模型周度验证",
        *_metrics_block(metrics),
        "",
        "## 下周展望与策略",
    ]
    latest_pred = _latest(predictions)
    if latest_pred is not None:
        lines.extend(
            [
                f"- 市场状态：{latest_pred['regime']}",
                f"- 预测区间：[{latest_pred['pred_low']:.0f}, {latest_pred['pred_high']:.0f}]",
                f"- 上涨概率：{latest_pred.get('prob_up_multimodal', latest_pred['prob_up']):.2%}",
                f"- 置信度：{latest_pred.get('confidence_multimodal', latest_pred['confidence']):.1f}",
                f"- 驱动摘要：{latest_pred['driver_summary']}",
            ]
        )
    lines.extend(
        [
            f"- 核心因子组合：{', '.join(selected_features[:10])}",
            "",
            "## 周度风险全景",
            f"- 最新事件分数：{_fmt_num(raw.iloc[-1]['event_score'], 2)}",
            f"- 保税区库存变化：{_fmt_num(raw.iloc[-1]['bonded_inventory_delta'])}",
            f"- 是否交割月：{int(raw.iloc[-1]['delivery_month_flag'])}",
            "",
            "## 最近交易",
            _table(trades if isinstance(trades, pd.DataFrame) else pd.DataFrame(), ["signal_label", "confidence", "pnl", "regime"], rows=8),
            "",
            "## 周度因子诊断",
            dataframe_to_text(diagnostics.head(12), index=False) if not diagnostics.empty else "暂无诊断结果。",
            "",
            "## 周度实时与情景叠加",
            *_live_block(live_snapshot),
            "",
            *_scenario_block(scenario_matrix),
            "",
            "## 周度持仓风险",
            *_position_risk_block(position_risk),
        ]
    )
    return with_disclaimer(lines)


def build_monthly_report(
    raw: pd.DataFrame,
    predictions: pd.DataFrame,
    metrics: dict[str, float],
    diagnostics: pd.DataFrame,
    selected_features: list[str],
    live_snapshot: dict[str, object] | None = None,
    scenario_matrix: pd.DataFrame | None = None,
    position_risk: dict[str, float] | None = None,
) -> str:
    monthly = raw.resample("ME").agg(
        {
            "open": "first",
            "high": "max",
            "low": "min",
            "close": "last",
            "volume": "sum",
            "shfe_inventory": "last",
            "lme_inventory": "last",
            "bonded_inventory": "last",
            "spot_premium": "last",
            "mine_import_tons": "last",
            "refined_output_tons": "last",
            "apparent_demand_tons": "last",
            "usd_cny": "last",
            "dollar_index": "last",
            "us10y": "last",
        }
    )
    latest_month = monthly.iloc[-1]
    lines = [
        "# 沪锡月度展望报告",
        "",
        "## 封面",
        f"- 月末日期：{monthly.index[-1].date()}",
        f"- 月度涨跌幅：{_fmt_pct(latest_month['close'] / latest_month['open'] - 1)}",
        f"- 月度区间：[{_fmt_num(latest_month['low'])}, {_fmt_num(latest_month['high'])}]",
        "",
        "## 月度行情与市场状态",
    ]
    latest_pred = _latest(predictions)
    if latest_pred is not None:
        lines.extend(
            [
                f"- 最新市场状态：{latest_pred['regime']}",
                f"- 月度参考置信度：{latest_pred.get('confidence_multimodal', latest_pred['confidence']):.1f}",
                f"- 预测锚定区间：[{latest_pred['pred_low']:.0f}, {latest_pred['pred_high']:.0f}]",
            ]
        )
    lines.extend(
        [
            "",
            "## 供需平衡表更新",
            f"- 锡矿进口量：{_fmt_num(latest_month['mine_import_tons'])}",
            f"- 精炼锡产量：{_fmt_num(latest_month['refined_output_tons'])}",
            f"- 表观需求：{_fmt_num(latest_month['apparent_demand_tons'])}",
            f"- 上期所库存：{_fmt_num(latest_month['shfe_inventory'])}",
            f"- LME库存：{_fmt_num(latest_month['lme_inventory'])}",
            f"- 保税区库存：{_fmt_num(latest_month['bonded_inventory'])}",
            "",
            "## 宏观与跨市场联动",
            f"- 美元兑人民币：{_fmt_num(latest_month['usd_cny'], 4)}",
            f"- 美元指数：{_fmt_num(latest_month['dollar_index'], 2)}",
            f"- 美国10年期收益率：{_fmt_num(latest_month['us10y'], 2)}",
            "",
            "## 月度模型验证",
            *_metrics_block(metrics),
            "",
            "## 下月展望",
            f"- 核心因子栈：{', '.join(selected_features[:12])}",
            f"- 重点诊断表：\n{dataframe_to_text(diagnostics.head(12), index=False) if not diagnostics.empty else '暂无诊断结果。'}",
            "",
            "## 月度风险提示",
            f"- 最新事件分数：{_fmt_num(raw.iloc[-1]['event_score'], 2)}",
            f"- 长假跳空风险标记：{int(raw.iloc[-1]['holiday_gap_flag'])}",
            "",
            "## 多模态叠加",
            *_live_block(live_snapshot),
            "",
            "## 情景矩阵",
            *_scenario_block(scenario_matrix),
            "",
            "## 持仓风险快照",
            *_position_risk_block(position_risk),
        ]
    )
    return with_disclaimer(lines)


def build_event_report(
    raw: pd.DataFrame,
    predictions: pd.DataFrame,
    trades: pd.DataFrame,
    live_snapshot: dict[str, object] | None = None,
    scenario_matrix: pd.DataFrame | None = None,
) -> str:
    flagged = raw[raw["event_flag"] == 1]
    event_row = flagged.iloc[-1] if not flagged.empty else raw.iloc[-1]
    latest_pred = _latest(predictions)
    lines = [
        "# 沪锡事件影响专项报告",
        "",
        "## 封面",
        f"- 事件日期：{event_row.name.date()}",
        f"- 事件冲击分数：{_fmt_num(event_row['event_score'], 2)}",
        f"- 事件情绪分数：{_fmt_num(event_row['sentiment_score'], 2)}",
        "",
        "## 事件详情",
        f"- 事件分类代理：{'供需冲击' if event_row['event_score'] > 0 else '宏观/流动性冲击'}",
        f"- 事件标记：{int(event_row['event_flag'])}",
        f"- LME隔夜联动：{_fmt_pct(event_row['lme_overnight_return'])}",
        f"- 国内开盘缺口：{_fmt_pct(event_row['domestic_open_gap'])}",
        "",
        "## 影响评估",
    ]
    if latest_pred is not None:
        lines.extend(
            [
                f"- 当前市场状态：{latest_pred['regime']}",
                f"- 预测收益：{latest_pred['predicted_return']:.2%}",
                f"- 预测区间：[{latest_pred['pred_low']:.0f}, {latest_pred['pred_high']:.0f}]",
                f"- 置信度：{latest_pred.get('confidence_multimodal', latest_pred['confidence']):.1f}",
                f"- 驱动摘要：{latest_pred['driver_summary']}",
            ]
        )
    lines.extend(
        [
            "",
            "## 历史交易对比",
            _table(trades if isinstance(trades, pd.DataFrame) else pd.DataFrame(), ["signal_label", "confidence", "pnl", "regime"], rows=5),
            "",
            "## 短期关注点",
            f"- 仓单注销率代理：{_fmt_pct(event_row['warrant_cancelled'] / max(event_row['warrant'], 1))}",
            f"- 保税区库存变化：{_fmt_num(event_row['bonded_inventory_delta'])}",
            f"- 下游订单指数：{_fmt_num(event_row['downstream_orders_idx'], 1)}",
            "",
            "## 实时事件叠加",
            *_live_block(live_snapshot),
            "",
            "## 情景矩阵",
            *_scenario_block(scenario_matrix),
        ]
    )
    return with_disclaimer(lines)


def build_report_bundle(
    raw: pd.DataFrame,
    predictions: pd.DataFrame,
    metrics: dict[str, float],
    diagnostics: pd.DataFrame,
    selected_features: list[str],
    signals: pd.DataFrame,
    trades: pd.DataFrame,
    live_snapshot: dict[str, object] | None = None,
    scenario_matrix: pd.DataFrame | None = None,
    position_risk: dict[str, float] | None = None,
) -> dict[str, str]:
    return {
        "daily": build_daily_report(
            raw,
            predictions,
            metrics,
            diagnostics,
            signals,
            trades,
            selected_features,
            live_snapshot=live_snapshot,
            scenario_matrix=scenario_matrix,
            position_risk=position_risk,
        ),
        "weekly": build_weekly_report(
            raw,
            predictions,
            metrics,
            diagnostics,
            trades,
            selected_features,
            live_snapshot=live_snapshot,
            scenario_matrix=scenario_matrix,
            position_risk=position_risk,
        ),
        "monthly": build_monthly_report(
            raw,
            predictions,
            metrics,
            diagnostics,
            selected_features,
            live_snapshot=live_snapshot,
            scenario_matrix=scenario_matrix,
            position_risk=position_risk,
        ),
        "event": build_event_report(
            raw,
            predictions,
            trades,
            live_snapshot=live_snapshot,
            scenario_matrix=scenario_matrix,
        ),
    }


def build_markdown_report(
    predictions: pd.DataFrame,
    metrics: dict[str, float],
    diagnostics: pd.DataFrame,
    selected_features: list[str],
) -> str:
    lines = [
        "# 沪锡期货模型运行摘要",
        "",
        "## 模型绩效快照",
        *_metrics_block(metrics),
        "",
        "## 当前入选因子",
        "- " + ", ".join(selected_features[:12]) if selected_features else "- 暂无入选因子",
        "",
        "## 因子诊断",
        dataframe_to_text(diagnostics.head(10), index=False) if not diagnostics.empty else "暂无诊断结果。",
    ]
    latest = _latest(predictions)
    if latest is not None:
        lines[2:2] = [
            f"- 最新市场状态：{latest['regime']}",
            f"- 预测收益：{latest['predicted_return']:.2%}",
            f"- 上涨概率：{latest.get('prob_up_multimodal', latest['prob_up']):.2%}",
            f"- 置信度：{latest.get('confidence_multimodal', latest['confidence']):.1f}",
            f"- 预测区间：[{latest['pred_low']:.0f}, {latest['pred_high']:.0f}]",
        ]
    return with_disclaimer(lines)


def build_prediction_detail_report(
    live_predictions: dict[str, object] | None,
    horizon_key: str,
) -> str:
    payload = live_predictions or {}
    cards = payload.get("cards", {}) if isinstance(payload, dict) else {}
    card = cards.get(horizon_key, {}) if isinstance(cards, dict) else {}
    if not isinstance(card, dict) or not card:
        return with_disclaimer(
            [
                f"# {horizon_key} 预测详情",
                "",
                "当前还没有可展示的详细归因。",
            ]
        )

    historical = pd.DataFrame(card.get("historical_matches", []))
    lines = [
        f"# {card.get('horizon_label', horizon_key)} 预测详情",
        "",
        f"- 生成时间：{card.get('generated_at', 'n/a')}",
        f"- 锚点时间：{card.get('anchor_time', 'n/a')}",
        f"- 目标窗口：{card.get('target_label', 'n/a')}",
        f"- 合约：{card.get('contract_code', 'n/a')}",
        f"- 方向：{card.get('direction_label', 'n/a')}",
        f"- 价格中枢：{float(card.get('price_center', 0.0) or 0.0):.0f}",
        f"- 价格区间：[{float(card.get('range_low', 0.0) or 0.0):.0f}, {float(card.get('range_high', 0.0) or 0.0):.0f}]",
        f"- 上涨概率：{float(card.get('prob_up', 0.0) or 0.0):.2%}",
        f"- 置信度：{float(card.get('confidence', 0.0) or 0.0):.1f}",
        "",
        "## 核心驱动",
    ]
    drivers = card.get("core_drivers", [])
    if isinstance(drivers, list) and drivers:
        lines.extend(f"- {item}" for item in drivers)
    else:
        lines.append("- 当前没有可展示的驱动清单。")
    lines.extend(
        [
            "",
            "## 情景备注",
            f"- {card.get('scenario_note', 'n/a')}",
            "",
            "## 历史相似情形",
            dataframe_to_text(historical, index=False) if not historical.empty else "当前没有可用的历史相似样本。",
        ]
    )
    return with_disclaimer(lines)


def _safe_write_text(path: Path, content: str, *, encoding: str = "utf-8") -> bool:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding=encoding)
        return True
    except OSError:
        return False


def _safe_write_csv(frame: pd.DataFrame, path: Path, **kwargs: object) -> bool:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        frame.to_csv(path, **kwargs)
        return True
    except OSError:
        return False


def _safe_write_json(path: Path, payload: object, *, encoding: str = "utf-8") -> bool:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, default=str),
            encoding=encoding,
        )
        return True
    except OSError:
        return False


def save_outputs(
    output_dir: Path,
    report_dir: Path,
    report_text: str,
    diagnostics: pd.DataFrame,
    predictions: pd.DataFrame,
    trades: pd.DataFrame,
    report_bundle: dict[str, str],
    live_snapshot: dict[str, object] | None = None,
    scenario_matrix: pd.DataFrame | None = None,
    optimization_table: pd.DataFrame | None = None,
    bandit_summary: dict[str, object] | None = None,
) -> list[dict[str, str]]:
    try:
        output_dir.mkdir(parents=True, exist_ok=True)
        report_dir.mkdir(parents=True, exist_ok=True)
    except OSError:
        pass

    _safe_write_text(output_dir / "sn_demo_report.md", report_text, encoding="utf-8")
    _safe_write_csv(diagnostics, output_dir / "sn_factor_diagnostics.csv", index=False, encoding="utf-8-sig")
    _safe_write_csv(predictions, output_dir / "sn_predictions.csv", encoding="utf-8-sig")
    _safe_write_csv(trades, output_dir / "sn_backtest_trades.csv", encoding="utf-8-sig")
    if isinstance(scenario_matrix, pd.DataFrame) and not scenario_matrix.empty:
        _safe_write_csv(scenario_matrix, output_dir / "sn_scenario_matrix.csv", encoding="utf-8-sig")
    if isinstance(optimization_table, pd.DataFrame) and not optimization_table.empty:
        _safe_write_csv(optimization_table, output_dir / "sn_model_optimization.csv", index=False, encoding="utf-8-sig")
    if isinstance(bandit_summary, dict) and bandit_summary:
        _safe_write_json(output_dir / "sn_bandit_summary.json", bandit_summary, encoding="utf-8")
    if isinstance(live_snapshot, dict) and live_snapshot:
        _safe_write_json(output_dir / "sn_live_snapshot.json", live_snapshot, encoding="utf-8")

    generated_at = pd.Timestamp.now(tz="Asia/Hong_Kong").strftime("%Y-%m-%d %H:%M:%S %Z")
    manifest: list[dict[str, str]] = []
    title_map = {
        "daily": "沪锡日度投研跟踪报告",
        "weekly": "沪锡周度策略报告",
        "monthly": "沪锡月度展望报告",
        "event": "沪锡重大事件专项报告",
    }
    for report_type, content in report_bundle.items():
        filename = f"sn_{report_type}_report.md"
        path = report_dir / filename
        if not _safe_write_text(path, content, encoding="utf-8"):
            continue
        artifact = ReportArtifact(
            report_type=report_type,
            title=title_map.get(report_type, f"沪锡{report_type}报告"),
            path=str(path),
            generated_at=generated_at,
        )
        manifest.append(asdict(artifact))

    _safe_write_json(report_dir / "report_manifest.json", manifest, encoding="utf-8")
    return manifest


# Override legacy mojibake helpers with explicit Chinese placeholders.  The
# report body still contains older text templates, but all tabular and numeric
# missing values should render as readable business text instead of nan.
def _table(df: pd.DataFrame, columns: list[str], rows: int = 8) -> str:  # type: ignore[no-redef]
    if df.empty:
        return "数据暂缺。"
    safe_cols = [col for col in columns if col in df.columns]
    if not safe_cols:
        return "数据暂缺。"
    return dataframe_to_text(df[safe_cols], index=True, rows=rows)


def _fmt_num(value: object, digits: int = 0) -> str:  # type: ignore[no-redef]
    try:
        numeric = float(value)
    except Exception:
        return "数据暂缺"
    if pd.isna(numeric):
        return "数据暂缺"
    return f"{numeric:.{digits}f}"


def _fmt_pct(value: object) -> str:  # type: ignore[no-redef]
    try:
        numeric = float(value)
    except Exception:
        return "数据暂缺"
    if pd.isna(numeric):
        return "数据暂缺"
    return f"{numeric:.2%}"


def _metrics_block(metrics: dict[str, float]) -> list[str]:  # type: ignore[no-redef]
    return [
        f"- 累计收益：{_fmt_pct(metrics.get('cumulative_return'))}",
        f"- 年化收益：{_fmt_pct(metrics.get('annual_return'))}",
        f"- 夏普比率：{_fmt_num(metrics.get('sharpe'), 2)}",
        f"- Sortino：{_fmt_num(metrics.get('sortino'), 2)}",
        f"- Calmar：{_fmt_num(metrics.get('calmar'), 2)}",
        f"- 最大回撤：{_fmt_pct(metrics.get('max_drawdown'))}",
        f"- 胜率：{_fmt_pct(metrics.get('win_rate'))}",
        f"- 盈亏比：{_fmt_num(metrics.get('reward_risk_ratio'), 2)}",
        f"- 交易次数：{_fmt_num(metrics.get('trade_count'), 0)}",
    ]


def _scenario_block(scenario_matrix: pd.DataFrame | None) -> list[str]:  # type: ignore[no-redef]
    if not isinstance(scenario_matrix, pd.DataFrame) or scenario_matrix.empty:
        return ["情景矩阵数据暂缺。"]
    show = scenario_matrix.copy()
    for column in ("expected_return", "prob_up"):
        if column in show.columns:
            show[column] = show[column].map(_fmt_pct)
    for column in ("confidence", "range_low", "range_high"):
        if column in show.columns:
            show[column] = show[column].map(lambda value: _fmt_num(value, 1 if column == "confidence" else 0))
    return [dataframe_to_text(show, index=False)]


def _position_risk_block(position_risk: dict[str, float] | None) -> list[str]:  # type: ignore[no-redef]
    if not isinstance(position_risk, dict) or not position_risk:
        return ["持仓风险数据暂缺。"]
    return [
        f"- 手数：{_fmt_num(position_risk.get('contracts'), 0)}",
        f"- 名义敞口：{_fmt_num(position_risk.get('notional'), 0)}",
        f"- 保证金占用：{_fmt_num(position_risk.get('margin_required'), 0)}",
        f"- VaR 95：{_fmt_num(position_risk.get('var_95'), 0)}",
        f"- 压力 VaR：{_fmt_num(position_risk.get('stressed_var'), 0)}",
        f"- 保证金占用率：{_fmt_pct(position_risk.get('margin_usage_ratio'))}",
    ]
