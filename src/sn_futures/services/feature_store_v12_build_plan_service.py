from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping

from ..api.json_utils import sanitize_for_json
from ..runtime import get_user_output_dir
from .feature_store_v12_service import V12_REQUIRED_FUNDAMENTAL_FIELDS, V12_REQUIRED_TIMESTAMP_FIELDS


PLAN_VERSION = "feature_store_v12_build_dry_run_plan_v1"
PLAN_REPORT_FILENAME = "feature_store_v12_build_plan_report.json"


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _output_dir() -> Path:
    return get_user_output_dir()


def _diagnostics_path(filename: str) -> Path:
    return _output_dir() / "diagnostics" / filename


def _model_research_path(filename: str) -> Path:
    return _output_dir() / "model_research" / filename


def _report_path() -> Path:
    path = _diagnostics_path(PLAN_REPORT_FILENAME)
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _expected_feature_store_path() -> Path:
    return _output_dir() / "feature_store" / "v12" / "feature_store.csv"


def _expected_manifest_path() -> Path:
    return _output_dir() / "feature_store" / "v12" / "feature_store_manifest.json"


def _training_dataset_v12_path() -> Path:
    return _output_dir() / "training_datasets" / "v12"


def _active_model_path() -> Path:
    return _output_dir() / "model_registry" / "active_model.json"


def _customer_predictions_path() -> Path:
    return _output_dir() / "customer_predictions"


def _read_json(path: Path) -> Any:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return None


def _write_json(path: Path, payload: Mapping[str, Any]) -> dict[str, Any]:
    safe = sanitize_for_json(dict(payload))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(safe, ensure_ascii=False, indent=2), encoding="utf-8")
    return safe


def _status(payload: Any) -> str:
    if not isinstance(payload, Mapping):
        return "missing"
    return str(payload.get("status") or "missing").lower()


def _is_ready(payload: Any) -> bool:
    return _status(payload) in {"ready", "pass", "passed", "success", "ok"}


def _normalise_reasons(values: Any) -> list[str]:
    if not isinstance(values, list):
        return []
    return sorted({str(item) for item in values if str(item or "").strip()})


def _safe_check(name: str, *, passed: bool, status: str, path: Path, reasons: list[str] | None = None) -> dict[str, Any]:
    return sanitize_for_json(
        {
            "name": name,
            "status": status,
            "passed": bool(passed),
            "path": str(path),
            "blocking_reasons": sorted({reason for reason in (reasons or []) if reason}),
        }
    )


def _load_inputs() -> dict[str, Any]:
    paths = {
        "input_contract": _diagnostics_path("feature_store_v12_input_contract_report.json"),
        "production_cache_gate": _diagnostics_path("managed_data_production_cache_gate_report.json"),
        "evidence_freshness": _model_research_path("evidence_freshness_report.json"),
    }
    return {
        "paths": paths,
        "input_contract": _read_json(paths["input_contract"]),
        "production_cache_gate": _read_json(paths["production_cache_gate"]),
        "evidence_freshness": _read_json(paths["evidence_freshness"]),
    }


