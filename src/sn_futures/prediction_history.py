from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from .forecast_math import cohere_directional_forecast
from .price_risk import apply_realistic_price_gate, get_horizon_spec


HISTORY_FILE_NAME = "sn_prediction_history.jsonl"
EVALUATION_FILE_NAME = "sn_prediction_evaluation.csv"
BASELINE_FILE_NAME = "sn_prediction_baseline.csv"
MODEL_MEMORY_FILE_NAME = "sn_model_memory.json"
MAX_HISTORY_LINES = 3000
INTRADAY_HORIZON_KEYS = {"next_5m", "next_15m", "next_30m", "next_hour"}


def prediction_history_path(output_dir: Path) -> Path:
    return output_dir / HISTORY_FILE_NAME


def prediction_evaluation_path(output_dir: Path) -> Path:
    return output_dir / EVALUATION_FILE_NAME


def prediction_baseline_path(output_dir: Path) -> Path:
    return output_dir / BASELINE_FILE_NAME


def model_memory_path(output_dir: Path) -> Path:
    return output_dir / MODEL_MEMORY_FILE_NAME


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        parsed = float(value)
    except Exception:
        return default
    if not np.isfinite(parsed):
        return default
    return parsed


def _safe_date(value: Any) -> str:
    text = str(value or "").replace(" HKT", "").replace(" CST", "")
    parsed = pd.to_datetime(text, errors="coerce")
    if pd.isna(parsed):
        return ""
    return parsed.strftime("%Y-%m-%d")


def _direction_key(prob_up: float) -> str:
    if prob_up >= 0.60:
        return "bullish"
    if prob_up <= 0.40:
        return "bearish"
    return "neutral"


def _direction_label_zh(prob_up: float) -> str:
    if prob_up >= 0.60:
        return "偏多"
    if prob_up <= 0.40:
        return "偏空"
    return "中性"


def _compact_jsonl(path: Path, max_lines: int = MAX_HISTORY_LINES) -> None:
    if not path.exists():
        return
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except Exception:
        return
    if len(lines) <= max_lines:
        return
    path.write_text("\n".join(lines[-max_lines:]) + "\n", encoding="utf-8")


def load_prediction_history(output_dir: Path, max_rows: int | None = None) -> pd.DataFrame:
    path = prediction_history_path(output_dir)
    if not path.exists():
        return pd.DataFrame()
    rows: list[dict[str, Any]] = []
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            payload = json.loads(line)
            if isinstance(payload, dict):
                rows.append(payload)
    except Exception:
        return pd.DataFrame()
    if max_rows is not None and len(rows) > max_rows:
        rows = rows[-max_rows:]
    return pd.DataFrame(rows)


