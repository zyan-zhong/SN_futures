from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Mapping

import numpy as np
import pandas as pd

from ..api.json_utils import sanitize_for_json
from ..governance.model_registry import ModelRegistry, make_model_record
from ..models.baselines import predict_baseline, train_baseline_models
from ..models.calibration import brier_score, expected_calibration_error, fit_probability_calibrator
from ..models.tree_models import predict_tree_bundle, train_tree_model_bundle
from ..runtime import get_user_output_dir
from .oof_trace_service import build_oof_trace_records, write_oof_trace
from .training_dataset_service import get_training_dataset_status


DEFAULT_HORIZONS = ("1d", "3d", "5d", "10d", "20d")
INTERNAL_COST = 0.0002


def _output_dir() -> Path:
    return get_user_output_dir()


def _normalise_version(version: str | None) -> str:
    value = str(version or "v1").strip().lower()
    return value or "v1"


def _walk_forward_dir(candidate_version: str | None = "v1") -> Path:
    path = _output_dir() / "walk_forward"
    version = _normalise_version(candidate_version)
    if version != "v1":
        path = path / version
    path.mkdir(parents=True, exist_ok=True)
    return path


def _registry_dir() -> Path:
    path = _output_dir() / "model_registry"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _candidate_registry_path(candidate_version: str | None = "v1") -> Path:
    version = _normalise_version(candidate_version)
    if version == "v1":
        return _registry_dir() / "candidate_model_registry.json"
    return _registry_dir() / f"candidate_{version}_model_registry.json"


def _candidate_status_path(candidate_version: str | None = "v1") -> Path:
    version = _normalise_version(candidate_version)
    if version == "v1":
        return _registry_dir() / "candidate_training_status.json"
    return _registry_dir() / f"candidate_{version}_training_status.json"


def _artifact_dir(candidate_version: str | None = "v1") -> Path:
    path = _registry_dir() / "candidate_artifacts"
    version = _normalise_version(candidate_version)
    if version != "v1":
        path = path / version
    path.mkdir(parents=True, exist_ok=True)
    return path


def _read_json(path: Path) -> Any:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(sanitize_for_json(dict(payload)), ensure_ascii=False, indent=2), encoding="utf-8")


def _safe_float(value: Any, default: float | None = None) -> float | None:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return default
    return parsed if np.isfinite(parsed) else default


def _dataset_for_horizon(horizon: str, dataset_version: str = "v1") -> tuple[pd.DataFrame, dict[str, Any]]:
    status = get_training_dataset_status(dataset_version=dataset_version)
    if not status.get("exists"):
        raise FileNotFoundError("训练数据集尚未生成，请先运行 training-dataset/build。")
    if status.get("sample_data_used"):
        raise ValueError("样例数据不能用于 candidate 训练。")
    dataset_paths = status.get("dataset_paths") or {}
    path = Path(str(dataset_paths.get(horizon) or ""))
    if not path.exists():
        raise FileNotFoundError(f"未找到 {horizon} 训练数据集：{path}")
    if path.suffix.lower() == ".parquet":
        frame = pd.read_parquet(path)
    else:
        frame = pd.read_csv(path)
    if frame.empty:
        raise ValueError(f"{horizon} 训练数据集为空。")
    return frame, status


def _feature_cols(manifest: Mapping[str, Any], frame: pd.DataFrame) -> list[str]:
    cols = [str(col) for col in manifest.get("feature_cols", []) if str(col) in frame.columns]
    forbidden = (
        "ret_",
        "direction_",
        "abs_ret_",
        "realized_vol_",
        "max_favorable_excursion_",
        "max_adverse_excursion_",
        "tb_",
        "y_",
    )
    return [col for col in cols if not col.startswith(forbidden)]


def _horizon_days(horizon: str) -> int:
    try:
        return int(str(horizon).lower().replace("d", ""))
    except Exception:
        return 1


def _date_bounds(frame: pd.DataFrame) -> tuple[str, str]:
    if frame.empty:
        return "", ""
    values = pd.to_datetime(frame["label_start_time"], errors="coerce")
    return values.min().isoformat(), values.max().isoformat()


