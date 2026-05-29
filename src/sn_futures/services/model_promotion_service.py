from __future__ import annotations

import json
import shutil
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping

import numpy as np

from ..api.json_utils import sanitize_for_json
from ..governance.model_registry import ModelRegistry
from ..runtime import get_user_output_dir
from .training_dataset_service import get_training_dataset_status
from .walk_forward_training_service import get_candidate_training_status


@dataclass(frozen=True)
class StrictPromotionConfig:
    min_fold_count: int = 3
    min_validation_sample_count: int = 300
    directional_accuracy_margin: float = 0.02
    max_brier_score: float = 0.24
    max_calibration_error: float = 0.08
    min_cost_adjusted_expectancy: float = 0.0
    max_drawdown_proxy_abs: float = 0.25
    min_feature_coverage: float = 0.70
    min_data_quality_score: float = 0.80


def _output_dir() -> Path:
    return get_user_output_dir()


def _registry_dir() -> Path:
    path = _output_dir() / "model_registry"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _normalise_version(version: str | None) -> str:
    value = str(version or "v1").strip().lower()
    return value or "v1"


def _candidate_registry_path(candidate_version: str | None = "v1") -> Path:
    version = _normalise_version(candidate_version)
    if version == "v1":
        return _registry_dir() / "candidate_model_registry.json"
    return _registry_dir() / f"candidate_{version}_model_registry.json"


def _active_model_path() -> Path:
    return _registry_dir() / "active_model.json"


def _candidate_rejected_path(candidate_version: str | None = "v1") -> Path:
    version = _normalise_version(candidate_version)
    if version == "v1":
        return _registry_dir() / "candidate_rejected.json"
    return _registry_dir() / f"candidate_{version}_rejected.json"


def _promotion_report_path(candidate_version: str | None = "v1") -> Path:
    version = _normalise_version(candidate_version)
    if version == "v1":
        return _registry_dir() / "promotion_report.json"
    return _registry_dir() / f"promotion_report_{version}.json"


def _active_artifact_dir() -> Path:
    path = _registry_dir() / "model_artifacts"
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


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return default
    return parsed if np.isfinite(parsed) else default


def _safe_bool(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "passed", "ok"}
    if value is None:
        return default
    return bool(value)


def _feature_coverage(manifest: Mapping[str, Any]) -> float:
    missing = manifest.get("missing_rate_by_feature") or {}
    if not isinstance(missing, Mapping) or not missing:
        return 1.0 if manifest.get("feature_count") else 0.0
    rates = [1.0 - _safe_float(value, 1.0) for value in missing.values()]
    return float(sum(rates) / max(len(rates), 1))


def _check(name: str, passed: bool, value: Any, threshold: Any, failure: str) -> dict[str, Any]:
    return {
        "name": name,
        "passed": bool(passed),
        "value": value,
        "threshold": threshold,
        "failure_reason_zh": "" if passed else failure,
    }