def build_walk_forward_baseline_from_predictions(output_dir: Path, *, force: bool = False) -> pd.DataFrame:
    """Build a transparent historical validation baseline from saved daily predictions.

    This is deliberately stored separately from live realized predictions. It gives the
    terminal an initial calibration baseline without pretending those rows are live
    forward predictions generated while the app was running.
    """
    baseline_path = prediction_baseline_path(output_dir)
    predictions_path = output_dir / "sn_predictions.csv"
    if baseline_path.exists() and not force:
        try:
            existing = pd.read_csv(baseline_path)
            if "baseline_version" in existing.columns and existing["baseline_version"].astype(str).eq("v2.8_realistic").any():
                return existing
        except Exception:
            pass
    if not predictions_path.exists():
        return pd.DataFrame()
    try:
        predictions = pd.read_csv(predictions_path)
    except Exception:
        return pd.DataFrame()
    if predictions.empty or "close" not in predictions.columns:
        return pd.DataFrame()

    work = predictions.copy()
    date_col = "date" if "date" in work.columns else work.columns[0]
    work[date_col] = pd.to_datetime(work[date_col], errors="coerce")
    work["close"] = pd.to_numeric(work["close"], errors="coerce")
    work = work.dropna(subset=[date_col, "close"]).sort_values(date_col).reset_index(drop=True)
    if len(work) < 80:
        return pd.DataFrame()

    horizon_specs = {
        "tomorrow": {"label": "下一交易日", "offset": 1, "prob_decay": 0.86},
        "one_to_two_weeks": {"label": "未来1-2周", "offset": 10, "prob_decay": 0.72},
        "one_to_three_months": {"label": "未来1-3个月", "offset": 60, "prob_decay": 0.58},
    }
    rows: list[dict[str, Any]] = []
    for horizon_key, spec in horizon_specs.items():
        offset = int(spec["offset"])
        prob_decay = float(spec["prob_decay"])
        risk_spec = get_horizon_spec(horizon_key)
        for idx in range(0, len(work) - offset):
            row = work.iloc[idx]
            future = work.iloc[idx + offset]
            anchor = _safe_float(row.get("close", 0.0))
            realized = _safe_float(future.get("close", 0.0))
            if anchor <= 0 or realized <= 0:
                continue
            base_return = _safe_float(row.get("predicted_return", 0.0))
            base_prob = _safe_float(row.get("prob_up_multimodal", row.get("prob_up", 0.5)), 0.5)
            prob_up = float(np.clip(0.5 + (base_prob - 0.5) * prob_decay, 0.02, 0.98))
            expected_return = float(np.clip(base_return, -risk_spec.max_center_offset, risk_spec.max_center_offset))
            center = anchor * (1.0 + expected_return)
            low_raw = _safe_float(row.get("pred_low", center), center)
            high_raw = _safe_float(row.get("pred_high", center), center)
            base_width_pct = abs(high_raw - low_raw) / max(anchor * 2.0, 1e-9)
            atr_width_pct = _safe_float(row.get("atr_14", 0.0), 0.0) / anchor if anchor > 0 else 0.0
            half_width_pct = float(
                np.clip(
                    max(base_width_pct, atr_width_pct * risk_spec.volatility_multiplier, risk_spec.min_half_width),
                    risk_spec.min_half_width,
                    risk_spec.max_half_width,
                )
            )
            half_width_pct = float(np.clip(half_width_pct * 0.86, risk_spec.min_half_width, risk_spec.max_half_width))
            half_width = anchor * half_width_pct
            realized_return = realized / anchor - 1.0
            direction_active = abs(prob_up - 0.5) >= 0.10
            direction_hit = (
                float((prob_up >= 0.5 and realized_return >= 0) or (prob_up < 0.5 and realized_return < 0))
                if direction_active
                else np.nan
            )
            rows.append(
                {
                    "snapshot_id": f"baseline|{horizon_key}|{pd.Timestamp(row[date_col]).date()}",
                    "generated_at": pd.Timestamp(row[date_col]).strftime("%Y-%m-%d"),
                    "anchor_date": pd.Timestamp(row[date_col]).strftime("%Y-%m-%d"),
                    "anchor_close": anchor,
                    "source_mode": "walk_forward_baseline",
                    "validation_mode": "walk_forward_baseline",
                    "baseline_version": "v2.8_realistic",
                    "horizon_key": horizon_key,
                    "horizon_label": str(spec["label"]),
                    "target_label": pd.Timestamp(future[date_col]).strftime("%Y-%m-%d"),
                    "target_start": pd.Timestamp(future[date_col]).strftime("%Y-%m-%d"),
                    "target_end": pd.Timestamp(future[date_col]).strftime("%Y-%m-%d"),
                    "contract_code": str(row.get("contract_code", "SN")),
                    "direction_key": _direction_key(prob_up),
                    "direction_label": _direction_label_zh(prob_up),
                    "price_center": center,
                    "range_low": max(0.0, center - half_width),
                    "range_high": center + half_width,
                    "prob_up": prob_up,
                    "prob_down": 1.0 - prob_up,
                    "confidence": _safe_float(row.get("confidence_multimodal", row.get("confidence", 50.0)), 50.0),
                    "expected_return": expected_return,
                    "realized_close": realized,
                    "realized_return": realized_return,
                    "center_error_pct": realized / center - 1.0 if center > 0 else np.nan,
                    "direction_active": float(direction_active),
                    "direction_hit": direction_hit,
                    "range_hit": float(max(0.0, center - half_width) <= realized <= center + half_width),
                }
            )
    baseline = pd.DataFrame(rows)
    if not baseline.empty:
        output_dir.mkdir(parents=True, exist_ok=True)
        baseline.to_csv(baseline_path, index=False, encoding="utf-8-sig")
    return baseline


