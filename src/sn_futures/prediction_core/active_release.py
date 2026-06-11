from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from .gates import dirty_reasons, output_dir, read_json, safe_payload


def _active_model_path(root: Path) -> Path:
    return root / "model_registry" / "active_model.json"


def _active_release_audit_path(root: Path) -> Path:
    return root / "model_registry" / "active_release_audit.json"


def _normalise_horizon(value: Any) -> str:
    return str(value or "").strip().lower()


def _passed(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"pass", "passed", "success", "ready", "active_released", "true"}
    if isinstance(value, Mapping):
        if "passed" in value:
            return bool(value.get("passed"))
        return _passed(value.get("status"))
    return bool(value)


def _calibration_ready(model: Mapping[str, Any]) -> bool:
    calibration = model.get("calibration")
    if isinstance(calibration, Mapping):
        status = str(calibration.get("status") or "").lower()
        if status in {"ready", "success", "calibrated", "pass", "passed"}:
            return True
        if calibration.get("enabled") is True and calibration.get("ece") is not None:
            return True
    return bool(model.get("calibration_ready") or model.get("calibration_report_path"))


def _walk_forward_ready(model: Mapping[str, Any]) -> bool:
    walk = model.get("walk_forward")
    if isinstance(walk, Mapping):
        if str(walk.get("status") or "").lower() in {"ready", "success", "pass", "passed"}:
            return True
        if int(walk.get("fold_count") or 0) > 0 and int(walk.get("sample_count") or 0) > 0:
            return True
    return bool(model.get("walk_forward_path") or model.get("oof_trace_path"))


def _release_audit_safe(audit: Mapping[str, Any]) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    if not audit:
        return False, ["active_release_audit_missing"]
    if str(audit.get("status") or "").lower() not in {"active_released", "ready", "success", "pass", "passed"}:
        reasons.append("active_release_audit_not_released")
    if audit.get("active_updated") is False:
        reasons.append("active_release_not_updated")
    if audit.get("live_trading_enabled") is not False:
        reasons.append("active_release_live_trading_not_disabled")
    if audit.get("customer_order_routing_enabled") is not False:
        reasons.append("active_release_order_routing_not_disabled")
    checklist = [item for item in audit.get("approval_checklist") or [] if isinstance(item, Mapping)]
    failed = [item for item in checklist if item.get("passed") is False]
    if failed:
        reasons.append("active_release_approval_checklist_failed")
    return not reasons, sorted(set(reasons))


def _model_evidence(model: Mapping[str, Any]) -> Mapping[str, Any]:
    evidence = model.get("evidence")
    return evidence if isinstance(evidence, Mapping) else model


def _hash_gate(model: Mapping[str, Any], current_hashes: Mapping[str, Any]) -> list[str]:
    evidence = _model_evidence(model)
    reasons: list[str] = []
    expected_feature_manifest = str(evidence.get("feature_store_manifest_hash") or evidence.get("feature_manifest_hash") or "")
    expected_feature_data = str(evidence.get("feature_store_data_hash") or "")
    current_feature_manifest = str(current_hashes.get("feature_store_manifest_hash") or "")
    current_feature_data = str(current_hashes.get("feature_store_data_hash") or "")
    if expected_feature_manifest and current_feature_manifest and expected_feature_manifest != current_feature_manifest:
        reasons.append("feature_manifest_mismatch")
    if expected_feature_data and current_feature_data and expected_feature_data != current_feature_data:
        reasons.append("feature_data_mismatch")
    return reasons


def active_release_readiness(
    *,
    output_dir: Path | None = None,
    horizons: list[str],
    data_manifest_hashes: Mapping[str, Any],
) -> dict[str, Any]:
    root = output_dir or output_dir_from_runtime()
    active_path = _active_model_path(root)
    audit_path = _active_release_audit_path(root)
    active = read_json(active_path)
    audit = read_json(audit_path)
    if not active:
        return safe_payload(
            {
                "status": "blocked",
                "exists": False,
                "active_model_path": str(active_path),
                "audit_path": str(audit_path),
                "active_release_safe": False,
                "models": {},
                "missing_evidence": ["active_model"],
                "blocking_reasons": ["active_model_missing"],
            }
        )

    audit_safe, audit_reasons = _release_audit_safe(audit)
    active_models = [item for item in active.get("active_models") or [] if isinstance(item, Mapping)]
    models_by_horizon: dict[str, dict[str, Any]] = {}
    missing_evidence: set[str] = set()
    blocking: list[str] = [*dirty_reasons(active, "active_model"), *dirty_reasons(audit, "active_release"), *audit_reasons]
    for horizon in horizons:
        model = next((item for item in active_models if _normalise_horizon(item.get("horizon")) == horizon), None)
        horizon_reasons: list[str] = []
        if model is None:
            horizon_reasons.append("active_model_missing_for_horizon")
            missing_evidence.add("active_model")
            model_payload: Mapping[str, Any] = {}
        else:
            model_payload = model
            if not _calibration_ready(model):
                horizon_reasons.append("calibration_missing")
                missing_evidence.add("calibration")
            if not _walk_forward_ready(model):
                horizon_reasons.append("walk_forward_missing")
                missing_evidence.add("walk_forward")
            hash_reasons = _hash_gate(model, data_manifest_hashes)
            horizon_reasons.extend(hash_reasons)
            if hash_reasons:
                missing_evidence.add("feature_manifest")
        prefixed = [f"{horizon}:{reason}" for reason in horizon_reasons]
        blocking.extend(prefixed)
        models_by_horizon[horizon] = safe_payload(
            {
                "horizon": horizon,
                "status": "ready" if not horizon_reasons else "blocked",
                "model_id": model_payload.get("model_id", "") if isinstance(model_payload, Mapping) else "",
                "calibration_ready": bool(isinstance(model_payload, Mapping) and _calibration_ready(model_payload)),
                "walk_forward_ready": bool(isinstance(model_payload, Mapping) and _walk_forward_ready(model_payload)),
                "blocking_reasons": prefixed,
            }
        )

    release_safe = bool(audit_safe and not dirty_reasons(active, "active_model") and not dirty_reasons(audit, "active_release"))
    if not release_safe and "active_release_safe_failed" not in blocking:
        blocking.append("active_release_safe_failed")
    return safe_payload(
        {
            "status": "ready" if not blocking else "blocked",
            "exists": True,
            "active_model_path": str(active_path),
            "audit_path": str(audit_path),
            "candidate_version": active.get("candidate_version", ""),
            "release_mode": active.get("release_mode", ""),
            "active_release_safe": release_safe,
            "models": models_by_horizon,
            "missing_evidence": sorted(missing_evidence),
            "blocking_reasons": sorted(set(blocking)),
        }
    )


def output_dir_from_runtime() -> Path:
    return output_dir()
