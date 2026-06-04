from __future__ import annotations

import csv
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping, Sequence

from ..api.json_utils import sanitize_for_json
from ..runtime import get_user_output_dir
from ..utils.secret_sanitizer import contains_secret_like_value, sanitize_mapping
from .feature_store_v12_service import V12_REQUIRED_FUNDAMENTAL_FIELDS, V12_REQUIRED_TIMESTAMP_FIELDS
from .research_run_ledger_service import append_run_ledger, finalize_research_run, start_research_run


EXECUTOR_VERSION = "feature_store_v12_controlled_build_executor_v1"
EXECUTION_REPORT_FILENAME = "feature_store_v12_controlled_build_report.json"


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _output_dir() -> Path:
    return get_user_output_dir()


def _diagnostics_path(filename: str) -> Path:
    return _output_dir() / "diagnostics" / filename


def _model_research_path(filename: str) -> Path:
    return _output_dir() / "model_research" / filename


def _report_path() -> Path:
    path = _diagnostics_path(EXECUTION_REPORT_FILENAME)
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _feature_store_path() -> Path:
    return _output_dir() / "feature_store" / "v12" / "feature_store.csv"


def _controlled_manifest_path() -> Path:
    return _output_dir() / "feature_store" / "v12" / "feature_store_controlled_build_manifest.json"


def _standard_manifest_path() -> Path:
    return _output_dir() / "feature_store" / "v12" / "feature_store_manifest.json"


def _production_cache_path() -> Path:
    return _output_dir() / "fundamentals" / "managed_fundamentals.json"


def _training_dataset_v12_path() -> Path:
    return _output_dir() / "training_datasets" / "v12"


def _candidate_v12_report_path() -> Path:
    return _output_dir() / "model_research" / "candidate_v12" / "candidate_v12_gated_research_report.json"


def _active_model_paths() -> list[Path]:
    return [
        _output_dir() / "model_registry" / "active_model.json",
        _output_dir() / "models" / "active_model.json",
    ]


def _customer_prediction_paths() -> list[Path]:
    return [
        _output_dir() / "customer_predictions",
        _output_dir() / "customer_predictions.json",
    ]


def _read_json(path: Path) -> Any:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return None


def _safe_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    return sanitize_for_json(sanitize_mapping(dict(payload)))


def _write_json(path: Path, payload: Mapping[str, Any]) -> dict[str, Any]:
    safe = _safe_payload(payload)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(safe, ensure_ascii=False, indent=2), encoding="utf-8")
    return safe


def _status(payload: Any) -> str:
    if not isinstance(payload, Mapping):
        return "missing"
    return str(payload.get("status") or "missing").lower()


def _is_ready(payload: Any) -> bool:
    return _status(payload) in {"ready", "pass", "passed", "success", "ok", "approved", "completed"}


def _normalise_reasons(values: Any) -> list[str]:
    if not isinstance(values, list):
        return []
    return sorted({str(item) for item in values if str(item or "").strip()})


def _rows_from_payload(payload: Any) -> list[dict[str, Any]]:
    rows = payload.get("rows") or payload.get("data") or payload.get("history") or [] if isinstance(payload, Mapping) else []
    if not isinstance(rows, list):
        return []
    return [dict(row) for row in rows if isinstance(row, Mapping)]


def _present(value: Any) -> bool:
    return value is not None and str(value).strip() != ""


def _safe_check(name: str, *, passed: bool, status: str, path: Path, reasons: Sequence[str] | None = None) -> dict[str, Any]:
    return _safe_payload(
        {
            "name": name,
            "status": status,
            "passed": bool(passed),
            "path": str(path),
            "blocking_reasons": sorted({str(reason) for reason in reasons or [] if str(reason or "").strip()}),
        }
    )


def _load_inputs() -> dict[str, Any]:
    paths = {
        "production_cache_gate": _diagnostics_path("managed_data_production_cache_gate_report.json"),
        "input_contract": _diagnostics_path("feature_store_v12_input_contract_report.json"),
        "build_plan": _diagnostics_path("feature_store_v12_build_plan_report.json"),
        "evidence_freshness": _model_research_path("evidence_freshness_report.json"),
        "pit_replay": _diagnostics_path("managed_pit_replay_report.json"),
        "pit_audit": _diagnostics_path("managed_data_audit_manifest.json"),
        "data_quality": _diagnostics_path("managed_data_quality_scorecard.json"),
        "incident_drill": _model_research_path("incident_drill_report.json"),
        "production_cache": _production_cache_path(),
    }
    return {"paths": paths, **{name: _read_json(path) for name, path in paths.items()}}