def append_prediction_snapshot(
    *,
    output_dir: Path,
    live_predictions: dict[str, Any],
    raw: pd.DataFrame,
    metrics: dict[str, Any] | None = None,
    optimization_summary: dict[str, Any] | None = None,
    bandit_summary: dict[str, Any] | None = None,
) -> pd.DataFrame:
    cards = live_predictions.get("cards", {}) if isinstance(live_predictions, dict) else {}
    if not isinstance(cards, dict) or not cards:
        return load_prediction_history(output_dir, max_rows=MAX_HISTORY_LINES)

    output_dir.mkdir(parents=True, exist_ok=True)
    path = prediction_history_path(output_dir)
    latest_raw = raw.iloc[-1] if isinstance(raw, pd.DataFrame) and not raw.empty else pd.Series(dtype=float)
    source_mode = str(latest_raw.get("data_source_mode", "") or "")
    latest_close = _safe_float(latest_raw.get("close", 0.0))
    latest_date = _safe_date(raw.index[-1]) if isinstance(raw, pd.DataFrame) and not raw.empty else ""
    generated_at = str(live_predictions.get("generated_at") or datetime.now().isoformat())
    best_score = _safe_float((optimization_summary or {}).get("best_score", 0.0))
    latest_action = str((bandit_summary or {}).get("latest_action", ""))

    rows: list[dict[str, Any]] = []
    for horizon_key, card in cards.items():
        if not isinstance(card, dict):
            continue
        center = _safe_float(card.get("price_center", 0.0))
        anchor_close = _safe_float(card.get("anchor_close", latest_close), latest_close)
        row = {
            "snapshot_id": f"{generated_at}|{horizon_key}|{card.get('contract_code', '')}",
            "generated_at": generated_at,
            "anchor_date": latest_date,
            "anchor_close": anchor_close,
            "source_mode": source_mode,
            "horizon_key": str(horizon_key),
            "horizon_label": str(card.get("horizon_label", "")),
            "target_label": str(card.get("target_label", "")),
            "target_start": _safe_date(card.get("target_start")),
            "target_end": _safe_date(card.get("target_end")),
            "target_start_ts": str(card.get("target_start", "")),
            "target_end_ts": str(card.get("target_end", "")),
            "window_minutes": _safe_float(card.get("window_minutes", 0.0)),
            "validation_eligible": bool(card.get("validation_eligible", True)),
            "validation_note": str(card.get("validation_note", "")),
            "micro_data_source": str(card.get("micro_data_source", "")),
            "contract_code": str(card.get("contract_code", "")),
            "direction_key": str(card.get("direction_key", "")),
            "direction_label": str(card.get("direction_label", "")),
            "price_center": center,
            "range_low": _safe_float(card.get("range_low", 0.0)),
            "range_high": _safe_float(card.get("range_high", 0.0)),
            "prob_up": _safe_float(card.get("prob_up", 0.5), 0.5),
            "prob_down": _safe_float(card.get("prob_down", 0.5), 0.5),
            "confidence": _safe_float(card.get("confidence", 0.0)),
            "expected_return": _safe_float(card.get("expected_return", center / anchor_close - 1.0 if anchor_close else 0.0)),
            "realized_close": None,
            "realized_return": None,
            "center_error_pct": None,
            "direction_hit": None,
            "range_hit": None,
            "backtest_win_rate": _safe_float((metrics or {}).get("win_rate", 0.0)),
            "backtest_sharpe": _safe_float((metrics or {}).get("sharpe", 0.0)),
            "backtest_reward_risk": _safe_float((metrics or {}).get("reward_risk_ratio", 0.0)),
            "optimization_score": best_score,
            "bandit_action": latest_action,
            "direction_gate_status": str((card.get("direction_gate") or {}).get("status", "")) if isinstance(card.get("direction_gate"), dict) else "",
            "direction_gate_reason": "；".join(str(item) for item in (card.get("direction_gate") or {}).get("reasons", [])) if isinstance(card.get("direction_gate"), dict) else "",
        }
        rows.append(row)

    if rows:
        with path.open("a", encoding="utf-8") as handle:
            for row in rows:
                handle.write(json.dumps(row, ensure_ascii=False, default=str, allow_nan=False) + "\n")
        _compact_jsonl(path)
    return load_prediction_history(output_dir, max_rows=MAX_HISTORY_LINES)


