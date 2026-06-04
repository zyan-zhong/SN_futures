from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping

import numpy as np
import pandas as pd

from ..api.json_utils import sanitize_for_json
from ..features_core.pipeline import build_feature_matrix
from ..labels.leakage_guard import check_feature_label_leakage, infer_label_columns
from ..runtime import get_user_output_dir
from .cross_market_feature_join_service import CROSS_MARKET_VALUE_FIELDS, build_cross_market_feature_frame
from .feature_coverage_service import EXPECTED_FEATURES, _augment_fundamental_features
from .feature_store_service import (
    EVENT_FACTOR_INPUT_FIELDS,
    RAW_MARKET_FIELDS,
    _build_event_frame,
    _build_pipeline_raw_frame,
    _classify_fields,
    _feature_store_manifest_path,
    _load_market_frame,
    _read_json,
    _write_store_frame,
)
from .training_dataset_service import build_training_dataset


V5_FEATURE_SET = "ohlcv_technical_mean_reversion_regime_tushare_managed_cross_market_event"

FUNDAMENTAL_FILES = {
    "tushare_daily": "sn_tushare_daily.json",
    "tushare_warehouse": "sn_tushare_warehouse_receipt.json",
    "tushare_holding": "sn_tushare_holding.json",
    "tushare_settlement": "sn_tushare_settlement.json",
    "managed_proxy": "managed_fundamentals.json",
    "alpha_cross_market": "sn_cross_market.json",
    "news_events": "../events/event_factor_inputs.json",
}

MANAGED_FIELDS = {
    "spot_price",
    "spot_premium",
    "spot_futures_basis",
    "basis_zscore_60",
    "basis_mom_5",
    "basis_mom_20",
    "shfe_inventory",
    "shfe_inventory_delta_1w",
    "shfe_inventory_delta_4w",
    "shfe_warehouse_receipt",
    "lme_tin_close",
    "lme_tin_return_1d",
    "lme_tin_return_3d",
    "lme_shfe_spread",
    "lme_inventory",
    "lme_inventory_delta_1w",
    "near_contract_close",
    "far_contract_close",
    "near_far_spread",
    "term_structure_slope",
    "roll_yield_proxy",
    "near_open_interest",
    "far_open_interest",
    "open_interest_roll_ratio",
    "main_contract_switch_flag",
}

TUSHARE_DAILY_FIELDS = {
    "open_interest",
    "settlement",
}

TUSHARE_WSR_FIELDS = {
    "warehouse_receipt",
    "warehouse_receipt_delta",
    "warehouse_receipt_delta_1w",
}

TUSHARE_SETTLE_FIELDS = {
    "trading_fee_rate",
    "trading_fee",
    "long_margin_rate",
    "short_margin_rate",
    "offset_today_fee",
}

TUSHARE_HOLDING_FIELDS = {
    "long_position",
    "short_position",
    "long_change",
    "short_change",
    "member_net_position",
}

TUSHARE_FIELDS = TUSHARE_DAILY_FIELDS | TUSHARE_WSR_FIELDS | TUSHARE_SETTLE_FIELDS | TUSHARE_HOLDING_FIELDS


def _output_dir() -> Path:
    return get_user_output_dir()


def _source_payload_path(output_dir: Path, filename: str) -> Path:
    if filename.startswith("../"):
        return (output_dir / "fundamentals" / filename).resolve()
    return output_dir / "fundamentals" / filename


def _row_count(payload: Any) -> int:
    if isinstance(payload, Mapping):
        rows = payload.get("rows") or payload.get("inputs") or payload.get("history") or payload.get("points") or []
        return len(rows) if isinstance(rows, list) else int(payload.get("row_count") or 0)
    if isinstance(payload, list):
        return len(payload)
    return 0


def _source_quality(output_dir: Path) -> tuple[dict[str, dict[str, Any]], bool, bool]:
    quality: dict[str, dict[str, Any]] = {}
    mock_data_used = False
    sample_data_used = False
    for name, filename in FUNDAMENTAL_FILES.items():
        path = _source_payload_path(output_dir, filename)
        payload = _read_json(path)
        row_count = _row_count(payload)
        source_mock = bool(isinstance(payload, Mapping) and payload.get("mock_data_used"))
        source_sample = bool(isinstance(payload, Mapping) and (payload.get("sample") or payload.get("sample_data_used")))
        mock_data_used = mock_data_used or source_mock
        sample_data_used = sample_data_used or source_sample
        quality[name] = {
            "path": str(path),
            "exists": payload is not None,
            "row_count": row_count,
            "status": "mock_data" if source_mock else "sample_data" if source_sample else "available" if row_count else "missing_or_empty",
            "mock_data_used": source_mock,
            "sample_data_used": source_sample,
        }
    return quality, mock_data_used, sample_data_used