def validate_v12_build_preconditions() -> dict[str, Any]:
    loaded = _load_inputs()
    paths: dict[str, Path] = loaded["paths"]
    input_contract = loaded["input_contract"]
    production_gate = loaded["production_cache_gate"]
    freshness = loaded["evidence_freshness"]
    checks: list[dict[str, Any]] = []

    input_ready = bool(isinstance(input_contract, Mapping) and _is_ready(input_contract) and input_contract.get("input_contract_ready"))
    input_reasons = _normalise_reasons(input_contract.get("blocking_reasons") if isinstance(input_contract, Mapping) else ["input_contract_missing"])
    checks.append(
        _safe_check(
            "v12_input_contract_ready",
            passed=input_ready,
            status=_status(input_contract),
            path=paths["input_contract"],
            reasons=[] if input_ready else ["input_contract_blocked", *input_reasons],
        )
    )

    production_ready = bool(
        isinstance(production_gate, Mapping)
        and _is_ready(production_gate)
        and production_gate.get("production_cache_written")
        and production_gate.get("feature_store_v12_allowed")
    )
    production_reasons = _normalise_reasons(production_gate.get("blocking_reasons") if isinstance(production_gate, Mapping) else ["production_cache_gate_missing"])
    if isinstance(production_gate, Mapping) and not production_gate.get("production_cache_written"):
        production_reasons.append("production_cache_not_written")
    checks.append(
        _safe_check(
            "production_cache_written",
            passed=production_ready,
            status=_status(production_gate),
            path=paths["production_cache_gate"],
            reasons=[] if production_ready else ["production_cache_gate_blocked", *production_reasons],
        )
    )

    freshness_ready = bool(
        isinstance(freshness, Mapping)
        and _is_ready(freshness)
        and not freshness.get("stale_reports")
        and not freshness.get("missing_timestamps")
        and not freshness.get("timestamp_inversions")
    )
    freshness_reasons = _normalise_reasons(freshness.get("blocking_reasons") if isinstance(freshness, Mapping) else ["evidence_freshness_missing"])
    if isinstance(freshness, Mapping):
        freshness_reasons.extend(f"stale:{item}" for item in freshness.get("stale_reports") or [])
        freshness_reasons.extend(f"missing_timestamp:{item}" for item in freshness.get("missing_timestamps") or [])
        freshness_reasons.extend("timestamp_inversion" for _ in freshness.get("timestamp_inversions") or [])
    checks.append(
        _safe_check(
            "evidence_freshness_ready",
            passed=freshness_ready,
            status=_status(freshness),
            path=paths["evidence_freshness"],
            reasons=[] if freshness_ready else ["evidence_freshness_blocked", *freshness_reasons],
        )
    )

    blocking = sorted({reason for check in checks for reason in check.get("blocking_reasons", []) if reason})
    return sanitize_for_json(
        {
            "status": "ready" if not blocking else "blocked",
            "precondition_checks": checks,
            "blocking_reasons": blocking,
            "input_contract": dict(input_contract) if isinstance(input_contract, Mapping) else {},
            "production_cache_gate": dict(production_gate) if isinstance(production_gate, Mapping) else {},
            "evidence_freshness": dict(freshness) if isinstance(freshness, Mapping) else {},
        }
    )


def estimate_v12_build_outputs(preconditions: Mapping[str, Any] | None = None) -> dict[str, Any]:
    preconditions = preconditions or validate_v12_build_preconditions()
    input_contract = preconditions.get("input_contract") if isinstance(preconditions.get("input_contract"), Mapping) else {}
    coverage_diff = input_contract.get("coverage_diff") if isinstance(input_contract.get("coverage_diff"), Mapping) else {}
    expected_fields = list(input_contract.get("required_fields") or V12_REQUIRED_FUNDAMENTAL_FIELDS)
    expected_fields.extend(f"managed_{field}" for field in ("asof_date", "source_timestamp", "ingest_timestamp"))
    return sanitize_for_json(
        {
            "expected_feature_store_path": str(_expected_feature_store_path()),
            "expected_manifest_path": str(_expected_manifest_path()),
            "expected_fields": sorted({str(field) for field in expected_fields if str(field or "").strip()}),
            "expected_timestamp_fields": list(V12_REQUIRED_TIMESTAMP_FIELDS),
            "expected_row_count": int(coverage_diff.get("row_count") or 0),
            "expected_coverage": coverage_diff,
        }
    )


