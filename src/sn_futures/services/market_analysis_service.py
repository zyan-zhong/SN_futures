from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from ..runtime import get_user_output_dir


MIN_ANALYSIS_ROWS = 20


def _now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _safe_float(value: Any) -> float | None:
    try:
        if value is None:
            return None
        number = float(value)
        if not np.isfinite(number):
            return None
        return round(number, 6)
    except Exception:
        return None


def _load_json(path: Path) -> Any:
    try:
        if not path.exists():
            return None
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _extract_rows(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, dict)]
    if not isinstance(payload, dict):
        return []
    for key in ("history", "points", "rows", "data"):
        rows = payload.get(key)
        if isinstance(rows, list):
            return [row for row in rows if isinstance(row, dict)]
    return []


def _row_count(path: Path) -> int:
    payload = _load_json(path)
    if isinstance(payload, dict) and isinstance(payload.get("row_count"), int):
        return int(payload["row_count"])
    return len(_extract_rows(payload))


def _load_market_frame(output_dir: Path) -> tuple[pd.DataFrame, str]:
    candidates = [
        output_dir / "sn_market_history.json",
        output_dir / "last_good_market_history.json",
    ]
    for path in candidates:
        rows = _extract_rows(_load_json(path))
        if not rows:
            continue
        frame = pd.DataFrame(rows).copy()
        date_col = next((col for col in ("time", "trade_date", "date", "timestamp") if col in frame.columns), None)
        if date_col is None:
            continue
        frame["trade_date"] = pd.to_datetime(frame[date_col], errors="coerce")
        for col in ("open", "high", "low", "close", "volume", "open_interest"):
            if col in frame.columns:
                frame[col] = pd.to_numeric(frame[col], errors="coerce")
            else:
                frame[col] = np.nan
        frame = frame.dropna(subset=["trade_date", "close"]).sort_values("trade_date")
        frame = frame.drop_duplicates(subset=["trade_date"], keep="last")
        frame = frame[frame["close"] > 0].reset_index(drop=True)
        if not frame.empty:
            return frame, str(path)
    return pd.DataFrame(), ""


def _trend_label(close: float, ma_fast: float | None, ma_mid: float | None, ret: float | None) -> str:
    if ma_fast is None or ma_mid is None or ret is None:
        return "range"
    if close > ma_fast > ma_mid and ret > 0:
        return "up"
    if close < ma_fast < ma_mid and ret < 0:
        return "down"
    return "range"


def _ma_structure(row: pd.Series) -> str:
    values = {
        "price": _safe_float(row.get("close")),
        "MA5": _safe_float(row.get("ma_5")),
        "MA20": _safe_float(row.get("ma_20")),
        "MA60": _safe_float(row.get("ma_60")),
    }
    ordered = [item for item in values.items() if item[1] is not None]
    if len(ordered) < 3:
        return "history_insufficient_for_full_ma_structure"
    sorted_names = [name for name, _ in sorted(ordered, key=lambda item: item[1] or 0, reverse=True)]
    return ">".join(sorted_names)


def _volatility_regime(realized_vol: float | None, atr_pct: float | None) -> str:
    score = realized_vol if realized_vol is not None else atr_pct
    if score is None:
        return "unknown"
    if score >= 0.45:
        return "extreme"
    if score >= 0.28:
        return "high"
    if score <= 0.12:
        return "low"
    return "normal"


def _support_resistance(frame: pd.DataFrame) -> tuple[list[float], list[float]]:
    latest = frame.iloc[-1]
    support_candidates = [
        frame["low"].tail(20).min(),
        frame["low"].tail(60).min(),
        latest.get("ma_20"),
        latest.get("ma_60"),
    ]
    resistance_candidates = [
        frame["high"].tail(20).max(),
        frame["high"].tail(60).max(),
        latest.get("ma_20"),
        latest.get("ma_60"),
    ]

    def clean(values: list[Any]) -> list[float]:
        unique: list[float] = []
        for value in values:
            number = _safe_float(value)
            if number is None:
                continue
            if all(abs(number - existing) > 1e-6 for existing in unique):
                unique.append(number)
        return unique[:4]

    return clean(support_candidates), clean(resistance_candidates)