def _build_group_coverage(usable_fields: list[str], *, include_v6_groups: bool = False) -> dict[str, dict[str, Any]]:
    usable = set(usable_fields)
    expected: dict[str, tuple[str, ...]] = dict(EXPECTED_FEATURES)
    if include_v6_groups:
        expected["warehouse"] = tuple(sorted(TUSHARE_WSR_FIELDS))
        expected["cost_risk"] = tuple(sorted(TUSHARE_SETTLE_FIELDS | {"settlement"}))
        expected["positioning"] = tuple(sorted(TUSHARE_HOLDING_FIELDS))
    out: dict[str, dict[str, Any]] = {}
    for group, fields in expected.items():
        present = sorted(field for field in fields if field in usable)
        out[group] = {
            "feature_count": len(fields),
            "usable_count": len(present),
            "coverage_rate": round(float(len(present) / len(fields)), 6) if fields else 0.0,
            "usable_fields": present,
        }
    return out


def _tushare_probe_metadata(output_dir: Path) -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
    payload = _read_json(output_dir / "fundamentals" / "tushare_param_probe_report.json")
    results = payload.get("results") if isinstance(payload, Mapping) and isinstance(payload.get("results"), Mapping) else {}
    selected: dict[str, Any] = {}
    failed: list[dict[str, Any]] = []
    for api_name, item in results.items():
        if not isinstance(item, Mapping):
            continue
        selected[str(api_name)] = item.get("selected_params") or {}
        if not item.get("success"):
            failed.append(
                {
                    "api_name": str(api_name),
                    "status": item.get("status") or "unknown",
                    "row_count": int(item.get("row_count") or 0),
                    "error_message_zh": item.get("error_message_zh") or "",
                }
            )
    return dict(results), selected, failed


def _field_sources_for(combined: pd.DataFrame) -> dict[str, str]:
    sources: dict[str, str] = {}
    for field in RAW_MARKET_FIELDS:
        if field in combined.columns:
            sources[field] = "sn_market_history.json"
    for field in TUSHARE_FIELDS:
        if field in combined.columns:
            sources[field] = "tushare"
    for field in MANAGED_FIELDS:
        if field in combined.columns:
            sources[field] = "managed_proxy"
    for field in CROSS_MARKET_VALUE_FIELDS:
        if field in combined.columns:
            sources[field] = "alpha_cross_market"
    for field in EVENT_FACTOR_INPUT_FIELDS:
        if field in combined.columns:
            sources[field] = "event_factor_inputs.json"
    for field in combined.columns:
        sources.setdefault(str(field), "features_core.pipeline")
    return sources


def _no_lookahead_pass(combined: pd.DataFrame) -> bool:
    if "trade_date" not in combined.columns:
        return False
    if "_event_data_status" not in combined.columns:
        return True

    event_cols = [field for field in EVENT_FACTOR_INPUT_FIELDS if field in combined.columns]
    if not event_cols:
        return True

    # Event inputs are exact-date signals. Rows without news data must stay zero.
    mask = combined["_event_data_status"].astype(str) == "missing_news_data"
    return not bool((combined.loc[mask, event_cols].fillna(0.0).abs().sum(axis=1) > 0).any())