def _make_folds(frame: pd.DataFrame, horizon: str, max_folds: int = 5) -> list[dict[str, Any]]:
    work = frame.copy()
    work["label_start_time"] = pd.to_datetime(work["label_start_time"], errors="coerce")
    work["label_end_time"] = pd.to_datetime(work["label_end_time"], errors="coerce")
    work = work.dropna(subset=["label_start_time", "label_end_time"]).sort_values("label_start_time").reset_index(drop=True)
    n = len(work)
    h = max(1, _horizon_days(horizon))
    min_train = max(80, int(n * 0.45))
    validation_size = max(30, int((n - min_train) / max_folds)) if n > min_train else 0
    if validation_size <= 0:
        return []

    folds: list[dict[str, Any]] = []
    start = min_train
    fold_no = 1
    while start < n and fold_no <= max_folds:
        end = min(n, start + validation_size)
        validation = work.iloc[start:end].copy()
        if validation.empty:
            break
        validation_start = validation["label_start_time"].min()
        validation_end = validation["label_start_time"].max()
        train_candidate = work.iloc[:start].copy()
        overlap_mask = train_candidate["label_end_time"] >= validation_start
        purged_samples = int(overlap_mask.sum())
        train = train_candidate.loc[~overlap_mask].copy()
        embargo_end = min(n, end + h)
        embargo_available_samples = int(max(0, embargo_end - end))
        embargo_samples = max(h, embargo_available_samples)
        if len(train) >= 40 and len(validation) >= 10:
            folds.append(
                {
                    "fold": fold_no,
                    "train_frame": train,
                    "validation_frame": validation,
                    "train_start": train["label_start_time"].min().isoformat(),
                    "train_end": train["label_start_time"].max().isoformat(),
                    "validation_start": validation_start.isoformat(),
                    "validation_end": validation_end.isoformat(),
                    "train_samples": int(len(train)),
                    "validation_samples": int(len(validation)),
                    "purged_samples": purged_samples,
                    "embargo_samples": embargo_samples,
                    "embargo_available_samples": embargo_available_samples,
                    "embargo_days": h,
                }
            )
        start = end + h
        fold_no += 1
    return folds


def _prepare_fold(train: pd.DataFrame, validation: pd.DataFrame, feature_cols: list[str]) -> tuple[pd.DataFrame, pd.DataFrame, list[str]]:
    train_out = train.copy()
    validation_out = validation.copy()
    usable: list[str] = []
    for col in feature_cols:
        if col not in train_out.columns or col not in validation_out.columns:
            continue
        if train_out[col].dtype == "object" or str(train_out[col].dtype).startswith("category"):
            categories = {value: idx for idx, value in enumerate(sorted(train_out[col].dropna().astype(str).unique()))}
            train_values = train_out[col].astype(str).map(categories).fillna(-1.0)
            val_values = validation_out[col].astype(str).map(categories).fillna(-1.0)
        else:
            train_values = pd.to_numeric(train_out[col], errors="coerce")
            val_values = pd.to_numeric(validation_out[col], errors="coerce")
        train_values = train_values.replace([np.inf, -np.inf], np.nan)
        val_values = val_values.replace([np.inf, -np.inf], np.nan)
        median = train_values.median()
        fill_value = float(median) if pd.notna(median) and np.isfinite(float(median)) else 0.0
        train_out[col] = train_values.fillna(fill_value).astype(float)
        validation_out[col] = val_values.fillna(fill_value).astype(float)
        usable.append(col)
    return train_out, validation_out, usable


def _ternary_predictions(prob_up: np.ndarray, expected_return: np.ndarray) -> np.ndarray:
    pred = np.zeros(len(prob_up), dtype=int)
    pred[(prob_up > 0.55) & (expected_return > 0)] = 1
    pred[(prob_up < 0.45) & (expected_return < 0)] = -1
    return pred