def evaluate_prediction_history(output_dir: Path, raw: pd.DataFrame) -> pd.DataFrame:
    history = load_prediction_history(output_dir, max_rows=MAX_HISTORY_LINES)
    if history.empty or not isinstance(raw, pd.DataFrame) or raw.empty:
        return pd.DataFrame()

    price = raw[["close"]].copy()
    price.index = pd.to_datetime(price.index, errors="coerce").tz_localize(None)
    price = price.dropna().sort_index()
    if price.empty:
        return pd.DataFrame()

    evaluated = history.copy()
    actual_close: list[float] = []
    for _, row in evaluated.iterrows():
        horizon_key = str(row.get("horizon_key", ""))
        if horizon_key in INTRADAY_HORIZON_KEYS:
            # Intraday horizons require minute/snapshot realization. Daily closes
            # would make fake hit-rate numbers, so keep them pending here.
            actual_close.append(np.nan)
            continue
        target_date = pd.to_datetime(row.get("target_end"), errors="coerce")
        if pd.isna(target_date):
            actual_close.append(np.nan)
            continue
        available = price[price.index <= target_date]
        if available.empty or available.index[-1].date() < target_date.date():
            actual_close.append(np.nan)
            continue
        actual_close.append(float(available["close"].iloc[-1]))

    evaluated["realized_close"] = actual_close
    evaluated["anchor_close"] = pd.to_numeric(evaluated["anchor_close"], errors="coerce")
    evaluated["price_center"] = pd.to_numeric(evaluated["price_center"], errors="coerce")
    evaluated["range_low"] = pd.to_numeric(evaluated["range_low"], errors="coerce")
    evaluated["range_high"] = pd.to_numeric(evaluated["range_high"], errors="coerce")
    evaluated["prob_up"] = pd.to_numeric(evaluated["prob_up"], errors="coerce")

    valid = evaluated["realized_close"].notna() & evaluated["anchor_close"].gt(0) & evaluated["price_center"].gt(0)
    evaluated.loc[valid, "realized_return"] = evaluated.loc[valid, "realized_close"] / evaluated.loc[valid, "anchor_close"] - 1.0
    evaluated.loc[valid, "center_error_pct"] = evaluated.loc[valid, "realized_close"] / evaluated.loc[valid, "price_center"] - 1.0
    direction_edge = (evaluated["prob_up"] - 0.5).abs()
    direction_declared = evaluated.get("direction_key", pd.Series("", index=evaluated.index)).astype(str).ne("neutral")
    direction_valid = valid & direction_edge.ge(0.10) & direction_declared
    pred_direction = np.where(evaluated["prob_up"] >= 0.5, 1, -1)
    actual_direction = np.where(evaluated["realized_return"] >= 0, 1, -1)
    evaluated.loc[direction_valid, "direction_hit"] = (pred_direction[direction_valid.to_numpy()] == actual_direction[direction_valid.to_numpy()]).astype(float)
    evaluated.loc[valid, "direction_active"] = direction_valid[valid].astype(float)
    evaluated.loc[valid, "range_hit"] = (
        (evaluated.loc[valid, "realized_close"] >= evaluated.loc[valid, "range_low"])
        & (evaluated.loc[valid, "realized_close"] <= evaluated.loc[valid, "range_high"])
    ).astype(float)
    evaluated.loc[valid, "validation_mode"] = "live_realized"

    out = evaluated[valid].copy()
    if not out.empty:
        out.to_csv(prediction_evaluation_path(output_dir), index=False, encoding="utf-8-sig")
    return out


def build_calibration_profile(evaluated: pd.DataFrame, min_samples: int = 8) -> dict[str, dict[str, float]]:
    if not isinstance(evaluated, pd.DataFrame) or evaluated.empty:
        return {}
    profile: dict[str, dict[str, float]] = {}
    work = evaluated.dropna(subset=["center_error_pct", "direction_hit"]).copy()
    if work.empty:
        return {}
    for horizon_key, group in work.groupby("horizon_key"):
        recent = group.tail(80)
        if len(recent) < min_samples:
            continue
        bias = float(np.clip(pd.to_numeric(recent["center_error_pct"], errors="coerce").mean(), -0.035, 0.035))
        mae = float(np.clip(pd.to_numeric(recent["center_error_pct"], errors="coerce").abs().mean(), 0.0, 0.12))
        hit_rate = float(np.clip(pd.to_numeric(recent["direction_hit"], errors="coerce").mean(), 0.0, 1.0))
        range_hit = float(np.clip(pd.to_numeric(recent["range_hit"], errors="coerce").mean(), 0.0, 1.0))
        profile[str(horizon_key)] = {
            "sample_count": float(len(recent)),
            "center_bias_pct": bias,
            "center_mae_pct": mae,
            "direction_hit_rate": hit_rate,
            "range_hit_rate": range_hit,
        }
    return profile