def validate_v12_build_forbidden_side_effects() -> dict[str, Any]:
    feature_store_exists = _expected_feature_store_path().exists()
    manifest_exists = _expected_manifest_path().exists()
    training_dataset_exists = _training_dataset_v12_path().exists()
    active_model_exists = _active_model_path().exists()
    customer_predictions_exists = _customer_predictions_path().exists()
    violations: list[str] = []
    if feature_store_exists:
        violations.append("feature_store_v12_output_exists_before_dry_run")
    if manifest_exists:
        violations.append("feature_store_v12_manifest_exists_before_dry_run")
    if training_dataset_exists:
        violations.append("training_dataset_v12_exists")
    if active_model_exists:
        violations.append("active_model_json_exists")
    if customer_predictions_exists:
        violations.append("customer_predictions_exists")
    return sanitize_for_json(
        {
            "status": "pass" if not violations else "violation",
            "feature_store_v12_build_executed": False,
            "feature_store_v12_output_exists": feature_store_exists,
            "feature_store_v12_manifest_exists": manifest_exists,
            "training_dataset_v12_exists": training_dataset_exists,
            "active_model_json_exists": active_model_exists,
            "customer_predictions_exists": customer_predictions_exists,
            "violations": violations,
        }
    )


def _rollback_plan() -> list[str]:
    return [
        "rollback_delete_new_feature_store_v12_outputs",
        "restore_prior_feature_store_v12_manifest_if_present",
        "rerun_v12_input_contract",
        "rerun_evidence_freshness",
        "keep_training_dataset_v12_blocked_until_v12_build_success",
    ]


def _resource_budget(row_count: int) -> dict[str, Any]:
    expected_rows = max(row_count, 0)
    return {
        "max_runtime_seconds": 120,
        "max_memory_mb": 1024,
        "max_output_rows": max(expected_rows, 1),
        "max_output_size_mb": 128,
        "requires_manual_review_before_execution": True,
    }


def _forbidden_side_effects() -> list[str]:
    return [
        "build_feature_store_v12",
        "build_training_dataset_v12",
        "run_candidate_v12_research",
        "promotion",
        "active_model.json",
        "customer_predictions",
    ]


def build_feature_store_v12_dry_run_plan() -> dict[str, Any]:
    preconditions = validate_v12_build_preconditions()
    outputs = estimate_v12_build_outputs(preconditions)
    boundary = validate_v12_build_forbidden_side_effects()
    blocking = list(preconditions.get("blocking_reasons") or [])
    if boundary.get("violations"):
        blocking.extend(str(item) for item in boundary.get("violations") or [])
    blocking = sorted({reason for reason in blocking if reason})
    ready = not blocking
    return sanitize_for_json(
        {
            "status": "ready" if ready else "blocked",
            "generated_at": _now(),
            "plan_version": PLAN_VERSION,
            "input_contract_status": preconditions.get("input_contract", {}).get("status", "missing") if isinstance(preconditions.get("input_contract"), Mapping) else "missing",
            **outputs,
            "precondition_checks": preconditions.get("precondition_checks", []),
            "rollback_plan": _rollback_plan(),
            "resource_budget": _resource_budget(int(outputs.get("expected_row_count") or 0)),
            "forbidden_side_effects": _forbidden_side_effects(),
            "side_effect_boundary": boundary,
            "feature_store_v12_build_executed": False,
            "training_invoked": False,
            "active_updated": False,
            "customer_prediction_generated": False,
            "blocking_reasons": blocking,
            "warning_reasons": ["dry_run_plan_only_no_feature_store_v12_build"],
            "report_path": str(_report_path()),
        }
    )


def write_v12_build_plan_report() -> dict[str, Any]:
    return _write_json(_report_path(), build_feature_store_v12_dry_run_plan())


def get_latest_v12_build_plan_report() -> dict[str, Any]:
    payload = _read_json(_report_path())
    if isinstance(payload, Mapping):
        return sanitize_for_json(dict(payload))
    report = build_feature_store_v12_dry_run_plan()
    report["status"] = "blocked"
    report["blocking_reasons"] = sorted(set(list(report.get("blocking_reasons") or []) + ["feature_store_v12_build_plan_report_missing"]))
    return sanitize_for_json(report)
