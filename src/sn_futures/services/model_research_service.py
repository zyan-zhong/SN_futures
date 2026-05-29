from __future__ import annotations

import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping

import numpy as np
import pandas as pd

from ..api.json_utils import sanitize_for_json
from ..runtime import get_user_output_dir
from .feature_stability_service import build_feature_stability_report
from .label_variants import add_label_variants
from .oof_trace_service import build_oof_trace_records, get_research_oof_trace_summary, write_oof_trace
from .selective_threshold_optimizer import build_calibration_bins, optimize_selective_thresholds
from .training_dataset_service import get_training_dataset_status
from .walk_forward_training_service import _feature_cols, _make_folds, _prepare_fold


DEFAULT_HORIZONS = ("1d", "3d", "5d", "10d", "20d")
DEFAULT_MODEL_FAMILIES = (
    "lightgbm_gbdt",
    "lightgbm_random_forest",
    "sklearn_hist_gradient",
    "extra_trees",
    "random_forest",
    "elasticnet",
    "huber",
)
INTERNAL_COST = 0.0002


def _research_root() -> Path:
    path = get_user_output_dir() / "model_research" / "experiments"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(sanitize_for_json(dict(payload)), ensure_ascii=False, indent=2), encoding="utf-8")


def _read_json(path: Path) -> Any:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _new_experiment_dir() -> tuple[str, Path]:
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    for _ in range(10):
        experiment_id = f"research-{stamp}-{uuid.uuid4().hex[:8]}"
        path = _research_root() / experiment_id
        if not path.exists():
            path.mkdir(parents=True, exist_ok=False)
            return experiment_id, path
    raise RuntimeError("无法创建唯一研究实验目录。")


def _load_dataset(path: str) -> pd.DataFrame:
    dataset_path = Path(path)
    if dataset_path.suffix.lower() == ".parquet":
        return pd.read_parquet(dataset_path)
    return pd.read_csv(dataset_path)


def _make_classifier(model_family: str):
    if model_family == "extra_trees":
        from sklearn.ensemble import ExtraTreesClassifier

        return ExtraTreesClassifier(n_estimators=80, max_depth=5, min_samples_leaf=8, random_state=42, n_jobs=1)
    if model_family == "random_forest" or model_family == "lightgbm_random_forest":
        from sklearn.ensemble import RandomForestClassifier

        return RandomForestClassifier(n_estimators=80, max_depth=5, min_samples_leaf=8, random_state=42, n_jobs=1)
    if model_family == "lightgbm_gbdt":
        try:
            from lightgbm import LGBMClassifier  # type: ignore

            return LGBMClassifier(
                n_estimators=80,
                learning_rate=0.04,
                max_depth=3,
                num_leaves=15,
                min_child_samples=20,
                subsample=0.8,
                colsample_bytree=0.8,
                random_state=42,
                verbose=-1,
            )
        except Exception:
            pass
    from sklearn.ensemble import HistGradientBoostingClassifier

    return HistGradientBoostingClassifier(max_iter=80, learning_rate=0.04, max_leaf_nodes=15, random_state=42)


def _make_regressor(model_family: str):
    if model_family == "elasticnet":
        from sklearn.linear_model import ElasticNet

        return ElasticNet(alpha=0.001, l1_ratio=0.25, random_state=42, max_iter=2000)
    if model_family == "huber":
        from sklearn.linear_model import HuberRegressor

        return HuberRegressor(max_iter=300)
    try:
        from sklearn.ensemble import HistGradientBoostingRegressor

        return HistGradientBoostingRegressor(max_iter=80, learning_rate=0.04, max_leaf_nodes=15, random_state=42)
    except Exception:
        from sklearn.linear_model import Ridge

        return Ridge(alpha=1.0)


def _predict_probability(model: Any, x_val: pd.DataFrame) -> np.ndarray:
    if hasattr(model, "predict_proba"):
        probs = model.predict_proba(x_val)
        if np.asarray(probs).ndim == 2 and probs.shape[1] > 1:
            return np.asarray(probs[:, 1], dtype=float)
        return np.asarray(probs, dtype=float).reshape(-1)
    if hasattr(model, "decision_function"):
        raw = np.asarray(model.decision_function(x_val), dtype=float)
        return 1.0 / (1.0 + np.exp(-raw))
    pred = np.asarray(model.predict(x_val), dtype=float)
    return np.clip(pred, 0.0, 1.0)


def _safe_mean(values: list[float]) -> float | None:
    finite = [float(v) for v in values if np.isfinite(v)]
    return float(np.mean(finite)) if finite else None