def _build_feature_store_tushare(version: str = "v5") -> dict[str, Any]:
    output_dir = _output_dir()
    market, market_diag = _load_market_frame(output_dir)
    manifest_path = _feature_store_manifest_path(version)
    if market.empty:
        payload = {
            "version": version,
            "status": "failed",
            "row_count": 0,
            "message_zh": "未找到真实沪锡历史行情，Feature Store v5 未构建。",
            "sample_data_used": False,
            "baseline_used": False,
            "mock_data_used": False,
            "no_lookahead_pass": False,
            "market_diagnostics": market_diag,
        }
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        manifest_path.write_text(json.dumps(sanitize_for_json(payload), ensure_ascii=False, indent=2), encoding="utf-8")
        return sanitize_for_json(payload)

    market_index = pd.DatetimeIndex(market.index).normalize()
    raw = market.set_index(market_index).copy()
    raw["trade_date"] = market_index.strftime("%Y-%m-%d")
    _augment_fundamental_features(raw, output_dir)

    cross_frame, cross_diag = build_cross_market_feature_frame(raw, output_dir=output_dir)
    if cross_frame.empty:
        cross_frame = pd.DataFrame(index=market_index)
    event_frame, event_diag = _build_event_frame(market_index, output_dir)
    for column in cross_frame.columns:
        raw[column] = cross_frame[column]
    for column in event_frame.columns:
        raw[column] = event_frame[column]

    pipeline_raw = _build_pipeline_raw_frame(raw)
    feature_result = build_feature_matrix(pipeline_raw)
    combined = pd.concat([feature_result.feature_df, raw], axis=1)
    combined = combined.loc[:, ~combined.columns.duplicated(keep="last")]
    combined["trade_date"] = market_index.strftime("%Y-%m-%d")
    combined = combined.replace([np.inf, -np.inf], np.nan).reset_index(drop=True)

    source_quality, mock_data_used, sample_data_used = _source_quality(output_dir)
    field_sources = _field_sources_for(combined)
    usable, excluded, exclusion_reasons = _classify_fields(
        combined,
        field_sources=field_sources,
        event_status=str(event_diag.get("status") or ""),
    )
    label_cols = infer_label_columns(list(combined.columns))
    forbidden = [field for field in usable if field in label_cols or str(field).startswith(("ret_", "direction_", "tb_"))]
    leakage = check_feature_label_leakage(usable, label_cols)
    no_lookahead = _no_lookahead_pass(combined)
    leakage_check_pass = bool(leakage.get("ok") and not forbidden and no_lookahead)
    group_coverage = _build_group_coverage(usable, include_v6_groups=version.lower() == "v6")
    tushare_fields = sorted(field for field in usable if field in TUSHARE_FIELDS)
    tushare_quality = {
        name: payload
        for name, payload in source_quality.items()
        if str(name).startswith("tushare_") and isinstance(payload, Mapping)
    }
    tushare_used = bool(tushare_fields and any(int((payload or {}).get("row_count") or 0) > 0 for payload in tushare_quality.values()))
    _, selected_params, failed_subinterfaces = _tushare_probe_metadata(output_dir)

    store_path = _write_store_frame(combined, version)
    wsr_used = bool(source_quality.get("tushare_warehouse", {}).get("row_count") and set(tushare_fields).intersection(TUSHARE_WSR_FIELDS))
    settle_used = bool(source_quality.get("tushare_settlement", {}).get("row_count") and set(tushare_fields).intersection(TUSHARE_SETTLE_FIELDS | {"settlement"}))
    holding_used = bool(source_quality.get("tushare_holding", {}).get("row_count") and set(tushare_fields).intersection(TUSHARE_HOLDING_FIELDS))
    manifest = {
        "version": version,
        "status": "success",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "row_count": int(len(combined)),
        "date_range": {
            "start": str(combined["trade_date"].min()) if len(combined) else None,
            "end": str(combined["trade_date"].max()) if len(combined) else None,
        },
        "date_start": str(combined["trade_date"].min()) if len(combined) else None,
        "date_end": str(combined["trade_date"].max()) if len(combined) else None,
        "feature_store_path": store_path,
        "manifest_path": str(manifest_path),
        "field_sources": field_sources,
        "source_quality": source_quality,
        "tushare_used": tushare_used,
        "tushare_fields": tushare_fields,
        "tushare_wsr_used": wsr_used,
        "tushare_settle_used": settle_used,
        "tushare_holding_used": holding_used,
        "selected_params": selected_params,
        "failed_subinterfaces": failed_subinterfaces,
        "usable_fields": usable,
        "excluded_fields": excluded,
        "exclusion_reasons": exclusion_reasons,
        "group_coverage": group_coverage,
        "cross_market_diagnostics": cross_diag,
        "event_factor_diagnostics": event_diag,
        "market_diagnostics": market_diag,
        "feature_pipeline_warnings": feature_result.warnings,
        "feature_pipeline_missing": feature_result.missing_feature_report,
        "no_lookahead_pass": bool(no_lookahead),
        "leakage_check_pass": leakage_check_pass,
        "leakage_check_details": {
            "feature_label_leakage": leakage,
            "forbidden_feature_leaks": forbidden,
            "event_exact_date_join": bool(no_lookahead),
        },
        "mock_data_used": bool(mock_data_used),
        "sample_data_used": bool(sample_data_used),
        "baseline_used": False,
        "customer_prediction_generated": False,
        "active_model_written": False,
        "message_zh": "Feature Store v5 已构建；本步骤不训练模型、不生成客户预测、不发布 active。",
    }
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(sanitize_for_json(manifest), ensure_ascii=False, indent=2), encoding="utf-8")
    return sanitize_for_json(manifest)


def build_feature_store_v5() -> dict[str, Any]:
    return _build_feature_store_tushare("v5")


def build_feature_store_v6() -> dict[str, Any]:
    return _build_feature_store_tushare("v6")


def build_training_dataset_v5(
    *,
    horizons: tuple[int, ...] = (1, 3, 5, 10, 20),
    min_feature_coverage: float = 0.7,
) -> dict[str, Any]:
    feature_manifest = build_feature_store_v5()
    dataset = build_training_dataset(
        horizons=horizons,
        min_feature_coverage=min_feature_coverage,
        dataset_version="v5",
        feature_store_version="v5",
        feature_set=V5_FEATURE_SET,
    )
    dataset["feature_store_version"] = "v5"
    dataset["feature_set"] = V5_FEATURE_SET
    dataset["source_quality"] = feature_manifest.get("source_quality", {})
    dataset["group_coverage"] = feature_manifest.get("group_coverage", {})
    dataset["mock_data_used"] = bool(feature_manifest.get("mock_data_used"))
    dataset["sample_data_used"] = bool(feature_manifest.get("sample_data_used"))
    dataset["baseline_used"] = False
    dataset["customer_prediction_generated"] = False
    dataset["active_model_written"] = False
    manifest_path = _output_dir() / "training_dataset_manifest_v5.json"
    manifest_path.write_text(json.dumps(sanitize_for_json(dataset), ensure_ascii=False, indent=2), encoding="utf-8")
    return sanitize_for_json(dataset)
