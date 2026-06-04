from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping

import numpy as np
import pandas as pd

from ..api.json_utils import sanitize_for_json
from ..features_core.pipeline import build_feature_matrix
from ..labels.leakage_guard import infer_label_columns
from ..runtime import get_user_output_dir
from .cross_market_feature_join_service import build_cross_market_feature_frame


LABEL_PREFIXES = ("ret_", "direction_", "tb_", "meta_")

RAW_MARKET_FEATURES = ("open", "high", "low", "close", "volume", "open_interest")
EXPECTED_FEATURES: dict[str, tuple[str, ...]] = {
    "raw_market": RAW_MARKET_FEATURES,
    "technical": (
        "ema_spread_5_20",
        "ema_spread_10_60",
        "ma_bias_20",
        "ma_bias_60",
        "roc_5",
        "roc_10",
        "roc_20",
        "breakout_20",
        "breakout_60",
        "rsi_14",
        "atr_14",
        "bollinger_z_20",
        "cci_20",
        "wr_14",
        "obv_slope_10",
    ),
    "mean_reversion": (
        "zscore_close_20",
        "zscore_close_60",
        "rsi_reversal_14",
        "gap_reversion",
        "price_overextension_score",
    ),
    "term_structure": (
        "near_far_spread",
        "term_structure_slope",
        "calendar_spread_momentum",
        "roll_yield_proxy",
        "open_interest_roll_ratio",
        "main_contract_switch_flag",
    ),
    "basis": (
        "spot_futures_basis",
        "basis_zscore_60",
        "basis_mom_5",
        "basis_mom_20",
        "basis_percentile_252",
        "spot_premium_mom",
        "delivery_basis_momentum",
        "cash_tightness_score",
    ),
    "inventory": (
        "shfe_inventory_delta_1w",
        "shfe_inventory_delta_4w",
        "warehouse_receipt_delta_1w",
        "member_net_position",
        "lme_inventory_delta_1w",
        "global_visible_inventory",
        "inventory_percentile_3y",
        "inventory_pressure_score",
    ),
    "cross_market": (
        "lme_tin_return_1d",
        "lme_tin_return_3d",
        "lme_tin_overnight_return",
        "lme_shfe_spread",
        "usd_cny",
        "usd_cny_return",
        "us10y",
        "us10y_change",
        "copper_global_proxy",
        "copper_global_proxy_return",
        "dxy_return",
        "global_risk_sentiment_proxy",
    ),
    "event": (
        "news_count_1d",
        "news_count_7d",
        "supply_shock_score",
        "demand_shock_score",
        "inventory_shock_score",
        "macro_risk_score",
        "event_recency_decay_score",
        "event_vol_regime_shift",
    ),
    "regime": ("regime_label", "regime_volatility_score", "regime_trend_score"),
}


def _read_json(path: Path) -> Any:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _history_rows(payload: Any) -> list[Mapping[str, Any]]:
    if isinstance(payload, Mapping):
        rows = payload.get("history") or payload.get("points") or []
    elif isinstance(payload, list):
        rows = payload
    else:
        rows = []
    return [row for row in rows if isinstance(row, Mapping)]


def _build_raw_frame(output_dir: Path) -> tuple[pd.DataFrame, list[str]]:
    payload = _read_json(output_dir / "sn_market_history.json")
    rows = _history_rows(payload)
    warnings: list[str] = []
    if not rows:
        return pd.DataFrame(), ["未找到真实 sn_market_history.json 或 history 为空。"]

    frame = pd.DataFrame(rows)
    rename_map = {
        "日期": "date",
        "时间": "time",
        "trade_date": "date",
        "开盘": "open",
        "最高": "high",
        "最低": "low",
        "收盘": "close",
        "收盘价": "close",
        "成交量": "volume",
        "持仓量": "open_interest",
    }
    frame = frame.rename(columns={k: v for k, v in rename_map.items() if k in frame.columns})
    time_col = "time" if "time" in frame.columns else "date" if "date" in frame.columns else None
    if time_col is None:
        return pd.DataFrame(), ["历史行情缺少 time/date 字段，无法构造时间索引。"]

    frame.index = pd.to_datetime(frame[time_col], errors="coerce")
    frame = frame[~frame.index.isna()].sort_index()
    frame = frame[~frame.index.duplicated(keep="last")]

    for column in RAW_MARKET_FEATURES:
        if column in frame.columns:
            frame[column] = pd.to_numeric(frame[column], errors="coerce")
        else:
            frame[column] = np.nan

    if "close" in frame.columns:
        before = len(frame)
        frame = frame[pd.to_numeric(frame["close"], errors="coerce") > 0]
        if len(frame) != before:
            warnings.append("已剔除 close 非正或无效的历史行情行。")

    snapshot = _read_json(output_dir / "sn_live_snapshot.json")
    contract = None
    if isinstance(snapshot, Mapping):
        contract = snapshot.get("active_contract") or snapshot.get("contract")
    if contract is None and isinstance(payload, Mapping):
        contract = payload.get("contract") or payload.get("symbol")
    frame["main_contract"] = str(contract or "SN0")

    _augment_event_features(frame, output_dir)
    _augment_shfe_auxiliary_features(frame, output_dir)
    _augment_fundamental_features(frame, output_dir)
    _augment_cross_market_features(frame, output_dir)
    return frame, warnings


