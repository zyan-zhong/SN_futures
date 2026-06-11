from __future__ import annotations

import json
import math
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import numpy as np
import pandas as pd

from ..api.json_utils import sanitize_for_json
from ..core.data_safety import DataSafetyViolation, assert_manifest_allowed_for_pipeline
from ..runtime import get_user_output_dir
from .feature_store_service import _feature_store_manifest_path
from .managed_data_proxy_service import MANAGED_REQUIRED_RESEARCH_FIELDS


DATASET_VERSION = "v12"
FEATURE_STORE_VERSION = "v12"
FEATURE_SET = "managed_proxy_pit_training_v12"
DEFAULT_HORIZONS = (1, 3, 5, 10, 20)
REQUIRED_MANAGED_FIELDS = tuple(MANAGED_REQUIRED_RESEARCH_FIELDS)
MANAGED_INTERACTION_FEATURES = (
    "managed_basis_zscore",
    "inventory_zscore",
    "warehouse_receipt_zscore",
    "lme_shfe_inventory_spread",
    "near_far_carry",
    "open_interest_term_spread",
)
REQUIRED_DATASET_FIELDS = (
    "horizon",
    "target_return",
    "target_direction",
    "split",
    "sample_weight",
    "technical_regime_label",
    "managed_regime_label",
    "managed_regime_sample_weight",
    *MANAGED_INTERACTION_FEATURES,
    *REQUIRED_MANAGED_FIELDS,
)
FORBIDDEN_FEATURE_PREFIXES = (
    "target_",
    "label_",
    "future_",
    "ret_",
    "direction_",
    "tb_",
)


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _dataset_dir() -> Path:
    path = get_user_output_dir() / "training_datasets" / DATASET_VERSION
    path.mkdir(parents=True, exist_ok=True)
    return path


def _manifest_path() -> Path:
    return get_user_output_dir() / f"training_dataset_manifest_{DATASET_VERSION}.json"


def _read_json(path: Path) -> Any:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _write_json(path: Path, payload: Mapping[str, Any]) -> dict[str, Any]:
    safe = sanitize_for_json(dict(payload))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(safe, ensure_ascii=False, indent=2), encoding="utf-8")
    return safe


def _to_number(series: pd.Series | Any, default: float = np.nan) -> pd.Series:
    if isinstance(series, pd.Series):
        return pd.to_numeric(series, errors="coerce")
    return pd.Series(dtype="float64").fillna(default)


def _coverage_from_frame(frame: pd.DataFrame, fields: Sequence[str]) -> dict[str, Any]:
    total_rows = int(len(frame))
    by_field: dict[str, dict[str, Any]] = {}
    available = 0
    for field in fields:
        if field not in frame.columns:
            present = 0
        else:
            present = int(frame[field].notna().sum())
        if present:
            available += 1
        by_field[field] = {
            "present": present,
            "missing": max(total_rows - present, 0),
            "coverage": round(present / total_rows, 4) if total_rows else 0.0,
        }
    complete_rows = int(frame[list(fields)].notna().all(axis=1).sum()) if total_rows and all(field in frame.columns for field in fields) else 0
    return {
        "total": len(fields),
        "available": available,
        "missing": max(len(fields) - available, 0),
        "ratio": round(available / len(fields), 4) if fields else 0.0,
        "label": f"{available}/{len(fields)}",
        "row_count": total_rows,
        "complete_rows": complete_rows,
        "complete_ratio": round(complete_rows / total_rows, 4) if total_rows else 0.0,
        "by_field": by_field,
    }


def _manifest_managed_coverage(manifest: Mapping[str, Any]) -> dict[str, Any]:
    coverage = manifest.get("managed_field_coverage")
    if isinstance(coverage, Mapping):
        return dict(coverage)
    return {"total": len(REQUIRED_MANAGED_FIELDS), "available": 0, "missing": len(REQUIRED_MANAGED_FIELDS), "ratio": 0.0, "label": f"0/{len(REQUIRED_MANAGED_FIELDS)}"}