def _max_drawdown_proxy(returns: np.ndarray) -> float:
    if returns.size == 0:
        return 0.0
    equity = np.cumsum(returns)
    peak = np.maximum.accumulate(equity)
    return float(np.min(equity - peak))


def _fold_metrics(
    y_direction: pd.Series,
    y_return: pd.Series,
    raw_prob: np.ndarray,
    calibrated_prob: np.ndarray,
    expected_return: np.ndarray,
) -> dict[str, Any]:
    from sklearn.metrics import balanced_accuracy_score, precision_score, recall_score

    y_dir = pd.to_numeric(y_direction, errors="coerce").fillna(0).astype(int).to_numpy()
    y_ret = pd.to_numeric(y_return, errors="coerce").fillna(0.0).to_numpy(dtype=float)
    y_up = (y_dir > 0).astype(int)
    pred_dir = _ternary_predictions(calibrated_prob, expected_return)
    covered = pred_dir != 0
    if covered.any():
        directional_accuracy = float((pred_dir[covered] == y_dir[covered]).mean())
    else:
        directional_accuracy = 0.0
    strategy_returns = np.where(covered, np.sign(pred_dir) * y_ret - INTERNAL_COST, 0.0)
    ic = 0.0
    if len(y_ret) > 2 and float(np.std(expected_return)) > 1e-12 and float(np.std(y_ret)) > 1e-12:
        ic = float(np.corrcoef(expected_return, y_ret)[0, 1])
        if not np.isfinite(ic):
            ic = 0.0
    return {
        "directional_accuracy": directional_accuracy,
        "balanced_accuracy": float(balanced_accuracy_score(y_up, (calibrated_prob > 0.5).astype(int))) if len(np.unique(y_up)) > 1 else 0.0,
        "precision_up": float(precision_score(y_dir, pred_dir, labels=[1], average="macro", zero_division=0)),
        "precision_down": float(precision_score(y_dir, pred_dir, labels=[-1], average="macro", zero_division=0)),
        "recall_up": float(recall_score(y_dir, pred_dir, labels=[1], average="macro", zero_division=0)),
        "recall_down": float(recall_score(y_dir, pred_dir, labels=[-1], average="macro", zero_division=0)),
        "brier_score": brier_score(y_up, calibrated_prob),
        "calibration_error": expected_calibration_error(y_up, calibrated_prob),
        "return_mae": float(np.mean(np.abs(expected_return - y_ret))),
        "return_rmse": float(np.sqrt(np.mean((expected_return - y_ret) ** 2))),
        "information_coefficient": ic,
        "coverage_rate": float(covered.mean()),
        "abstain_rate": float(1.0 - covered.mean()),
        "cost_adjusted_expectancy": float(strategy_returns[covered].mean()) if covered.any() else 0.0,
        "max_drawdown_proxy": _max_drawdown_proxy(strategy_returns),
        "sample_count": int(len(y_dir)),
    }


def _aggregate_metrics(folds: list[dict[str, Any]]) -> dict[str, Any]:
    if not folds:
        return {}
    keys = [
        "directional_accuracy",
        "balanced_accuracy",
        "precision_up",
        "precision_down",
        "recall_up",
        "recall_down",
        "brier_score",
        "calibration_error",
        "return_mae",
        "return_rmse",
        "information_coefficient",
        "coverage_rate",
        "abstain_rate",
        "cost_adjusted_expectancy",
        "max_drawdown_proxy",
    ]
    total_samples = sum(int(fold["metrics"].get("sample_count", 0)) for fold in folds)
    out = {key: 0.0 for key in keys}
    for key in keys:
        weighted = 0.0
        weight_sum = 0
        for fold in folds:
            weight = int(fold["metrics"].get("sample_count", 0))
            value = _safe_float(fold["metrics"].get(key), 0.0) or 0.0
            weighted += value * weight
            weight_sum += weight
        out[key] = float(weighted / max(weight_sum, 1))
    out["fold_count"] = len(folds)
    out["sample_count"] = total_samples
    return out


