from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Mapping

import numpy as np
import pandas as pd

from ..api.json_utils import sanitize_for_json
from ..features_core.pipeline import build_feature_matrix
from ..labels.leakage_guard import check_feature_label_leakage, infer_label_columns
from ..runtime import get_user_output_dir
from .cross_market_feature_join_service import (
    CROSS_MARKET_VALUE_FIELDS,
    MAX_FORWARD_FILL_TRADING_DAYS,
    build_cross_market_feature_frame,
)


RAW_MARKET_FIELDS = ("open", "high", "low", "close", "volume", "open_interest")
EVENT_FACTOR_INPUT_FIELDS = (
    "news_count",
    "used_in_model_count",
    "supply_shock_score",
    "demand_shock_score",
    "inventory_shock_score",
    "macro_risk_score",
    "exchange_event_score",
    "event_recency_decay_score",
    "max_relevance_score",
    "avg_relevance_score",
)
EVENT_PIPELINE_SCORE_FIELDS = (
    "news_event_score",
    "supply_event_score",
    "demand_event_score",
    "inventory_event_score",
    "macro_event_score",
)
FORBIDDEN_FEATURE_PREFIXES = (
    "ret_",
    "direction_",
    "abs_ret_",
    "realized_vol_",
    "max_favorable_excursion_",
    "max_adverse_excursion_",
    "tb_",
)


def _output_dir() -> Path:
    return get_user_output_dir()


def _normalise_version(version: str | None) -> str:
    value = str(version or "v3").strip().lower()
    return value or "v3"


def _feature_store_dir(version: str | None = "v3") -> Path:
    path = _output_dir() / "feature_store" / _normalise_version(version)
    path.mkdir(parents=True, exist_ok=True)
    return path


def _feature_store_csv_path(version: str | None = "v3") -> Path:
    return _feature_store_dir(version) / "feature_store.csv"


def _feature_store_manifest_path(version: str | None = "v3") -> Path:
    return _feature_store_dir(version) / "feature_store_manifest.json"


def _read_json(path: Path) -> Any:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _rows_from_payload(payload: Any) -> list[Mapping[str, Any]]:
    if isinstance(payload, Mapping):
        if payload.get("sample") or payload.get("sample_mode"):
            return []
        rows = payload.get("history") or payload.get("points") or payload.get("rows") or payload.get("data") or []
    elif isinstance(payload, list):
        rows = payload
    else:
        rows = []
    return [row for row in rows if isinstance(row, Mapping) and not row.get("sample")]


def _load_market_frame(output_dir: Path) -> tuple[pd.DataFrame, dict[str, Any]]:
    path = output_dir / "sn_market_history.json"
    payload = _read_json(path)
    rows = _rows_from_payload(payload)
    if not rows:
        return pd.DataFrame(), {"path": str(path), "status": "missing_or_empty"}
    frame = pd.DataFrame(rows)
    rename = {
        "date": "trade_date",
        "time": "trade_date",
        "timestamp": "trade_date",
        "日期": "trade_date",
        "开盘": "open",
        "最高": "high",
        "最低": "low",
        "收盘": "close",
        "收盘价": "close",
        "成交量": "volume",
        "持仓量": "open_interest",
    }
    frame = frame.rename(columns={key: value for key, value in rename.items() if key in frame.columns})
    if "trade_date" not in frame.columns:
        return pd.DataFrame(), {"path": str(path), "status": "missing_trade_date"}
    date_values = frame["trade_date"]
    if isinstance(date_values, pd.DataFrame):
        date_values = date_values.bfill(axis=1).iloc[:, 0]
        frame = frame.loc[:, ~frame.columns.duplicated(keep="last")]
        frame["trade_date"] = date_values
    parsed = pd.to_datetime(date_values, errors="coerce")
    frame.index = pd.DatetimeIndex(parsed).normalize()
    frame = frame[~frame.index.isna()].sort_index()
    frame = frame[~frame.index.duplicated(keep="last")]
    for column in RAW_MARKET_FIELDS:
        if column in frame.columns:
            frame[column] = pd.to_numeric(frame[column], errors="coerce")
        else:
            frame[column] = np.nan
    frame = frame[pd.to_numeric(frame["close"], errors="coerce") > 0]
    frame["trade_date"] = frame.index.strftime("%Y-%m-%d")
    return frame[list(dict.fromkeys(["trade_date", *RAW_MARKET_FIELDS]))], {
        "path": str(path),
        "status": "success",
        "row_count": int(len(frame)),
    }