def _fold_feature_importance(frame: pd.DataFrame, feature_cols: list[str], target: pd.Series) -> dict[str, float]:
    y = pd.to_numeric(target, errors="coerce").fillna(0.0).to_numpy(dtype=float)
    importances: dict[str, float] = {}
    if len(y) < 3 or float(np.std(y)) < 1e-12:
        return {col: 0.0 for col in feature_cols}
    for col in feature_cols:
        x = pd.to_numeric(frame[col], errors="coerce").fillna(0.0).to_numpy(dtype=float)
        if len(x) != len(y) or float(np.std(x)) < 1e-12:
            importances[col] = 0.0
            continue
        corr = float(np.corrcoef(x, y)[0, 1])
        importances[col] = abs(corr) if np.isfinite(corr) else 0.0
    return importances


def _evaluate_horizon(
    frame: pd.DataFrame,
    manifest: Mapping[str, Any],
    horizon: str,
    config: Mapping[str, Any],
    experiment_id: str | None = None,
) -> dict[str, Any]:
    feature_cols = _feature_cols(manifest, frame)
    model_family = str(config.get("model_family") or "sklearn_hist_gradient")
    label_variant = str(config.get("label_variant") or "direction_thresholded")
    folds = _make_folds(frame, horizon, max_folds=int(config.get("max_folds", 5)))
    fold_results: list[dict[str, Any]] = []
    fold_importances: list[dict[str, Any]] = []
    oof_records: list[dict[str, Any]] = []

    for fold in folds:
        train, validation, usable = _prepare_fold(fold["train_frame"], fold["validation_frame"], feature_cols)
        if not usable:
            continue
        train_labeled, label_report = add_label_variants(train, cost=float(config.get("cost", INTERNAL_COST)))
        val_labeled, _ = add_label_variants(validation, cost=float(config.get("cost", INTERNAL_COST)))

        train_target = train_labeled[label_variant] if label_variant in train_labeled.columns else train_labeled["direction_raw"]
        train_mask = pd.to_numeric(train_target, errors="coerce").fillna(0).astype(int) != 0
        if int(train_mask.sum()) < 30:
            train_target = train_labeled["direction_raw"]
            train_mask = pd.Series(True, index=train_labeled.index)
        y_train_binary = (pd.to_numeric(train_target.loc[train_mask], errors="coerce").fillna(0).astype(int) > 0).astype(int)
        if len(np.unique(y_train_binary)) < 2:
            continue

        x_train = train_labeled.loc[train_mask, usable]
        x_val = val_labeled[usable]
        y_val_direction = pd.to_numeric(val_labeled["y_direction"], errors="coerce").fillna(0).astype(int)
        y_val_binary = (y_val_direction > 0).astype(int)
        y_val_return = pd.to_numeric(val_labeled["y_return"], errors="coerce").fillna(0.0)

        classifier = _make_classifier(model_family)
        classifier.fit(x_train, y_train_binary)
        raw_prob = np.clip(_predict_probability(classifier, x_val), 0.0, 1.0)

        regressor_family = str(config.get("regressor_family") or "huber")
        regressor = _make_regressor(regressor_family)
        regressor.fit(x_train, pd.to_numeric(train_labeled.loc[train_mask, "y_return"], errors="coerce").fillna(0.0))
        expected_return = np.asarray(regressor.predict(x_val), dtype=float)

        calibration = build_calibration_bins(y_val_binary, raw_prob, bins=10)
        thresholds = optimize_selective_thresholds(
            calibrated_prob=raw_prob,
            expected_return=expected_return,
            realized_return=y_val_return,
            realized_direction=y_val_direction,
            cost=float(config.get("cost", INTERNAL_COST)),
        )
        oof_records.extend(
            build_oof_trace_records(
                horizon=horizon,
                fold_id=fold["fold"],
                validation=validation,
                raw_prob_up=raw_prob,
                calibrated_prob_up=raw_prob,
                expected_return=expected_return,
                model_family=model_family,
                model_id=f"research_{model_family}_{horizon}",
                calibration_method="research_fold_raw_probability",
                cost_assumption=float(config.get("cost", INTERNAL_COST)),
                data_quality_score=None,
                feature_coverage_score=None,
            )
        )
        pred_direction = np.where(raw_prob >= 0.5, 1, -1)
        directional_accuracy = float((pred_direction == np.where(y_val_direction > 0, 1, -1)).mean()) if len(pred_direction) else 0.0
        fold_importance = _fold_feature_importance(train_labeled, usable, train_labeled["y_return"])
        fold_importances.append({"fold": fold["fold"], "feature_importance": fold_importance})
        fold_results.append(
            {
                "fold": fold["fold"],
                "train_start": fold["train_start"],
                "train_end": fold["train_end"],
                "validation_start": fold["validation_start"],
                "validation_end": fold["validation_end"],
                "train_samples": fold["train_samples"],
                "validation_samples": fold["validation_samples"],
                "purged_samples": fold["purged_samples"],
                "embargo_samples": fold["embargo_samples"],
                "model_family": model_family,
                "regressor_family": regressor_family,
                "label_variant": label_variant,
                "directional_accuracy": directional_accuracy,
                "brier_score": calibration.get("brier_score"),
                "calibration_error": calibration.get("ece"),
                "threshold_optimization": thresholds,
                "label_distribution": label_report.get("label_distribution"),
                "feature_importance": fold_importance,
            }
        )

    accuracy_values = [float(item["directional_accuracy"]) for item in fold_results if item.get("directional_accuracy") is not None]
    brier_values = [float(item["brier_score"]) for item in fold_results if item.get("brier_score") is not None]
    ece_values = [float(item["calibration_error"]) for item in fold_results if item.get("calibration_error") is not None]
    threshold_by_fold = [item["threshold_optimization"] for item in fold_results if isinstance(item.get("threshold_optimization"), Mapping)]
    stability = build_feature_stability_report(
        fold_importances,
        feature_cols=feature_cols,
        missing_rate_by_feature=manifest.get("missing_rate_by_feature") if isinstance(manifest, Mapping) else None,
    )
    oof_summary = write_oof_trace(oof_records, horizon=horizon, experiment_id=experiment_id) if experiment_id and oof_records else {}
    return sanitize_for_json(
        {
            "horizon": horizon,
            "fold_count": len(fold_results),
            "folds": fold_results,
            "metric_summary": {
                "directional_accuracy_mean": _safe_mean(accuracy_values),
                "brier_score_mean": _safe_mean(brier_values),
                "calibration_error_mean": _safe_mean(ece_values),
                "sample_count": int(sum(int(item.get("validation_samples", 0)) for item in fold_results)),
            },
            "threshold_results": threshold_by_fold,
            "oof_trace": oof_summary,
            "feature_stability": stability,
            "feature_cols": feature_cols,
            "model_candidates": list(DEFAULT_MODEL_FAMILIES),
        }
    )