def build_walk_forward_calibration_profile(
    predictions: pd.DataFrame,
    raw: pd.DataFrame,
    *,
    min_samples: int = 30,
) -> dict[str, dict[str, float]]:
    if not isinstance(predictions, pd.DataFrame) or predictions.empty:
        return {}
    if not isinstance(raw, pd.DataFrame) or raw.empty or "close" not in raw.columns:
        return {}

    price = raw[["close"]].copy()
    price.index = pd.to_datetime(price.index, errors="coerce").tz_localize(None)
    price = price.dropna().sort_index()
    preds = predictions.copy()
    preds.index = pd.to_datetime(preds.index, errors="coerce").tz_localize(None)
    preds = preds.dropna(how="all").sort_index()
    rows: list[dict[str, float]] = []
    for idx, row in preds.tail(420).iterrows():
        if pd.isna(idx) or idx not in price.index:
            continue
        future = price[price.index > idx]
        if future.empty:
            continue
        anchor = _safe_float(price.loc[idx, "close"])
        actual = _safe_float(future["close"].iloc[0])
        if anchor <= 0 or actual <= 0:
            continue
        if "pred_center" in row:
            center = _safe_float(row.get("pred_center", 0.0))
        elif "pred_low" in row and "pred_high" in row:
            center = (_safe_float(row.get("pred_low", 0.0)) + _safe_float(row.get("pred_high", 0.0))) / 2.0
        else:
            center = anchor * (1.0 + _safe_float(row.get("predicted_return", 0.0)))
        low = _safe_float(row.get("pred_low", center))
        high = _safe_float(row.get("pred_high", center))
        if center <= 0:
            continue
        prob_up = _safe_float(row.get("prob_up_multimodal", row.get("prob_up", 0.5)), 0.5)
        realized_return = actual / anchor - 1.0
        direction_active = abs(prob_up - 0.5) >= 0.10
        rows.append(
            {
                "center_error_pct": actual / center - 1.0,
                "direction_hit": float((prob_up >= 0.5 and realized_return >= 0) or (prob_up < 0.5 and realized_return < 0)) if direction_active else np.nan,
                "direction_active": float(direction_active),
                "range_hit": float(low <= actual <= high),
            }
        )
    if len(rows) < min_samples:
        return {}
    frame = pd.DataFrame(rows).tail(160)
    base = {
            "sample_count": float(len(frame)),
            "center_bias_pct": float(np.clip(pd.to_numeric(frame["center_error_pct"], errors="coerce").mean(), -0.030, 0.030)),
            "center_mae_pct": float(np.clip(pd.to_numeric(frame["center_error_pct"], errors="coerce").abs().mean(), 0.0, 0.10)),
            "direction_hit_rate": float(np.clip(pd.to_numeric(frame["direction_hit"], errors="coerce").dropna().mean(), 0.0, 1.0)) if pd.to_numeric(frame["direction_hit"], errors="coerce").notna().any() else 0.5,
            "direction_active_rate": float(np.clip(pd.to_numeric(frame["direction_active"], errors="coerce").mean(), 0.0, 1.0)),
            "range_hit_rate": float(np.clip(pd.to_numeric(frame["range_hit"], errors="coerce").mean(), 0.0, 1.0)),
            "source": "walk_forward_backtest",
    }

    def derived_profile(scale_bias: float, scale_mae: float, horizon_penalty: float, source: str) -> dict[str, float | str]:
        hit_rate = 0.5 + (float(base["direction_hit_rate"]) - 0.5) * horizon_penalty
        range_hit = 0.5 + (float(base["range_hit_rate"]) - 0.5) * horizon_penalty
        return {
            "sample_count": float(base["sample_count"]),
            "center_bias_pct": float(np.clip(float(base["center_bias_pct"]) * scale_bias, -0.035, 0.035)),
            "center_mae_pct": float(np.clip(float(base["center_mae_pct"]) * scale_mae, 0.0, 0.16)),
            "direction_hit_rate": float(np.clip(hit_rate, 0.0, 1.0)),
            "range_hit_rate": float(np.clip(range_hit, 0.0, 1.0)),
            "source": source,
        }

    return {
        "next_5m": derived_profile(0.08, 0.12, 0.20, "short_reference_from_walk_forward"),
        "next_15m": derived_profile(0.14, 0.20, 0.26, "short_reference_from_walk_forward"),
        "next_30m": derived_profile(0.22, 0.30, 0.32, "short_reference_from_walk_forward"),
        "next_hour": derived_profile(0.35, 0.45, 0.45, "derived_from_walk_forward"),
        "tomorrow": base,
        "one_to_two_weeks": derived_profile(0.75, 1.85, 0.55, "derived_from_walk_forward"),
        "one_to_three_months": derived_profile(0.55, 2.80, 0.35, "derived_from_walk_forward"),
    }