def _event_input_rows(payload: Any) -> tuple[list[Mapping[str, Any]], str]:
    if not isinstance(payload, Mapping):
        return [], "missing_news_data"
    rows = payload.get("inputs") or payload.get("events") or []
    if not isinstance(rows, list):
        return [], "missing_news_data"
    usable = [
        row
        for row in rows
        if isinstance(row, Mapping)
        and not row.get("sample")
        and row.get("used_in_model", True) is not False
    ]
    if not usable:
        return [], "no_used_in_model_event_inputs"
    return usable, ""


def _build_event_frame(market_index: pd.DatetimeIndex, output_dir: Path) -> tuple[pd.DataFrame, dict[str, Any]]:
    path = output_dir / "events" / "event_factor_inputs.json"
    payload = _read_json(path)
    rows, empty_reason = _event_input_rows(payload)
    event = pd.DataFrame(index=market_index)
    event["_event_data_status"] = "missing_news_data" if empty_reason == "missing_news_data" else "true_zero_event"
    for column in EVENT_FACTOR_INPUT_FIELDS:
        event[column] = 0.0
    if empty_reason:
        return event, {
            "path": str(path),
            "status": empty_reason,
            "row_count": 0,
            "used_in_model_count": 0,
            "message_zh": "暂无可进入模型的新闻事件输入；Feature Store 不会伪造事件因子。",
        }

    data = pd.DataFrame(rows)
    date_col = "trade_date" if "trade_date" in data.columns else "date" if "date" in data.columns else None
    if date_col is None:
        return event, {
            "path": str(path),
            "status": "missing_trade_date",
            "row_count": 0,
            "used_in_model_count": 0,
        }
    data.index = pd.DatetimeIndex(pd.to_datetime(data[date_col], errors="coerce")).normalize()
    data = data[~data.index.isna()].sort_index()
    data = data[~data.index.duplicated(keep="last")]
    observed_count = 0
    for day, row in data.iterrows():
        if day not in event.index:
            continue
        observed_count += 1
        event.loc[day, "_event_data_status"] = "event_observed"
        for column in EVENT_FACTOR_INPUT_FIELDS:
            if column in row:
                event.loc[day, column] = float(pd.to_numeric(pd.Series([row.get(column)]), errors="coerce").iloc[0] or 0.0)
    return event, {
        "path": str(path),
        "status": "success",
        "row_count": int(len(data)),
        "aligned_event_count": int(observed_count),
        "used_in_model_count": int(payload.get("used_in_model_count") or len(rows)) if isinstance(payload, Mapping) else int(len(rows)),
        "message_zh": "事件因子按沪锡交易日精确对齐；无事件日期填 0，并标记 true_zero_event。",
    }


def _build_pipeline_raw_frame(store_base: pd.DataFrame) -> pd.DataFrame:
    raw = store_base.copy()
    raw.index = pd.DatetimeIndex(pd.to_datetime(raw["trade_date"], errors="coerce")).normalize()
    raw["news_event_score"] = pd.to_numeric(raw.get("max_relevance_score", 0.0), errors="coerce").fillna(0.0)
    raw["supply_event_score"] = pd.to_numeric(raw.get("supply_shock_score", 0.0), errors="coerce").fillna(0.0)
    raw["demand_event_score"] = pd.to_numeric(raw.get("demand_shock_score", 0.0), errors="coerce").fillna(0.0)
    raw["inventory_event_score"] = pd.to_numeric(raw.get("inventory_shock_score", 0.0), errors="coerce").fillna(0.0)
    raw["macro_event_score"] = pd.to_numeric(raw.get("macro_risk_score", 0.0), errors="coerce").fillna(0.0)
    return raw


def _field_is_forbidden(field: str) -> bool:
    return bool(field in infer_label_columns([field]) or field.startswith(FORBIDDEN_FEATURE_PREFIXES))


