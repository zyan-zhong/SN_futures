from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Mapping

import numpy as np
import pandas as pd

from ..api.json_utils import sanitize_for_json
from ..features_core.pipeline import build_feature_matrix
from ..labels.forward_return import add_forward_return_labels, forward_label_columns
from ..labels.leakage_guard import LABEL_PREFIXES, check_feature_label_leakage, infer_label_columns
from ..labels.triple_barrier import add_triple_barrier_labels
from ..runtime import get_user_output_dir
from .feature_coverage_service import _build_raw_frame, build_feature_coverage_report
from .feature_store_service import build_feature_store, load_feature_store


DEFAULT_HORIZONS = (1, 3, 5, 10, 20)
FORBIDDEN_FEATURE_PATTERNS = (
    "ret_",
    "direction_",
    "abs_ret_",
    "realized_vol_",
    "max_favorable_excursion_",
    "max_adverse_excursion_",
    "tb_",
)
V2_CROSS_MARKET_INPUT_COLS = (
    "usd_cny",
    "usd_cny_return",
    "us10y",
    "us10y_change",
    "copper_global_proxy",
    "copper_global_proxy_return",
    "copper_proxy_return",
    "global_risk_sentiment_proxy",
)
V2_EVENT_INPUT_COLS = (
    "news_event_score",
    "supply_event_score",
    "demand_event_score",
    "inventory_event_score",
    "macro_event_score",
    "event_shock_score",
    "news_count_1d",
    "news_count_7d",
    "supply_shock_score",
    "demand_shock_score",
    "inventory_shock_score",
    "macro_risk_score",
    "event_recency_decay_score",
    "event_vol_regime_shift",
)
V3_EVENT_INPUT_COLS = (
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
    *V2_EVENT_INPUT_COLS,
)


def _output_dir() -> Path:
    return get_user_output_dir()


def _normalise_version(version: str | None) -> str:
    value = str(version or "v1").strip().lower()
    return value or "v1"


def _dataset_dir(dataset_version: str | None = "v1") -> Path:
    path = _output_dir() / "training_datasets"
    version = _normalise_version(dataset_version)
    if version != "v1":
        path = path / version
    path.mkdir(parents=True, exist_ok=True)
    return path


def _manifest_path(dataset_version: str | None = "v1") -> Path:
    version = _normalise_version(dataset_version)
    if version == "v1":
        return _output_dir() / "training_dataset_manifest.json"
    return _output_dir() / f"training_dataset_manifest_{version}.json"


def _read_json(path: Path) -> Any:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _hash_file(path: Path) -> str:
    if not path.exists():
        return ""
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _safe_feature_cols(feature_df: pd.DataFrame, usable_cols: Iterable[str], min_feature_coverage: float) -> list[str]:
    candidates = [col for col in usable_cols if col in feature_df.columns]
    forbidden = set(infer_label_columns(candidates))
    safe: list[str] = []
    for col in candidates:
        if col in forbidden or str(col).startswith(FORBIDDEN_FEATURE_PATTERNS):
            continue
        non_null_rate = float(feature_df[col].notna().mean()) if len(feature_df) else 0.0
        if non_null_rate >= float(min_feature_coverage):
            safe.append(str(col))
    return sorted(set(safe))


def _usable_existing_cols(frame: pd.DataFrame, columns: Iterable[str], min_feature_coverage: float) -> list[str]:
    selected: list[str] = []
    for col in columns:
        if col not in frame.columns or str(col).startswith(FORBIDDEN_FEATURE_PATTERNS):
            continue
        series = pd.to_numeric(frame[col], errors="coerce")
        non_null_rate = float(series.notna().mean()) if len(series) else 0.0
        if non_null_rate >= float(min_feature_coverage):
            selected.append(str(col))
    return sorted(set(selected))


def _label_end_times(index: pd.Index, horizon: int) -> pd.Series:
    values = pd.Series(index, index=index).shift(-int(horizon))
    return pd.to_datetime(values, errors="coerce")


def _add_research_tb_labels(frame: pd.DataFrame, horizon: int) -> pd.DataFrame:
    tb_input = frame.copy()
    labelled = add_triple_barrier_labels(tb_input, horizon=int(horizon), conservative=True)
    suffix = f"{int(horizon)}d"
    return pd.DataFrame(
        {
            f"tb_label_{suffix}": labelled["tb_label"],
            f"tb_hit_time_{suffix}": labelled["tb_hit_time"],
            f"tb_hit_price_{suffix}": labelled["tb_hit_price"],
            f"tb_horizon_{suffix}": labelled["tb_horizon"],
            f"tb_upper_{suffix}": labelled["tb_upper"],
            f"tb_lower_{suffix}": labelled["tb_lower"],
        },
        index=frame.index,
    )


