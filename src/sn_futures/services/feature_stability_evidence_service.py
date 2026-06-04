from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Mapping

import numpy as np

from ..api.json_utils import sanitize_for_json
from ..runtime import get_user_output_dir


DEFAULT_THRESHOLD = 0.55
EPSILON = 1e-12


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _normalise_version(version: str | None) -> str:
    value = str(version or "v5").strip().lower()
    return value or "v5"


def _out() -> Path:
    return get_user_output_dir()


def _registry_dir() -> Path:
    path = _out() / "model_registry"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _report_path(candidate_version: str | None = "v5") -> Path:
    return _registry_dir() / f"feature_stability_report_{_normalise_version(candidate_version)}.json"


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


def _as_float(value: Any, default: float = 0.0) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return default
    return parsed if np.isfinite(parsed) else default


def _candidate_registry_path(candidate_version: str) -> Path:
    if candidate_version == "v1":
        return _registry_dir() / "candidate_model_registry.json"
    return _registry_dir() / f"candidate_{candidate_version}_model_registry.json"


def _iter_candidate_artifact_paths(candidate_version: str) -> Iterable[Path]:
    registry = _read_json(_candidate_registry_path(candidate_version))
    models = registry.get("models") if isinstance(registry, Mapping) else None
    if isinstance(models, list):
        for model in models:
            if not isinstance(model, Mapping):
                continue
            artifact_path = model.get("artifact_path")
            if artifact_path:
                yield Path(str(artifact_path))

    artifact_dir = _registry_dir() / "candidate_artifacts"
    if candidate_version != "v1":
        artifact_dir = artifact_dir / candidate_version
    if artifact_dir.exists():
        yield from sorted(artifact_dir.glob("candidate*.json"))


def _importance_map(raw: Any) -> dict[str, float]:
    if isinstance(raw, Mapping):
        iterator = raw.items()
    elif isinstance(raw, list):
        rows: list[tuple[Any, Any]] = []
        for item in raw:
            if isinstance(item, Mapping):
                rows.append((item.get("feature") or item.get("name"), item.get("importance", item.get("value", 0.0))))
        iterator = rows
    else:
        iterator = []

    values: dict[str, float] = {}
    for raw_name, raw_value in iterator:
        name = str(raw_name or "").strip()
        if not name:
            continue
        values[name] = abs(_as_float(raw_value, 0.0))
    return values


def _normalise_importance(values: Mapping[str, float]) -> dict[str, float]:
    total = float(sum(abs(value) for value in values.values()))
    if total <= EPSILON:
        return {str(key): 0.0 for key in values}
    return {str(key): abs(float(value)) / total for key, value in values.items()}


def _record(record_id: str, horizon: str, values: Mapping[str, float], source_file: Path, *, source_type: str) -> dict[str, Any]:
    normalised = _normalise_importance(values)
    return {
        "record_id": record_id,
        "horizon": horizon,
        "source_type": source_type,
        "source_file": str(source_file),
        "importance": normalised,
        "informative": any(value > EPSILON for value in normalised.values()),
    }


def _collect_fold_records(candidate_version: str) -> list[dict[str, Any]]:
    base = _out() / "walk_forward"
    if candidate_version != "v1":
        base = base / candidate_version
    records: list[dict[str, Any]] = []
    for path in sorted(base.glob("wf_*.json")) if base.exists() else []:
        payload = _read_json(path)
        if not isinstance(payload, Mapping):
            continue
        horizon = str(payload.get("horizon") or path.stem.replace("wf_", ""))
        for idx, fold in enumerate(payload.get("folds") or [], start=1):
            if not isinstance(fold, Mapping):
                continue
            values = _importance_map(fold.get("feature_importance") or fold.get("importances"))
            if values:
                fold_id = str(fold.get("fold") or fold.get("fold_id") or idx)
                records.append(_record(f"{horizon}:fold:{fold_id}", horizon, values, path, source_type="walk_forward_fold"))
        values = _importance_map(payload.get("feature_importance"))
        if values:
            records.append(_record(f"{horizon}:aggregate", horizon, values, path, source_type="walk_forward_horizon"))
    return records


def _collect_candidate_records(candidate_version: str) -> list[dict[str, Any]]:
    seen: set[Path] = set()
    records: list[dict[str, Any]] = []
    for path in _iter_candidate_artifact_paths(candidate_version):
        resolved = path.resolve() if path.exists() else path
        if resolved in seen or not path.exists():
            continue
        seen.add(resolved)
        payload = _read_json(path)
        if not isinstance(payload, Mapping):
            continue
        values = _importance_map(payload.get("feature_importance") or payload.get("importances"))
        if not values:
            continue
        horizon = str(payload.get("horizon") or path.stem)
        model_id = str(payload.get("model_id") or path.stem)
        records.append(_record(f"{horizon}:candidate:{model_id}", horizon, values, path, source_type="candidate_artifact"))
    return records


def _collect_permutation_records(candidate_version: str) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    base = _out() / "walk_forward"
    if candidate_version != "v1":
        base = base / candidate_version
    for path in sorted(base.glob("wf_*.json")) if base.exists() else []:
        payload = _read_json(path)
        if not isinstance(payload, Mapping):
            continue
        horizon = str(payload.get("horizon") or path.stem.replace("wf_", ""))
        for idx, fold in enumerate(payload.get("folds") or [], start=1):
            if not isinstance(fold, Mapping):
                continue
            values = _importance_map(fold.get("permutation_importance"))
            if values:
                fold_id = str(fold.get("fold") or fold.get("fold_id") or idx)
                records.append(_record(f"{horizon}:permutation:{fold_id}", horizon, values, path, source_type="permutation_fold"))
    return records