def _importance_from_train(train: pd.DataFrame, feature_cols: list[str], target_col: str) -> list[dict[str, Any]]:
    target = pd.to_numeric(train[target_col], errors="coerce")
    rows: list[dict[str, Any]] = []
    for col in feature_cols:
        values = pd.to_numeric(train[col], errors="coerce")
        if values.notna().sum() < 5 or target.notna().sum() < 5 or float(values.std() or 0.0) <= 1e-12:
            score = 0.0
        else:
            score = abs(float(values.corr(target)))
            if not np.isfinite(score):
                score = 0.0
        rows.append({"feature": col, "importance": float(score)})
    total = sum(item["importance"] for item in rows)
    if total > 0:
        for item in rows:
            item["importance"] = float(item["importance"] / total)
    return sorted(rows, key=lambda item: item["importance"], reverse=True)


def run_purged_walk_forward(
    horizon: str,
    *,
    dataset_version: str = "v1",
    candidate_version: str = "v1",
    feature_set: str = "",
) -> dict[str, Any]:
    horizon = str(horizon)
    dataset_version = _normalise_version(dataset_version)
    candidate_version = _normalise_version(candidate_version)
    frame, manifest = _dataset_for_horizon(horizon, dataset_version=dataset_version)
    feature_set = feature_set or str(manifest.get("feature_set") or "")
    feature_cols = _feature_cols(manifest, frame)
    direction_col = "y_direction"
    return_col = "y_return"
    folds_raw = _make_folds(frame, horizon)
    fold_results: list[dict[str, Any]] = []
    oof_records: list[dict[str, Any]] = []

    for fold in folds_raw:
        train_raw = fold["train_frame"]
        validation_raw = fold["validation_frame"]
        train, validation, usable_cols = _prepare_fold(train_raw, validation_raw, feature_cols)
        if len(usable_cols) < 3:
            continue
        baseline_pred: dict[str, Any] | None = None
        if candidate_version == "v1":
            baseline = train_baseline_models(
                train,
                usable_cols,
                horizon=horizon,
                direction_col=direction_col,
                return_col=return_col,
            )
            baseline_pred = predict_baseline(baseline, validation)
        candidate = train_tree_model_bundle(
            train,
            validation,
            usable_cols,
            horizon=horizon,
            direction_col=direction_col,
            return_col=return_col,
            feature_set_version=str(manifest.get("data_source_hash", "real_features"))[:16],
        )
        pred = predict_tree_bundle(candidate, validation)
        y_up = (pd.to_numeric(validation[direction_col], errors="coerce").fillna(0).astype(int) > 0).astype(int)
        calibrator = fit_probability_calibrator(pred["prob_up"], y_up, method="sigmoid")
        calibrated = calibrator.transform(pred["prob_up"])
        metrics = _fold_metrics(validation[direction_col], validation[return_col], pred["prob_up"], calibrated, pred["expected_return"])
        oof_records.extend(
            build_oof_trace_records(
                horizon=horizon,
                fold_id=fold["fold"],
                validation=validation_raw,
                raw_prob_up=pred["prob_up"],
                calibrated_prob_up=calibrated,
                expected_return=pred["expected_return"],
                model_family=str(candidate.backend),
                model_id=str(candidate.model_id),
                calibration_method=str(calibrator.method),
                cost_assumption=INTERNAL_COST,
                data_quality_score=_safe_float(manifest.get("data_quality_score"), None),
                feature_coverage_score=_safe_float(manifest.get("feature_coverage_score"), None),
                candidate_version=candidate_version,
                dataset_version=dataset_version,
                feature_set=feature_set,
            )
        )
        row = {
            **{key: value for key, value in fold.items() if not key.endswith("_frame")},
            "candidate_model_id": candidate.model_id,
            "candidate_backend": candidate.backend,
            "candidate_version": candidate_version,
            "dataset_version": dataset_version,
            "feature_set": feature_set,
            "calibration_method": calibrator.method,
            "metrics": metrics,
            "feature_importance": candidate.feature_importance[:20],
        }
        if baseline_pred is not None:
            row["internal_baseline_metrics"] = _fold_metrics(
                validation[direction_col],
                validation[return_col],
                np.asarray(baseline_pred["prob_up"], dtype=float),
                np.asarray(baseline_pred["prob_up"], dtype=float),
                np.asarray(baseline_pred["expected_return"], dtype=float),
            )
        fold_results.append(row)

    metrics = _aggregate_metrics(fold_results)
    feature_importance = _importance_from_train(frame, feature_cols, return_col)[:30]
    oof_summary = write_oof_trace(oof_records, horizon=horizon, candidate_version=candidate_version) if oof_records else {}
    result = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "candidate_version": candidate_version,
        "dataset_version": dataset_version,
        "feature_set": feature_set,
        "horizon": horizon,
        "status": "success" if fold_results else "failed",
        "message_zh": "purged walk-forward 已完成；结果仅用于 candidate 研究验证，不生成客户预测。",
        "folds": fold_results,
        "metrics": metrics,
        "feature_importance": feature_importance,
        "oof_trace": oof_summary,
        "candidate_is_active": False,
        "customer_prediction_generated": False,
        "baseline_scope": "none" if candidate_version != "v1" else "internal_contrast_only",
        "baseline_used": False,
        "dataset_manifest_hash": manifest.get("data_source_hash", ""),
    }
    path = _walk_forward_dir(candidate_version) / f"wf_{horizon}.json"
    _write_json(path, result)
    result["path"] = str(path)
    return sanitize_for_json(result)