def apply_history_calibration(live_predictions: dict[str, Any], profile: dict[str, dict[str, float]]) -> dict[str, Any]:
    if not isinstance(live_predictions, dict) or not profile:
        return live_predictions
    cards = live_predictions.get("cards", {})
    if not isinstance(cards, dict):
        return live_predictions
    calibrated = json.loads(json.dumps(live_predictions, ensure_ascii=False, default=str))
    cards_out = calibrated.get("cards", {})
    for horizon_key, stats in profile.items():
        card = cards_out.get(horizon_key) if isinstance(cards_out, dict) else None
        if not isinstance(card, dict):
            continue
        bias = _safe_float(stats.get("center_bias_pct", 0.0))
        mae = _safe_float(stats.get("center_mae_pct", 0.0))
        hit_rate = _safe_float(stats.get("direction_hit_rate", 0.5), 0.5)
        center = _safe_float(card.get("price_center", 0.0))
        low = _safe_float(card.get("range_low", 0.0))
        high = _safe_float(card.get("range_high", 0.0))
        anchor = _safe_float(card.get("anchor_close", 0.0))
        if center <= 0 or low <= 0 or high <= 0:
            continue
        adjusted_center = center * (1.0 + bias)
        half_width = max((high - low) / 2.0, adjusted_center * max(mae, 0.006))
        card["price_center_raw"] = center
        card["range_low_raw"] = low
        card["range_high_raw"] = high
        card["price_center"] = adjusted_center
        card["range_low"] = max(0.0, adjusted_center - half_width)
        card["range_high"] = adjusted_center + half_width
        if anchor > 0:
            card["expected_return"] = adjusted_center / anchor - 1.0
            adjusted_return, adjusted_prob = cohere_directional_forecast(
                _safe_float(card.get("expected_return", 0.0)),
                _safe_float(card.get("prob_up", 0.5), 0.5),
                max(_safe_float(card.get("volatility", mae), mae), 1e-4),
            )
            cap = get_horizon_spec(str(horizon_key)).max_center_offset
            clipped_return = float(np.clip(adjusted_return, -cap, cap))
            if abs(clipped_return - adjusted_return) > 1e-9:
                adjusted_return = clipped_return
                vol = max(_safe_float(card.get("volatility", mae), mae), 1e-4)
                implied_prob = 0.5 + 0.5 * float(np.tanh(adjusted_return / max(vol * 1.35, 1e-4)))
                adjusted_prob = float(np.clip(0.55 * adjusted_prob + 0.45 * implied_prob, 0.02, 0.98))
            card["expected_return"] = adjusted_return
            card["price_center"] = anchor * (1.0 + adjusted_return)
            card["range_low"] = max(0.0, card["price_center"] - half_width)
            card["range_high"] = card["price_center"] + half_width
            card["prob_up"] = adjusted_prob
            card["prob_down"] = 1.0 - adjusted_prob
            card["direction_key"] = _direction_key(adjusted_prob)
            card["direction_label"] = _direction_label_zh(adjusted_prob)
            apply_realistic_price_gate(card)
        confidence = _safe_float(card.get("confidence", 0.0))
        card["confidence"] = float(np.clip(confidence + (hit_rate - 0.5) * 12.0 - mae * 35.0, 5.0, 99.0))
        card["calibration"] = {
            "enabled": True,
            "sample_count": stats.get("sample_count", 0.0),
            "center_bias_pct": bias,
            "center_mae_pct": mae,
            "direction_hit_rate": hit_rate,
            "range_hit_rate": stats.get("range_hit_rate", 0.0),
            "source": stats.get("source", "prediction_history"),
            "note": "已基于历史预测误差进行轻量校准，并保持概率、方向与价格中枢一致。",
        }
    return calibrated