def _failed_experiment(config: Mapping[str, Any], message: str) -> dict[str, Any]:
    experiment_id, exp_dir = _new_experiment_dir()
    payload = {
        "experiment_id": experiment_id,
        "status": "failed",
        "message_zh": message,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "config": dict(config),
        "active_updated": False,
        "customer_prediction_generated": False,
        "promotion_gate_lowered": False,
        "baseline_scope": "internal_comparison_only",
        "artifact_dir": str(exp_dir),
    }
    _write_json(exp_dir / "experiment_summary.json", payload)
    _write_json(exp_dir / "config.json", dict(config))
    return sanitize_for_json(payload)


def run_model_experiment(config: Mapping[str, Any] | None = None) -> dict[str, Any]:
    cfg = dict(config or {})
    status = get_training_dataset_status()
    if not status.get("exists") or status.get("status") != "success":
        return _failed_experiment(cfg, "未找到可用真实训练数据集；请先构建训练数据集。")
    if status.get("sample_data_used"):
        return _failed_experiment(cfg, "样例数据不能进入模型研究实验。")

    experiment_id, exp_dir = _new_experiment_dir()
    horizons = [str(item) for item in cfg.get("horizons", DEFAULT_HORIZONS)]
    dataset_paths = status.get("dataset_paths") or {}
    horizon_results: dict[str, Any] = {}
    for horizon in horizons:
        path = dataset_paths.get(horizon)
        if not path:
            horizon_results[horizon] = {"status": "skipped", "message_zh": f"未找到 {horizon} 训练数据。"}
            continue
        try:
            frame = _load_dataset(str(path))
            horizon_results[horizon] = _evaluate_horizon(frame, status, horizon, cfg, experiment_id=experiment_id)
        except Exception as exc:
            horizon_results[horizon] = {"status": "failed", "message_zh": str(exc)}

    walk_forward_results = {"experiment_id": experiment_id, "horizons": horizon_results}
    threshold_results = {
        horizon: result.get("threshold_results", [])
        for horizon, result in horizon_results.items()
        if isinstance(result, Mapping)
    }
    calibration_report = {
        horizon: result.get("metric_summary", {})
        for horizon, result in horizon_results.items()
        if isinstance(result, Mapping)
    }
    feature_stability = {
        horizon: result.get("feature_stability", {})
        for horizon, result in horizon_results.items()
        if isinstance(result, Mapping)
    }
    promotion_preview = {
        "eligible_for_active": False,
        "message_zh": "研究实验只做 candidate 改进预览，不发布 active；正式上线仍必须通过原 promotion gate。",
        "promotion_gate_lowered": False,
        "active_updated": False,
        "blocking_reasons": ["本实验未执行正式 promotion gate。"],
    }
    feature_set = {
        "feature_source": "training_dataset_manifest",
        "feature_count": status.get("feature_count", 0),
        "sample_data_used": False,
    }
    label_config = {
        "label_variants": [
            "direction_raw",
            "direction_thresholded",
            "triple_barrier_atr",
            "volatility_adjusted_return",
            "high_confidence_meta_label",
        ],
        "selected_label_variant": cfg.get("label_variant", "direction_thresholded"),
        "no_trade_samples_not_forced": True,
    }

    artifacts = {
        "config.json": cfg,
        "feature_set.json": feature_set,
        "label_config.json": label_config,
        "walk_forward_results.json": walk_forward_results,
        "threshold_results.json": threshold_results,
        "calibration_report.json": calibration_report,
        "feature_stability.json": feature_stability,
        "promotion_preview.json": promotion_preview,
        "oof_trace_summary.json": get_research_oof_trace_summary(experiment_id),
    }
    for filename, payload in artifacts.items():
        _write_json(exp_dir / filename, payload if isinstance(payload, Mapping) else {"items": payload})

    summary = {
        "experiment_id": experiment_id,
        "status": "success",
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "artifact_dir": str(exp_dir),
        "config": cfg,
        "horizons": horizons,
        "model_candidates": list(DEFAULT_MODEL_FAMILIES),
        "label_variants": label_config["label_variants"],
        "walk_forward_results_path": str(exp_dir / "walk_forward_results.json"),
        "threshold_results_path": str(exp_dir / "threshold_results.json"),
        "calibration_report_path": str(exp_dir / "calibration_report.json"),
        "feature_stability_path": str(exp_dir / "feature_stability.json"),
        "promotion_preview_path": str(exp_dir / "promotion_preview.json"),
        "oof_trace_summary_path": str(exp_dir / "oof_trace_summary.json"),
        "active_updated": False,
        "customer_prediction_generated": False,
        "promotion_gate_lowered": False,
        "baseline_scope": "internal_comparison_only",
        "message_zh": "研究实验已完成；未发布 active，未生成客户预测，未降低 promotion gate。",
    }
    _write_json(exp_dir / "experiment_summary.json", summary)
    return sanitize_for_json(summary)