def run_candidate_training(
    horizons: Iterable[str] = DEFAULT_HORIZONS,
    *,
    candidate_version: str = "v1",
    dataset_version: str = "v1",
    feature_set: str = "",
    label_variants: Iterable[str] | None = None,
    models: Iterable[str] | None = None,
    calibration: Iterable[str] | None = None,
    no_trade_filters: Iterable[str] | None = None,
) -> dict[str, Any]:
    candidate_version = _normalise_version(candidate_version)
    dataset_version = _normalise_version(dataset_version)
    registry = ModelRegistry(_candidate_registry_path(candidate_version))
    results: dict[str, Any] = {}
    records: list[dict[str, Any]] = []
    for horizon in horizons:
        h = str(horizon)
        wf = run_purged_walk_forward(h, dataset_version=dataset_version, candidate_version=candidate_version, feature_set=feature_set)
        frame, manifest = _dataset_for_horizon(h, dataset_version=dataset_version)
        feature_set = feature_set or str(manifest.get("feature_set") or "")
        feature_cols = _feature_cols(manifest, frame)
        artifact_payload = {
            "horizon": h,
            "candidate_version": candidate_version,
            "dataset_version": dataset_version,
            "feature_set": feature_set,
            "label_variants": list(label_variants or []),
            "models": list(models or []),
            "calibration": list(calibration or []),
            "no_trade_filters": list(no_trade_filters or []),
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "metrics": wf.get("metrics", {}),
            "feature_importance": wf.get("feature_importance", []),
            "oof_trace": wf.get("oof_trace", {}),
            "status": "candidate_only",
            "note_zh": "该 artifact 只记录候选模型验证结果，不是 active 模型，不用于客户预测。",
        }
        seed = json.dumps({"candidate_version": candidate_version, "dataset_version": dataset_version, "horizon": h, "metrics": wf.get("metrics", {}), "feature_cols": feature_cols}, sort_keys=True, default=str)
        model_id = f"candidate_{candidate_version}_" + hashlib.sha1(seed.encode("utf-8")).hexdigest()[:16]
        artifact_path = _artifact_dir(candidate_version) / f"{model_id}.json"
        _write_json(artifact_path, artifact_payload)
        train_start, train_end = _date_bounds(frame)
        record = make_model_record(
            model_id=model_id,
            horizon=h,
            metrics=dict(wf.get("metrics") or {}),
            status="candidate",
            model_type="hist_gradient_boosting_candidate",
            feature_set_version=str(manifest.get("data_source_hash", "real_features"))[:16],
            label_version=f"forward_return_triple_barrier_{h}",
            artifact_path=str(artifact_path),
            train_period={"start": train_start, "end": train_end},
            validation_period={"method": "purged_walk_forward", "fold_count": str(wf.get("metrics", {}).get("fold_count", 0))},
            test_period={"status": "not_promoted_no_customer_prediction"},
            data_quality_snapshot={
                "sample_data_used": False,
                "baseline_used": False,
                "training_dataset_status": manifest.get("status"),
                "dataset_version": dataset_version,
                "candidate_version": candidate_version,
            },
            feature_columns=feature_cols,
            label_columns=[f"direction_{h}", f"ret_{h}", f"tb_label_{h}"],
        )
        registry.register_candidate(record)
        row = record.to_dict()
        row["walk_forward_path"] = wf.get("path")
        row["oof_trace_path"] = (wf.get("oof_trace") or {}).get("path") if isinstance(wf.get("oof_trace"), Mapping) else None
        row["feature_importance"] = wf.get("feature_importance", [])
        records.append(sanitize_for_json(row))
        results[h] = wf

    status = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "candidate_version": candidate_version,
        "dataset_version": dataset_version,
        "feature_set": feature_set,
        "label_variants": list(label_variants or []),
        "models": list(models or []),
        "calibration": list(calibration or []),
        "no_trade_filters": list(no_trade_filters or []),
        "status": "success",
        "message_zh": "candidate 训练与 purged walk-forward 已完成；未发布 active，未生成客户预测。",
        "candidate_is_active": False,
        "active_updated": False,
        "customer_prediction_generated": False,
        "baseline_scope": "none" if candidate_version != "v1" else "internal_contrast_only",
        "baseline_used": False,
        "registry_path": str(_candidate_registry_path(candidate_version)),
        "records": records,
        "metrics_by_horizon": {key: value.get("metrics", {}) for key, value in results.items()},
        "walk_forward_paths": {key: value.get("path") for key, value in results.items()},
        "oof_trace_paths": {
            key: (value.get("oof_trace") or {}).get("path") if isinstance(value.get("oof_trace"), Mapping) else None
            for key, value in results.items()
        },
    }
    _write_json(_candidate_status_path(candidate_version), status)
    return sanitize_for_json(status)


