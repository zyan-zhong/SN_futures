from __future__ import annotations

import csv
import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Mapping

from ..api.json_utils import sanitize_for_json
from ..labels.horizons import INTRADAY_HORIZONS, build_intraday_label_gate, normalise_label_specs
from ..runtime import get_user_output_dir
from ..utils.secret_sanitizer import sanitize_mapping


DEFAULT_MIN_ROWS = 30
DIRTY_FLAGS = ("sample_data_used", "sample", "sample_mode", "fake_data_used", "fake", "demo_data_used", "demo", "baseline_used", "mock_data_used")
DOWNSTREAM_FALSE_FLAGS = {
    "training_invoked": False,
    "prediction_generated": False,
    "backtest_invoked": False,
    "feature_store_written": False,
    "production_cache_written": False,
    "customer_prediction_generated": False,
}


def _safe(payload: Any) -> Any:
    return sanitize_for_json(sanitize_mapping(payload))


def _output_dir(output_dir: Path | None = None) -> Path:
    return output_dir or get_user_output_dir()


def _normalise_version(value: str | None, default: str) -> str:
    text = str(value or default).strip().lower()
    return text or default


def _feature_manifest_path(output_dir: Path, version: str) -> Path:
    return output_dir / "feature_store" / _normalise_version(version, "v3") / "feature_store_manifest.json"


def _training_manifest_path(output_dir: Path, dataset_version: str) -> Path:
    version = _normalise_version(dataset_version, "v3")
    if version == "v1":
        return output_dir / "training_dataset_manifest.json"
    return output_dir / f"training_dataset_manifest_{version}.json"


def _read_json(path: Path) -> dict[str, Any]:
    try:
        if path.exists():
            payload = json.loads(path.read_text(encoding="utf-8"))
            return dict(payload) if isinstance(payload, Mapping) else {}
    except Exception:
        return {}
    return {}


def _hash_file(path: Path) -> str:
    if not path.exists() or not path.is_file():
        return ""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y", "sample", "fake", "demo"}
    return bool(value)


def _dirty_reasons(manifest: Mapping[str, Any], prefix: str) -> list[str]:
    reasons: list[str] = []
    for flag in DIRTY_FLAGS:
        if _truthy(manifest.get(flag)):
            if flag in {"sample_data_used", "sample", "sample_mode"}:
                reasons.append(prefix)
            elif flag in {"fake_data_used", "fake"}:
                reasons.append(prefix.replace("sample_", "fake_"))
            elif flag in {"demo_data_used", "demo"}:
                reasons.append(prefix.replace("sample_", "demo_"))
            elif flag in {"baseline_used", "mock_data_used"}:
                reasons.append(f"{prefix}_{flag.replace('_used', '')}")
    return sorted(set(reasons))


def _as_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return default


def _dataset_path(manifest: Mapping[str, Any], horizon: str) -> Path | None:
    dataset_paths = manifest.get("dataset_paths")
    if isinstance(dataset_paths, Mapping):
        raw = dataset_paths.get(horizon)
        if raw:
            return Path(str(raw))
    outputs = manifest.get("dataset_outputs")
    if isinstance(outputs, Mapping) and isinstance(outputs.get(horizon), Mapping):
        raw = outputs[horizon].get("path")
        if raw:
            return Path(str(raw))
    return None


def _distribution(manifest: Mapping[str, Any], horizon: str) -> dict[str, int]:
    for key in ("class_distribution", "label_distribution_by_horizon"):
        value = manifest.get(key)
        if isinstance(value, Mapping) and isinstance(value.get(horizon), Mapping):
            return {str(label): _as_int(count) for label, count in value[horizon].items()}
    return {}


def _sample_count(manifest: Mapping[str, Any], horizon: str) -> int:
    sample_counts = manifest.get("sample_count_by_horizon")
    if isinstance(sample_counts, Mapping):
        return _as_int(sample_counts.get(horizon), 0)
    outputs = manifest.get("dataset_outputs")
    if isinstance(outputs, Mapping) and isinstance(outputs.get(horizon), Mapping):
        return _as_int(outputs[horizon].get("sample_count"), 0)
    return 0