def _coverage_incomplete(coverage: Mapping[str, Any], manifest: Mapping[str, Any]) -> bool:
    missing_fields = manifest.get("missing_fundamental_fields")
    if isinstance(missing_fields, list) and missing_fields:
        return True
    total = int(coverage.get("total") or len(REQUIRED_MANAGED_FIELDS))
    available = int(coverage.get("available") or 0)
    ratio = float(coverage.get("ratio") or 0.0)
    return total <= 0 or available < total or ratio < 1.0


def load_feature_store_v12_manifest() -> dict[str, Any] | None:
    payload = _read_json(_feature_store_manifest_path(FEATURE_STORE_VERSION))
    return dict(payload) if isinstance(payload, Mapping) else None


def load_feature_store_v12_frame(manifest: Mapping[str, Any] | None = None) -> pd.DataFrame:
    manifest = manifest or load_feature_store_v12_manifest() or {}
    raw_path = str(manifest.get("feature_store_path") or "")
    if not raw_path:
        return pd.DataFrame()
    path = Path(raw_path)
    if not path.is_file():
        return pd.DataFrame()
    try:
        return pd.read_csv(path)
    except Exception:
        return pd.DataFrame()


def validate_training_dataset_v12_readiness() -> dict[str, Any]:
    manifest_path = _feature_store_manifest_path(FEATURE_STORE_VERSION)
    manifest = load_feature_store_v12_manifest()
    blocked: list[str] = []
    feature_store_status = "missing"
    feature_store_path = ""
    managed_coverage: dict[str, Any] = _manifest_managed_coverage({})

    if manifest is None:
        blocked.append("feature_store_v12_manifest_missing")
    else:
        feature_store_status = str(manifest.get("status") or "missing")
        feature_store_path = str(manifest.get("feature_store_path") or "")
        managed_coverage = _manifest_managed_coverage(manifest)
        try:
            assert_manifest_allowed_for_pipeline(manifest, pipeline="training")
        except DataSafetyViolation as exc:
            blocked.extend(exc.blocking_reasons)
        if feature_store_status.lower() not in {"ready", "success"}:
            blocked.append("feature_store_v12_blocked")
            blocked.extend(str(item) for item in (manifest.get("blocking_reasons") or []) if item)
        if not feature_store_path or not Path(feature_store_path).is_file():
            blocked.append("feature_store_v12_csv_missing")
        if not bool(manifest.get("no_lookahead_pass")):
            blocked.append("feature_store_v12_no_lookahead_failed")
        if not bool(manifest.get("point_in_time_join_ready")):
            blocked.append("feature_store_v12_pit_join_not_ready")
        if _coverage_incomplete(managed_coverage, manifest):
            blocked.append("managed_field_coverage_incomplete")
        if bool(manifest.get("fake_data_used")):
            blocked.append("feature_store_v12_fake_data_used")
        if bool(manifest.get("mock_data_used")):
            blocked.append("feature_store_v12_mock_data_used")
        if bool(manifest.get("sample_data_used")):
            blocked.append("feature_store_v12_sample_data_used")
        if bool(manifest.get("baseline_used")):
            blocked.append("feature_store_v12_baseline_used")

    return sanitize_for_json(
        {
            "status": "ready" if not blocked else "blocked",
            "dataset_version": DATASET_VERSION,
            "feature_store_version": FEATURE_STORE_VERSION,
            "feature_store_status": feature_store_status,
            "feature_store_manifest_path": str(manifest_path),
            "feature_store_path": feature_store_path,
            "managed_field_coverage": managed_coverage,
            "no_lookahead_pass": bool(manifest.get("no_lookahead_pass")) if isinstance(manifest, Mapping) else False,
            "point_in_time_join_ready": bool(manifest.get("point_in_time_join_ready")) if isinstance(manifest, Mapping) else False,
            "blocked_reasons": sorted(set(blocked)),
            "manifest": manifest or {},
        }
    )


def _rolling_zscore(series: pd.Series, window: int = 20) -> pd.Series:
    numeric = pd.to_numeric(series, errors="coerce")
    mean = numeric.rolling(window=window, min_periods=3).mean()
    std = numeric.rolling(window=window, min_periods=3).std().replace(0.0, np.nan)
    score = (numeric - mean) / std
    return score.replace([np.inf, -np.inf], np.nan).fillna(0.0)