def get_candidate_training_status(candidate_version: str = "v1") -> dict[str, Any]:
    candidate_version = _normalise_version(candidate_version)
    payload = _read_json(_candidate_status_path(candidate_version))
    registry = ModelRegistry(_candidate_registry_path(candidate_version))
    records = [record.to_dict() for record in registry.list_candidates()]
    if not isinstance(payload, Mapping):
        return sanitize_for_json(
            {
                "status": "not_run",
                "message_zh": "candidate 训练尚未运行。",
                "candidate_is_active": False,
                "active_updated": False,
                "customer_prediction_generated": False,
                "candidate_version": candidate_version,
                "registry_path": str(_candidate_registry_path(candidate_version)),
                "records": records,
            }
        )
    out = dict(payload)
    out["candidate_version"] = candidate_version
    out["records"] = records or out.get("records", [])
    out["candidate_is_active"] = False
    out["active_updated"] = False
    out["customer_prediction_generated"] = False
    return sanitize_for_json(out)


def get_walk_forward_results(horizon: str | None = None, candidate_version: str = "v1") -> dict[str, Any]:
    candidate_version = _normalise_version(candidate_version)
    horizons = [str(horizon)] if horizon else list(DEFAULT_HORIZONS)
    rows: dict[str, Any] = {}
    for h in horizons:
        path = _walk_forward_dir(candidate_version) / f"wf_{h}.json"
        rows[h] = _read_json(path) or {
            "horizon": h,
            "candidate_version": candidate_version,
            "status": "not_run",
            "message_zh": "该周期 purged walk-forward 尚未运行。",
            "path": str(path),
        }
    return sanitize_for_json(
        {
            "status": "success",
            "results": rows,
            "message_zh": "walk-forward 结果仅用于 candidate 研究验证，不直接生成客户预测。",
        }
    )