def _parse_time(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text or text.lower() in {"nat", "nan", "none"}:
        return None
    try:
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        return datetime.fromisoformat(text)
    except Exception:
        return None


def _dataset_has_label_timestamp_leakage(path: Path | None) -> bool:
    if path is None or not path.exists() or path.suffix.lower() != ".csv":
        return False
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            for row in csv.DictReader(handle):
                feature_time = _parse_time(row.get("feature_time") or row.get("label_start_time"))
                label_available_at = _parse_time(row.get("label_available_at") or row.get("label_end_time"))
                if feature_time is not None and label_available_at is not None and label_available_at <= feature_time:
                    return True
    except Exception:
        return False
    return False


def _feature_store_state(output_dir: Path, version: str) -> tuple[dict[str, Any], list[str], dict[str, str]]:
    path = _feature_manifest_path(output_dir, version)
    manifest = _read_json(path)
    hashes = {"feature_store_manifest_hash": _hash_file(path), "feature_store_data_hash": ""}
    if not manifest:
        return (
            {
                "status": "blocked",
                "exists": False,
                "manifest_path": str(path),
                "row_count": 0,
                "point_in_time_ready": False,
                "sample_data_used": False,
            },
            ["feature_store_missing"],
            hashes,
        )

    store_path = Path(str(manifest.get("feature_store_path") or output_dir / "feature_store" / version / "feature_store.csv"))
    data_hash = str(manifest.get("data_source_hash") or manifest.get("content_hash") or _hash_file(store_path))
    hashes["feature_store_data_hash"] = data_hash
    reasons = _dirty_reasons(manifest, "sample_feature_store")
    if not store_path.exists():
        reasons.append("feature_store_data_missing")
    if str(manifest.get("status") or "").lower() not in {"success", "ready"}:
        reasons.append("feature_store_not_ready")
    if not bool(manifest.get("leakage_check_pass")):
        reasons.append("feature_store_leakage_check_failed")
    point_in_time_ready = bool(
        manifest.get("point_in_time_join_ready") is True
        or manifest.get("pit_ready") is True
        or isinstance(manifest.get("point_in_time_join_rules"), Mapping)
    )
    if manifest.get("point_in_time_join_ready") is False:
        point_in_time_ready = False
    if not point_in_time_ready:
        reasons.append("feature_store_pit_missing")

    row_count = _as_int(manifest.get("row_count"), 0)
    state = {
        "status": "ready" if not reasons else "blocked",
        "exists": True,
        "version": version,
        "manifest_path": str(path),
        "feature_store_path": str(store_path),
        "row_count": row_count,
        "feature_count": _as_int(manifest.get("feature_count"), len(manifest.get("usable_fields") or [])),
        "point_in_time_ready": point_in_time_ready,
        "leakage_check_pass": bool(manifest.get("leakage_check_pass")),
        "sample_data_used": bool(_truthy(manifest.get("sample_data_used"))),
        "fake_data_used": bool(_truthy(manifest.get("fake_data_used"))),
        "baseline_used": bool(_truthy(manifest.get("baseline_used"))),
        "blocking_reasons": sorted(set(reasons)),
    }
    return state, sorted(set(reasons)), hashes


def _training_state(
    output_dir: Path,
    *,
    dataset_version: str,
    horizons: list[str],
    min_rows: int,
) -> tuple[dict[str, Any], dict[str, dict[str, Any]], list[str], dict[str, Any]]:
    path = _training_manifest_path(output_dir, dataset_version)
    manifest = _read_json(path)
    hashes: dict[str, Any] = {"training_dataset_manifest_hash": _hash_file(path), "dataset_hashes": {}}
    horizon_states: dict[str, dict[str, Any]] = {}
    if not manifest:
        return (
            {"status": "blocked", "exists": False, "manifest_path": str(path), "sample_data_used": False},
            {},
            ["training_dataset_missing"],
            hashes,
        )

    reasons = _dirty_reasons(manifest, "sample_training_dataset")
    if str(manifest.get("status") or "").lower() not in {"success", "ready"}:
        reasons.append("training_dataset_not_ready")
    if not bool(manifest.get("leakage_check_pass")):
        reasons.append("training_dataset_leakage_check_failed")
    label_specs = manifest.get("label_specs") if isinstance(manifest.get("label_specs"), Mapping) else {}

    intraday_horizons = [horizon for horizon in horizons if horizon in INTRADAY_HORIZONS]
    intraday_gate = build_intraday_label_gate(intraday_horizons) if intraday_horizons else {"horizons": {}}
    intraday_by_horizon = intraday_gate.get("horizons") if isinstance(intraday_gate.get("horizons"), Mapping) else {}

    for horizon in horizons:
        horizon_reasons: list[str] = []
        sample_count = _sample_count(manifest, horizon)
        enough_rows = sample_count >= min_rows
        if not enough_rows:
            horizon_reasons.append(f"insufficient_rows:{sample_count}<{min_rows}")
        distribution = _distribution(manifest, horizon)
        populated_classes = [label for label, count in distribution.items() if int(count) > 0]
        if len(populated_classes) < 2:
            horizon_reasons.append("insufficient_class_distribution")
        if horizon not in label_specs:
            horizon_reasons.append("label_spec_missing")
        dataset_path = _dataset_path(manifest, horizon)
        dataset_exists = bool(dataset_path and dataset_path.exists())
        if not dataset_exists:
            horizon_reasons.append("dataset_file_missing")
        else:
            hashes["dataset_hashes"][horizon] = _hash_file(dataset_path)
        timestamp_leakage = _dataset_has_label_timestamp_leakage(dataset_path)
        leakage_pass = bool(manifest.get("leakage_check_pass")) and not timestamp_leakage
        if timestamp_leakage:
            horizon_reasons.append("label_timestamp_leakage")

        requires_intraday = horizon in INTRADAY_HORIZONS
        intraday_allowed = True
        intraday_row = {}
        if requires_intraday:
            intraday_row = dict(intraday_by_horizon.get(horizon) or {})
            intraday_allowed = bool(intraday_row.get("allowed"))
            if not intraday_allowed:
                horizon_reasons.extend(str(reason) for reason in intraday_row.get("blocking_reasons") or ["intraday_bars_missing"])

        prefixed = [f"{horizon}:{reason}" for reason in horizon_reasons]
        reasons.extend(prefixed)
        horizon_states[horizon] = _safe(
            {
                "horizon": horizon,
                "status": "ready" if not horizon_reasons else "blocked",
                "sample_count": sample_count,
                "min_rows": min_rows,
                "enough_rows": enough_rows,
                "class_distribution": distribution,
                "label_spec": dict(label_specs.get(horizon) or {}),
                "dataset_path": str(dataset_path or ""),
                "dataset_hash": hashes["dataset_hashes"].get(horizon, ""),
                "leakage_check_pass": leakage_pass,
                "requires_intraday_bars": requires_intraday,
                "intraday_allowed": intraday_allowed,
                "intraday_gate": intraday_row,
                "blocking_reasons": prefixed,
            }
        )

    state = {
        "status": "ready" if not reasons else "blocked",
        "exists": True,
        "dataset_version": dataset_version,
        "manifest_path": str(path),
        "label_version": manifest.get("label_version", ""),
        "leakage_check_pass": bool(manifest.get("leakage_check_pass")),
        "sample_data_used": bool(_truthy(manifest.get("sample_data_used"))),
        "fake_data_used": bool(_truthy(manifest.get("fake_data_used"))),
        "baseline_used": bool(_truthy(manifest.get("baseline_used"))),
        "blocking_reasons": sorted(set(reasons)),
    }
    return _safe(state), horizon_states, sorted(set(reasons)), hashes


def build_prediction_data_readiness(
    *,
    output_dir: Path | None = None,
    horizons: Iterable[int | str] = ("tomorrow",),
    dataset_version: str = "v3",
    feature_store_version: str = "v3",
    min_rows: int = DEFAULT_MIN_ROWS,
) -> dict[str, Any]:
    out = _output_dir(output_dir)
    specs = normalise_label_specs(horizons)
    horizon_names = [spec.horizon for spec in specs]
    feature_version = _normalise_version(feature_store_version, "v3")
    dataset_version = _normalise_version(dataset_version, "v3")

    feature_state, feature_reasons, feature_hashes = _feature_store_state(out, feature_version)
    training_state, horizon_states, training_reasons, training_hashes = _training_state(
        out,
        dataset_version=dataset_version,
        horizons=horizon_names,
        min_rows=int(min_rows),
    )
    reasons = sorted(set([*feature_reasons, *training_reasons]))
    ready = not reasons
    manifest_hashes = {
        **feature_hashes,
        **training_hashes,
    }
    payload = {
        "schema_version": "prediction-data-readiness-v1",
        "status": "ready" if ready else "blocked",
        "reason": "" if ready else (reasons[0] if reasons else "blocked"),
        "ready_for_prediction": ready,
        "horizons_requested": horizon_names,
        "min_rows": int(min_rows),
        "feature_store": feature_state,
        "training_dataset": training_state,
        "labels": {
            "label_version": training_state.get("label_version", ""),
            "horizons": horizon_names,
            "label_specs": {horizon: horizon_states.get(horizon, {}).get("label_spec", {}) for horizon in horizon_names},
        },
        "horizons": horizon_states,
        "manifest_hashes": manifest_hashes,
        "blocking_reasons": reasons,
        "sample_data_used": False,
        "fake_data_used": False,
        "baseline_used": False,
        **DOWNSTREAM_FALSE_FLAGS,
    }
    return _safe(payload)