def _events_from_payload(payload: Any) -> list[Mapping[str, Any]]:
    if isinstance(payload, Mapping):
        if payload.get("sample") or payload.get("sample_mode"):
            return []
        events = payload.get("events") or payload.get("news") or []
    elif isinstance(payload, list):
        events = payload
    else:
        events = []
    filtered: list[Mapping[str, Any]] = []
    for event in events:
        if not isinstance(event, Mapping):
            continue
        if event.get("sample") or event.get("sample_mode"):
            continue
        if event.get("used_in_model") is False or event.get("allowed_for_event_factor") is False:
            continue
        filtered.append(event)
    return filtered


def _event_time(event: Mapping[str, Any]) -> pd.Timestamp | None:
    value = event.get("available_at") or event.get("published_at") or event.get("time") or event.get("date")
    parsed = pd.to_datetime(value, errors="coerce", utc=False)
    if pd.isna(parsed):
        return None
    if getattr(parsed, "tzinfo", None) is not None:
        parsed = parsed.tz_convert(None) if hasattr(parsed, "tz_convert") else parsed.tz_localize(None)
    return pd.Timestamp(parsed).normalize()


def _score(event: Mapping[str, Any], *keys: str) -> float:
    for key in keys:
        try:
            value = float(event.get(key, 0.0) or 0.0)
        except Exception:
            value = 0.0
        if value:
            return value
    return 0.0


def _augment_event_features(frame: pd.DataFrame, output_dir: Path) -> None:
    event_payloads = [
        _read_json(output_dir / "events" / "event_store.json"),
        _read_json(output_dir / "events" / "news_events.json"),
        _read_json(output_dir / "events" / "event_factor_inputs.json"),
        _read_json(output_dir / "events" / "news_events_filtered.json"),
    ]
    events: list[Mapping[str, Any]] = []
    for payload in event_payloads:
        events.extend(_events_from_payload(payload))
    if not events or frame.empty:
        return

    by_date: dict[pd.Timestamp, dict[str, float]] = {}
    for event in events:
        day = _event_time(event)
        if day is None:
            continue
        bucket = by_date.setdefault(
            day,
            {
                "news_event_score": 0.0,
                "supply_event_score": 0.0,
                "demand_event_score": 0.0,
                "inventory_event_score": 0.0,
                "macro_event_score": 0.0,
            },
        )
        impact = abs(_score(event, "impact_score", "final_event_weight", "sentiment_score"))
        bucket["news_event_score"] += impact
        category = str(event.get("category") or event.get("event_type") or "").lower()
        bucket["supply_event_score"] += _score(event, "supply_score") or (impact if "supply" in category or "供应" in category else 0.0)
        bucket["demand_event_score"] += _score(event, "demand_score") or (impact if "demand" in category or "需求" in category else 0.0)
        bucket["inventory_event_score"] += _score(event, "inventory_score") or (impact if "inventory" in category or "库存" in category else 0.0)
        bucket["macro_event_score"] += _score(event, "macro_score", "policy_score") or (impact if "macro" in category or "policy" in category or "政策" in category else 0.0)

    if not by_date:
        return

    normalized_index = pd.Series(frame.index.normalize(), index=frame.index)
    for column in (
        "news_event_score",
        "supply_event_score",
        "demand_event_score",
        "inventory_event_score",
        "macro_event_score",
    ):
        frame[column] = normalized_index.map(lambda day: by_date.get(day, {}).get(column, 0.0)).astype(float)


