from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from ..api.json_utils import sanitize_for_json
from ..data_layer.stores import atomic_write_json, read_json
from ..runtime import get_user_output_dir
from .registry import evaluate_active_model_safety


ACTIVE_RELEASE_SCHEMA_VERSION = "dev-model-active-release-v1"


def _output_dir(output_dir: Path | None = None) -> Path:
    return output_dir or get_user_output_dir()


def _active_model_path(output_dir: Path) -> Path:
    return output_dir / "model_registry" / "active_model.json"


def _active_release_audit_path(output_dir: Path) -> Path:
    return output_dir / "model_registry" / "active_release_audit.json"


def _release_manifest_path(output_dir: Path) -> Path:
    return output_dir / "model_governance" / "active_release" / "active_release_manifest.json"


def _passed(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"pass", "passed", "ready", "success", "approved", "active_released", "true"}
    if isinstance(value, Mapping):
        if "passed" in value:
            return bool(value.get("passed"))
        return _passed(value.get("status"))
    return bool(value)


def _model_payload(candidate: Mapping[str, Any], evidence: Mapping[str, Any]) -> dict[str, Any]:
    calibration = evidence.get("calibration") if isinstance(evidence.get("calibration"), Mapping) else {}
    walk_forward = evidence.get("walk_forward") if isinstance(evidence.get("walk_forward"), Mapping) else {}
    return {
        "model_id": str(candidate.get("model_id") or ""),
        "horizon": str(candidate.get("horizon") or "tomorrow"),
        "status": "active",
        "artifact_path": str(candidate.get("artifact_uri") or ""),
        "feature_columns": list(candidate.get("feature_columns") or []),
        "label_columns": list(candidate.get("label_columns") or []),
        "evidence": {
            "dataset_hash": str(candidate.get("dataset_hash") or ""),
            "feature_store_manifest_hash": str(candidate.get("feature_store_manifest_hash") or candidate.get("feature_manifest_hash") or ""),
            "feature_store_data_hash": str(candidate.get("feature_store_data_hash") or ""),
            "data_watermark_hash": str(candidate.get("data_watermark_hash") or ""),
        },
        "calibration": dict(calibration),
        "walk_forward": dict(walk_forward),
        "sample_data_used": False,
        "fake_data_used": False,
        "baseline_used": False,
    }


def _evidence_blockers(evidence: Mapping[str, Any]) -> list[str]:
    blocking: list[str] = []
    for name in ("calibration", "walk_forward", "backtest"):
        item = evidence.get(name)
        if not isinstance(item, Mapping) or not item:
            blocking.append(f"{name}_missing")
            continue
        if not _passed(item):
            blocking.append(f"{name}_missing")
    return sorted(set(blocking))


def _promotion_gate_summary(candidate: Mapping[str, Any], evidence: Mapping[str, Any]) -> dict[str, Any]:
    active_safety = evaluate_active_model_safety(candidate)
    blocking = sorted(
        set(
            [
                *[str(reason) for reason in active_safety.get("blocking_reasons") or [] if str(reason)],
                *_evidence_blockers(evidence),
            ]
        )
    )
    return sanitize_for_json(
        {
            "schema_version": "dev-model-promotion-gate-v1",
            "status": "ready" if not blocking else "blocked",
            "candidate_model_id": str(candidate.get("model_id") or ""),
            "promotion_allowed": not blocking,
            "approval_required": True,
            "no_customer_prediction_until_approved": True,
            "blocking_reasons": blocking,
            "active_updated": False,
            "customer_prediction_generated": False,
            "prediction_generated": False,
            "real_training_invoked": False,
            "backtest_invoked": False,
        }
    )