def _evaluate_record(record: Mapping[str, Any], candidate_status: Mapping[str, Any], manifest: Mapping[str, Any], config: StrictPromotionConfig) -> dict[str, Any]:
    horizon = str(record.get("horizon", ""))
    metrics_by_horizon = candidate_status.get("metrics_by_horizon") or {}
    metrics = dict(metrics_by_horizon.get(horizon) or record.get("metrics") or {})
    data_quality_snapshot = record.get("data_quality_snapshot") if isinstance(record.get("data_quality_snapshot"), Mapping) else {}
    feature_coverage = _feature_coverage(manifest)
    data_quality = _safe_float(data_quality_snapshot.get("data_quality_score", manifest.get("data_quality_score", 1.0)), 1.0)
    naive_accuracy = _safe_float(metrics.get("naive_directional_accuracy"), 0.50)
    drawdown_abs = abs(_safe_float(metrics.get("max_drawdown_proxy"), 0.0))
    baseline_used = _safe_bool(manifest.get("baseline_used"), False) or _safe_bool(data_quality_snapshot.get("baseline_used"), False)
    sample_used = _safe_bool(manifest.get("sample_data_used"), False) or _safe_bool(data_quality_snapshot.get("sample_data_used"), False)
    recent_degradation = _safe_bool(metrics.get("recent_degradation_triggered"), False)
    leakage_pass = _safe_bool(manifest.get("leakage_check_pass"), False)

    checks = [
        _check("walk-forward fold 数", int(_safe_float(metrics.get("fold_count"), 0)) >= config.min_fold_count, metrics.get("fold_count"), f">= {config.min_fold_count}", "walk-forward fold 数不足"),
        _check("验证样本数", int(_safe_float(metrics.get("sample_count"), 0)) >= config.min_validation_sample_count, metrics.get("sample_count"), f">= {config.min_validation_sample_count}", "验证样本数不足"),
        _check(
            "方向准确率超过朴素阈值",
            _safe_float(metrics.get("directional_accuracy"), 0.0) > naive_accuracy + config.directional_accuracy_margin,
            metrics.get("directional_accuracy"),
            f"> {naive_accuracy + config.directional_accuracy_margin:.4f}",
            "方向准确率未显著超过朴素阈值",
        ),
        _check("Brier 概率误差", _safe_float(metrics.get("brier_score"), 1.0) <= config.max_brier_score, metrics.get("brier_score"), f"<= {config.max_brier_score}", "Brier 概率误差过高"),
        _check("校准误差", _safe_float(metrics.get("calibration_error"), 1.0) <= config.max_calibration_error, metrics.get("calibration_error"), f"<= {config.max_calibration_error}", "概率校准误差过高"),
        _check("成本后期望", _safe_float(metrics.get("cost_adjusted_expectancy"), -1.0) > config.min_cost_adjusted_expectancy, metrics.get("cost_adjusted_expectancy"), f"> {config.min_cost_adjusted_expectancy}", "成本后期望不为正"),
        _check("回撤代理", drawdown_abs <= config.max_drawdown_proxy_abs, metrics.get("max_drawdown_proxy"), f"abs <= {config.max_drawdown_proxy_abs}", "回撤代理超过阈值"),
        _check("特征覆盖率", feature_coverage >= config.min_feature_coverage, feature_coverage, f">= {config.min_feature_coverage}", "特征覆盖率不足"),
        _check("数据质量", data_quality >= config.min_data_quality_score, data_quality, f">= {config.min_data_quality_score}", "数据质量不足"),
        _check("无泄漏检查", leakage_pass, leakage_pass, True, "泄漏检查未通过"),
        _check("非样例数据", not sample_used, sample_used, False, "样例数据不可晋级"),
        _check("未使用 baseline 作为候选", not baseline_used, baseline_used, False, "baseline 不可晋级为 active"),
        _check("近期未退化", not recent_degradation, recent_degradation, False, "近期表现退化"),
    ]
    failure_reasons = [item["failure_reason_zh"] for item in checks if not item["passed"]]
    return {
        "model_id": record.get("model_id", ""),
        "horizon": horizon,
        "passed": not failure_reasons,
        "checks": checks,
        "failure_reasons": failure_reasons,
        "metrics": metrics,
        "artifact_path": record.get("artifact_path", ""),
        "feature_columns": record.get("feature_columns", []),
        "label_columns": record.get("label_columns", []),
        "feature_coverage": feature_coverage,
        "data_quality_score": data_quality,
    }


def evaluate_promotion_gate(config: StrictPromotionConfig | None = None, *, candidate_version: str = "v1", dry_run: bool = False) -> dict[str, Any]:
    cfg = config or StrictPromotionConfig()
    candidate_version = _normalise_version(candidate_version)
    candidate_status = get_candidate_training_status(candidate_version=candidate_version)
    manifest = get_training_dataset_status(dataset_version=candidate_version)
    registry = ModelRegistry(_candidate_registry_path(candidate_version))
    records = [record.to_dict() for record in registry.list_candidates()]
    if not records:
        records = list(candidate_status.get("records") or [])
    decisions = [_evaluate_record(record, candidate_status, manifest, cfg) for record in records if isinstance(record, Mapping)]
    passed = [item for item in decisions if item.get("passed")]
    report = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "candidate_version": candidate_version,
        "dry_run": bool(dry_run),
        "status": "pass" if passed else "failed",
        "passed": bool(passed),
        "message_zh": "存在 candidate 通过 promotion gate。" if passed else "没有 candidate 通过 promotion gate，active 保持不变。",
        "config": asdict(cfg),
        "decisions": decisions,
        "passed_candidates": passed,
        "active_updated": False,
        "customer_prediction_generated": False,
        "sample_data_used": bool(manifest.get("sample_data_used", False)),
        "baseline_used": bool(manifest.get("baseline_used", False)),
    }
    _write_json(_promotion_report_path(candidate_version), report)
    if not passed:
        if dry_run and passed:
            report["message_zh"] = "Promotion dry-run 通过；等待人工审批发布 active，本次未写入 active_model.json。"
        _write_json(_candidate_rejected_path(candidate_version), report)
    return sanitize_for_json(report)


