from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np
import pandas as pd

from ..api.json_utils import sanitize_for_json
from ..runtime import get_user_output_dir
from ..utils.secret_sanitizer import sanitize_mapping
from .research_run_ledger_service import append_run_ledger, finalize_research_run, start_research_run


REPLAY_VERSION = "shadow_replay_evaluator_v1"
REPORT_FILENAME = "shadow_replay_report.json"
SCHEMA_FIELDS = (
    "mode",
    "source_candidate_version",
    "source_oof_trace_path",
    "horizon",
    "instrument",
    "prediction_timestamp",
    "prediction_cutoff_date",
    "signal",
    "confidence",
    "technical_regime_label",
    "managed_regime_label",
    "risk_tags",
    "explanation_summary",
    "not_for_customer_use",
    "customer_visible",
    "active_model_used",
)


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _output_dir() -> Path:
    return get_user_output_dir()


def _normalise_version(candidate_version: str | None) -> str:
    value = str(candidate_version or "v10").strip().lower()
    if value.startswith("candidate_"):
        value = value.replace("candidate_", "", 1)
    return value or "v10"


def _safe_payload(payload: Any) -> Any:
    return sanitize_for_json(sanitize_mapping(payload))


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return {}
    return dict(payload) if isinstance(payload, Mapping) else {}


def _write_json(path: Path, payload: Mapping[str, Any]) -> dict[str, Any]:
    safe = _safe_payload(dict(payload))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(safe, ensure_ascii=False, indent=2), encoding="utf-8")
    return safe


def _report_path() -> Path:
    path = _output_dir() / "model_research" / REPORT_FILENAME
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _shadow_root() -> Path:
    path = _output_dir() / "shadow_mode"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _replay_artifact_path(candidate_version: str) -> Path:
    return _shadow_root() / f"shadow_replay_{_normalise_version(candidate_version)}.json"


def _path(relative_path: str) -> Path:
    primary = _output_dir() / relative_path
    if primary.exists():
        return primary
    fallback = Path("outputs") / relative_path
    if fallback.exists():
        return fallback
    return primary


def _candidate_report_path(candidate_version: str) -> Path:
    version = _normalise_version(candidate_version)
    return _path(f"model_research/candidate_{version}/candidate_{version}_gated_research_report.json")


def _decision_board_path() -> Path:
    return _path("model_research/research_decision_board.json")


def _shadow_readiness_path() -> Path:
    return _path("model_research/shadow_mode_readiness_spec.json")


def _cost_attribution_path(candidate_version: str) -> Path:
    version = _normalise_version(candidate_version)
    candidate_specific = _path(f"model_research/candidate_{version}/cost_stress_attribution_{version}.json")
    if candidate_specific.exists():
        return candidate_specific
    return _path("model_research/cost_stress_attribution.json")


def _year_evidence_path(candidate_version: str) -> Path:
    version = _normalise_version(candidate_version)
    candidate_specific = _path(f"model_research/candidate_{version}/year_concentration_evidence_{version}.json")
    if candidate_specific.exists():
        return candidate_specific
    return _path("model_research/year_concentration_evidence.json")


def _active_model_paths() -> list[Path]:
    out = _output_dir()
    cwd = Path.cwd()
    return [
        out / "model_registry" / "active_model.json",
        out / "models" / "active_model.json",
        cwd / "outputs" / "model_registry" / "active_model.json",
        cwd / "outputs" / "models" / "active_model.json",
    ]


def _active_pointer_paths() -> list[Path]:
    out = _output_dir()
    cwd = Path.cwd()
    return [
        out / "model_registry" / "active_pointer.json",
        out / "model_registry" / "active_model_pointer.json",
        cwd / "outputs" / "model_registry" / "active_pointer.json",
        cwd / "outputs" / "model_registry" / "active_model_pointer.json",
    ]


def _customer_prediction_paths() -> list[Path]:
    out = _output_dir()
    cwd = Path.cwd()
    return [
        out / "customer_predictions",
        out / "customer_predictions.json",
        out.parent / "customer_predictions",
        cwd / "outputs" / "customer_predictions",
        cwd / "outputs" / "customer_predictions.json",
        cwd / "app_data" / "customer_predictions",
    ]