def _active_model_exists() -> bool:
    return any(path.exists() for path in _active_model_paths())


def _customer_predictions_exists() -> bool:
    return any(path.exists() for path in _customer_prediction_paths())


def _production_gate_pass(payload: Any) -> bool:
    return bool(isinstance(payload, Mapping) and _is_ready(payload) and payload.get("production_cache_written") and payload.get("feature_store_v12_allowed"))


def _input_contract_pass(payload: Any) -> bool:
    return bool(isinstance(payload, Mapping) and _is_ready(payload) and payload.get("input_contract_ready"))


def _build_plan_pass(payload: Any) -> bool:
    return bool(isinstance(payload, Mapping) and _is_ready(payload) and not payload.get("feature_store_v12_build_executed"))


def _freshness_pass(payload: Any) -> bool:
    return bool(
        isinstance(payload, Mapping)
        and _is_ready(payload)
        and not payload.get("stale_reports")
        and not payload.get("missing_timestamps")
        and not payload.get("timestamp_inversions")
    )


def _pit_replay_pass(payload: Any) -> bool:
    return bool(isinstance(payload, Mapping) and _is_ready(payload) and payload.get("point_in_time_join_ready") and int(payload.get("cases_failed") or 0) == 0)


def _pit_audit_pass(payload: Any) -> bool:
    if not isinstance(payload, Mapping) or not _is_ready(payload):
        return False
    leakage = payload.get("leakage_checks") if isinstance(payload.get("leakage_checks"), Mapping) else {}
    return bool(payload.get("point_in_time_join_ready") or payload.get("v12_allowed") or leakage.get("point_in_time_join_ready"))


def _quality_pass(payload: Any) -> bool:
    return bool(isinstance(payload, Mapping) and _is_ready(payload) and payload.get("gate_passed"))


def _lockdown_clear(payload: Any) -> bool:
    if not isinstance(payload, Mapping):
        return True
    if payload.get("real_lockdown_state") is True:
        return False
    if payload.get("lockdown_triggered") is True and not payload.get("simulated_artifacts_only"):
        return False
    return True