def _build_frame_features(frame: pd.DataFrame) -> pd.DataFrame:
    frame = frame.copy()
    frame["ma_5"] = frame["close"].rolling(5, min_periods=3).mean()
    frame["ma_20"] = frame["close"].rolling(20, min_periods=10).mean()
    frame["ma_60"] = frame["close"].rolling(60, min_periods=30).mean()
    frame["ret_5"] = frame["close"].pct_change(5, fill_method=None)
    frame["ret_20"] = frame["close"].pct_change(20, fill_method=None)
    frame["ret_60"] = frame["close"].pct_change(60, fill_method=None)
    frame["realized_vol_20"] = frame["close"].pct_change(fill_method=None).rolling(20, min_periods=10).std() * np.sqrt(252)

    prev_close = frame["close"].shift(1)
    true_range = pd.concat(
        [
            frame["high"] - frame["low"],
            (frame["high"] - prev_close).abs(),
            (frame["low"] - prev_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    frame["atr_14"] = true_range.rolling(14, min_periods=7).mean()
    frame["atr_pct_14"] = frame["atr_14"] / frame["close"]
    boll_mid = frame["close"].rolling(20, min_periods=10).mean()
    boll_std = frame["close"].rolling(20, min_periods=10).std()
    frame["bollinger_width_20"] = (4 * boll_std) / boll_mid
    frame["volume_ma_20"] = frame["volume"].rolling(20, min_periods=10).mean()
    frame["volume_std_20"] = frame["volume"].rolling(20, min_periods=10).std()
    frame["volume_zscore"] = (frame["volume"] - frame["volume_ma_20"]) / frame["volume_std_20"].replace(0, np.nan)
    frame["volume_momentum_5"] = frame["volume"].pct_change(5, fill_method=None)
    return frame


def _fundamental_availability(output_dir: Path) -> tuple[list[str], dict[str, bool]]:
    fundamentals = output_dir / "fundamentals"
    tushare_available = any(
        _row_count(fundamentals / name) > 0
        for name in (
            "sn_tushare_daily.json",
            "sn_tushare_warehouse_receipt.json",
            "sn_tushare_settlement.json",
            "sn_tushare_holding.json",
        )
    )
    managed_proxy_available = _row_count(fundamentals / "managed_fundamentals.json") > 0
    has_basis = _row_count(fundamentals / "sn_spot_basis.json") > 0 or managed_proxy_available
    has_inventory = (
        _row_count(fundamentals / "sn_shfe_inventory.json") > 0
        or _row_count(fundamentals / "sn_inventory.json") > 0
        or managed_proxy_available
    )
    has_lme = _row_count(fundamentals / "sn_lme_tin.json") > 0 or managed_proxy_available
    has_warehouse = (
        _row_count(fundamentals / "sn_shfe_warehouse_receipts.json") > 0
        or _row_count(fundamentals / "sn_tushare_warehouse_receipt.json") > 0
        or managed_proxy_available
    )
    missing = []
    if not has_basis:
        missing.append("basis")
    if not has_inventory:
        missing.append("inventory")
    if not has_lme:
        missing.append("lme_tin")
    if not has_warehouse:
        missing.append("warehouse_receipt")
    return missing, {
        "tushare_available": tushare_available,
        "managed_proxy_available": managed_proxy_available,
        "basis_available": has_basis,
        "inventory_available": has_inventory,
        "lme_tin_available": has_lme,
        "warehouse_receipt_available": has_warehouse,
    }


def _base_payload(status: str, message_zh: str) -> dict[str, Any]:
    return {
        "status": status,
        "analysis_mode": "ohlcv_regime_analysis",
        "not_prediction": True,
        "sample_data_used": False,
        "baseline_used": False,
        "generated_at": _now_iso(),
        "message_zh": message_zh,
        "disclaimer": "行情分析不构成投资建议，不代表预测。",
        "next_actions_zh": [
            "可继续观察真实行情图",
            "如需完整基本面分析，请配置 Tushare 或托管数据服务",
            "当前不生成预测",
        ],
    }


def build_market_analysis() -> dict[str, Any]:
    """Build professional market analysis from real OHLCV only.

    This service intentionally does not create customer predictions, trade
    points, or active-model outputs. It remains useful when Tushare/managed
    fundamentals are unavailable by separating market analysis from prediction.
    """

    output_dir = get_user_output_dir()
    frame, source_path = _load_market_frame(output_dir)
    missing_fundamentals, source_flags = _fundamental_availability(output_dir)

    if len(frame) < MIN_ANALYSIS_ROWS:
        payload = _base_payload(
            "insufficient_data",
            f"真实历史行情不足，至少需要 {MIN_ANALYSIS_ROWS} 条 OHLCV 才能生成专业行情分析。",
        )
        payload.update(
            {
                "data_sources": {
                    "market_history_available": False,
                    "history_rows": int(len(frame)),
                    "history_source": source_path,
                    **source_flags,
                },
                "risk_flags": ["真实历史行情不足", "无 active 模型"],
                "missing_fundamentals": missing_fundamentals,
                "trend": {},
                "volatility": {},
                "key_levels": {},
                "volume_liquidity": {},
                "regime": {},
            }
        )
        return payload

    frame = _build_frame_features(frame)
    latest = frame.iloc[-1]
    close = float(latest["close"])
    ret_5 = _safe_float(latest.get("ret_5"))
    ret_20 = _safe_float(latest.get("ret_20"))
    ret_60 = _safe_float(latest.get("ret_60"))
    ma_5 = _safe_float(latest.get("ma_5"))
    ma_20 = _safe_float(latest.get("ma_20"))
    ma_60 = _safe_float(latest.get("ma_60"))
    realized_vol = _safe_float(latest.get("realized_vol_20"))
    atr_pct = _safe_float(latest.get("atr_pct_14"))
    volatility_regime = _volatility_regime(realized_vol, atr_pct)
    short_term = _trend_label(close, ma_5, ma_20, ret_5)
    medium_term = _trend_label(close, ma_20, ma_60, ret_20)
    momentum_values = [value for value in (ret_5, ret_20, ret_60) if value is not None]
    momentum_score = _safe_float(np.mean(momentum_values) * 100 if momentum_values else None)
    support_levels, resistance_levels = _support_resistance(frame)
    volume_zscore = _safe_float(latest.get("volume_zscore"))
    volume_momentum = _safe_float(latest.get("volume_momentum_5"))
    if volume_zscore is None:
        volume_trend = "unknown"
    elif volume_zscore >= 1:
        volume_trend = "expanding"
    elif volume_zscore <= -1:
        volume_trend = "contracting"
    else:
        volume_trend = "stable"

    trend_score = _safe_float((1 if short_term == "up" else -1 if short_term == "down" else 0) + (momentum_score or 0) / 5)
    volatility_score = _safe_float((realized_vol or 0) * 100)
    regime_label = "RANGE"
    if volatility_regime in {"high", "extreme"}:
        regime_label = "HIGH_VOL"
    elif short_term == "up" and medium_term == "up":
        regime_label = "TREND_UP"
    elif short_term == "down" and medium_term == "down":
        regime_label = "TREND_DOWN"

    risk_flags = ["基本面数据不足", "无 active 模型"]
    if volatility_regime in {"high", "extreme"}:
        risk_flags.insert(0, "高波动")
    if medium_term == "range":
        risk_flags.append("趋势结构不明确")

    live_snapshot = _load_json(output_dir / "sn_live_snapshot.json") or {}
    payload = _base_payload("success", "已基于真实 OHLCV 生成专业行情分析；当前不生成预测。")
    payload.update(
        {
            "latest_trade_date": frame["trade_date"].iloc[-1].date().isoformat(),
            "data_sources": {
                "market_history_available": True,
                "history_rows": int(len(frame)),
                "history_source": source_path,
                "date_start": frame["trade_date"].iloc[0].date().isoformat(),
                "date_end": frame["trade_date"].iloc[-1].date().isoformat(),
                "live_snapshot_available": bool(live_snapshot),
                "latest_price": _safe_float(live_snapshot.get("latest_price") if isinstance(live_snapshot, dict) else None),
                **source_flags,
            },
            "trend": {
                "short_term": short_term,
                "medium_term": medium_term,
                "ma_structure": _ma_structure(latest),
                "ma_5": ma_5,
                "ma_20": ma_20,
                "ma_60": ma_60,
                "return_5": ret_5,
                "return_20": ret_20,
                "return_60": ret_60,
                "momentum_score": momentum_score,
            },
            "volatility": {
                "atr_14": _safe_float(latest.get("atr_14")),
                "atr_pct_14": atr_pct,
                "realized_vol_20": realized_vol,
                "bollinger_width_20": _safe_float(latest.get("bollinger_width_20")),
                "volatility_regime": volatility_regime,
            },
            "key_levels": {
                "recent_high_20": _safe_float(frame["high"].tail(20).max()),
                "recent_low_20": _safe_float(frame["low"].tail(20).min()),
                "recent_high_60": _safe_float(frame["high"].tail(60).max()),
                "recent_low_60": _safe_float(frame["low"].tail(60).min()),
                "support_levels": support_levels,
                "resistance_levels": resistance_levels,
            },
            "volume_liquidity": {
                "volume_trend": volume_trend,
                "volume_zscore": volume_zscore,
                "volume_momentum_5": volume_momentum,
                "latest_volume": _safe_float(latest.get("volume")),
                "open_interest_available": bool(frame["open_interest"].notna().any()),
            },
            "regime": {
                "label": regime_label,
                "trend_score": trend_score,
                "volatility_score": volatility_score,
            },
            "risk_flags": risk_flags,
            "missing_fundamentals": missing_fundamentals,
        }
    )
    return payload