def build_active_release_manifest(
    candidate: Mapping[str, Any],
    *,
    evidence: Mapping[str, Any],
    approval: Mapping[str, Any],
) -> dict[str, Any]:
    candidate_payload = dict(candidate)
    evidence_payload = dict(evidence)
    approval_payload = dict(approval)
    promotion = _promotion_gate_summary(candidate_payload, evidence_payload)
    active_safety = evaluate_active_model_safety(candidate_payload)
    blocking = sorted(
        set(
            [
                *[str(reason) for reason in promotion.get("blocking_reasons") or [] if str(reason)],
                *[str(reason) for reason in active_safety.get("blocking_reasons") or [] if str(reason)],
            ]
        )
    )
    if not _passed(approval_payload):
        blocking.append("manual_approval_missing")
    blocking = sorted(set(blocking))
    ready = not blocking
    return sanitize_for_json(
        {
            "schema_version": ACTIVE_RELEASE_SCHEMA_VERSION,
            "status": "ready" if ready else "blocked",
            "dev_only": True,
            "candidate_model": candidate_payload,
            "active_model": _model_payload(candidate_payload, evidence_payload) if ready else {},
            "approval": approval_payload,
            "promotion_gate": promotion,
            "blocking_reasons": blocking,
            "manual_approval_required": True,
            "active_publish_allowed": ready,
            "training_invoked": False,
            "real_training_invoked": False,
            "backtest_invoked": False,
            "prediction_generated": False,
            "customer_prediction_generated": False,
            "active_updated": False,
        }
    )


def publish_active_release(
    manifest: Mapping[str, Any],
    *,
    output_dir: Path | None = None,
) -> dict[str, Any]:
    out = _output_dir(output_dir)
    payload = dict(manifest)
    blocking = [str(reason) for reason in payload.get("blocking_reasons") or [] if str(reason)]
    if payload.get("schema_version") != ACTIVE_RELEASE_SCHEMA_VERSION:
        blocking.append("active_release_schema_version_missing")
    if payload.get("status") != "ready" or payload.get("active_publish_allowed") is not True:
        blocking.append("active_release_not_ready")
    active_model = payload.get("active_model") if isinstance(payload.get("active_model"), Mapping) else {}
    if not active_model:
        blocking.append("active_model_missing")
    blocking = sorted(set(blocking))
    if blocking:
        return sanitize_for_json(
            {
                "schema_version": ACTIVE_RELEASE_SCHEMA_VERSION,
                "status": "blocked",
                "active_updated": False,
                "blocking_reasons": blocking,
                "training_invoked": False,
                "prediction_generated": False,
                "customer_prediction_generated": False,
            }
        )

    release_manifest_path = _release_manifest_path(out)
    atomic_write_json(release_manifest_path, payload)
    active_payload = {
        "status": "active_available",
        "release_mode": "manual_human_approval",
        "candidate_version": active_model.get("model_id", ""),
        "active_models": [dict(active_model)],
        "live_trading_enabled": False,
        "customer_order_routing_enabled": False,
        "sample_data_used": False,
        "fake_data_used": False,
        "baseline_used": False,
    }
    audit_payload = {
        "schema_version": ACTIVE_RELEASE_SCHEMA_VERSION,
        "status": "active_released",
        "active_updated": True,
        "candidate_version": active_model.get("model_id", ""),
        "approval_checklist": [
            {"name": "manual approval", "passed": True},
            {"name": "promotion gate", "passed": True},
            {"name": "no sample baseline model", "passed": True},
        ],
        "live_trading_enabled": False,
        "customer_order_routing_enabled": False,
        "training_invoked": False,
        "prediction_generated": False,
        "customer_prediction_generated": False,
    }
    atomic_write_json(_active_model_path(out), active_payload)
    atomic_write_json(_active_release_audit_path(out), audit_payload)
    return sanitize_for_json(
        {
            "schema_version": ACTIVE_RELEASE_SCHEMA_VERSION,
            "status": "active_released",
            "active_updated": True,
            "release_manifest_path": str(release_manifest_path),
            "active_model_path": str(_active_model_path(out)),
            "active_release_audit_path": str(_active_release_audit_path(out)),
            "blocking_reasons": [],
            "training_invoked": False,
            "prediction_generated": False,
            "customer_prediction_generated": False,
        }
    )


def load_active_release_manifest(*, output_dir: Path | None = None) -> dict[str, Any]:
    out = _output_dir(output_dir)
    payload = read_json(_release_manifest_path(out), {})
    if isinstance(payload, Mapping) and payload:
        return sanitize_for_json(dict(payload))
    return sanitize_for_json(
        {
            "schema_version": ACTIVE_RELEASE_SCHEMA_VERSION,
            "status": "missing",
            "active_updated": False,
            "blocking_reasons": ["active_release_manifest_missing"],
            "training_invoked": False,
            "prediction_generated": False,
            "customer_prediction_generated": False,
        }
    )