def validate_v12_controlled_build_preconditions() -> dict[str, Any]:
    loaded = _load_inputs()
    paths: dict[str, Path] = loaded["paths"]
    checks: list[dict[str, Any]] = []

    gate = loaded.get("production_cache_gate")
    gate_pass = _production_gate_pass(gate)
    checks.append(
        _safe_check(
            "production_cache_gate_ready",
            passed=gate_pass,
            status=_status(gate),
            path=paths["production_cache_gate"],
            reasons=[] if gate_pass else ["production_cache_gate_blocked", *_normalise_reasons(gate.get("blocking_reasons") if isinstance(gate, Mapping) else ["production_cache_gate_missing"])],
        )
    )

    cache_exists = paths["production_cache"].exists()
    checks.append(
        _safe_check(
            "production_cache_written",
            passed=cache_exists and gate_pass,
            status="pass" if cache_exists and gate_pass else "blocked",
            path=paths["production_cache"],
            reasons=[] if cache_exists and gate_pass else ["production_cache_not_written"],
        )
    )

    contract = loaded.get("input_contract")
    contract_pass = _input_contract_pass(contract)
    checks.append(
        _safe_check(
            "v12_input_contract_ready",
            passed=contract_pass,
            status=_status(contract),
            path=paths["input_contract"],
            reasons=[] if contract_pass else ["input_contract_blocked", *_normalise_reasons(contract.get("blocking_reasons") if isinstance(contract, Mapping) else ["input_contract_missing"])],
        )
    )

    plan = loaded.get("build_plan")
    plan_pass = _build_plan_pass(plan)
    checks.append(
        _safe_check(
            "v12_build_dry_run_plan_ready",
            passed=plan_pass,
            status=_status(plan),
            path=paths["build_plan"],
            reasons=[] if plan_pass else ["build_plan_blocked", *_normalise_reasons(plan.get("blocking_reasons") if isinstance(plan, Mapping) else ["build_plan_missing"])],
        )
    )

    freshness = loaded.get("evidence_freshness")
    freshness_pass = _freshness_pass(freshness)
    checks.append(
        _safe_check(
            "evidence_freshness_pass",
            passed=freshness_pass,
            status=_status(freshness),
            path=paths["evidence_freshness"],
            reasons=[] if freshness_pass else ["evidence_freshness_blocked", *_normalise_reasons(freshness.get("blocking_reasons") if isinstance(freshness, Mapping) else ["evidence_freshness_missing"])],
        )
    )

    pit_replay = loaded.get("pit_replay")
    pit_replay_pass = _pit_replay_pass(pit_replay)
    checks.append(
        _safe_check(
            "pit_replay_pass",
            passed=pit_replay_pass,
            status=_status(pit_replay),
            path=paths["pit_replay"],
            reasons=[] if pit_replay_pass else ["pit_replay_not_passed", *_normalise_reasons(pit_replay.get("blocking_reasons") if isinstance(pit_replay, Mapping) else ["pit_replay_missing"])],
        )
    )

    pit_audit = loaded.get("pit_audit")
    pit_audit_pass = _pit_audit_pass(pit_audit)
    checks.append(
        _safe_check(
            "pit_audit_pass",
            passed=pit_audit_pass,
            status=_status(pit_audit),
            path=paths["pit_audit"],
            reasons=[] if pit_audit_pass else ["pit_audit_not_passed", *_normalise_reasons(pit_audit.get("blocking_reasons") if isinstance(pit_audit, Mapping) else ["pit_audit_missing"])],
        )
    )

    data_quality = loaded.get("data_quality")
    quality_pass = _quality_pass(data_quality)
    checks.append(
        _safe_check(
            "data_quality_pass",
            passed=quality_pass,
            status=_status(data_quality),
            path=paths["data_quality"],
            reasons=[] if quality_pass else ["data_quality_not_passed", *_normalise_reasons(data_quality.get("blocking_reasons") if isinstance(data_quality, Mapping) else ["data_quality_missing"])],
        )
    )

    incident = loaded.get("incident_drill")
    lockdown_clear = _lockdown_clear(incident)
    checks.append(
        _safe_check(
            "governance_lockdown_clear",
            passed=lockdown_clear,
            status="pass" if lockdown_clear else "blocked",
            path=paths["incident_drill"],
            reasons=[] if lockdown_clear else ["governance_lockdown_active"],
        )
    )

    active_absent = not _active_model_exists()
    checks.append(
        _safe_check(
            "active_model_json_absent",
            passed=active_absent,
            status="pass" if active_absent else "blocked",
            path=_output_dir() / "model_registry" / "active_model.json",
            reasons=[] if active_absent else ["unexpected_active_model_json_exists"],
        )
    )

    predictions_absent = not _customer_predictions_exists()
    checks.append(
        _safe_check(
            "customer_predictions_absent",
            passed=predictions_absent,
            status="pass" if predictions_absent else "blocked",
            path=_output_dir() / "customer_predictions",
            reasons=[] if predictions_absent else ["unexpected_customer_predictions_exists"],
        )
    )

    blocking = sorted({reason for check in checks for reason in check.get("blocking_reasons", []) if reason})
    return _safe_payload(
        {
            "status": "ready" if not blocking else "blocked",
            "precondition_checks": checks,
            "blocking_reasons": blocking,
            "input_contract_summary": _summary(contract, ("status", "input_contract_ready", "missing_required_fields", "missing_timestamp_fields", "blocking_reasons")),
            "production_cache_gate_summary": _summary(gate, ("status", "production_cache_written", "feature_store_v12_allowed", "blocking_reasons")),
            "build_plan_summary": _summary(plan, ("status", "feature_store_v12_build_executed", "expected_feature_store_path", "blocking_reasons")),
        }
    )


def _summary(payload: Any, keys: Sequence[str]) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        return {"status": "missing"}
    return {key: payload.get(key) for key in keys if key in payload}