def list_model_experiments() -> dict[str, Any]:
    experiments: list[dict[str, Any]] = []
    for path in sorted(_research_root().glob("research-*"), reverse=True):
        summary = _read_json(path / "experiment_summary.json")
        if isinstance(summary, Mapping):
            experiments.append(
                {
                    "experiment_id": summary.get("experiment_id") or path.name,
                    "status": summary.get("status"),
                    "created_at": summary.get("created_at"),
                    "message_zh": summary.get("message_zh"),
                    "artifact_dir": str(path),
                    "active_updated": bool(summary.get("active_updated", False)),
                }
            )
    return sanitize_for_json({"experiments": experiments, "count": len(experiments)})


def get_model_experiment_detail(experiment_id: str) -> dict[str, Any]:
    safe_id = Path(str(experiment_id)).name
    path = _research_root() / safe_id
    if not safe_id or not path.exists():
        return sanitize_for_json({"status": "not_found", "message_zh": "未找到指定研究实验。", "experiment_id": experiment_id})
    payload = {"experiment_id": safe_id, "artifact_dir": str(path)}
    for filename in (
        "experiment_summary.json",
        "config.json",
        "feature_set.json",
        "label_config.json",
        "walk_forward_results.json",
        "threshold_results.json",
        "calibration_report.json",
        "feature_stability.json",
        "promotion_preview.json",
        "oof_trace_summary.json",
    ):
        payload[filename.replace(".json", "")] = _read_json(path / filename)
    return sanitize_for_json(payload)


def get_threshold_optimization(experiment_id: str) -> dict[str, Any]:
    safe_id = Path(str(experiment_id)).name
    path = _research_root() / safe_id / "threshold_results.json"
    payload = _read_json(path)
    if not isinstance(payload, Mapping):
        return sanitize_for_json({"status": "not_found", "message_zh": "未找到阈值优化结果。", "experiment_id": experiment_id})
    return sanitize_for_json({"experiment_id": safe_id, "threshold_results": payload})