def _write_dataset(frame: pd.DataFrame, path_stem: Path) -> tuple[str, str]:
    parquet_path = path_stem.with_suffix(".parquet")
    csv_path = path_stem.with_suffix(".csv")
    try:
        frame.to_parquet(parquet_path, index=False)
        return str(parquet_path), "parquet"
    except Exception:
        frame.to_csv(csv_path, index=False, encoding="utf-8-sig")
        return str(csv_path), "csv"


def _distribution(series: pd.Series) -> dict[str, int]:
    counts = series.value_counts(dropna=False).to_dict()
    return {str(key): int(value) for key, value in counts.items()}


def _return_summary(series: pd.Series) -> dict[str, float | None]:
    numeric = pd.to_numeric(series, errors="coerce").dropna()
    if numeric.empty:
        return {"mean": None, "std": None, "min": None, "max": None}
    return {
        "mean": float(numeric.mean()),
        "std": float(numeric.std()),
        "min": float(numeric.min()),
        "max": float(numeric.max()),
    }


def _event_factor_input_count(output_dir: Path) -> int:
    payload = _read_json(output_dir / "events" / "event_factor_inputs.json")
    if isinstance(payload, Mapping):
        events = payload.get("inputs") or payload.get("events") or []
        return len([item for item in events if isinstance(item, Mapping) and item.get("used_in_model", True) is not False])
    return 0


