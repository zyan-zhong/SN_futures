from __future__ import annotations

from statistics import median
from typing import Any, Mapping

import numpy as np
import pandas as pd

from ..horizon_registry import HORIZON_ORDER


def _num(value: Any, default: float = 0.0) -> float:
    try:
        out = float(value)
    except Exception:
        return default
    return out if np.isfinite(out) else default


def audit_single_forecast_path(chart: Mapping[str, Any]) -> dict[str, Any]:
    history = chart.get("history_series", []) if isinstance(chart.get("history_series", []), list) else []
    forecast = chart.get("forecast_series", []) if isinstance(chart.get("forecast_series", []), list) else []
    horizon = str(chart.get("horizon") or "")
    issues: list[str] = []
    warnings: list[str] = []
    if not history or not forecast:
        return {
            "horizon": horizon,
            "ok": False,
            "severity": "red",
            "summary": "历史区或未来预测区为空",
            "issues": ["missing_history_or_forecast"],
        }

    last_price = _num(history[-1].get("close"))
    centers = [_num(row.get("pred_center"), np.nan) for row in forecast]
    lowers = [_num(row.get("pred_low"), np.nan) for row in forecast]
    uppers = [_num(row.get("pred_high"), np.nan) for row in forecast]
    valid_centers = [value for value in centers if np.isfinite(value) and value > 0]
    if last_price <= 0 or not valid_centers:
        issues.append("invalid_price_path")
        return {"horizon": horizon, "ok": False, "severity": "red", "summary": "价格路径无有效价格", "issues": issues}

    closes = [_num(row.get("close"), np.nan) for row in history[-40:]]
    closes = [value for value in closes if np.isfinite(value) and value > 0]
    pct_moves = [abs(closes[idx] / closes[idx - 1] - 1.0) for idx in range(1, len(closes)) if closes[idx - 1] > 0]
    recent_move = median(pct_moves) if pct_moves else 0.003
    max_allowed_first_jump = max(last_price * recent_move * 3.5, last_price * 0.0012, 3.0)
    first_jump = abs(valid_centers[0] - last_price)
    if first_jump > max_allowed_first_jump:
        issues.append("first_step_jump_too_large")

    unique_centers = {round(value, 4) for value in valid_centers}
    flatline_rate = 1.0 - (len(unique_centers) / max(len(valid_centers), 1))
    if len(valid_centers) >= 4 and flatline_rate > 0.82:
        issues.append("center_flatline")
    elif len(valid_centers) >= 4 and flatline_rate > 0.62:
        warnings.append("center_low_variation")

    crossing_count = 0
    widths: list[float] = []
    for low, center, high in zip(lowers, centers, uppers):
        if not (np.isfinite(low) and np.isfinite(center) and np.isfinite(high)):
            continue
        if low > center or center > high or high <= low:
            crossing_count += 1
        widths.append(max(0.0, high - low))
    if crossing_count:
        issues.append("interval_crossing")

    interval_explosion_rate = 0.0
    if len(widths) >= 4 and widths[0] > 0:
        interval_explosion_rate = widths[-1] / widths[0]
        if interval_explosion_rate > 8.0:
            issues.append("interval_explosion")
        elif interval_explosion_rate > 5.0:
            warnings.append("interval_fast_expansion")

    diffs = [abs(valid_centers[idx] - valid_centers[idx - 1]) for idx in range(1, len(valid_centers))]
    smoothness_score = 1.0
    if diffs:
        avg_step = sum(diffs) / len(diffs)
        smoothness_score = float(max(0.0, min(1.0, 1.0 - (max(diffs) / max(avg_step * 8.0, 1.0)))))

    ok = not issues
    return {
        "horizon": horizon,
        "ok": ok,
        "severity": "normal" if ok else "red",
        "summary": "预测路径连续性通过" if ok else "预测路径存在突跳/扁平/区间异常",
        "issues": issues,
        "warnings": warnings,
        "last_price": last_price,
        "first_center": valid_centers[0],
        "first_step_jump": first_jump,
        "max_allowed_first_jump": max_allowed_first_jump,
        "flatline_rate": round(flatline_rate, 4),
        "interval_explosion_rate": round(interval_explosion_rate, 4),
        "quantile_crossing_count": crossing_count,
        "path_smoothness_score": round(smoothness_score, 4),
        "forecast_steps": len(forecast),
    }


def audit_forecast_paths(chart_payloads: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    rows = []
    for key in HORIZON_ORDER:
        chart = dict(chart_payloads.get(key, {}))
        chart.setdefault("horizon", key)
        rows.append(audit_single_forecast_path(chart))
    ok = all(row.get("ok") for row in rows)
    return {
        "ok": ok,
        "status": "passed" if ok else "failed",
        "severity": "normal" if ok else "red",
        "summary": "七周期预测路径连续性通过" if ok else "部分周期预测路径存在异常",
        "rows": rows,
    }
