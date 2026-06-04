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
from .feature_store_service import (
    EVENT_FACTOR_INPUT_FIELDS,
    RAW_MARKET_FIELDS,
    _build_event_frame,
    _build_pipeline_raw_frame,
    _classify_fields,
    _feature_store_manifest_path,
    _load_market_frame,
    _write_store_frame,
)
from .feature_store_v5_service import MANAGED_FIELDS, TUSHARE_FIELDS, _field_sources_for, _no_lookahead_pass, _source_quality
from .training_dataset_service import build_training_dataset
from .tushare_feature_engineering_service import COST_FEATURES, POSITIONING_FEATURES, SPARSE_FEATURES, SPARSE_POLICY, build_tushare_v7_feature_frame
from .warehouse_missing_policy_service import build_warehouse_missing_policy


V7_FEATURE_SET = "institutional_tushare_cost_positioning"
WAREHOUSE_POLICY_FEATURES = ("inventory_missing_flag", "warehouse_data_quality_score")


def _output_dir() -> Path:
    return get_user_output_dir()


def _field_sources_for_v7(combined: pd.DataFrame) -> dict[str, str]:
    sources = _field_sources_for(combined)
    for field in WAREHOUSE_POLICY_FEATURES:
        if field in combined.columns:
            sources[field] = "warehouse_missing_policy"
    for field in set(COST_FEATURES) | set(POSITIONING_FEATURES):
        if field in combined.columns:
            sources[field] = "tushare_v7_feature_engineering"
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
    return sources


def _append_v7_curated_fields(
    frame: pd.DataFrame,
    usable: list[str],
    excluded: list[str],
    reasons: dict[str, str],
) -> tuple[list[str], list[str], dict[str, str]]:
    usable_set = set(usable)
    excluded_set = set(excluded)
    curated = set(COST_FEATURES) | set(POSITIONING_FEATURES) | set(WAREHOUSE_POLICY_FEATURES)
    for field in curated:
        if field not in frame.columns:
            continue
        numeric = pd.to_numeric(frame[field], errors="coerce")
        non_null = int(numeric.notna().sum())
        non_zero = bool(float(numeric.fillna(0.0).abs().sum()) > 0.0)
        if non_null <= 0:
            excluded_set.add(field)
            reasons[field] = "all_missing"
            continue
        if field in SPARSE_FEATURES or field in WAREHOUSE_POLICY_FEATURES:
            usable_set.add(field)
            excluded_set.discard(field)
            reasons.pop(field, None)
            continue
        if non_zero or field == "member_position_available_flag":
            usable_set.add(field)
            excluded_set.discard(field)
            reasons.pop(field, None)
    return sorted(usable_set), sorted(excluded_set - usable_set), reasons


def _group_coverage(usable_fields: list[str]) -> dict[str, dict[str, Any]]:
    usable = set(usable_fields)
    groups = {
        "cost_risk": tuple(COST_FEATURES),
        "positioning": tuple(POSITIONING_FEATURES),
        "sparse_positioning": tuple(SPARSE_FEATURES),
        "inventory_missing_risk": tuple(WAREHOUSE_POLICY_FEATURES),
    }
    out: dict[str, dict[str, Any]] = {}
    for group, fields in groups.items():
        present = sorted(field for field in fields if field in usable)
        out[group] = {
            "feature_count": len(fields),
            "usable_count": len(present),
            "coverage_rate": round(float(len(present) / len(fields)), 6) if fields else 0.0,
            "usable_fields": present,
        }
    return out