def promote_candidate(config: StrictPromotionConfig | None = None, *, candidate_version: str = "v1", dry_run: bool = False) -> dict[str, Any]:
    candidate_version = _normalise_version(candidate_version)
    report = evaluate_promotion_gate(config=config, candidate_version=candidate_version, dry_run=dry_run)
    passed = list(report.get("passed_candidates") or [])
    if not passed or dry_run:
        report["active_updated"] = False
        if dry_run and passed:
            report["message_zh"] = "Promotion dry-run 通过；等待人工审批发布 active，本次未写入 active_model.json。"
        report["message_zh"] = "Promotion gate 未通过，未写入 active_model.json。"
        if dry_run and passed:
            report["message_zh"] = "Promotion dry-run 通过；等待人工审批发布 active，本次未写入 active_model.json。"
        _write_json(_candidate_rejected_path(candidate_version), report)
        _write_json(_promotion_report_path(candidate_version), report)
        return sanitize_for_json(report)

    active_models: list[dict[str, Any]] = []
    for item in passed:
        artifact_path = Path(str(item.get("artifact_path") or ""))
        active_artifact_path = ""
        if artifact_path.exists():
            target = _active_artifact_dir() / f"active_{artifact_path.name}"
            shutil.copyfile(artifact_path, target)
            active_artifact_path = str(target)
        active_models.append(
            {
                "model_id": item.get("model_id"),
                "horizon": item.get("horizon"),
                "status": "active",
                "activated_at": datetime.now().isoformat(timespec="seconds"),
                "artifact_path": active_artifact_path or str(artifact_path),
                "metrics": item.get("metrics", {}),
                "promotion_checks": item.get("checks", []),
                "feature_columns": item.get("feature_columns", []),
                "label_columns": item.get("label_columns", []),
            }
        )
    active_payload = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "status": "active_available",
        "active_models": active_models,
        "disclaimer": "仅供沪锡期货量化投研参考，不构成投资建议，不承诺收益，不接实盘交易。",
    }
    _write_json(_active_model_path(), active_payload)
    report["active_updated"] = True
    report["active_model_path"] = str(_active_model_path())
    report["message_zh"] = "通过 promotion gate 的 candidate 已写入 active_model.json。"
    _write_json(_promotion_report_path(candidate_version), report)
    return sanitize_for_json(report)


def get_active_model_status() -> dict[str, Any]:
    payload = _read_json(_active_model_path())
    if not isinstance(payload, Mapping):
        return sanitize_for_json(
            {
                "status": "no_active",
                "exists": False,
                "message_zh": "暂无通过 promotion gate 的 active model。",
                "active_model_path": str(_active_model_path()),
            }
        )
    out = dict(payload)
    out["exists"] = True
    out["active_model_path"] = str(_active_model_path())
    return sanitize_for_json(out)


def get_promotion_report(candidate_version: str = "v1") -> dict[str, Any]:
    payload = _read_json(_promotion_report_path(candidate_version))
    if not isinstance(payload, Mapping):
        return sanitize_for_json(
            {
                "status": "not_run",
                "passed": False,
                "message_zh": "promotion gate 尚未运行。",
                "promotion_report_path": str(_promotion_report_path(candidate_version)),
            }
        )
    out = dict(payload)
    out["promotion_report_path"] = str(_promotion_report_path(candidate_version))
    return sanitize_for_json(out)