def compute_basis_inventory_interactions(frame: pd.DataFrame) -> pd.DataFrame:
    enriched = frame.copy()
    enriched["managed_basis_zscore"] = _rolling_zscore(enriched.get("spot_futures_basis", pd.Series(index=enriched.index)))
    enriched["inventory_zscore"] = _rolling_zscore(enriched.get("shfe_inventory", pd.Series(index=enriched.index)))
    enriched["warehouse_receipt_zscore"] = _rolling_zscore(enriched.get("shfe_warehouse_receipt", pd.Series(index=enriched.index)))
    enriched["lme_shfe_inventory_spread"] = _to_number(enriched.get("lme_inventory", pd.Series(index=enriched.index))).fillna(0.0) - _to_number(
        enriched.get("shfe_inventory", pd.Series(index=enriched.index))
    ).fillna(0.0)
    near_close = _to_number(enriched.get("near_contract_close", pd.Series(index=enriched.index)))
    far_close = _to_number(enriched.get("far_contract_close", pd.Series(index=enriched.index)))
    enriched["near_far_carry"] = ((far_close - near_close) / near_close.replace(0.0, np.nan)).replace([np.inf, -np.inf], np.nan).fillna(0.0)
    near_oi = _to_number(enriched.get("near_open_interest", pd.Series(index=enriched.index)))
    far_oi = _to_number(enriched.get("far_open_interest", pd.Series(index=enriched.index)))
    denominator = (near_oi.abs() + far_oi.abs()).replace(0.0, np.nan)
    enriched["open_interest_term_spread"] = ((far_oi - near_oi) / denominator).replace([np.inf, -np.inf], np.nan).fillna(0.0)
    return enriched


def _technical_regime_labels(frame: pd.DataFrame) -> pd.Series:
    if "technical_regime_label" in frame.columns:
        labels = frame["technical_regime_label"].fillna("range").astype(str)
        if len(set(labels)) > 1:
            return labels
    if "atr_14" in frame.columns:
        score = _to_number(frame["atr_14"]).fillna(0.0)
    else:
        close = _to_number(frame.get("close", pd.Series(index=frame.index)))
        score = close.pct_change().abs().rolling(10, min_periods=2).mean().fillna(0.0)
    ranks = score.rank(method="first", pct=True)
    labels = pd.Series("range", index=frame.index, dtype="object")
    labels.loc[ranks <= 1.0 / 3.0] = "low_volatility"
    labels.loc[ranks > 2.0 / 3.0] = "high_volatility"
    return labels


def _managed_regime_labels(frame: pd.DataFrame) -> pd.Series:
    score = (
        _to_number(frame.get("managed_basis_zscore", pd.Series(index=frame.index))).fillna(0.0)
        - _to_number(frame.get("inventory_zscore", pd.Series(index=frame.index))).fillna(0.0)
        - _to_number(frame.get("warehouse_receipt_zscore", pd.Series(index=frame.index))).fillna(0.0)
        + _to_number(frame.get("near_far_carry", pd.Series(index=frame.index))).fillna(0.0)
    )
    ranks = score.rank(method="first", pct=True)
    labels = pd.Series("managed_range", index=frame.index, dtype="object")
    labels.loc[ranks <= 1.0 / 3.0] = "managed_loose_inventory"
    labels.loc[ranks > 2.0 / 3.0] = "managed_tight_basis"
    return labels


def compute_managed_regime_features(frame: pd.DataFrame) -> pd.DataFrame:
    enriched = compute_basis_inventory_interactions(frame)
    enriched["technical_regime_label"] = _technical_regime_labels(enriched).values
    enriched["managed_regime_label"] = _managed_regime_labels(enriched).values
    return enriched


def split_train_validation_by_regime_and_time(frame: pd.DataFrame) -> pd.Series:
    labels = frame.get("managed_regime_label")
    if not isinstance(labels, pd.Series):
        return pd.Series("train", index=frame.index, dtype="object")
    split = pd.Series("train", index=frame.index, dtype="object")
    for _, indexes in labels.groupby(labels, sort=False).groups.items():
        ordered = list(indexes)
        if len(ordered) <= 1:
            continue
        validation_count = min(len(ordered) - 1, max(1, math.ceil(len(ordered) * 0.2)))
        split.loc[ordered[-validation_count:]] = "validation"
    return split