def _date_range(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    dates = sorted(
        {
            str(row.get("feature_date") or row.get("trading_date") or row.get("date") or "").strip()
            for row in rows
            if str(row.get("feature_date") or row.get("trading_date") or row.get("date") or "").strip()
        }
    )
    return {"date_start": dates[0] if dates else "", "date_end": dates[-1] if dates else ""}


def _coverage(rows: Sequence[Mapping[str, Any]], fields: Sequence[str]) -> dict[str, Any]:
    total = len(rows)
    by_field: dict[str, Any] = {}
    for field in fields:
        if field == "feature_date":
            present = sum(1 for row in rows if _present(row.get("feature_date") or row.get("trading_date")))
        else:
            present = sum(1 for row in rows if _present(row.get(field)))
        by_field[field] = {"present": present, "missing": max(total - present, 0), "coverage": round(present / total, 4) if total else 0.0}
    return {"row_count": total, "by_field": by_field}


def _write_feature_store_csv(rows: Sequence[Mapping[str, Any]]) -> None:
    path = _feature_store_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = sorted({key for row in rows for key in row.keys()})
    if "feature_date" in fields:
        fields.remove("feature_date")
        fields.insert(0, "feature_date")
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})


def _write_controlled_manifest(rows: Sequence[Mapping[str, Any]], report_path: Path) -> dict[str, Any]:
    payload = {
        "status": "success",
        "manifest_version": EXECUTOR_VERSION,
        "generated_at": _now(),
        "feature_set": "managed_proxy_pit_gated_v12_controlled",
        "row_count": len(rows),
        "date_range": _date_range(rows),
        "feature_store_path": str(_feature_store_path()),
        "controlled_build_report_path": str(report_path),
        "sample_data_used": False,
        "mock_data_used": False,
        "baseline_used": False,
        "training_invoked": False,
        "active_updated": False,
        "customer_prediction_generated": False,
    }
    return _write_json(_controlled_manifest_path(), payload)


def validate_v12_build_artifact_boundary(*, build_executed: bool = False) -> dict[str, Any]:
    feature_store_written = _feature_store_path().exists()
    manifest_written = _controlled_manifest_path().exists()
    standard_manifest_written = _standard_manifest_path().exists()
    training_dataset_written = _training_dataset_v12_path().exists()
    candidate_written = _candidate_v12_report_path().exists()
    active_absent = not _active_model_exists()
    predictions_absent = not _customer_predictions_exists()
    text = ""
    for path in (_report_path(), _controlled_manifest_path()):
        if path.exists():
            try:
                text += path.read_text(encoding="utf-8")
            except Exception:
                pass
    no_raw_token = not contains_secret_like_value(text)
    checks = {
        "feature_store_v12_csv_written": bool(feature_store_written),
        "feature_store_v12_manifest_written": bool(manifest_written),
        "standard_feature_store_manifest_not_written": not standard_manifest_written,
        "training_dataset_v12_not_written": not training_dataset_written,
        "candidate_report_not_written": not candidate_written,
        "active_model_json_absent": active_absent,
        "customer_predictions_absent": predictions_absent,
        "no_raw_token_in_artifacts": no_raw_token,
        "no_raw_managed_rows_in_report": True,
    }
    blocking: list[str] = []
    if build_executed and not feature_store_written:
        blocking.append("feature_store_v12_csv_missing_after_success")
    if build_executed and not manifest_written:
        blocking.append("controlled_manifest_missing_after_success")
    if standard_manifest_written:
        blocking.append("standard_feature_store_manifest_written")
    if training_dataset_written:
        blocking.append("training_dataset_v12_written")
    if candidate_written:
        blocking.append("candidate_v12_report_written")
    if not active_absent:
        blocking.append("active_model_json_exists")
    if not predictions_absent:
        blocking.append("customer_predictions_exists")
    if not no_raw_token:
        blocking.append("raw_token_detected_in_artifacts")
    return _safe_payload({"status": "pass" if not blocking else "violation", **checks, "blocking_reasons": blocking})


