from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from ..api.json_utils import sanitize_for_json
from ..core.data_safety import DataSafetyViolation, assert_manifest_allowed_for_pipeline
from ..data_layer.stores import atomic_write_json
from ..resource_manager.scheduler import InMemoryJobQueue, ResourceSnapshot
from ..runtime import get_user_output_dir
from .resource_policy import evaluate_training_resource_policy


EXPERIMENT_SCHEMA_VERSION = "dev-model-training-experiment-v1"


def _output_dir(output_dir: Path | None = None) -> Path:
    return output_dir or get_user_output_dir()


def _read_json(path: Path) -> dict[str, Any]:
    try:
        if path.exists():
            payload = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(payload, Mapping):
                return dict(payload)
    except Exception:
        return {}
    return {}


def _dataset_manifest(path_value: Any) -> tuple[dict[str, Any], str, list[str]]:
    path = Path(str(path_value or ""))
    if not str(path_value or "").strip() or not path.exists():
        return {}, str(path), ["dataset_manifest_missing"]
    payload = _read_json(path)
    if not payload:
        return {}, str(path), ["dataset_manifest_malformed"]
    reasons: list[str] = []
    try:
        assert_manifest_allowed_for_pipeline(payload, pipeline="training")
    except DataSafetyViolation as exc:
        reasons.extend(exc.blocking_reasons)
    if payload.get("allowed_for_training") is not True:
        reasons.append("dataset_not_allowed_for_training")
    for key in ("content_hash", "feature_manifest_hash", "data_watermark_hash"):
        if not str(payload.get(key) or "").strip():
            reasons.append(f"{key}_missing")
    if str(payload.get("status") or "").lower() not in {"ready", "success", "passed", "pass"}:
        reasons.append("dataset_manifest_not_ready")
    return payload, str(path), sorted(set(reasons))


def _experiment_path(output_dir: Path, job_id: str) -> Path:
    safe_id = Path(str(job_id or "training_job")).name.replace(" ", "_")
    return output_dir / "model_governance" / "experiments" / f"{safe_id}.json"


def submit_training_job(
    request: Mapping[str, Any],
    *,
    resources: ResourceSnapshot | Mapping[str, Any] | None = None,
    queue: InMemoryJobQueue | None = None,
    output_dir: Path | None = None,
) -> dict[str, Any]:
    out = _output_dir(output_dir)
    request_payload = dict(request)
    job_id = str(request_payload.get("job_id") or "dev_training_job")
    policy = evaluate_training_resource_policy(request_payload, resources=resources)
    manifest, manifest_path, manifest_reasons = _dataset_manifest(request_payload.get("dataset_manifest_path"))
    blocking = sorted(
        set(
            [
                *[str(reason) for reason in policy.get("blocking_reasons") or [] if str(reason)],
                *manifest_reasons,
            ]
        )
    )
    status = "blocked" if blocking else "queued"
    experiment_manifest = sanitize_for_json(
        {
            "schema_version": EXPERIMENT_SCHEMA_VERSION,
            "status": status,
            "job_id": job_id,
            "dev_only": True,
            "fake_job_contract": True,
            "dataset_manifest_path": manifest_path,
            "dataset_manifest": {
                "status": manifest.get("status", "missing"),
                "dataset_id": manifest.get("dataset_id", ""),
                "content_hash": manifest.get("content_hash", ""),
                "feature_manifest_hash": manifest.get("feature_manifest_hash", ""),
                "data_watermark_hash": manifest.get("data_watermark_hash", ""),
                "row_count": manifest.get("row_count", 0),
            },
            "resource_plan": policy["resource_plan"],
            "blocking_reasons": blocking,
            "training_invoked": False,
            "real_training_invoked": False,
            "model_artifact_written": False,
            "active_updated": False,
            "customer_prediction_generated": False,
        }
    )
    atomic_write_json(_experiment_path(out, job_id), experiment_manifest)
    enqueued = False
    queue_record: dict[str, Any] = {}
    if status == "queued" and queue is not None:
        queue_record = queue.enqueue(job_id=job_id, kind="dev_model_training", manifest=experiment_manifest)
        enqueued = True
    return sanitize_for_json(
        {
            "status": status,
            "dev_only": True,
            "job_id": job_id,
            "job_enqueued": enqueued,
            "queue_record": queue_record,
            "experiment_manifest": experiment_manifest,
            "resource_plan": policy["resource_plan"],
            "blocking_reasons": blocking,
            "training_invoked": False,
            "real_training_invoked": False,
            "backtest_invoked": False,
            "prediction_generated": False,
            "candidate_promotion_invoked": False,
            "model_artifact_written": False,
            "active_updated": False,
            "customer_prediction_generated": False,
        }
    )