def assign_v12_sample_weights(frame: pd.DataFrame) -> pd.DataFrame:
    weighted = frame.copy()
    labels = weighted.get("managed_regime_label", pd.Series("managed_range", index=weighted.index)).astype(str)
    counts = labels.value_counts().to_dict()
    total = max(1, int(len(weighted)))
    raw_weights = {label: total / max(1, int(count)) for label, count in counts.items()}
    managed_weights = labels.map(raw_weights).astype(float)
    mean = float(managed_weights.mean()) if len(managed_weights) else 1.0
    if mean <= 0:
        mean = 1.0
    weighted["managed_regime_sample_weight"] = managed_weights / mean
    weighted["sample_weight"] = weighted["managed_regime_sample_weight"].astype(float)
    sample_mean = float(weighted["sample_weight"].mean()) if len(weighted) else 1.0
    if sample_mean and math.isfinite(sample_mean):
        weighted["sample_weight"] = weighted["sample_weight"] / sample_mean
    return weighted


def validate_v12_dataset_no_lookahead(dataset: pd.DataFrame) -> dict[str, Any]:
    audit_columns = {
        "target_return",
        "target_direction",
        "horizon",
        "split",
        "sample_weight",
        "managed_regime_sample_weight",
        "label_start_time",
        "label_end_time",
    }
    feature_columns = [str(column) for column in dataset.columns if str(column) not in audit_columns]
    forbidden = [column for column in feature_columns if column.startswith(FORBIDDEN_FEATURE_PREFIXES)]
    return {
        "no_lookahead_pass": not forbidden,
        "forbidden_feature_columns": forbidden,
        "label_columns_excluded_from_features": True,
        "point_in_time_join_ready": bool(dataset.get("managed_asof_date", pd.Series(dtype="object")).notna().any())
        if "managed_asof_date" in dataset.columns
        else True,
    }


def _distribution(series: pd.Series) -> dict[str, int]:
    counts = series.value_counts(dropna=False).to_dict()
    return {str(key): int(value) for key, value in counts.items()}


def _nested_distribution(dataset: pd.DataFrame, column: str) -> dict[str, int]:
    if column not in dataset.columns:
        return {}
    return _distribution(dataset[column])


def _sample_weight_summary(dataset: pd.DataFrame) -> dict[str, float | int | None]:
    weights = pd.to_numeric(dataset.get("sample_weight", pd.Series(dtype="float64")), errors="coerce").dropna()
    if weights.empty:
        return {"count": 0, "mean": None, "min": None, "max": None}
    return {"count": int(len(weights)), "mean": float(weights.mean()), "min": float(weights.min()), "max": float(weights.max())}


def _write_parquet(frame: pd.DataFrame, horizon: int) -> str:
    path = _dataset_dir() / f"train_{int(horizon)}d.parquet"
    frame.to_parquet(path, index=False)
    return str(path)


def _horizon_dataset(base: pd.DataFrame, horizon: int) -> pd.DataFrame:
    frame = base.copy().sort_values("trade_date", kind="mergesort").reset_index(drop=True)
    close = _to_number(frame.get("close", pd.Series(index=frame.index)))
    frame["target_return"] = close.shift(-int(horizon)) / close - 1.0
    frame["target_direction"] = (frame["target_return"] > 0).astype(int)
    frame["horizon"] = f"{int(horizon)}d"
    if "trade_date" in frame.columns:
        frame["label_start_time"] = frame["trade_date"]
        frame["label_end_time"] = pd.Series(frame["trade_date"]).shift(-int(horizon))
    frame = frame[frame["target_return"].notna()].copy()
    frame["split"] = split_train_validation_by_regime_and_time(frame).values
    frame = assign_v12_sample_weights(frame)
    keep = list(dict.fromkeys([*REQUIRED_DATASET_FIELDS, "trade_date", "prediction_cutoff_date", "managed_asof_date", "managed_source_timestamp", "managed_ingest_timestamp", "label_start_time", "label_end_time", "close", "open", "high", "low", "volume", "atr_14"]))
    keep = [column for column in keep if column in frame.columns]
    return frame[keep].reset_index(drop=True)


