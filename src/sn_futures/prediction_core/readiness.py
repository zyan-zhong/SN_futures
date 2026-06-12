from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable

from ..labels.horizons import normalise_label_specs
from ..runtime import get_user_output_dir
from .active_release import active_release_readiness
from .contracts import DOWNSTREAM_FALSE_FLAGS, PUBLIC_PREDICTION_CORE_SCHEMA_VERSION
from .data_readiness import build_prediction_data_readiness
from .gates import assert_no_prediction_values, data_watermark_gate, safe_payload


def _output_dir(output_dir: Path | None = None) -> Path:
    return output_dir or get_user_output_dir()


def _horizon_names(horizons: Iterable[int | str]) -> list[str]:
    return [spec.horizon for spec in normalise_label_specs(horizons)]


def _missing_from_data(data: dict[str, Any]) -> list[str]:
    missing: set[str] = set()
    feature_store = data.get("feature_store", {})
    if feature_store.get("status") != "ready":
        reasons = set(str(reason) for reason in feature_store.get("blocking_reasons") or [])
        if "feature_store_pit_missing" in reasons:
            missing.add("point_in_time_feature_store")
        if "sample_feature_store" in reasons:
            missing.add("real_feature_store")
        missing.add("feature_store")
    training_dataset = data.get("training_dataset", {})
    if training_dataset.get("status") != "ready":
        reasons = set(str(reason) for reason in training_dataset.get("blocking_reasons") or [])
        if "training_dataset_missing" in reasons:
            missing.add("training_dataset")
        if "sample_training_dataset" in reasons:
            missing.add("real_training_dataset")
        missing.add("training_dataset")
    for horizon, row in (data.get("horizons") or {}).items():
        if not isinstance(row, dict) or row.get("status") == "ready":
            continue
        horizon_reasons = set(str(reason) for reason in row.get("blocking_reasons") or [])
        if f"{horizon}:label_spec_missing" in horizon_reasons:
            missing.add("labels")
        if row.get("requires_intraday_bars") and not row.get("intraday_allowed"):
            missing.add("intraday_bars")
        if not row.get("leakage_check_pass"):
            missing.add("leakage_evidence")
        if not row.get("enough_rows"):
            missing.add(f"{horizon}_rows")
        if f"{horizon}:insufficient_class_distribution" in horizon_reasons:
            missing.add("class_distribution")
    return sorted(missing)


def _missing_from_watermark(watermark: dict[str, Any]) -> list[str]:
    if watermark.get("status") == "ready":
        return []
    return ["data_watermark"]


def _missing_model_evidence(active: dict[str, Any]) -> list[str]:
    missing: set[str] = set(str(item) for item in active.get("missing_evidence") or [] if str(item))
    for reason in active.get("blocking_reasons") or []:
        text = str(reason)
        if "active_model_missing" in text:
            missing.add("active_model")
        if "calibration_missing" in text:
            missing.add("calibration")
        if "walk_forward_missing" in text:
            missing.add("walk_forward")
        if "feature_manifest_mismatch" in text or "feature_data_mismatch" in text:
            missing.add("feature_manifest")
        if text.startswith("active_release_audit_") or text == "active_release_safe_failed":
            missing.add("active_release_audit")
    return sorted(missing)


def build_public_prediction_core_readiness(
    *,
    output_dir: Path | None = None,
    horizons: Iterable[int | str] = ("tomorrow",),
    dataset_version: str = "v3",
    feature_store_version: str = "v3",
) -> dict[str, Any]:
    out = _output_dir(output_dir)
    requested_horizons = _horizon_names(horizons)
    data = build_prediction_data_readiness(
        output_dir=out,
        horizons=requested_horizons,
        dataset_version=dataset_version,
        feature_store_version=feature_store_version,
    )
    watermark = data_watermark_gate(out)
    active = active_release_readiness(
        output_dir=out,
        horizons=requested_horizons,
        data_manifest_hashes=data.get("manifest_hashes") if isinstance(data.get("manifest_hashes"), dict) else {},
    )

    blocking: list[str] = []
    blocking.extend(str(reason) for reason in data.get("blocking_reasons") or [] if str(reason))
    blocking.extend(str(reason) for reason in watermark.get("blocking_reasons") or [] if str(reason))
    blocking.extend(str(reason) for reason in active.get("blocking_reasons") or [] if str(reason))
    blocking = sorted(set(blocking))

    missing_data = sorted(set([*_missing_from_data(data), *_missing_from_watermark(watermark)]))
    missing_model_evidence = _missing_model_evidence(active)
    missing_evidence = sorted(set([*missing_data, *missing_model_evidence]))
    ready = not blocking
    payload = {
        "schema_version": PUBLIC_PREDICTION_CORE_SCHEMA_VERSION,
        "status": "ready_no_prediction_output" if ready else "blocked",
        "can_predict": ready,
        "ready_for_prediction": ready,
        "reason": "" if ready else (blocking[0] if blocking else "blocked"),
        "horizons": requested_horizons,
        "active_release_safe": bool(active.get("active_release_safe")) and ready,
        "missing_data": missing_data,
        "missing_model_evidence": missing_model_evidence,
        "missing_evidence": missing_evidence,
        "blocking_reasons": blocking,
        "prediction_output_available": False,
        "prediction_output_suppressed": True,
        "prediction_output_reason": "public_readiness_only",
        "data_readiness": data,
        "active_release": active,
        "data_watermark": {
            "status": watermark.get("status"),
            "stale_status": watermark.get("stale_status"),
            "blocking_reasons": watermark.get("blocking_reasons", []),
        },
        "sample_data_used": False,
        "fake_data_used": False,
        "baseline_used": False,
        **DOWNSTREAM_FALSE_FLAGS,
    }
    safe = assert_no_prediction_values(payload)
    if safe.get("status") == "blocked" and "prediction_value_output_forbidden" in safe.get("blocking_reasons", []):
        return safe_payload({**payload, **safe, **DOWNSTREAM_FALSE_FLAGS})
    return safe_payload(payload)
