from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from ..api.json_utils import sanitize_for_json
from ..core.data_safety import DataSafetyViolation, assert_manifest_allowed_for_pipeline
from ..data_layer.stores import atomic_write_json, read_json
from ..runtime import get_user_output_dir


REGISTRY_SCHEMA_VERSION = "dev-model-registry-v1"
DIRTY_MODEL_FLAGS = ("sample_data_used", "sample", "baseline_used", "baseline", "fake_data_used", "fake")


def _output_dir(output_dir: Path | None = None) -> Path:
    return output_dir or get_user_output_dir()


def _truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y", "sample", "baseline", "fake"}
    return bool(value)


def _read_manifest(path_value: Any) -> tuple[dict[str, Any], str, list[str]]:
    path = Path(str(path_value or ""))
    if not str(path_value or "").strip() or not path.exists():
        return {}, str(path), ["dataset_manifest_missing"]
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}, str(path), ["dataset_manifest_malformed"]
    if not isinstance(payload, Mapping):
        return {}, str(path), ["dataset_manifest_malformed"]
    data = dict(payload)
    reasons: list[str] = []
    try:
        assert_manifest_allowed_for_pipeline(data, pipeline="training")
    except DataSafetyViolation as exc:
        reasons.extend(exc.blocking_reasons)
    if data.get("allowed_for_training") is not True:
        reasons.append("dataset_not_allowed_for_training")
    return data, str(path), sorted(set(reasons))


def _dirty_reasons(payload: Mapping[str, Any]) -> list[str]:
    return sorted(flag for flag in DIRTY_MODEL_FLAGS if _truthy(payload.get(flag)))


def _registry_path(output_dir: Path) -> Path:
    return output_dir / "model_governance" / "registry" / "candidate_registry.json"


def evaluate_active_model_safety(active_model: Mapping[str, Any]) -> dict[str, Any]:
    model = dict(active_model)
    blocking = _dirty_reasons(model)
    status = "blocked" if blocking else "ready"
    return sanitize_for_json(
        {
            "status": status,
            "active_allowed": not blocking,
            "blocking_reasons": blocking,
            "model_id": model.get("model_id", ""),
            "active_updated": False,
            "customer_prediction_generated": False,
        }
    )


def _validate_registry_record(candidate: Mapping[str, Any], dataset_manifest: Mapping[str, Any]) -> list[str]:
    reasons = _dirty_reasons(candidate)
    required_pairs = [
        ("dataset_hash", "content_hash"),
        ("feature_manifest_hash", "feature_manifest_hash"),
        ("data_watermark_hash", "data_watermark_hash"),
    ]
    for candidate_key, manifest_key in required_pairs:
        candidate_value = str(candidate.get(candidate_key) or "").strip()
        manifest_value = str(dataset_manifest.get(manifest_key) or "").strip()
        if not candidate_value:
            reasons.append(f"{candidate_key}_missing")
            continue
        if not manifest_value:
            reasons.append(f"{manifest_key}_missing")
            continue
        if candidate_value != manifest_value:
            reasons.append(f"{candidate_key}_mismatch")
    if not str(candidate.get("artifact_uri") or "").strip():
        reasons.append("artifact_uri_missing")
    return sorted(set(reasons))


def register_candidate_model(
    candidate: Mapping[str, Any],
    *,
    dataset_manifest_path: str | Path,
    output_dir: Path | None = None,
) -> dict[str, Any]:
    out = _output_dir(output_dir)
    record = dict(candidate)
    manifest, manifest_path, manifest_reasons = _read_manifest(dataset_manifest_path)
    blocking = sorted(set([*manifest_reasons, *_validate_registry_record(record, manifest)]))
    if blocking:
        return sanitize_for_json(
            {
                "schema_version": REGISTRY_SCHEMA_VERSION,
                "status": "blocked",
                "candidate_registered": False,
                "registry_record": {},
                "dataset_manifest_path": manifest_path,
                "blocking_reasons": blocking,
                "active_updated": False,
                "customer_prediction_generated": False,
            }
        )

    registry_record = {
        "model_id": str(record.get("model_id")),
        "status": "candidate",
        "horizon": str(record.get("horizon") or ""),
        "dataset_hash": str(record.get("dataset_hash")),
        "feature_manifest_hash": str(record.get("feature_manifest_hash")),
        "data_watermark_hash": str(record.get("data_watermark_hash")),
        "artifact_uri": str(record.get("artifact_uri")),
        "sample_data_used": False,
        "baseline_used": False,
        "fake_data_used": False,
        "active_updated": False,
        "customer_prediction_generated": False,
    }
    path = _registry_path(out)
    existing = read_json(path, {})
    rows = list(existing.get("models") or []) if isinstance(existing, Mapping) else []
    rows = [row for row in rows if isinstance(row, Mapping) and row.get("model_id") != registry_record["model_id"]]
    rows.append(registry_record)
    atomic_write_json(path, {"schema_version": REGISTRY_SCHEMA_VERSION, "models": rows})
    return sanitize_for_json(
        {
            "schema_version": REGISTRY_SCHEMA_VERSION,
            "status": "registered",
            "candidate_registered": True,
            "registry_path": str(path),
            "registry_record": registry_record,
            "blocking_reasons": [],
            "active_updated": False,
            "customer_prediction_generated": False,
        }
    )