def build_v12_controlled_build_execution_report(*, build_executed: bool = False, rows: Sequence[Mapping[str, Any]] | None = None, blocking_reasons: Sequence[str] | None = None) -> dict[str, Any]:
    rows = list(rows or [])
    artifact_boundary = validate_v12_build_artifact_boundary(build_executed=build_executed)
    blocking = sorted({str(item) for item in list(blocking_reasons or []) + list(artifact_boundary.get("blocking_reasons") or []) if str(item or "").strip()})
    return _safe_payload(
        {
            "status": "success" if build_executed and not blocking else "blocked",
            "generated_at": _now(),
            "executor_version": EXECUTOR_VERSION,
            "build_executed": bool(build_executed),
            "feature_store_v12_path": str(_feature_store_path()),
            "feature_store_v12_manifest_path": str(_controlled_manifest_path()),
            "precondition_checks": [],
            "input_contract_summary": {},
            "production_cache_gate_summary": {},
            "build_plan_summary": {},
            "row_count": len(rows),
            "date_range": _date_range(rows),
            "field_coverage": _coverage(rows, V12_REQUIRED_FUNDAMENTAL_FIELDS),
            "timestamp_coverage": _coverage(rows, V12_REQUIRED_TIMESTAMP_FIELDS),
            "artifact_boundary_checks": artifact_boundary,
            "forbidden_side_effect_checks": artifact_boundary,
            "blocking_reasons": blocking,
            "warning_reasons": [] if build_executed else ["controlled_build_blocked_no_feature_store_v12_artifact_written"],
            "training_dataset_v12_triggered": False,
            "candidate_triggered": False,
            "training_invoked": False,
            "active_updated": False,
            "customer_prediction_generated": False,
            "report_path": str(_report_path()),
        }
    )


def execute_feature_store_v12_controlled_build() -> dict[str, Any]:
    run = start_research_run(
        service_name="feature_store_v12_controlled_build",
        run_type="heavy_task_blocked",
        input_paths=[
            _diagnostics_path("managed_data_production_cache_gate_report.json"),
            _diagnostics_path("feature_store_v12_input_contract_report.json"),
            _diagnostics_path("feature_store_v12_build_plan_report.json"),
            _production_cache_path(),
        ],
        output_paths=[_report_path()],
        allowed_side_effects=["write_controlled_build_report"],
        forbidden_side_effects=["active_model", "customer_prediction"],
    )
    try:
        preconditions = validate_v12_controlled_build_preconditions()
        rows: list[dict[str, Any]] = []
        build_executed = False
        if preconditions["status"] == "ready":
            rows = _rows_from_payload(_read_json(_production_cache_path()))
            if not rows:
                preconditions["blocking_reasons"] = sorted(set(list(preconditions.get("blocking_reasons") or []) + ["production_cache_rows_missing"]))
                preconditions["status"] = "blocked"
            else:
                _write_feature_store_csv(rows)
                _write_controlled_manifest(rows, _report_path())
                build_executed = True

        report = build_v12_controlled_build_execution_report(
            build_executed=build_executed,
            rows=rows,
            blocking_reasons=preconditions.get("blocking_reasons") or [],
        )
        report["precondition_checks"] = preconditions.get("precondition_checks", [])
        report["input_contract_summary"] = preconditions.get("input_contract_summary", {})
        report["production_cache_gate_summary"] = preconditions.get("production_cache_gate_summary", {})
        report["build_plan_summary"] = preconditions.get("build_plan_summary", {})
        report = _write_json(_report_path(), report)
        finalized = finalize_research_run(run, error_summary="" if build_executed else "controlled_build_blocked")
        append_run_ledger(finalized)
        return report
    except Exception as exc:
        report = build_v12_controlled_build_execution_report(build_executed=False, blocking_reasons=[f"controlled_build_exception:{type(exc).__name__}"])
        report = _write_json(_report_path(), report)
        finalized = finalize_research_run(run, error_summary=str(exc))
        append_run_ledger(finalized)
        return report


def get_latest_v12_controlled_build_report() -> dict[str, Any]:
    payload = _read_json(_report_path())
    if isinstance(payload, Mapping):
        return _safe_payload(payload)
    report = build_v12_controlled_build_execution_report(build_executed=False, blocking_reasons=["v12_controlled_build_report_missing"])
    return _safe_payload(report)