def _classify_fields(
    frame: pd.DataFrame,
    *,
    field_sources: Mapping[str, str],
    event_status: str,
    min_coverage: float = 0.7,
) -> tuple[list[str], list[str], dict[str, str]]:
    usable: list[str] = []
    excluded: list[str] = []
    reasons: dict[str, str] = {}
    for field in frame.columns:
        if field in {"trade_date", "_cross_market_stale", "_event_data_status"}:
            continue
        if _field_is_forbidden(str(field)):
            excluded.append(str(field))
            reasons[str(field)] = "label_or_future_return_field"
            continue
        series = frame[field]
        numeric = pd.to_numeric(series, errors="coerce")
        if numeric.notna().sum() <= 0:
            excluded.append(str(field))
            reasons[str(field)] = "all_missing"
            continue
        non_null_rate = float(numeric.notna().mean())
        all_zero = bool(float(numeric.fillna(0.0).abs().sum()) == 0.0)
        if field in EVENT_FACTOR_INPUT_FIELDS and all_zero:
            excluded.append(str(field))
            reasons[str(field)] = event_status if event_status in {"missing_news_data", "no_used_in_model_event_inputs"} else "all_zero_true_zero_event"
            continue
        if all_zero and field not in RAW_MARKET_FIELDS and field != "main_contract_switch_flag":
            excluded.append(str(field))
            reasons[str(field)] = "all_zero_no_real_signal"
            continue
        if non_null_rate < min_coverage:
            excluded.append(str(field))
            reasons[str(field)] = f"insufficient_non_null_rate:{non_null_rate:.3f}"
            continue
        source = field_sources.get(str(field), "")
        if source == "cross_market" and "_cross_market_stale" in frame.columns:
            valid_non_stale = numeric.where(~frame["_cross_market_stale"].astype(bool)).notna().mean()
            if float(valid_non_stale) < min_coverage:
                excluded.append(str(field))
                reasons[str(field)] = f"stale_after_alignment:{valid_non_stale:.3f}"
                continue
        usable.append(str(field))
    return sorted(set(usable)), sorted(set(excluded)), reasons


def _write_store_frame(frame: pd.DataFrame, version: str) -> str:
    path = _feature_store_csv_path(version)
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, index=False, encoding="utf-8-sig")
    return str(path)


def _read_manifest(version: str | None = "v3") -> dict[str, Any] | None:
    path = _feature_store_manifest_path(version)
    payload = _read_json(path)
    return dict(payload) if isinstance(payload, Mapping) else None