def _score_records(records: list[Mapping[str, Any]]) -> dict[str, Any]:
    informative = [record for record in records if bool(record.get("informative"))]
    if not informative:
        return {
            "feature_details": [],
            "stable_features": [],
            "unstable_features": [],
            "stability_score": 0.0,
            "record_count": len(records),
            "informative_record_count": 0,
        }

    feature_names = sorted({feature for record in informative for feature in (record.get("importance") or {})})
    rows: list[dict[str, Any]] = []
    for feature in feature_names:
        values = np.asarray([_as_float((record.get("importance") or {}).get(feature), 0.0) for record in informative], dtype=float)
        mean = float(np.mean(values)) if values.size else 0.0
        std = float(np.std(values)) if values.size else 0.0
        cv = float(std / mean) if mean > EPSILON else None
        presence_rate = float(np.mean(values > EPSILON)) if values.size else 0.0
        consistency = float(1.0 / (1.0 + cv)) if cv is not None else 0.0
        feature_score = max(0.0, min(1.0, presence_rate * consistency))
        rows.append(
            {
                "feature": feature,
                "importance_mean": mean,
                "importance_std": std,
                "importance_cv": cv,
                "presence_rate": presence_rate,
                "stability": feature_score,
                "stable": bool(presence_rate >= 0.6 and feature_score >= DEFAULT_THRESHOLD),
            }
        )

    rows.sort(key=lambda item: item["importance_mean"], reverse=True)
    top_rows = rows[: max(1, min(20, len(rows)))]
    stability_score = float(np.mean([row["stability"] for row in top_rows])) if top_rows else 0.0
    return {
        "feature_details": rows,
        "stable_features": [str(row["feature"]) for row in rows if row.get("stable")],
        "unstable_features": [str(row["feature"]) for row in rows if not row.get("stable")],
        "stability_score": stability_score,
        "record_count": len(records),
        "informative_record_count": len(informative),
    }


def build_feature_stability_evidence(
    *,
    candidate_version: str = "v5",
    threshold: float = DEFAULT_THRESHOLD,
) -> dict[str, Any]:
    """Build feature-stability evidence from existing candidate artifacts only."""

    version = _normalise_version(candidate_version)
    fold_records = _collect_fold_records(version)
    candidate_records = _collect_candidate_records(version)
    informative_fold_count = sum(1 for record in fold_records if record.get("informative"))
    if informative_fold_count >= 2:
        evidence_records = fold_records
        evidence_mode = "fold_wise_feature_importance"
    else:
        evidence_records = candidate_records
        evidence_mode = "candidate_artifact_feature_importance"

    scored = _score_records(evidence_records)
    permutation_records = _collect_permutation_records(version)
    permutation = _score_records(permutation_records) if permutation_records else None
    score = _as_float(scored.get("stability_score"), 0.0)
    passed = score >= threshold and int(scored.get("informative_record_count") or 0) >= 2
    recommendations: list[str] = []
    if not scored.get("stable_features"):
        recommendations.append("Recompute candidate artifacts with non-zero feature importance or permutation importance evidence.")
    if scored.get("unstable_features"):
        recommendations.append("Review unstable high-importance features before active approval.")
    if evidence_mode != "fold_wise_feature_importance":
        recommendations.append("Fold-wise importances were missing or non-informative; using candidate artifact horizon-level importance.")
    if not permutation_records:
        recommendations.append("Permutation importance unavailable from current artifacts; keep it as optional evidence, not a gate bypass.")

    source_files = sorted({str(record.get("source_file")) for record in evidence_records if record.get("source_file")})
    payload = {
        "generated_at": _now(),
        "candidate_version": version,
        "evidence_status": "success" if evidence_records else "missing",
        "evidence_mode": evidence_mode if evidence_records else "missing",
        "fold_count": len(fold_records),
        "informative_fold_count": informative_fold_count,
        "candidate_artifact_count": len(candidate_records),
        "record_count": scored.get("record_count", 0),
        "informative_record_count": scored.get("informative_record_count", 0),
        "stable_features": scored.get("stable_features", []),
        "unstable_features": scored.get("unstable_features", []),
        "feature_details": scored.get("feature_details", []),
        "stability_score": score,
        "threshold": threshold,
        "passed": bool(passed),
        "permutation_importance_status": "available" if permutation_records else "unavailable",
        "permutation_stability_score": None if permutation is None else permutation.get("stability_score"),
        "permutation_feature_details": [] if permutation is None else permutation.get("feature_details", []),
        "recommendations": recommendations,
        "source_files": source_files,
        "report_path": str(_report_path(version)),
        "active_updated": False,
        "customer_prediction_generated": False,
        "training_invoked": False,
        "message_zh": "Feature stability evidence built from existing candidate artifacts; no training, active publishing, or customer prediction was triggered.",
    }
    _write_json(_report_path(version), payload)
    return sanitize_for_json(payload)


def get_feature_stability_evidence(candidate_version: str = "v5") -> dict[str, Any]:
    version = _normalise_version(candidate_version)
    payload = _read_json(_report_path(version))
    if isinstance(payload, Mapping):
        return sanitize_for_json(payload)
    return build_feature_stability_evidence(candidate_version=version)
