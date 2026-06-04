from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping, Sequence

from ..api.json_utils import sanitize_for_json
from ..runtime import get_user_output_dir
from ..utils.secret_sanitizer import sanitize_mapping
from .research_run_ledger_service import append_run_ledger, finalize_research_run, start_research_run


CONTRACT_VERSION = "shadow_output_contract_v1"
SCHEMA_FIELDS = (
    "generated_at",
    "mode",
    "candidate_version",
    "model_version_or_candidate_id",
    "horizon",
    "instrument",
    "prediction_timestamp",
    "prediction_cutoff_date",
    "signal",
    "confidence",
    "explanation_summary",
    "not_for_customer_use",
    "active_model_used",
    "customer_visible",
)


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _output_dir() -> Path:
    return get_user_output_dir()


def _shadow_output_root() -> Path:
    path = _output_dir() / "shadow_mode"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _report_path() -> Path:
    path = _output_dir() / "model_research" / "shadow_output_contract_report.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _dry_run_artifact_path() -> Path:
    return _shadow_output_root() / "shadow_output_dry_run_contract.json"


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


def _normalise(path: Path) -> Path:
    return path.resolve(strict=False)


def _is_within(path: Path, root: Path) -> bool:
    try:
        _normalise(path).relative_to(_normalise(root))
        return True
    except ValueError:
        return False


def _forbidden_output_roots() -> list[Path]:
    output = _output_dir()
    cwd = Path.cwd()
    return [
        output / "customer_predictions",
        output / "customer_predictions.json",
        output / "model_registry",
        output / "models",
        output.parent / "customer_predictions",
        cwd / "outputs" / "customer_predictions",
        cwd / "outputs" / "customer_predictions.json",
        cwd / "outputs" / "model_registry",
        cwd / "outputs" / "models",
        cwd / "app_data" / "customer_predictions",
    ]


def _active_model_paths() -> list[Path]:
    output = _output_dir()
    cwd = Path.cwd()
    return [
        output / "model_registry" / "active_model.json",
        output / "models" / "active_model.json",
        cwd / "outputs" / "model_registry" / "active_model.json",
        cwd / "outputs" / "models" / "active_model.json",
    ]


def _customer_prediction_paths() -> list[Path]:
    output = _output_dir()
    cwd = Path.cwd()
    return [
        output / "customer_predictions",
        output / "customer_predictions.json",
        output.parent / "customer_predictions",
        cwd / "outputs" / "customer_predictions",
        cwd / "outputs" / "customer_predictions.json",
        cwd / "app_data" / "customer_predictions",
    ]


def _as_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value if str(item or "").strip()]
    if value is None:
        return []
    text = str(value).strip()
    return [text] if text else []


def _status(payload: Mapping[str, Any]) -> str:
    return str(payload.get("status") or "missing").lower()


def _shadow_readiness_path() -> Path:
    return _output_dir() / "model_research" / "shadow_mode_readiness_spec.json"


def _manual_approval_path() -> Path:
    return _output_dir() / "model_research" / "manual_approval_report.json"


def build_shadow_output_contract() -> dict[str, Any]:
    return _safe_payload(
        {
            "contract_version": CONTRACT_VERSION,
            "shadow_output_root": str(_shadow_output_root()),
            "forbidden_output_roots": [str(path) for path in _forbidden_output_roots()],
            "schema_fields": list(SCHEMA_FIELDS),
            "path_rule": "Shadow outputs may only be written under outputs/shadow_mode and must never write customer_predictions or active model files.",
            "real_shadow_output_generation_allowed_by_this_service": False,
            "training_invoked": False,
            "active_updated": False,
            "customer_prediction_generated": False,
        }
    )


def validate_shadow_output_path_isolation(output_path: str | Path | None = None) -> dict[str, Any]:
    candidate = Path(output_path) if output_path is not None else _dry_run_artifact_path()
    if not candidate.is_absolute():
        candidate = _output_dir() / candidate
    blocking: list[str] = []
    if not _is_within(candidate, _shadow_output_root()):
        blocking.append("shadow_output_path_not_under_shadow_mode")
    for root in _forbidden_output_roots():
        if candidate == root or _is_within(candidate, root):
            if "customer_predictions" in str(root):
                blocking.append("shadow_output_path_collides_with_customer_predictions")
            else:
                blocking.append("shadow_output_path_collides_with_active_model_output")
    return _safe_payload(
        {
            "status": "pass" if not blocking else "fail",
            "path_isolation_status": "pass" if not blocking else "fail",
            "shadow_output_path": str(candidate),
            "shadow_output_root": str(_shadow_output_root()),
            "forbidden_output_roots": [str(path) for path in _forbidden_output_roots()],
            "blocking_reasons": sorted(set(blocking)),
        }
    )