def _normalise_path(path: Path) -> Path:
    return path.resolve(strict=False)


def _is_within(path: Path, root: Path) -> bool:
    try:
        _normalise_path(path).relative_to(_normalise_path(root))
        return True
    except ValueError:
        return False


def _as_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value if str(item or "").strip()]
    if value is None:
        return []
    text = str(value).strip()
    return [text] if text else []


def _status(payload: Mapping[str, Any]) -> str:
    return str(payload.get("status") or "missing").lower()


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return default
    return float(parsed) if np.isfinite(parsed) else default


def _parse_time(value: Any) -> tuple[str, str]:
    parsed = pd.to_datetime(value, errors="coerce")
    if pd.isna(parsed):
        now = _now()
        return now, now.split("T", 1)[0]
    iso = parsed.isoformat()
    return iso, iso.split("T", 1)[0]


def _signal_from_row(row: Mapping[str, Any]) -> str:
    selected = str(row.get("selected_signal") or row.get("signal") or "").strip()
    if selected:
        return selected
    direction = _safe_float(row.get("predicted_direction"), 0.0)
    if direction > 0:
        return "long"
    if direction < 0:
        return "short"
    return "observe"


def _row_risk_tags(row: Mapping[str, Any]) -> list[str]:
    tags: list[str] = []
    horizon = str(row.get("horizon") or "").lower()
    regime = str(row.get("regime_label") or row.get("technical_regime_label") or "").lower()
    if "high" in regime and "vol" in regime:
        tags.append("high_volatility_exposure")
    if horizon in {"1d", "1"}:
        tags.append("cost_sensitive_horizon")
    if _safe_float(row.get("confidence"), 0.0) <= 0.15:
        tags.append("low_confidence_shadow_signal")
    if abs(_safe_float(row.get("trade_edge"), 0.0)) <= 0.0:
        tags.append("empty_or_low_edge_signal")
    return list(dict.fromkeys(tags))


def _oof_paths(candidate_version: str) -> list[Path]:
    version = _normalise_version(candidate_version)
    base = _output_dir() / "walk_forward" / version
    if base.exists():
        return sorted(base.glob("oof_trace_*.csv"))
    fallback = Path("outputs") / "walk_forward" / version
    return sorted(fallback.glob("oof_trace_*.csv")) if fallback.exists() else []


def load_shadow_replay_source_oof(*, candidate_version: str = "v10") -> tuple[pd.DataFrame, list[str]]:
    frames: list[pd.DataFrame] = []
    loaded: list[str] = []
    for path in _oof_paths(candidate_version):
        try:
            frame = pd.read_csv(path)
        except Exception:
            continue
        if frame.empty:
            continue
        if "horizon" not in frame.columns:
            frame["horizon"] = path.stem.replace("oof_trace_", "")
        frame["_source_oof_trace_path"] = str(path)
        frames.append(frame)
        loaded.append(str(path))
    if not frames:
        return pd.DataFrame(), []
    return pd.concat(frames, ignore_index=True), loaded


def load_candidate_shadow_sources(*, candidate_version: str = "v10") -> dict[str, Any]:
    version = _normalise_version(candidate_version)
    paths = {
        "candidate_report": _candidate_report_path(version),
        "decision_board": _decision_board_path(),
        "shadow_mode_readiness": _shadow_readiness_path(),
        "cost_attribution": _cost_attribution_path(version),
        "year_evidence": _year_evidence_path(version),
    }
    return _safe_payload({name: {"path": str(path), "payload": _read_json(path)} for name, path in paths.items()})