def _augment_shfe_auxiliary_features(frame: pd.DataFrame, output_dir: Path) -> None:
    payload = _read_json(output_dir / "shfe_auxiliary_data.json")
    if not isinstance(payload, Mapping) or payload.get("sample") or frame.empty:
        return
    data = payload.get("data")
    if not isinstance(data, Mapping):
        return
    for source_key, target_col in (
        ("shfe_inventory", "shfe_inventory"),
        ("warehouse_receipts", "shfe_inventory"),
        ("spot_price", "spot_price"),
        ("spot_premium", "spot_premium"),
    ):
        value = data.get(source_key)
        if isinstance(value, (int, float)):
            frame[target_col] = float(value)


def _rows_from_fundamental_payload(payload: Any) -> list[Mapping[str, Any]]:
    if isinstance(payload, Mapping):
        if payload.get("sample") or payload.get("sample_mode"):
            return []
        rows = payload.get("rows") or payload.get("data") or []
    elif isinstance(payload, list):
        rows = payload
    else:
        rows = []
    return [row for row in rows if isinstance(row, Mapping)]


def _merge_fundamental_rows(frame: pd.DataFrame, rows: list[Mapping[str, Any]]) -> None:
    if frame.empty or not rows:
        return
    data = pd.DataFrame(rows)
    date_col = "trade_date" if "trade_date" in data.columns else "date" if "date" in data.columns else None
    if date_col is None:
        return
    data.index = pd.to_datetime(data[date_col], errors="coerce")
    data = data[~data.index.isna()].sort_index()
    data = data[~data.index.duplicated(keep="last")]
    if data.empty:
        return
    normalized_index = pd.Series(frame.index.normalize(), index=frame.index)
    metadata_columns = {
        "contract",
        "ts_code",
        "symbol",
        "product",
        "name",
        "member_name",
        "exchange",
        "source",
        "from_cache",
        "quality_flag",
    }
    for column in data.columns:
        if column in {"trade_date", "date", "time"} or column in metadata_columns:
            continue
        series = data[column]
        if series.dtype == object:
            numeric = pd.to_numeric(series, errors="coerce")
            if numeric.notna().any():
                series = numeric
            else:
                continue
        by_day = series.copy()
        by_day.index = by_day.index.normalize()
        mapped = normalized_index.map(lambda day: by_day.get(day, np.nan))
        if column in frame.columns:
            existing = frame[column]
            merged = existing.copy()
            fill_mask = merged.isna() & mapped.notna()
            if bool(fill_mask.any()):
                merged.loc[fill_mask] = mapped.loc[fill_mask]
            if merged.dropna().empty:
                merged = mapped
            frame.loc[:, column] = merged.to_numpy()
        else:
            frame.loc[:, column] = mapped.to_numpy()


def _augment_tushare_derived_features(frame: pd.DataFrame) -> None:
    if frame.empty:
        return
    if "warehouse_receipt" in frame.columns:
        receipt = pd.to_numeric(frame["warehouse_receipt"], errors="coerce")
        if receipt.notna().any():
            frame["warehouse_receipt_delta_1w"] = receipt.diff(5)
    if "long_position" in frame.columns or "short_position" in frame.columns:
        long_position = pd.to_numeric(frame.get("long_position", pd.Series(np.nan, index=frame.index)), errors="coerce")
        short_position = pd.to_numeric(frame.get("short_position", pd.Series(np.nan, index=frame.index)), errors="coerce")
        net = long_position - short_position
        if net.notna().any():
            frame["member_net_position"] = net


def _augment_fundamental_features(frame: pd.DataFrame, output_dir: Path) -> None:
    fundamentals = output_dir / "fundamentals"
    for filename in (
        "sn_term_structure.json",
        "sn_spot_basis.json",
        "sn_inventory.json",
        "sn_warehouse_receipts.json",
        "sn_shfe_inventory.json",
        "sn_shfe_warehouse_receipts.json",
        "sn_exchange_daily.json",
        "sn_member_positions.json",
        "sn_tushare_daily.json",
        "sn_tushare_warehouse_receipt.json",
        "sn_tushare_settlement.json",
        "sn_tushare_holding.json",
        "sn_tushare_contracts.json",
        "sn_lme_tin.json",
        "managed_fundamentals.json",
    ):
        _merge_fundamental_rows(frame, _rows_from_fundamental_payload(_read_json(fundamentals / filename)))
    _augment_tushare_derived_features(frame)