def build_feature_store(version: str = "v3") -> dict[str, Any]:
    version = _normalise_version(version)
    output_dir = _output_dir()
    market, market_diag = _load_market_frame(output_dir)
    manifest_path = _feature_store_manifest_path(version)
    if market.empty:
        payload = {
            "version": version,
            "status": "failed",
            "message_zh": "未找到真实沪锡历史行情，Feature Store v3 未构建。",
            "row_count": 0,
            "feature_store_path": str(_feature_store_csv_path(version)),
            "manifest_path": str(manifest_path),
            "sample_data_used": False,
            "baseline_used": False,
            "leakage_check_pass": False,
            "market_diagnostics": market_diag,
        }
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        manifest_path.write_text(json.dumps(sanitize_for_json(payload), ensure_ascii=False, indent=2), encoding="utf-8")
        return sanitize_for_json(payload)

    market_index = pd.DatetimeIndex(market.index).normalize()
    cross_frame, cross_diag = build_cross_market_feature_frame(market.set_index(market_index), output_dir=output_dir)
    if cross_frame.empty:
        cross_frame = pd.DataFrame(index=market_index)
    event_frame, event_diag = _build_event_frame(market_index, output_dir)

    store = market.set_index(market_index).copy()
    store["trade_date"] = market_index.strftime("%Y-%m-%d")
    for column in cross_frame.columns:
        store[column] = cross_frame[column]
    for column in event_frame.columns:
        store[column] = event_frame[column]

    pipeline_raw = _build_pipeline_raw_frame(store)
    feature_result = build_feature_matrix(pipeline_raw)
    feature_frame = feature_result.feature_df.copy()
    # Keep exact-date event inputs and aligned cross-market values authoritative
    # when feature builders emit same-named derived columns.
    combined = pd.concat([feature_frame, store], axis=1)
    combined = combined.loc[:, ~combined.columns.duplicated(keep="last")]
    combined["trade_date"] = market_index.strftime("%Y-%m-%d")
    combined = combined.reset_index(drop=True)

    field_sources: dict[str, str] = {}
    for field in RAW_MARKET_FIELDS:
        field_sources[field] = "sn_market_history.json"
    for field in CROSS_MARKET_VALUE_FIELDS:
        if field in combined.columns:
            field_sources[field] = "cross_market"
    for field in EVENT_FACTOR_INPUT_FIELDS:
        if field in combined.columns:
            field_sources[field] = "event_factor_inputs.json"
    for field in feature_frame.columns:
        field_sources.setdefault(str(field), "features_core.pipeline")

    event_status = str(event_diag.get("status") or "")
    usable, excluded, exclusion_reasons = _classify_fields(combined, field_sources=field_sources, event_status=event_status)
    label_cols = infer_label_columns(list(combined.columns))
    leakage = check_feature_label_leakage(usable, label_cols)
    leakage_check_pass = bool(leakage.get("ok") and not [field for field in usable if _field_is_forbidden(field)])

    store_path = _write_store_frame(combined, version)
    manifest = {
        "version": version,
        "status": "success",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "row_count": int(len(combined)),
        "date_start": str(combined["trade_date"].min()) if len(combined) else None,
        "date_end": str(combined["trade_date"].max()) if len(combined) else None,
        "feature_store_path": store_path,
        "manifest_path": str(manifest_path),
        "field_sources": field_sources,
        "alignment_rules": {
            "primary_index": "sn_market_history.trade_date",
            "cross_market": "date join with backward-looking forward-fill only",
            "event_factor_inputs": "exact trade_date join; no forward/back fill",
        },
        "forward_fill_rules": {
            "cross_market": {"method": "last_observation_carried_forward", "max_trading_days": MAX_FORWARD_FILL_TRADING_DAYS},
            "event_factor_inputs": {"method": "none", "no_event_fill": 0},
        },
        "stale_rules": {
            "cross_market": "forward-fill older than 5 trading days is marked stale and excluded from usable coverage",
            "event_factor_inputs": "missing file is missing_news_data; zero on valid non-event days is true_zero_event",
        },
        "usable_fields": usable,
        "excluded_fields": excluded,
        "exclusion_reasons": exclusion_reasons,
        "cross_market_diagnostics": cross_diag,
        "event_factor_diagnostics": event_diag,
        "market_diagnostics": market_diag,
        "feature_pipeline_warnings": feature_result.warnings,
        "feature_pipeline_missing": feature_result.missing_feature_report,
        "leakage_check_pass": leakage_check_pass,
        "leakage_check_details": leakage,
        "sample_data_used": False,
        "baseline_used": False,
        "customer_prediction_generated": False,
        "active_model_written": False,
        "message_zh": "Feature Store v3 已构建；本步骤不训练模型、不生成预测、不发布 active。",
    }
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(sanitize_for_json(manifest), ensure_ascii=False, indent=2), encoding="utf-8")
    return sanitize_for_json(manifest)


def get_feature_store_status(version: str = "v3") -> dict[str, Any]:
    version = _normalise_version(version)
    manifest = _read_manifest(version)
    manifest_path = _feature_store_manifest_path(version)
    store_path = _feature_store_csv_path(version)
    if not manifest:
        return sanitize_for_json(
            {
                "version": version,
                "status": "not_built",
                "exists": False,
                "feature_store_path": str(store_path),
                "manifest_path": str(manifest_path),
                "sample_data_used": False,
                "baseline_used": False,
                "message_zh": "Feature Store 尚未构建。",
            }
        )
    payload = dict(manifest)
    payload["exists"] = bool(store_path.exists())
    payload["feature_store_path"] = str(store_path)
    payload["manifest_path"] = str(manifest_path)
    return sanitize_for_json(payload)


def load_feature_store(version: str = "v3") -> tuple[pd.DataFrame, dict[str, Any]]:
    version = _normalise_version(version)
    manifest = _read_manifest(version)
    path = _feature_store_csv_path(version)
    if not manifest or not path.exists():
        manifest = build_feature_store(version)
    path = Path(str((manifest or {}).get("feature_store_path") or _feature_store_csv_path(version)))
    if not path.exists():
        return pd.DataFrame(), dict(manifest or {})
    frame = pd.read_csv(path)
    if "trade_date" in frame.columns:
        frame.index = pd.DatetimeIndex(pd.to_datetime(frame["trade_date"], errors="coerce")).normalize()
        frame = frame[~frame.index.isna()].sort_index()
    return frame, dict(manifest or {})