def build_training_dataset_v12_manifest(
    *,
    status: str,
    readiness: Mapping[str, Any],
    dataset_paths: Mapping[str, str] | None = None,
    datasets: Mapping[str, pd.DataFrame] | None = None,
    insufficient_coverage_reasons: Sequence[str] | None = None,
) -> dict[str, Any]:
    dataset_paths = dict(dataset_paths or {})
    datasets = dict(datasets or {})
    blocked_reasons = sorted(set(str(item) for item in readiness.get("blocked_reasons", []) if item))
    manifest_path = _manifest_path()
    horizon_row_counts = {horizon: int(len(dataset)) for horizon, dataset in datasets.items()}
    train_validation_counts = {horizon: _nested_distribution(dataset, "split") for horizon, dataset in datasets.items()}
    technical_regime_counts = {horizon: _nested_distribution(dataset, "technical_regime_label") for horizon, dataset in datasets.items()}
    managed_regime_counts = {horizon: _nested_distribution(dataset, "managed_regime_label") for horizon, dataset in datasets.items()}
    sample_weight_summary = {horizon: _sample_weight_summary(dataset) for horizon, dataset in datasets.items()}
    interaction_frame = pd.concat(list(datasets.values()), ignore_index=True) if datasets else pd.DataFrame()
    interaction_coverage = _coverage_from_frame(interaction_frame, MANAGED_INTERACTION_FEATURES)
    no_lookahead = {"no_lookahead_pass": True, "point_in_time_join_ready": True}
    for dataset in datasets.values():
        check = validate_v12_dataset_no_lookahead(dataset)
        no_lookahead["no_lookahead_pass"] = bool(no_lookahead["no_lookahead_pass"] and check.get("no_lookahead_pass"))
        no_lookahead["point_in_time_join_ready"] = bool(no_lookahead["point_in_time_join_ready"] and check.get("point_in_time_join_ready"))
    success = status == "success"
    payload = {
        "status": status,
        "dataset_version": DATASET_VERSION,
        "feature_store_version": FEATURE_STORE_VERSION,
        "feature_store_status": readiness.get("feature_store_status") or "missing",
        "feature_set": FEATURE_SET,
        "generated_at": _now(),
        "feature_store_manifest_path": readiness.get("feature_store_manifest_path") or str(_feature_store_manifest_path(FEATURE_STORE_VERSION)),
        "feature_store_path": readiness.get("feature_store_path") or "",
        "dataset_paths": dataset_paths if success else {},
        "row_count": int(sum(horizon_row_counts.values())) if success else 0,
        "horizons": [int(str(horizon).replace("d", "")) for horizon in dataset_paths.keys()] if success else list(DEFAULT_HORIZONS),
        "horizon_row_counts": horizon_row_counts if success else {},
        "train_validation_counts": train_validation_counts if success else {},
        "technical_regime_counts": technical_regime_counts if success else {},
        "managed_regime_counts": managed_regime_counts if success else {},
        "managed_field_coverage": readiness.get("managed_field_coverage") or {},
        "managed_interaction_feature_coverage": interaction_coverage if success else {},
        "sample_weight_summary": sample_weight_summary if success else {},
        "no_lookahead_pass": bool(no_lookahead.get("no_lookahead_pass")) if success else bool(readiness.get("no_lookahead_pass")),
        "point_in_time_join_ready": bool(no_lookahead.get("point_in_time_join_ready")) if success else bool(readiness.get("point_in_time_join_ready")),
        "blocked_reasons": [] if success else blocked_reasons,
        "insufficient_coverage_reasons": list(insufficient_coverage_reasons or []),
        "managed_data_used": bool(success),
        "fake_data_used": False,
        "mock_data_used": False,
        "sample_data_used": False,
        "baseline_used": False,
        "training_invoked": False,
        "active_updated": False,
        "active_model_written": False,
        "customer_prediction_generated": False,
        "candidate_v12_allowed": bool(success and no_lookahead.get("no_lookahead_pass") and no_lookahead.get("point_in_time_join_ready")),
        "manifest_path": str(manifest_path),
        "message_zh": "Training Dataset v12 built from Feature Store v12 with PIT managed fundamentals."
        if success
        else "Training Dataset v12 blocked until Feature Store v12, PIT readiness and managed field coverage pass.",
    }
    return _write_json(manifest_path, payload)