def simulate_shadow_outputs_from_oof(
    *,
    candidate_version: str = "v10",
    oof_trace_path: str | Path | None = None,
    instrument: str = "SN",
    max_rows: int = 500,
) -> list[dict[str, Any]]:
    version = _normalise_version(candidate_version)
    if oof_trace_path is not None:
        try:
            frame = pd.read_csv(Path(oof_trace_path))
        except Exception:
            frame = pd.DataFrame()
        if "horizon" not in frame.columns and not frame.empty:
            frame["horizon"] = Path(oof_trace_path).stem.replace("oof_trace_", "")
        if not frame.empty:
            frame["_source_oof_trace_path"] = str(oof_trace_path)
    else:
        frame, _ = load_shadow_replay_source_oof(candidate_version=version)
    if frame.empty:
        return []
    rows: list[dict[str, Any]] = []
    for _, raw in frame.head(max_rows).iterrows():
        record = raw.to_dict()
        timestamp = record.get("timestamp") or record.get("prediction_date") or record.get("label_start_time") or record.get("label_end_time")
        prediction_timestamp, cutoff = _parse_time(timestamp)
        risk_tags = _row_risk_tags(record)
        row = {
            "mode": "shadow_replay",
            "source_candidate_version": version,
            "source_oof_trace_path": str(record.get("_source_oof_trace_path") or oof_trace_path or ""),
            "horizon": str(record.get("horizon") or "unknown"),
            "instrument": str(record.get("instrument") or instrument),
            "prediction_timestamp": prediction_timestamp,
            "prediction_cutoff_date": cutoff,
            "signal": _signal_from_row(record),
            "confidence": _safe_float(record.get("confidence"), 0.0),
            "technical_regime_label": str(record.get("regime_label") or record.get("technical_regime_label") or ""),
            "managed_regime_label": str(record.get("managed_regime_label") or ""),
            "risk_tags": risk_tags,
            "explanation_summary": "Research-only replay from historical OOF trace; not a customer prediction.",
            "not_for_customer_use": True,
            "customer_visible": False,
            "active_model_used": False,
        }
        rows.append(_safe_payload(row))
    return rows