def _build_training_dataset_from_feature_store(
    *,
    horizons: Iterable[int],
    min_feature_coverage: float,
    dataset_version: str,
    feature_store_version: str,
    feature_set: str,
) -> dict[str, Any]:
    out = _output_dir()
    frame, feature_store_manifest = load_feature_store(feature_store_version)
    if frame.empty or "close" not in frame.columns:
        feature_store_manifest = build_feature_store(feature_store_version)
        frame, feature_store_manifest = load_feature_store(feature_store_version)
    if frame.empty or "close" not in frame.columns:
        manifest = {
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "dataset_version": dataset_version,
            "feature_store_version": feature_store_version,
            "feature_set": feature_set,
            "status": "failed",
            "message_zh": "Feature Store v3 不存在或缺少真实 close 字段，未构建训练数据。",
            "sample_data_used": False,
            "baseline_used": False,
        }
        _manifest_path(dataset_version).write_text(json.dumps(sanitize_for_json(manifest), ensure_ascii=False, indent=2), encoding="utf-8")
        return sanitize_for_json(manifest)

    if "trade_date" in frame.columns:
        frame.index = pd.DatetimeIndex(pd.to_datetime(frame["trade_date"], errors="coerce")).normalize()
        frame = frame[~frame.index.isna()].sort_index()
    usable_fields = list(feature_store_manifest.get("usable_fields") or [])
    feature_cols = _safe_feature_cols(frame, usable_fields, min_feature_coverage)
    if not feature_cols:
        raise ValueError("Feature Store v3 没有满足覆盖率和泄漏检查的真实特征列，未构建训练数据。")

    label_base = frame.copy()
    labelled = add_forward_return_labels(label_base, horizons=horizons)
    label_cols = forward_label_columns(horizons)
    removed_label_cols = sorted(set(infer_label_columns(list(frame.columns) + label_cols)))
    leakage = check_feature_label_leakage(feature_cols, label_cols)
    forbidden_leaks = [col for col in feature_cols if str(col).startswith(FORBIDDEN_FEATURE_PATTERNS)]
    leakage_check_pass = bool(leakage["ok"] and not forbidden_leaks)

    dataset_outputs: dict[str, dict[str, Any]] = {}
    sample_count_by_horizon: dict[str, int] = {}
    label_distribution_by_horizon: dict[str, dict[str, int]] = {}
    return_summary_by_horizon: dict[str, dict[str, float | None]] = {}
    dataset_paths: dict[str, str] = {}

    combined = pd.concat([frame[feature_cols], labelled[label_cols]], axis=1)
    for horizon in horizons:
        h = int(horizon)
        suffix = f"{h}d"
        ret_col = f"ret_{suffix}"
        direction_col = f"direction_{suffix}"
        label_end = _label_end_times(combined.index, h)
        tb_source = frame.copy()
        tb = _add_research_tb_labels(tb_source, h)
        dataset = pd.concat([combined[feature_cols + [ret_col, direction_col]], tb], axis=1)
        dataset["y_direction"] = dataset[direction_col]
        dataset["y_return"] = dataset[ret_col]
        dataset["label_start_time"] = dataset.index.astype(str)
        dataset["label_end_time"] = label_end.astype(str)
        dataset["horizon"] = suffix
        dataset = dataset.dropna(subset=["y_direction", "y_return", "label_end_time"])
        dataset = dataset[dataset["label_end_time"].astype(str).str.lower() != "nat"]
        path, fmt = _write_dataset(dataset.reset_index(drop=True), _dataset_dir(dataset_version) / f"train_{suffix}")
        sample_count_by_horizon[suffix] = int(len(dataset))
        label_distribution_by_horizon[suffix] = _distribution(dataset["y_direction"])
        return_summary_by_horizon[suffix] = _return_summary(dataset["y_return"])
        dataset_paths[suffix] = path
        dataset_outputs[suffix] = {
            "path": path,
            "format": fmt,
            "sample_count": int(len(dataset)),
            "label_start": str(dataset["label_start_time"].min()) if not dataset.empty else "",
            "label_end": str(dataset["label_end_time"].max()) if not dataset.empty else "",
        }

    cross_market_inputs = set(V2_CROSS_MARKET_INPUT_COLS)
    event_inputs = set(V3_EVENT_INPUT_COLS)
    cross_market_cols = sorted(col for col in feature_cols if col in cross_market_inputs)
    event_cols = sorted(col for col in feature_cols if col in event_inputs)
    feature_store_exclusions = dict(feature_store_manifest.get("exclusion_reasons") or {})
    missing_rate_by_feature = {col: round(float(frame[col].isna().mean()), 6) for col in feature_cols if col in frame.columns}
    manifest = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "dataset_version": dataset_version,
        "feature_store_version": feature_store_version,
        "feature_set": feature_set,
        "status": "success",
        "message_zh": "训练数据 v3 已基于 Feature Store 构建。本步骤未训练模型、未生成预测、未发布 active。",
        "manifest_path": str(_manifest_path(dataset_version)),
        "horizons": [int(h) for h in horizons],
        "feature_cols": feature_cols,
        "label_cols": label_cols + [f"tb_label_{int(h)}d" for h in horizons],
        "removed_label_cols": removed_label_cols,
        "forbidden_feature_patterns": list(FORBIDDEN_FEATURE_PATTERNS),
        "leakage_check_pass": leakage_check_pass,
        "leakage_check_details": {
            "feature_label_leakage": leakage,
            "forbidden_feature_leaks": forbidden_leaks,
            "label_columns_removed_from_features": removed_label_cols,
        },
        "sample_data_used": False,
        "baseline_used": False,
        "sample_count_by_horizon": sample_count_by_horizon,
        "feature_count": len(feature_cols),
        "date_start": frame.index.min().isoformat(),
        "date_end": frame.index.max().isoformat(),
        "missing_rate_by_feature": missing_rate_by_feature,
        "label_distribution_by_horizon": label_distribution_by_horizon,
        "return_summary_by_horizon": return_summary_by_horizon,
        "data_source_hash": _hash_file(Path(str(feature_store_manifest.get("feature_store_path") or ""))),
        "feature_store_path": str(feature_store_manifest.get("feature_store_path") or ""),
        "feature_store_manifest_path": str(feature_store_manifest.get("manifest_path") or ""),
        "dataset_paths": dataset_paths,
        "dataset_outputs": dataset_outputs,
        "cross_market_feature_cols": cross_market_cols,
        "cross_market_excluded_reason": "" if cross_market_cols else "no_usable_feature_store_cross_market_fields",
        "event_feature_cols": event_cols,
        "event_excluded_reason": "" if event_cols else "no_usable_feature_store_event_fields",
        "feature_store_exclusion_reasons": feature_store_exclusions,
        "customer_prediction_generated": False,
        "active_model_written": False,
        "warnings": [],
    }
    payload = sanitize_for_json(manifest)
    _manifest_path(dataset_version).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload


def build_training_dataset(
    horizons: Iterable[int] = DEFAULT_HORIZONS,
    min_feature_coverage: float = 0.7,
    dataset_version: str = "v1",
    feature_set: str = "ohlcv_technical_regime",
    feature_store_version: str | None = None,
) -> dict[str, Any]:
    dataset_version = _normalise_version(dataset_version)
    if feature_store_version or dataset_version == "v3":
        return _build_training_dataset_from_feature_store(
            horizons=horizons,
            min_feature_coverage=min_feature_coverage,
            dataset_version=dataset_version,
            feature_store_version=feature_store_version or "v3",
            feature_set=feature_set,
        )
    out = _output_dir()
    history_path = out / "sn_market_history.json"
    history_payload = _read_json(history_path)
    if isinstance(history_payload, Mapping) and (history_payload.get("sample") or history_payload.get("sample_mode")):
        raise ValueError("sample data 不能用于构建训练数据集。")

    raw, warnings = _build_raw_frame(out)
    if raw.empty:
        manifest = {
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "dataset_version": dataset_version,
            "feature_set": feature_set,
            "status": "failed",
            "message_zh": "未找到真实历史行情，未构建训练数据集。",
            "sample_data_used": False,
            "baseline_used": False,
            "warnings": warnings,
        }
        _manifest_path(dataset_version).write_text(json.dumps(sanitize_for_json(manifest), ensure_ascii=False, indent=2), encoding="utf-8")
        return sanitize_for_json(manifest)

    coverage = build_feature_coverage_report(report_version=dataset_version)
    feature_result = build_feature_matrix(raw)
    feature_df = feature_result.feature_df
    feature_cols = _safe_feature_cols(feature_df, coverage.get("usable_feature_cols", []), min_feature_coverage)
    cross_market_cols = _usable_existing_cols(raw, V2_CROSS_MARKET_INPUT_COLS, min_feature_coverage)
    event_cols = _usable_existing_cols(raw, V2_EVENT_INPUT_COLS, min_feature_coverage)
    event_factor_input_count = _event_factor_input_count(out)
    if dataset_version != "v1" and event_factor_input_count <= 0:
        event_cols = []
    if dataset_version != "v1" or "cross_market" in feature_set or "event" in feature_set:
        feature_cols = sorted(set(feature_cols + cross_market_cols + event_cols))
    if dataset_version != "v1" and event_factor_input_count <= 0:
        feature_cols = [col for col in feature_cols if col not in set(V2_EVENT_INPUT_COLS)]
    feature_frame = pd.concat([feature_df, raw[cross_market_cols + event_cols]], axis=1)
    feature_frame = feature_frame.loc[:, ~feature_frame.columns.duplicated()]
    if not feature_cols:
        raise ValueError("没有满足覆盖率阈值的真实特征列，未构建训练数据集。")

    labelled = add_forward_return_labels(raw, horizons=horizons)
    label_cols = forward_label_columns(horizons)
    removed_label_cols = sorted(set(infer_label_columns(list(feature_df.columns) + label_cols)))
    leakage = check_feature_label_leakage(feature_cols, label_cols)
    forbidden_leaks = [col for col in feature_cols if str(col).startswith(FORBIDDEN_FEATURE_PATTERNS)]
    leakage_check_pass = bool(leakage["ok"] and not forbidden_leaks)

    dataset_outputs: dict[str, dict[str, Any]] = {}
    sample_count_by_horizon: dict[str, int] = {}
    label_distribution_by_horizon: dict[str, dict[str, int]] = {}
    return_summary_by_horizon: dict[str, dict[str, float | None]] = {}
    dataset_paths: dict[str, str] = {}

    combined = pd.concat([feature_frame[feature_cols], labelled[label_cols]], axis=1)
    for horizon in horizons:
        h = int(horizon)
        suffix = f"{h}d"
        ret_col = f"ret_{suffix}"
        direction_col = f"direction_{suffix}"
        label_end = _label_end_times(combined.index, h)
        tb = _add_research_tb_labels(pd.concat([raw, feature_df[["atr_14"]] if "atr_14" in feature_df.columns else pd.DataFrame(index=raw.index)], axis=1), h)

        dataset = pd.concat([combined[feature_cols + [ret_col, direction_col]], tb], axis=1)
        dataset["y_direction"] = dataset[direction_col]
        dataset["y_return"] = dataset[ret_col]
        dataset["label_start_time"] = dataset.index.astype(str)
        dataset["label_end_time"] = label_end.astype(str)
        dataset["horizon"] = suffix
        dataset = dataset.dropna(subset=["y_direction", "y_return", "label_end_time"])
        dataset = dataset[dataset["label_end_time"].astype(str).str.lower() != "nat"]

        path, fmt = _write_dataset(dataset.reset_index(drop=True), _dataset_dir(dataset_version) / f"train_{suffix}")
        sample_count_by_horizon[suffix] = int(len(dataset))
        label_distribution_by_horizon[suffix] = _distribution(dataset["y_direction"])
        return_summary_by_horizon[suffix] = _return_summary(dataset["y_return"])
        dataset_paths[suffix] = path
        dataset_outputs[suffix] = {
            "path": path,
            "format": fmt,
            "sample_count": int(len(dataset)),
            "label_start": str(dataset["label_start_time"].min()) if not dataset.empty else "",
            "label_end": str(dataset["label_end_time"].max()) if not dataset.empty else "",
        }

    missing_rate_by_feature = {
        col: round(float(feature_frame[col].isna().mean()), 6)
        for col in feature_cols
        if col in feature_frame.columns
    }
    v2_warnings: list[str] = []
    if (dataset_version != "v1" or "cross_market" in feature_set) and not cross_market_cols:
        v2_warnings.append("cross_market 字段当前没有达到覆盖率阈值，未进入 v2 feature_cols。")
    if (dataset_version != "v1" or "event" in feature_set) and not event_cols:
        v2_warnings.append("NewsAPI 高相关新闻事件当前为空或覆盖率不足，event 字段未进入 v2 feature_cols。")
    manifest = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "dataset_version": dataset_version,
        "feature_set": feature_set,
        "status": "success",
        "message_zh": "训练数据集已构建。本步骤未训练模型、未生成预测、未生成回测。",
        "horizons": [int(h) for h in horizons],
        "feature_cols": feature_cols,
        "label_cols": label_cols + [f"tb_label_{int(h)}d" for h in horizons],
        "removed_label_cols": removed_label_cols,
        "forbidden_feature_patterns": list(FORBIDDEN_FEATURE_PATTERNS),
        "leakage_check_pass": leakage_check_pass,
        "leakage_check_details": {
            "feature_label_leakage": leakage,
            "forbidden_feature_leaks": forbidden_leaks,
            "label_columns_removed_from_features": removed_label_cols,
        },
        "sample_data_used": False,
        "baseline_used": False,
        "sample_count_by_horizon": sample_count_by_horizon,
        "feature_count": len(feature_cols),
        "date_start": raw.index.min().isoformat(),
        "date_end": raw.index.max().isoformat(),
        "missing_rate_by_feature": missing_rate_by_feature,
        "label_distribution_by_horizon": label_distribution_by_horizon,
        "return_summary_by_horizon": return_summary_by_horizon,
        "data_source_hash": _hash_file(history_path),
        "dataset_paths": dataset_paths,
        "dataset_outputs": dataset_outputs,
        "cross_market_feature_cols": sorted(
            set(
                col
                for col in feature_cols
                if col in set(V2_CROSS_MARKET_INPUT_COLS)
                or col in {"usd_cny_return", "us10y_change", "global_risk_sentiment_proxy"}
            )
        ),
        "cross_market_excluded_reason": "" if cross_market_cols else "no_usable_aligned_cross_market_fields",
        "event_feature_cols": sorted(set(col for col in feature_cols if col in set(V2_EVENT_INPUT_COLS))),
        "event_excluded_reason": "" if event_cols else "no_used_in_model_event_inputs_or_insufficient_coverage",
        "event_factor_input_count": event_factor_input_count,
        "unavailable_v2_fields": {
            "lme_tin_close": "unavailable",
            "lme_inventory": "unavailable",
            "spot_price": "unavailable",
            "spot_premium": "unavailable",
            "spot_futures_basis": "unavailable",
            "shfe_inventory": "unavailable",
            "shfe_warehouse_receipt": "unavailable",
        },
        "warnings": warnings + feature_result.warnings + v2_warnings,
    }
    payload = sanitize_for_json(manifest)
    _manifest_path(dataset_version).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload


def get_training_dataset_status(dataset_version: str = "v1") -> dict[str, Any]:
    dataset_version = _normalise_version(dataset_version)
    manifest_path = _manifest_path(dataset_version)
    manifest = _read_json(manifest_path)
    if not isinstance(manifest, Mapping):
        return sanitize_for_json(
            {
                "status": "not_built",
                "exists": False,
                "message_zh": "训练数据集尚未生成。",
                "manifest_path": str(manifest_path),
                "sample_data_used": False,
                "baseline_used": False,
            }
        )
    payload = dict(manifest)
    payload["exists"] = True
    payload["manifest_path"] = str(manifest_path)
    return sanitize_for_json(payload)