def build_training_dataset_v12(*, horizons: Iterable[int] = DEFAULT_HORIZONS) -> dict[str, Any]:
    readiness = validate_training_dataset_v12_readiness()
    if readiness["status"] != "ready":
        return build_training_dataset_v12_manifest(status="blocked", readiness=readiness)

    manifest = load_feature_store_v12_manifest() or {}
    frame = load_feature_store_v12_frame(manifest)
    if frame.empty:
        blocked = dict(readiness)
        blocked["blocked_reasons"] = sorted(set(list(blocked.get("blocked_reasons") or []) + ["feature_store_v12_empty"]))
        return build_training_dataset_v12_manifest(status="blocked", readiness=blocked)

    frame_coverage = _coverage_from_frame(frame, REQUIRED_MANAGED_FIELDS)
    if _coverage_incomplete(frame_coverage, manifest):
        blocked = dict(readiness)
        blocked["managed_field_coverage"] = frame_coverage
        blocked["blocked_reasons"] = sorted(set(list(blocked.get("blocked_reasons") or []) + ["managed_field_coverage_incomplete"]))
        return build_training_dataset_v12_manifest(status="blocked", readiness=blocked)

    enriched = compute_managed_regime_features(frame)
    dataset_paths: dict[str, str] = {}
    datasets: dict[str, pd.DataFrame] = {}
    for horizon in horizons:
        dataset = _horizon_dataset(enriched, int(horizon))
        if dataset.empty or "train" not in set(dataset.get("split", [])) or "validation" not in set(dataset.get("split", [])):
            continue
        key = f"{int(horizon)}d"
        dataset_paths[key] = _write_parquet(dataset, int(horizon))
        datasets[key] = dataset

    missing_horizons = [f"{int(h)}d" for h in horizons if f"{int(h)}d" not in dataset_paths]
    if missing_horizons:
        blocked = dict(readiness)
        blocked["managed_field_coverage"] = frame_coverage
        blocked["blocked_reasons"] = sorted(set(list(blocked.get("blocked_reasons") or []) + ["training_dataset_v12_insufficient_horizon_rows"]))
        return build_training_dataset_v12_manifest(
            status="blocked",
            readiness=blocked,
            insufficient_coverage_reasons=[f"missing_horizon:{horizon}" for horizon in missing_horizons],
        )

    ready = dict(readiness)
    ready["managed_field_coverage"] = frame_coverage
    return build_training_dataset_v12_manifest(status="success", readiness=ready, dataset_paths=dataset_paths, datasets=datasets)


def get_training_dataset_v12_status() -> dict[str, Any]:
    payload = _read_json(_manifest_path())
    if isinstance(payload, Mapping):
        return sanitize_for_json(dict(payload))
    readiness = validate_training_dataset_v12_readiness()
    return sanitize_for_json(
        {
            "status": "not_built",
            "dataset_version": DATASET_VERSION,
            "feature_store_version": FEATURE_STORE_VERSION,
            "feature_store_status": readiness.get("feature_store_status") or "missing",
            "feature_store_manifest_path": readiness.get("feature_store_manifest_path"),
            "dataset_paths": {},
            "managed_field_coverage": readiness.get("managed_field_coverage") or {},
            "managed_interaction_feature_coverage": {},
            "horizon_row_counts": {},
            "train_validation_counts": {},
            "technical_regime_counts": {},
            "managed_regime_counts": {},
            "sample_weight_summary": {},
            "no_lookahead_pass": bool(readiness.get("no_lookahead_pass")),
            "point_in_time_join_ready": bool(readiness.get("point_in_time_join_ready")),
            "blocked_reasons": readiness.get("blocked_reasons") or ["training_dataset_v12_not_built"],
            "candidate_v12_allowed": False,
            "training_invoked": False,
            "active_updated": False,
            "customer_prediction_generated": False,
            "manifest_path": str(_manifest_path()),
        }
    )
