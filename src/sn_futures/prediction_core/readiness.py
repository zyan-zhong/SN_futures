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
    if data.get("feature_store", {}).get("status") != "ready":
        missing.add("feature_store")
    if data.get("training_dataset", {}).get("status") != "ready":
        missing.add("training_dataset")
    for horizon, row in (data.get("horizons") or {}).items():
        if not isinstance(row, dict) or row.get("status") == "ready":
            continue
        if row.get("requires_intraday_bars") and not row.get("intraday_allowed"):
            missing.add("intraday_bars")
        if not row.get("leakage_check_pass"):
            missing.add("leakage_evidence")
        if not row.get("enough_rows"):
            missing.add(f"{horizon}_rows")
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

    missing_evidence = sorted(
        set(
            [
                *_missing_from_data(data),
                *[str(item) for item in active.get("missing_evidence") or [] if str(item)],
                *(["data_watermark"] if watermark.get("status") != "ready" else []),
            ]
        )
    )
    ready = not blocking
    payload = {
        "schema_version": PUBLIC_PREDICTION_CORE_SCHEMA_VERSION,
        "status": "ready" if ready else "blocked",
        "can_predict": ready,
        "reason": "" if ready else (blocking[0] if blocking else "blocked"),
        "horizons": requested_horizons,
        "active_release_safe": bool(active.get("active_release_safe")) and ready,
        "missing_evidence": missing_evidence,
        "blocking_reasons": blocking,
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