def _augment_cross_market_features(frame: pd.DataFrame, output_dir: Path) -> None:
    aligned, diagnostics = build_cross_market_feature_frame(frame, output_dir=output_dir)
    frame.attrs["cross_market_diagnostics"] = diagnostics
    if aligned.empty:
        return
    normalized_index = pd.Series(frame.index.normalize(), index=frame.index)
    for column in aligned.columns:
        if column == "_cross_market_stale":
            continue
        series = pd.to_numeric(aligned[column], errors="coerce")
        frame[column] = normalized_index.map(lambda day: series.get(day, np.nan))


def _metadata_by_feature(result: Any) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for row in result.feature_metadata:
        name = str(row.get("feature_name") or "")
        if name:
            out[name] = dict(row)
    return out


def _missing_reason_for(feature: str, metadata: Mapping[str, Any] | None, missing_report: Mapping[str, str], raw: pd.DataFrame) -> str:
    required = list((metadata or {}).get("required_columns") or [])
    missing_fields = [column for column in required if column not in raw.columns or raw[column].isna().all()]
    reasons: list[str] = []
    for column in missing_fields:
        if feature == "regime_label" and column == "open_interest":
            # The regime classifier can still produce a usable label from
            # close/volume/trend/volatility when open interest is unavailable.
            continue
        reasons.append(missing_report.get(column) or f"缺少底层字段 {column}。")
    if feature in RAW_MARKET_FEATURES and (feature not in raw.columns or raw[feature].isna().all()):
        reasons.append(f"真实行情未提供 {feature}。")
    return "；".join(dict.fromkeys(reasons))


def _latest_value(series: pd.Series) -> Any:
    valid = series.dropna()
    if valid.empty:
        return None
    value = valid.iloc[-1]
    if isinstance(value, (np.floating, float)):
        if not np.isfinite(float(value)):
            return None
        return float(value)
    if isinstance(value, (np.integer, int)):
        return int(value)
    return str(value)


def _classify_feature(feature: str, group: str, series: pd.Series | None, metadata: Mapping[str, Any] | None, missing_reason: str) -> dict[str, Any]:
    total = int(len(series)) if series is not None else 0
    non_null_count = int(series.notna().sum()) if series is not None else 0
    non_null_rate = float(non_null_count / total) if total else 0.0
    latest_value = _latest_value(series) if series is not None else None
    numeric = pd.to_numeric(series, errors="coerce") if series is not None else pd.Series(dtype=float)
    numeric_non_null = numeric.dropna()
    all_zero = bool(not numeric_non_null.empty and float(numeric_non_null.abs().sum()) == 0.0)

    label_like = bool(feature in infer_label_columns([feature]) or feature.startswith(LABEL_PREFIXES))
    should_not_all_zero = group in {"technical", "mean_reversion", "basis", "inventory", "cross_market", "event"} and feature not in {
        "main_contract_switch_flag"
    }
    reason = missing_reason
    if label_like:
        reason = "标签列或未来收益字段不得进入训练特征。"
    elif all_zero and should_not_all_zero:
        reason = reason or "该因子当前全为 0，缺少有效底层变化或事件输入。"

    if label_like or non_null_rate < 0.2 or reason:
        usable = False
        bucket = "missing"
    elif non_null_rate < 0.7:
        usable = False
        bucket = "partial"
    else:
        usable = True
        bucket = "available"

    return {
        "name": feature,
        "group": group,
        "non_null_count": non_null_count,
        "non_null_rate": round(non_null_rate, 6),
        "latest_value": latest_value,
        "usable_for_training": usable,
        "availability": bucket,
        "missing_reason": reason,
        "required_columns": list((metadata or {}).get("required_columns") or []),
        "direction_hint": (metadata or {}).get("direction_hint", ""),
        "description_zh": (metadata or {}).get("description_zh", ""),
        "lookback_window": (metadata or {}).get("lookback_window", 0),
    }


def _write_coverage_report(payload: Mapping[str, Any], report_version: str | None = None) -> None:
    output_dir = get_user_output_dir()
    version = str(report_version or "").strip().lower()
    paths = [output_dir / "feature_coverage_report.json"]
    if version and version != "v1":
        paths.append(output_dir / f"feature_coverage_report_{version}.json")
    for path in paths:
        path.write_text(json.dumps(sanitize_for_json(dict(payload)), ensure_ascii=False, indent=2), encoding="utf-8")