def validate_shadow_replay_schema(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    blocking: list[str] = []
    for idx, row in enumerate(rows):
        missing = [field for field in SCHEMA_FIELDS if field not in row]
        blocking.extend(f"row_{idx}_missing_field:{field}" for field in missing)
        if row.get("mode") != "shadow_replay":
            blocking.append(f"row_{idx}_mode_must_be_shadow_replay")
        if row.get("not_for_customer_use") is not True:
            blocking.append(f"row_{idx}_not_for_customer_use_must_be_true")
        if row.get("customer_visible") is not False:
            blocking.append(f"row_{idx}_customer_visible_must_be_false")
        if row.get("active_model_used") is not False:
            blocking.append(f"row_{idx}_active_model_used_must_be_false")
    if not rows:
        blocking.append("shadow_replay_rows_empty")
    return _safe_payload(
        {
            "status": "pass" if not blocking else "fail",
            "schema_validation_status": "pass" if not blocking else "fail",
            "schema_fields": list(SCHEMA_FIELDS),
            "blocking_reasons": blocking,
        }
    )


def validate_shadow_replay_output_isolation(output_path: str | Path | None = None) -> dict[str, Any]:
    candidate = Path(output_path) if output_path is not None else _replay_artifact_path("v10")
    if not candidate.is_absolute():
        candidate = _output_dir() / candidate
    blocking: list[str] = []
    if not _is_within(candidate, _shadow_root()):
        blocking.append("shadow_replay_path_not_under_shadow_mode")
    for path in _customer_prediction_paths():
        if candidate == path or _is_within(candidate, path):
            blocking.append("shadow_replay_path_collides_with_customer_predictions")
    for path in [*_active_model_paths(), *_active_pointer_paths()]:
        if candidate == path or _is_within(candidate, path):
            blocking.append("shadow_replay_path_collides_with_active_model")
    existing_active = [str(path) for path in _active_model_paths() if path.exists()]
    existing_customer = [str(path) for path in _customer_prediction_paths() if path.exists()]
    if existing_active:
        blocking.append("active_model_output_exists")
    if existing_customer:
        blocking.append("customer_prediction_output_exists")
    return _safe_payload(
        {
            "status": "pass" if not blocking else "fail",
            "output_isolation_status": "pass" if not blocking else "fail",
            "shadow_replay_path": str(candidate),
            "shadow_replay_root": str(_shadow_root()),
            "existing_active_model_paths": existing_active,
            "existing_customer_prediction_paths": existing_customer,
            "blocking_reasons": list(dict.fromkeys(blocking)),
        }
    )


def compute_shadow_replay_stability_metrics(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    if not rows:
        return {
            "signal_flip_rate": 0.0,
            "horizon_distribution": {},
            "regime_distribution": {},
            "confidence_distribution": {"min": 0.0, "median": 0.0, "max": 0.0},
            "high_risk_signal_share": 0.0,
            "empty_signal_share": 1.0,
            "unstable_period_count": 0,
        }
    signals = [str(row.get("signal") or "").lower() for row in rows]
    flips = sum(1 for idx in range(1, len(signals)) if signals[idx] != signals[idx - 1])
    horizons: dict[str, int] = {}
    regimes: dict[str, int] = {}
    confidences = [_safe_float(row.get("confidence"), 0.0) for row in rows]
    high_risk = 0
    empty = 0
    for row in rows:
        horizon = str(row.get("horizon") or "unknown")
        regime = str(row.get("technical_regime_label") or "unknown")
        horizons[horizon] = horizons.get(horizon, 0) + 1
        regimes[regime] = regimes.get(regime, 0) + 1
        if _as_list(row.get("risk_tags")):
            high_risk += 1
        if str(row.get("signal") or "").lower() in {"", "observe", "0", "none"}:
            empty += 1
    arr = np.asarray(confidences, dtype=float)
    return _safe_payload(
        {
            "signal_flip_rate": flips / max(len(rows) - 1, 1),
            "horizon_distribution": horizons,
            "regime_distribution": regimes,
            "confidence_distribution": {
                "min": float(np.min(arr)) if arr.size else 0.0,
                "median": float(np.median(arr)) if arr.size else 0.0,
                "max": float(np.max(arr)) if arr.size else 0.0,
            },
            "high_risk_signal_share": high_risk / max(len(rows), 1),
            "empty_signal_share": empty / max(len(rows), 1),
            "unstable_period_count": flips,
        }
    )


def compute_shadow_replay_risk_tags(
    rows: Sequence[Mapping[str, Any]],
    *,
    candidate_version: str = "v10",
    sources: Mapping[str, Any] | None = None,
) -> list[str]:
    tags: list[str] = []
    for row in rows:
        tags.extend(_as_list(row.get("risk_tags")))
    sources = sources or load_candidate_shadow_sources(candidate_version=candidate_version)
    source_payloads = {name: dict(item.get("payload") or {}) for name, item in sources.items() if isinstance(item, Mapping)}
    board = source_payloads.get("decision_board", {})
    shadow = source_payloads.get("shadow_mode_readiness", {})
    cost = source_payloads.get("cost_attribution", {})
    v12 = _read_json(_candidate_report_path("v12"))
    if _status(v12) in {"blocked", "missing", "failed", "fail"}:
        tags.append("insufficient_v12_data")
    if str(board.get("current_research_state") or "").lower() == "managed_data_blocked":
        tags.append("managed_data_blocked")
    if not bool(board.get("manual_approval_recommended")):
        tags.append("manual_approval_missing")
    if _status(shadow) in {"blocked", "missing", "failed", "fail"} or not bool(shadow.get("shadow_mode_allowed")):
        tags.append("shadow_readiness_blocked")
    for driver in _as_list(cost.get("failure_drivers")):
        if "year" in driver:
            tags.append("year_specific_cost_drag")
        if "cost" in driver:
            tags.append("cost_sensitive_horizon")
    return list(dict.fromkeys(tags))


def _candidate_blocked(candidate_version: str, sources: Mapping[str, Any]) -> tuple[bool, list[str]]:
    version = _normalise_version(candidate_version)
    candidate = dict((sources.get("candidate_report") or {}).get("payload") or {}) if isinstance(sources.get("candidate_report"), Mapping) else {}
    status = _status(candidate)
    if version == "v12" and status in {"blocked", "missing", "failed", "fail"}:
        return True, ["candidate_v12_blocked"]
    return False, []


def _write_replay_artifact(path: Path, rows: Sequence[Mapping[str, Any]], report_status: str) -> dict[str, Any]:
    artifact = {
        "status": report_status,
        "generated_at": _now(),
        "replay_version": REPLAY_VERSION,
        "mode": "shadow_replay_artifact",
        "synthetic_contract_only": False,
        "research_only": True,
        "row_count": len(rows),
        "rows": list(rows),
        "training_invoked": False,
        "active_updated": False,
        "customer_prediction_generated": False,
    }
    return _write_json(path, artifact)


def build_shadow_replay_report(
    *,
    candidate_version: str = "v10",
    write: bool = True,
    record_run: bool = True,
) -> dict[str, Any]:
    version = _normalise_version(candidate_version)
    sources = load_candidate_shadow_sources(candidate_version=version)
    candidate_blocked, candidate_skips = _candidate_blocked(version, sources)
    frame, oof_paths = load_shadow_replay_source_oof(candidate_version=version)
    rows: list[dict[str, Any]] = []
    skipped: list[str] = []
    blocking: list[str] = []
    artifact_path = _replay_artifact_path(version)
    isolation = validate_shadow_replay_output_isolation(artifact_path)
    if candidate_blocked:
        skipped.extend(candidate_skips)
    if frame.empty or not oof_paths:
        skipped.append("oof_trace_missing")
    if isolation["status"] != "pass":
        blocking.extend(isolation.get("blocking_reasons") or [])
    if not skipped and not blocking:
        rows = simulate_shadow_outputs_from_oof(candidate_version=version)
    schema = validate_shadow_replay_schema(rows) if rows else {"status": "skipped", "schema_validation_status": "skipped", "blocking_reasons": []}
    if schema.get("status") == "fail":
        blocking.extend(schema.get("blocking_reasons") or [])
    status = "research_only" if rows and not blocking else "skipped"
    if blocking:
        status = "blocked"
    if candidate_blocked:
        status = "skipped"
    stability = compute_shadow_replay_stability_metrics(rows)
    risk_tags = compute_shadow_replay_risk_tags(rows, candidate_version=version, sources=sources)
    if rows and write and isolation["status"] == "pass" and schema.get("status") == "pass":
        _write_replay_artifact(artifact_path, rows, status)
    report = {
        "status": status,
        "generated_at": _now(),
        "replay_version": REPLAY_VERSION,
        "source_candidate_version": version,
        "source_oof_trace_path": oof_paths[0] if oof_paths else "",
        "source_oof_trace_paths": oof_paths,
        "replay_artifact_path": str(artifact_path) if rows else "",
        "replay_row_count": len(rows),
        "schema_validation_status": schema.get("schema_validation_status", schema.get("status", "missing")),
        "output_isolation_status": isolation.get("output_isolation_status", isolation.get("status", "missing")),
        "stability_metrics": stability,
        "risk_tags": risk_tags,
        "top_risk_tags": risk_tags[:8],
        "skipped_reasons": list(dict.fromkeys(skipped)),
        "blocking_reasons": list(dict.fromkeys(blocking)),
        "warning_reasons": [
            "shadow_replay_is_research_only",
            "shadow_replay_is_not_customer_prediction",
            "shadow_replay_does_not_grant_manual_approval",
        ],
        "source_reports": {
            name: {"path": item.get("path", ""), "status": _status(item.get("payload", {}))}
            for name, item in sources.items()
            if isinstance(item, Mapping)
        },
        "training_invoked": False,
        "active_updated": False,
        "customer_prediction_generated": False,
        "report_path": str(_report_path()),
    }
    safe = _safe_payload(report)
    if write:
        _write_json(_report_path(), safe)
    if record_run:
        run = start_research_run(
            service_name="shadow_replay_evaluator",
            run_type="safe_dry_run",
            input_paths=[*oof_paths, *[str(item.get("path", "")) for item in sources.values() if isinstance(item, Mapping)]],
            output_paths=[str(_report_path()), str(artifact_path) if rows else ""],
        )
        append_run_ledger(finalize_research_run(run, error_summary="artifact boundary violation" if blocking else ""))
    return safe


def build_shadow_replay_evaluator(*, candidate_version: str = "v10") -> dict[str, Any]:
    return build_shadow_replay_report(candidate_version=candidate_version, write=True, record_run=True)


def get_shadow_replay_report() -> dict[str, Any]:
    payload = _read_json(_report_path())
    if payload:
        return _safe_payload(payload)
    return build_shadow_replay_report(write=False, record_run=False)