def build_feature_store_v7() -> dict[str, Any]:
    output_dir = _output_dir()
    market, market_diag = _load_market_frame(output_dir)
    manifest_path = _feature_store_manifest_path("v7")
    if market.empty:
        payload = {
            "version": "v7",
            "status": "failed",
            "row_count": 0,
            "message_zh": "未找到真实沪锡历史行情，Feature Store v7 未构建。",
            "sample_data_used": False,
            "baseline_used": False,
            "mock_data_used": False,
            "no_lookahead_pass": False,
            "market_diagnostics": market_diag,
            "customer_prediction_generated": False,
            "active_model_written": False,
        }
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        manifest_path.write_text(json.dumps(sanitize_for_json(payload), ensure_ascii=False, indent=2), encoding="utf-8")
        return sanitize_for_json(payload)

    market_index = pd.DatetimeIndex(market.index).normalize()
    raw = market.set_index(market_index).copy()
    raw["trade_date"] = market_index.strftime("%Y-%m-%d")
    warehouse_policy = build_warehouse_missing_policy(output_dir=output_dir)
    raw["inventory_missing_flag"] = float(warehouse_policy.get("inventory_missing_flag") or 0.0)
    raw["warehouse_data_quality_score"] = float(warehouse_policy.get("warehouse_data_quality_score") or 0.0)

    v7_frame, v7_diag = build_tushare_v7_feature_frame(raw.reset_index(drop=True), output_dir)
    if not v7_frame.empty:
        v7_frame.index = market_index
        for column in v7_frame.columns:
            if column == "trade_date":
                continue
            if column in raw.columns:
                engineered = pd.to_numeric(v7_frame[column], errors="coerce")
                existing = pd.to_numeric(raw[column], errors="coerce")
                raw[column] = engineered.where(engineered.notna(), existing)
            else:
                raw[column] = v7_frame[column]

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
    field_sources = _field_sources_for_v7(combined)
    usable, excluded, exclusion_reasons = _classify_fields(
        combined,
        field_sources=field_sources,
        event_status=str(event_diag.get("status") or ""),
    )
    usable, excluded, exclusion_reasons = _append_v7_curated_fields(combined, usable, excluded, exclusion_reasons)
    label_cols = infer_label_columns(list(combined.columns))
    forbidden = [field for field in usable if field in label_cols or str(field).startswith(("ret_", "direction_", "tb_"))]
    leakage = check_feature_label_leakage(usable, label_cols)
    no_lookahead = _no_lookahead_pass(combined)
    leakage_check_pass = bool(leakage.get("ok") and not forbidden and no_lookahead)

    store_path = _write_store_frame(combined, "v7")
    cost_features = [field for field in COST_FEATURES if field in combined.columns]
    positioning_features = [field for field in POSITIONING_FEATURES if field in combined.columns]
    sparse_features = [field for field in SPARSE_FEATURES if field in combined.columns]
    group_coverage = _group_coverage(usable)
    manifest = {
        "version": "v7",
        "status": "success",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "row_count": int(len(combined)),
        "date_start": str(combined["trade_date"].min()) if len(combined) else None,
        "date_end": str(combined["trade_date"].max()) if len(combined) else None,
        "feature_store_path": store_path,
        "manifest_path": str(manifest_path),
        "feature_set": V7_FEATURE_SET,
        "field_sources": field_sources,
        "source_quality": source_quality,
        "tushare_daily_used": bool(v7_diag.get("daily_used")),
        "tushare_settle_used": bool(v7_diag.get("settle_used")),
        "tushare_holding_used": bool(v7_diag.get("holding_used")),
        "tushare_wsr_used": bool((source_quality.get("tushare_warehouse") or {}).get("row_count")),
        "tushare_diagnostics": v7_diag,
        "warehouse_missing_policy": warehouse_policy,
        "warehouse_policy_features": list(WAREHOUSE_POLICY_FEATURES),
        "cost_features": cost_features,
        "positioning_features": positioning_features,
        "sparse_features": sparse_features,
        "sparse_policy": dict(SPARSE_POLICY),
        "sparse_feature_policy": dict(SPARSE_POLICY),
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
        "message_zh": "Feature Store v7 已构建成本/结算和稀疏会员持仓特征；本步骤不训练模型、不生成客户预测、不发布 active。",
    }
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(sanitize_for_json(manifest), ensure_ascii=False, indent=2), encoding="utf-8")
    return sanitize_for_json(manifest)


def build_training_dataset_v7(
    *,
    horizons: tuple[int, ...] = (1, 3, 5, 10, 20),
    min_feature_coverage: float = 0.0,
) -> dict[str, Any]:
    feature_manifest = build_feature_store_v7()
    dataset = build_training_dataset(
        horizons=horizons,
        min_feature_coverage=min_feature_coverage,
        dataset_version="v7",
        feature_store_version="v7",
        feature_set=V7_FEATURE_SET,
    )
    dataset["feature_store_version"] = "v7"
    dataset["feature_set"] = V7_FEATURE_SET
    dataset["cost_features"] = [field for field in feature_manifest.get("cost_features", []) if field in dataset.get("feature_cols", [])]
    dataset["positioning_features"] = [field for field in feature_manifest.get("positioning_features", []) if field in dataset.get("feature_cols", [])]
    dataset["sparse_features"] = [field for field in feature_manifest.get("sparse_features", []) if field in dataset.get("feature_cols", [])]
    dataset["sparse_policy"] = feature_manifest.get("sparse_policy", {})
    dataset["sparse_feature_policy"] = feature_manifest.get("sparse_feature_policy", {})
    dataset["source_quality"] = feature_manifest.get("source_quality", {})
    dataset["group_coverage"] = feature_manifest.get("group_coverage", {})
    dataset["no_lookahead_pass"] = bool(feature_manifest.get("no_lookahead_pass"))
    dataset["mock_data_used"] = bool(feature_manifest.get("mock_data_used"))
    dataset["sample_data_used"] = bool(feature_manifest.get("sample_data_used"))
    dataset["baseline_used"] = False
    dataset["customer_prediction_generated"] = False
    dataset["active_model_written"] = False
    manifest_path = _output_dir() / "training_dataset_manifest_v7.json"
    dataset["manifest_path"] = str(manifest_path)
    manifest_path.write_text(json.dumps(sanitize_for_json(dataset), ensure_ascii=False, indent=2), encoding="utf-8")
    return sanitize_for_json(dataset)