def build_feature_coverage_report(report_version: str | None = None, output_dir: Path | None = None) -> dict[str, Any]:
    output_dir = output_dir or get_user_output_dir()
    raw, warnings = _build_raw_frame(output_dir)
    if raw.empty:
        return sanitize_for_json(
            {
                "sample_count": 0,
                "date_start": None,
                "date_end": None,
                "groups": [],
                "usable_feature_cols": [],
                "partial_feature_cols": [],
                "not_usable_feature_cols": [],
                "blocking_missing_fields": ["sn_market_history.json"],
                "training_readiness": {
                    "can_train_ohlcv_model": False,
                    "can_train_full_fundamental_model": False,
                    "reason_zh": "未找到真实历史行情，不能训练基础技术模型。",
                },
                "message_zh": "未找到真实 sn_market_history.json，本次只做覆盖率审计，未生成预测或回测。",
                "warnings": warnings,
            }
        )

    result = build_feature_matrix(raw)
    feature_df = result.feature_df
    metadata = _metadata_by_feature(result)
    missing_report = result.missing_feature_report
    usable: list[str] = []
    partial: list[str] = []
    not_usable: list[str] = []
    groups: list[dict[str, Any]] = []

    for group, expected in EXPECTED_FEATURES.items():
        feature_rows: list[dict[str, Any]] = []
        counts = {"available": 0, "partial": 0, "missing": 0}
        for feature in expected:
            series = feature_df[feature] if feature in feature_df.columns else raw[feature] if feature in raw.columns else None
            row = _classify_feature(
                feature,
                group,
                series,
                metadata.get(feature),
                _missing_reason_for(feature, metadata.get(feature), missing_report, raw),
            )
            counts[str(row["availability"])] += 1
            if row["availability"] == "available":
                usable.append(feature)
            elif row["availability"] == "partial":
                partial.append(feature)
            else:
                not_usable.append(feature)
            feature_rows.append(row)
        total = len(expected)
        groups.append(
            {
                "group": group,
                "feature_count": total,
                "available_feature_count": counts["available"],
                "partial_feature_count": counts["partial"],
                "missing_feature_count": counts["missing"],
                "coverage_rate": round(counts["available"] / total, 6) if total else 0.0,
                "features": feature_rows,
            }
        )

    safe_usable = [
        col
        for col in usable
        if (col in feature_df.columns or col in raw.columns) and col not in infer_label_columns([col]) and not col.startswith(LABEL_PREFIXES)
    ]
    blocking_missing_fields = sorted(
        set(
            field
            for field, reason in missing_report.items()
            if reason and field not in {"raw_frame"}
        )
    )
    can_train_ohlcv = (
        len(raw) >= 120
        and all(col in raw.columns and raw[col].notna().mean() >= 0.7 for col in ("open", "high", "low", "close", "volume"))
        and sum(1 for col in safe_usable if col in EXPECTED_FEATURES["technical"] + EXPECTED_FEATURES["mean_reversion"]) >= 10
    )
    full_groups = {"basis", "inventory", "cross_market", "event"}
    can_train_full = can_train_ohlcv and all(
        next(group for group in groups if group["group"] == name)["coverage_rate"] >= 0.7 for name in full_groups
    )
    if can_train_ohlcv and not can_train_full:
        reason = "当前可训练技术面/均值回归模型，但基差、库存、外盘和事件因子仍缺底层数据。"
    elif can_train_full:
        reason = "当前真实数据覆盖率满足完整基本面模型训练前置条件。"
    else:
        reason = "当前真实 OHLCV 覆盖不足，暂不具备基础技术模型训练条件。"

    payload = {
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "sample_count": int(len(raw)),
            "date_start": raw.index.min().isoformat() if len(raw.index) else None,
            "date_end": raw.index.max().isoformat() if len(raw.index) else None,
            "groups": groups,
            "usable_feature_cols": sorted(set(safe_usable)),
            "partial_feature_cols": sorted(set(partial)),
            "not_usable_feature_cols": sorted(set(not_usable)),
            "blocking_missing_fields": blocking_missing_fields,
            "training_readiness": {
                "can_train_ohlcv_model": bool(can_train_ohlcv),
                "can_train_full_fundamental_model": bool(can_train_full),
                "reason_zh": reason,
            },
            "message_zh": "真实因子覆盖率审计完成。本接口不训练模型、不生成预测、不生成回测。",
            "warnings": warnings + result.warnings,
            "data_quality_score": result.data_quality_score,
            "cross_market_diagnostics": raw.attrs.get("cross_market_diagnostics", {}),
        }
    _write_coverage_report(payload, report_version)
    return sanitize_for_json(payload)