def detect_customer_prediction_path_collision(paths: Sequence[str | Path] | None = None) -> dict[str, Any]:
    checked = [Path(item) for item in paths] if paths is not None else _customer_prediction_paths()
    existing = [str(path) for path in checked if path.exists()]
    return _safe_payload(
        {
            "status": "pass" if not existing else "fail",
            "customer_prediction_collision_status": "pass" if not existing else "fail",
            "existing_customer_prediction_paths": existing,
            "blocking_reasons": [] if not existing else ["customer_prediction_path_exists"],
        }
    )


def _active_model_collision() -> dict[str, Any]:
    existing = [str(path) for path in _active_model_paths() if path.exists()]
    return _safe_payload(
        {
            "status": "pass" if not existing else "fail",
            "existing_active_model_paths": existing,
            "blocking_reasons": [] if not existing else ["active_model_path_exists"],
        }
    )


def validate_shadow_output_schema(payload: Mapping[str, Any]) -> dict[str, Any]:
    missing = [field for field in SCHEMA_FIELDS if field not in payload]
    blocking: list[str] = [f"missing_field:{field}" for field in missing]
    if payload.get("mode") != "shadow":
        blocking.append("mode_must_be_shadow")
    if payload.get("not_for_customer_use") is not True:
        blocking.append("not_for_customer_use_must_be_true")
    if payload.get("active_model_used") is not False:
        blocking.append("active_model_used_must_be_false")
    if payload.get("customer_visible") is not False:
        blocking.append("customer_visible_must_be_false")
    return _safe_payload(
        {
            "status": "pass" if not blocking else "fail",
            "schema_validation_status": "pass" if not blocking else "fail",
            "schema_fields": list(SCHEMA_FIELDS),
            "missing_fields": missing,
            "blocking_reasons": blocking,
        }
    )


def _contract_only_payload(*, candidate_version: str = "v12", horizon: str = "1d", instrument: str = "SN") -> dict[str, Any]:
    now = _now()
    return {
        "generated_at": now,
        "mode": "shadow",
        "candidate_version": candidate_version,
        "model_version_or_candidate_id": f"candidate_{candidate_version}",
        "horizon": horizon,
        "instrument": instrument,
        "prediction_timestamp": now,
        "prediction_cutoff_date": now.split("T", 1)[0],
        "signal": "contract_placeholder",
        "confidence": 0.0,
        "explanation_summary": "Synthetic contract-only placeholder; no real model signal or customer prediction.",
        "not_for_customer_use": True,
        "active_model_used": False,
        "customer_visible": False,
    }


def build_shadow_output_dry_run_artifact(
    *,
    synthetic_contract_only: bool = True,
    candidate_version: str = "v12",
    horizon: str = "1d",
    instrument: str = "SN",
) -> dict[str, Any]:
    if not synthetic_contract_only:
        return _safe_payload(
            {
                "status": "blocked",
                "dry_run_artifact_created": False,
                "synthetic_contract_only": False,
                "blocking_reasons": ["real_shadow_output_generation_not_supported"],
                "training_invoked": False,
                "active_updated": False,
                "customer_prediction_generated": False,
            }
        )
    payload = _contract_only_payload(candidate_version=candidate_version, horizon=horizon, instrument=instrument)
    schema = validate_shadow_output_schema(payload)
    path_check = validate_shadow_output_path_isolation(_dry_run_artifact_path())
    if schema["status"] != "pass" or path_check["status"] != "pass":
        return _safe_payload(
            {
                **payload,
                "status": "blocked",
                "dry_run_artifact_created": False,
                "synthetic_contract_only": True,
                "schema_validation_status": schema["status"],
                "path_isolation_status": path_check["status"],
                "blocking_reasons": list(schema.get("blocking_reasons") or []) + list(path_check.get("blocking_reasons") or []),
                "training_invoked": False,
                "active_updated": False,
                "customer_prediction_generated": False,
            }
        )
    artifact = {
        **payload,
        "status": "pass",
        "dry_run_artifact_created": True,
        "synthetic_contract_only": True,
        "artifact_path": str(_dry_run_artifact_path()),
        "schema_validation_status": "pass",
        "path_isolation_status": "pass",
        "real_prediction_generated": False,
        "training_invoked": False,
        "active_updated": False,
        "customer_prediction_generated": False,
    }
    written = _write_json(_dry_run_artifact_path(), artifact)
    _record_ledger("shadow_output_dry_run", "safe_dry_run", [_dry_run_artifact_path()])
    return written