def build_model_memory(
    *,
    evaluation_summary: dict[str, Any],
    calibration_profile: dict[str, dict[str, float]],
    backtest_metrics: dict[str, Any] | None = None,
    optimization_summary: dict[str, Any] | None = None,
    bandit_summary: dict[str, Any] | None = None,
) -> dict[str, Any]:
    best_config = (optimization_summary or {}).get("best_config", {}) if isinstance(optimization_summary, dict) else {}
    return {
        "updated_at": datetime.now().isoformat(),
        "purpose": "本地模型记忆：用于记录历史预测表现、校准参数、回测表现与Bandit策略状态。",
        "evaluation_summary": evaluation_summary,
        "calibration_profile": calibration_profile,
        "backtest_metrics": {
            "win_rate": _safe_float((backtest_metrics or {}).get("win_rate", 0.0)),
            "sharpe": _safe_float((backtest_metrics or {}).get("sharpe", 0.0)),
            "max_drawdown": _safe_float((backtest_metrics or {}).get("max_drawdown", 0.0)),
            "reward_risk_ratio": _safe_float((backtest_metrics or {}).get("reward_risk_ratio", 0.0)),
            "trade_count": _safe_float((backtest_metrics or {}).get("trade_count", 0.0)),
        },
        "best_training_config": best_config,
        "model_selection": {
            "best_score": _safe_float((optimization_summary or {}).get("best_score", 0.0)),
            "candidate_count": int(_safe_float((optimization_summary or {}).get("candidate_count", 0.0))),
            "selected_candidate_source": str((optimization_summary or {}).get("selected_candidate_source", "")),
            "rollback_applied": bool((optimization_summary or {}).get("rollback_applied", False)),
            "rollback_reason": str((optimization_summary or {}).get("rollback_reason", "")),
        },
        "bandit_state": bandit_summary or {},
        "next_actions": [
            "刷新后自动追加预测快照。",
            "目标日期出现真实价格后自动评估方向命中、区间命中与中枢误差。",
            "后续预测自动读取误差画像，微调价格中枢、区间宽度与置信度。",
            "下一轮回测会把本轮最优配置纳入候选，若历史配置在最新真实数据上更稳则自动回滚。",
        ],
    }


def save_model_memory(output_dir: Path, memory: dict[str, Any]) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    model_memory_path(output_dir).write_text(json.dumps(memory, ensure_ascii=False, indent=2, default=str), encoding="utf-8")


def summarize_prediction_evaluation(evaluated: pd.DataFrame) -> dict[str, Any]:
    if not isinstance(evaluated, pd.DataFrame) or evaluated.empty:
        return {"sample_count": 0, "by_horizon": []}
    rows: list[dict[str, Any]] = []
    for horizon_key, group in evaluated.groupby("horizon_key"):
        recent = group.tail(120)
        direction_hit = pd.to_numeric(recent.get("direction_hit", pd.Series(dtype=float)), errors="coerce")
        range_hit = pd.to_numeric(recent.get("range_hit", pd.Series(dtype=float)), errors="coerce")
        center_error = pd.to_numeric(recent.get("center_error_pct", pd.Series(dtype=float)), errors="coerce")
        direction_active = pd.to_numeric(recent.get("direction_active", pd.Series(dtype=float)), errors="coerce")
        rows.append(
            {
                "horizon_key": str(horizon_key),
                "sample_count": int(len(recent)),
                "direction_sample_count": int(direction_hit.notna().sum()),
                "direction_active_rate": float(direction_active.mean()) if direction_active.notna().any() else 0.0,
                "direction_hit_rate": float(direction_hit.mean()) if direction_hit.notna().any() else 0.0,
                "range_hit_rate": float(range_hit.mean()) if range_hit.notna().any() else 0.0,
                "center_mae_pct": float(center_error.abs().mean()) if center_error.notna().any() else 0.0,
                "center_bias_pct": float(center_error.mean()) if center_error.notna().any() else 0.0,
            }
        )
    return {"sample_count": int(len(evaluated)), "by_horizon": rows}
