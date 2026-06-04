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
from .feature_coverage_service import _augment_fundamental_features
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
from .feature_store_v5_service import MANAGED_FIELDS, TUSHARE_FIELDS, _build_group_coverage, _field_sources_for, _no_lookahead_pass, _source_quality
from .feature_store_v7_service import WAREHOUSE_POLICY_FEATURES, _append_v7_curated_fields
from .managed_data_proxy_service import managed_fundamentals_schema, managed_proxy_status
from .tushare_feature_engineering_service import COST_FEATURES, POSITIONING_FEATURES, SPARSE_FEATURES, SPARSE_POLICY, build_tushare_v7_feature_frame
from .warehouse_missing_policy_service import build_warehouse_missing_policy


V10_FEATURE_SET = "managed_basis_inventory_lme_ready"


def _output_dir() -> Path:
    return get_user_output_dir()


def _row_count(payload: Any) -> int:
    if isinstance(payload, Mapping):
        rows = payload.get("rows") or payload.get("history") or payload.get("data") or []
        return len(rows) if isinstance(rows, list) else int(payload.get("row_count") or 0)
    if isinstance(payload, list):
        return len(payload)
    return 0


def _tushare_wsr_status(output_dir: Path) -> str:
    status = _read_json(output_dir / "fundamentals" / "tushare_provider_status.json")
    if isinstance(status, Mapping):
        results = status.get("results")
        if isinstance(results, Mapping):
            warehouse = results.get("tushare_warehouse")
            if isinstance(warehouse, Mapping):
                return str(warehouse.get("status") or "missing")
    return "missing"


def _field_sources_for_v10(combined: pd.DataFrame) -> dict[str, str]:
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


def _managed_data_status(managed_row_count: int) -> dict[str, Any]:
    status = dict(managed_proxy_status())
    status["data_file_row_count"] = managed_row_count
    if managed_row_count > 0:
        status["status"] = "success"
        status["success"] = True
        status["row_count"] = managed_row_count
        status["message_zh"] = "已发现真实 managed fundamentals 文件；Feature Store v10 将按字段覆盖情况接入。"
    status["managed_schema"] = managed_fundamentals_schema()
    return status


def _readiness(usable: set[str], *, managed_row_count: int) -> dict[str, Any]:
    schema = managed_fundamentals_schema()
    required = set(schema["required_research_fields"])
    if managed_row_count <= 0:
        return {
            "status": "blocked",
            "ready": False,
            "available_fields": [],
            "missing_fields": sorted(required),
            "group_ready": {group: False for group in schema["groups"]},
            "blocking_reasons": ["managed_proxy_disabled_or_missing"],
            "next_actions_zh": ["配置真实 managed proxy endpoint/token，刷新 shfe warehouse、inventory、spot/basis 和 LME 字段。"],
        }
    available = sorted(required.intersection(usable))
    missing = sorted(required - usable)
    group_ready: dict[str, bool] = {}
    for group, fields in schema["groups"].items():
        numeric_fields = [field for field in fields if field in required]
        group_ready[group] = bool(set(numeric_fields).intersection(usable))
    ready = managed_row_count > 0 and all(group_ready.values())
    return {
        "status": "ready" if ready else "blocked",
        "ready": ready,
        "available_fields": available,
        "missing_fields": missing,
        "group_ready": group_ready,
        "blocking_reasons": [] if ready else ["managed_proxy_disabled_or_missing" if managed_row_count <= 0 else "managed_fundamental_field_coverage_incomplete"],
        "next_actions_zh": [] if ready else ["配置真实 managed proxy endpoint/token，刷新 shfe warehouse、inventory、spot/basis 和 LME 字段。"],
    }


def build_feature_store_v10() -> dict[str, Any]:
    output_dir = _output_dir()
    market, market_diag = _load_market_frame(output_dir)
    manifest_path = _feature_store_manifest_path("v10")
    if market.empty:
        payload = {
            "version": "v10",
            "status": "failed",
            "row_count": 0,
            "message_zh": "未找到真实沪锡历史行情，Feature Store v10 未构建。",
            "sample_data_used": False,
            "baseline_used": False,
            "mock_data_used": False,
            "no_fake_data": True,
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
    _augment_fundamental_features(raw, output_dir)
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
    managed_payload = _read_json(output_dir / "fundamentals" / "managed_fundamentals.json")
    managed_row_count = _row_count(managed_payload)
    field_sources = _field_sources_for_v10(combined)
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
    usable_set = set(usable)
    schema = managed_fundamentals_schema()
    required = set(schema["required_research_fields"])
    missing_managed_fields = sorted(required if managed_row_count <= 0 else required - usable_set)
    managed_fields_present = []
    if managed_row_count > 0:
        managed_fields_present = sorted(
            field
            for field in required
            if field in combined.columns and pd.to_numeric(combined[field], errors="coerce").notna().any()
        )
    readiness = _readiness(usable_set, managed_row_count=managed_row_count)

    store_path = _write_store_frame(combined, "v10")
    manifest = {
        "version": "v10",
        "status": "success",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "row_count": int(len(combined)),
        "date_start": str(combined["trade_date"].min()) if len(combined) else None,
        "date_end": str(combined["trade_date"].max()) if len(combined) else None,
        "feature_store_path": store_path,
        "manifest_path": str(manifest_path),
        "feature_set": V10_FEATURE_SET,
        "field_sources": field_sources,
        "source_quality": source_quality,
        "managed_schema": schema,
        "managed_proxy_status": _managed_data_status(managed_row_count),
        "managed_fundamentals_used": bool(managed_row_count > 0 and managed_fields_present),
        "managed_fundamental_fields": managed_fields_present,
        "missing_managed_fields": missing_managed_fields,
        "feature_store_v10_readiness": readiness,
        "fut_wsr_status": _tushare_wsr_status(output_dir),
        "warehouse_missing_policy": warehouse_policy,
        "warehouse_policy_features": list(WAREHOUSE_POLICY_FEATURES),
        "tushare_diagnostics": v7_diag,
        "cost_features": [field for field in COST_FEATURES if field in combined.columns],
        "positioning_features": [field for field in POSITIONING_FEATURES if field in combined.columns],
        "sparse_features": [field for field in SPARSE_FEATURES if field in combined.columns],
        "sparse_policy": dict(SPARSE_POLICY),
        "usable_fields": usable,
        "excluded_fields": excluded,
        "exclusion_reasons": exclusion_reasons,
        "group_coverage": _build_group_coverage(usable, include_v6_groups=True),
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
        "no_fake_data": True,
        "customer_prediction_generated": False,
        "active_model_written": False,
        "message_zh": "Feature Store v10 已接入 managed 仓单、库存、基差和 LME schema；没有真实字段时只记录 blocked，不伪造数据。",
    }
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(sanitize_for_json(manifest), ensure_ascii=False, indent=2), encoding="utf-8")
    return sanitize_for_json(manifest)