def _load_shadow_readiness() -> dict[str, Any]:
    return _read_json(_shadow_readiness_path())


def _load_manual_approval() -> dict[str, Any]:
    return _read_json(_manual_approval_path())


def _approval_allows_shadow(manual: Mapping[str, Any]) -> bool:
    return str(manual.get("status") or "") == "approved_for_shadow_only" and str(manual.get("requested_action") or "") == "shadow_mode_only"


def build_shadow_output_contract_report(*, write: bool = True) -> dict[str, Any]:
    shadow_readiness = _load_shadow_readiness()
    manual_approval = _load_manual_approval()
    contract = build_shadow_output_contract()
    dry_run = _read_json(_dry_run_artifact_path())
    schema = validate_shadow_output_schema(dry_run) if dry_run else validate_shadow_output_schema(_contract_only_payload())
    path_check = validate_shadow_output_path_isolation(_dry_run_artifact_path())
    collision = detect_customer_prediction_path_collision()
    active_collision = _active_model_collision()

    blocking: list[str] = []
    if not bool(shadow_readiness.get("shadow_mode_allowed")):
        blocking.append("shadow_readiness_false_or_missing")
    if not manual_approval:
        blocking.append("manual_approval_missing")
    elif not _approval_allows_shadow(manual_approval):
        blocking.append("manual_approval_not_approved_for_shadow")
    for source in (schema, path_check, collision, active_collision):
        blocking.extend(_as_list(source.get("blocking_reasons")))
    shadow_allowed = not blocking
    payload = {
        "status": "ready" if shadow_allowed else "blocked",
        "generated_at": _now(),
        "contract_version": CONTRACT_VERSION,
        "shadow_output_allowed": shadow_allowed,
        "dry_run_artifact_created": bool(dry_run.get("dry_run_artifact_created")),
        "shadow_output_root": contract["shadow_output_root"],
        "forbidden_output_roots": contract["forbidden_output_roots"],
        "schema_fields": list(SCHEMA_FIELDS),
        "schema_validation_status": schema.get("schema_validation_status", schema.get("status", "missing")),
        "path_isolation_status": path_check.get("path_isolation_status", path_check.get("status", "missing")),
        "customer_prediction_collision_status": collision.get("customer_prediction_collision_status", collision.get("status", "missing")),
        "active_model_collision_status": active_collision.get("status", "missing"),
        "blocking_reasons": sorted(set(blocking)),
        "warning_reasons": ["real_shadow_output_generation_not_supported_by_this_contract"],
        "training_invoked": False,
        "active_updated": False,
        "customer_prediction_generated": False,
        "report_path": str(_report_path()),
    }
    return _write_json(_report_path(), payload) if write else _safe_payload(payload)


def get_shadow_output_contract_report() -> dict[str, Any]:
    payload = _read_json(_report_path())
    if payload:
        return _safe_payload(payload)
    return build_shadow_output_contract_report(write=False)


def refresh_shadow_output_contract_report() -> dict[str, Any]:
    report = build_shadow_output_contract_report(write=True)
    _record_ledger("shadow_output_contract", "report_refresh", [_report_path()])
    return report


def _record_ledger(service_name: str, run_type: str, output_paths: Sequence[Path]) -> None:
    run = start_research_run(
        service_name=service_name,
        run_type=run_type,
        output_paths=[str(path) for path in output_paths],
    )
    finalized = finalize_research_run(run)
    append_run_ledger(finalized)
