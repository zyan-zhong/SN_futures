from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from ..api.json_utils import sanitize_for_json
from ..runtime import get_user_output_dir
from .managed_data_proxy_service import MANAGED_REQUIRED_RESEARCH_FIELDS
from .managed_proxy_setup_service import REQUIRED_TIMESTAMP_FIELDS
from .research_run_ledger_service import append_run_ledger, finalize_research_run, start_research_run


GATE_VERSION = "managed_data_production_cache_gate_v1"
GATE_REPORT_FILENAME = "managed_data_production_cache_gate_report.json"


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _output_dir() -> Path:
    return get_user_output_dir()


def _diagnostics_path(filename: str) -> Path:
    return _output_dir() / "diagnostics" / filename


def _model_research_path(filename: str) -> Path:
    return _output_dir() / "model_research" / filename


def _report_path() -> Path:
    path = _diagnostics_path(GATE_REPORT_FILENAME)
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _production_cache_path() -> Path:
    return _output_dir() / "fundamentals" / "managed_fundamentals.json"


def _feature_store_v12_path() -> Path:
    return _output_dir() / "feature_store" / "v12" / "feature_store.csv"


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


def _pass_status(payload: Any) -> bool:
    return _status(payload) in {"ready", "pass", "passed", "success", "ok", "approved"}


def _normalise_reasons(values: Any) -> list[str]:
    if not isinstance(values, list):
        return []
    return sorted({str(item) for item in values if str(item or "").strip()})


def _rows_from_payload(payload: Any) -> list[dict[str, Any]]:
    if not isinstance(payload, Mapping):
        return []
    rows = payload.get("rows") or payload.get("data") or []
    if not isinstance(rows, list):
        return []
    return [dict(row) for row in rows if isinstance(row, Mapping)]


def _date_range_from_rows(rows: list[Mapping[str, Any]]) -> dict[str, str]:
    dates = sorted(
        {
            str(row.get("feature_date") or row.get("trading_date") or row.get("date") or "").strip()
            for row in rows
            if str(row.get("feature_date") or row.get("trading_date") or row.get("date") or "").strip()
        }
    )
    return {"date_start": dates[0] if dates else "", "date_end": dates[-1] if dates else ""}


def _parse_dt(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except Exception:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def _safe_check(name: str, *, passed: bool, path: Path, reasons: list[str] | None = None, status: str | None = None) -> dict[str, Any]:
    return sanitize_for_json(
        {
            "name": name,
            "status": status or ("pass" if passed else "blocked"),
            "passed": bool(passed),
            "path": str(path),
            "blocking_reasons": sorted({reason for reason in (reasons or []) if reason}),
        }
    )


def _manual_approval_is_valid(payload: Any) -> bool:
    if not isinstance(payload, Mapping):
        return False
    if _status(payload) not in {"approved", "pass", "ready", "success"} and str(payload.get("approval_decision") or "").lower() != "approved":
        return False
    action = str(payload.get("requested_action") or "").lower()
    if action not in {"production_managed_cache_promotion", "managed_data_production_cache_promotion"}:
        return False
    if not bool(payload.get("two_person_review_pass", True)):
        return False
    expires_at = _parse_dt(payload.get("expires_at"))
    if expires_at is not None and expires_at < datetime.now(timezone.utc):
        return False
    return True


def _secret_scan_passed(payload: Any) -> bool:
    if not isinstance(payload, Mapping):
        return False
    status = _status(payload)
    if status in {"pass", "passed", "success", "ok"}:
        return True
    if payload.get("complete_key_leakage_detected") is False and int(payload.get("finding_count") or 0) == 0:
        return True
    return False


def _secret_scan_path() -> Path:
    primary = _diagnostics_path("runtime_secret_scan.json")
    if primary.exists():
        return primary
    fallback = Path("outputs") / "diagnostics" / "runtime_secret_scan.json"
    if fallback.exists():
        return fallback
    return primary


def validate_managed_cache_path_safety(path: str | Path | None = None) -> dict[str, Any]:
    candidate = Path(path) if path is not None else _production_cache_path()
    blocking: list[str] = []
    try:
        resolved = candidate.resolve()
        output_root = _output_dir().resolve()
        fundamentals_root = (_output_dir() / "fundamentals").resolve()
        if not str(resolved).startswith(str(output_root)):
            blocking.append("production_cache_path_outside_output_dir")
        if not str(resolved).startswith(str(fundamentals_root)):
            blocking.append("production_cache_path_not_under_fundamentals")
    except Exception:
        blocking.append("production_cache_path_not_resolvable")
    text = str(candidate).replace("\\", "/").lower()
    forbidden_fragments = ("customer_predictions", "feature_store", "training", "model_registry", "active_model")
    if any(fragment in text for fragment in forbidden_fragments):
        blocking.append("production_cache_path_collides_with_forbidden_output")
    if candidate.name != "managed_fundamentals.json":
        blocking.append("production_cache_filename_invalid")
    return sanitize_for_json(
        {
            "status": "pass" if not blocking else "blocked",
            "path": str(candidate),
            "blocking_reasons": sorted(set(blocking)),
        }
    )


def validate_production_cache_write_boundary() -> dict[str, Any]:
    candidate = _production_cache_path()
    return sanitize_for_json(
        {
            "status": "pass",
            "production_cache_write_allowed": False,
            "production_cache_written": False,
            "candidate_path": str(candidate),
            "production_cache_exists_before_dry_run": candidate.exists(),
            "feature_store_v12_exists": _feature_store_v12_path().exists(),
            "active_model_json_exists": _active_model_path().exists(),
            "customer_predictions_exists": _customer_predictions_path().exists(),
            "blocking_reasons": [],
        }
    )


def validate_production_cache_promotion_preconditions() -> dict[str, Any]:
    paths = {
        "endpoint_smoke": _diagnostics_path("managed_proxy_endpoint_smoke_report.json"),
        "quarantine_snapshot": _diagnostics_path("managed_proxy_quarantine_snapshot_report.json"),
        "quarantine_contract": _diagnostics_path("managed_proxy_quarantine_contract_report.json"),
        "backfill_plan": _diagnostics_path("managed_data_backfill_planner_report.json"),
        "pit_replay": _diagnostics_path("managed_pit_replay_report.json"),
        "pit_audit": _diagnostics_path("managed_data_audit_manifest.json"),
        "data_quality": _diagnostics_path("managed_data_quality_scorecard.json"),
        "evidence_freshness": _model_research_path("evidence_freshness_report.json"),
        "incident_drill": _model_research_path("incident_drill_report.json"),
        "manual_approval": _model_research_path("manual_approval_report.json"),
        "secret_scan": _secret_scan_path(),
    }
    payloads = {name: _read_json(path) for name, path in paths.items()}
    contract = payloads["quarantine_contract"]
    research_cache_path_text = str(contract.get("research_cache_path") or "").strip() if isinstance(contract, Mapping) else ""
    research_cache_path = Path(research_cache_path_text) if research_cache_path_text else None
    research_cache = _read_json(research_cache_path) if research_cache_path is not None else None
    checks: list[dict[str, Any]] = []

    smoke = payloads["endpoint_smoke"]
    smoke_pass = (
        _pass_status(smoke)
        and str(smoke.get("auth_status") or "").lower() == "pass"
        and bool(smoke.get("endpoint_reachable"))
        and str(smoke.get("response_format_status") or "").lower() == "pass"
        and str(smoke.get("token_echo_status") or "").lower() == "pass"
    ) if isinstance(smoke, Mapping) else False
    checks.append(_safe_check("endpoint_smoke_pass", passed=smoke_pass, path=paths["endpoint_smoke"], reasons=[] if smoke_pass else ["endpoint_smoke_not_passed"]))

    snapshot = payloads["quarantine_snapshot"]
    snapshot_pass = bool(isinstance(snapshot, Mapping) and _pass_status(snapshot) and snapshot.get("snapshot_pulled"))
    checks.append(_safe_check("quarantine_snapshot_pulled", passed=snapshot_pass, path=paths["quarantine_snapshot"], reasons=[] if snapshot_pass else ["quarantine_snapshot_not_pulled"]))

    contract_pass = bool(
        isinstance(contract, Mapping)
        and _pass_status(contract)
        and contract.get("research_cache_promotion_allowed")
        and contract.get("research_cache_written")
    )
    checks.append(_safe_check("quarantine_contract_pass", passed=contract_pass, path=paths["quarantine_contract"], reasons=[] if contract_pass else ["quarantine_contract_not_passed"]))

    research_cache_pass = bool(
        isinstance(research_cache, Mapping)
        and research_cache.get("research_cache")
        and not research_cache.get("production_eligible")
        and not research_cache.get("feature_store_v12_allowed")
        and not research_cache.get("sample_data_used")
        and not research_cache.get("fixture_only")
    )
    checks.append(
        _safe_check(
            "research_cache_written",
            passed=research_cache_pass,
            path=research_cache_path or paths["quarantine_contract"],
            reasons=[] if research_cache_pass else ["research_cache_missing"],
        )
    )

    backfill = payloads["backfill_plan"]
    backfill_pass = bool(isinstance(backfill, Mapping) and _pass_status(backfill))
    budget_pass = bool(backfill_pass and isinstance(backfill.get("coverage_budget"), Mapping) and backfill.get("coverage_budget"))
    checks.append(_safe_check("backfill_planner_ready", passed=backfill_pass, path=paths["backfill_plan"], reasons=[] if backfill_pass else ["backfill_planner_blocked"]))
    checks.append(_safe_check("backfill_coverage_budget_defined", passed=budget_pass, path=paths["backfill_plan"], reasons=[] if budget_pass else ["backfill_coverage_budget_missing"]))

    replay = payloads["pit_replay"]
    replay_pass = bool(isinstance(replay, Mapping) and _pass_status(replay) and replay.get("point_in_time_join_ready"))
    checks.append(_safe_check("pit_replay_pass", passed=replay_pass, path=paths["pit_replay"], reasons=[] if replay_pass else ["pit_replay_not_passed"]))

    audit = payloads["pit_audit"]
    audit_pass = bool(isinstance(audit, Mapping) and _pass_status(audit) and audit.get("v12_allowed"))
    checks.append(_safe_check("pit_audit_pass", passed=audit_pass, path=paths["pit_audit"], reasons=[] if audit_pass else ["pit_audit_not_passed"]))

    quality = payloads["data_quality"]
    quality_pass = bool(isinstance(quality, Mapping) and _pass_status(quality) and quality.get("gate_passed"))
    checks.append(_safe_check("data_quality_pass", passed=quality_pass, path=paths["data_quality"], reasons=[] if quality_pass else ["managed_data_quality_not_passed"]))

    freshness = payloads["evidence_freshness"]
    freshness_pass = bool(
        isinstance(freshness, Mapping)
        and _pass_status(freshness)
        and not freshness.get("stale_reports")
        and not freshness.get("missing_timestamps")
        and not freshness.get("timestamp_inversions")
    )
    checks.append(_safe_check("evidence_freshness_pass", passed=freshness_pass, path=paths["evidence_freshness"], reasons=[] if freshness_pass else ["evidence_freshness_not_passed"]))

    incident = payloads["incident_drill"]
    real_lockdown = incident.get("real_lockdown_state") if isinstance(incident, Mapping) and isinstance(incident.get("real_lockdown_state"), Mapping) else {}
    lockdown_pass = not bool(real_lockdown.get("lockdown_triggered"))
    checks.append(_safe_check("no_governance_lockdown", passed=lockdown_pass, path=paths["incident_drill"], reasons=[] if lockdown_pass else ["governance_lockdown_active"]))

    approval_pass = _manual_approval_is_valid(payloads["manual_approval"])
    checks.append(_safe_check("manual_approval_for_production_cache", passed=approval_pass, path=paths["manual_approval"], reasons=[] if approval_pass else ["manual_approval_missing_or_not_approved"]))

    secret_pass = _secret_scan_passed(payloads["secret_scan"])
    checks.append(_safe_check("secret_scan_pass", passed=secret_pass, path=paths["secret_scan"], reasons=[] if secret_pass else ["secret_scan_not_passed"]))

    blocking = sorted({reason for check in checks for reason in check.get("blocking_reasons", []) if reason})
    return sanitize_for_json(
        {
            "status": "ready" if not blocking else "blocked",
            "precondition_checks": checks,
            "blocking_reasons": blocking,
            "linked_research_cache_path": str(research_cache_path) if research_cache_path is not None else "",
            "linked_backfill_plan_path": str(paths["backfill_plan"]),
            "linked_pit_replay_path": str(paths["pit_replay"]),
            "linked_audit_path": str(paths["pit_audit"]),
            "linked_quality_path": str(paths["data_quality"]),
            "linked_manual_approval_path": str(paths["manual_approval"]),
        }
    )


def _research_cache_summary(path_text: str) -> dict[str, Any]:
    payload = _read_json(Path(path_text)) if path_text else None
    rows = _rows_from_payload(payload)
    explicit_range = payload.get("date_range") if isinstance(payload, Mapping) and isinstance(payload.get("date_range"), Mapping) else {}
    date_range = {
        "date_start": explicit_range.get("date_start") or _date_range_from_rows(rows).get("date_start", ""),
        "date_end": explicit_range.get("date_end") or _date_range_from_rows(rows).get("date_end", ""),
    }
    return sanitize_for_json(
        {
            "path": path_text,
            "exists": Path(path_text).exists() if path_text else False,
            "row_count": int(payload.get("row_count") or len(rows)) if isinstance(payload, Mapping) else 0,
            "date_range": date_range,
            "production_eligible": bool(payload.get("production_eligible")) if isinstance(payload, Mapping) else False,
            "feature_store_v12_allowed": bool(payload.get("feature_store_v12_allowed")) if isinstance(payload, Mapping) else False,
            "sample_data_used": bool(payload.get("sample_data_used")) if isinstance(payload, Mapping) else False,
            "fixture_only": bool(payload.get("fixture_only")) if isinstance(payload, Mapping) else False,
        }
    )


def _human_approval_checklist() -> list[str]:
    return [
        "verify endpoint/token configured securely",
        "verify PIT audit pass",
        "verify data quality pass",
        "verify no secret leakage",
        "verify research cache is not sample fixture",
        "verify backfill coverage budget satisfied",
        "verify rollback plan available",
    ]


def _rollback_plan() -> list[str]:
    return [
        "keep prior production managed cache snapshot before any future write",
        "delete newly written production cache if post-write validation fails",
        "rerun PIT audit, data quality, evidence freshness and secret scan",
        "refresh decision board and keep Feature Store v12 blocked until validation passes",
    ]


def build_production_cache_promotion_dry_run() -> dict[str, Any]:
    preconditions = validate_production_cache_promotion_preconditions()
    cache_summary = _research_cache_summary(str(preconditions.get("linked_research_cache_path") or ""))
    plan = {
        "status": "ready" if preconditions.get("status") == "ready" else "blocked",
        "source_research_cache_path": cache_summary["path"],
        "candidate_production_cache_path": str(_production_cache_path()),
        "expected_row_count": cache_summary["row_count"],
        "expected_date_range": cache_summary["date_range"],
        "required_fields": list(MANAGED_REQUIRED_RESEARCH_FIELDS),
        "required_timestamp_fields": list(REQUIRED_TIMESTAMP_FIELDS),
        "validation_commands": [
            "python -m compileall -q .",
            "pytest -q tests/test_feature_store_v12_*.py",
            ".\\scripts\\scan_runtime_secrets.ps1",
        ],
        "rollback_actions": _rollback_plan(),
        "explicit_note": "No write performed. Research cache is not production cache.",
        "production_cache_written": False,
        "feature_store_v12_allowed": False,
    }
    return sanitize_for_json(plan)


def _base_payload() -> dict[str, Any]:
    return {
        "status": "blocked",
        "generated_at": _now(),
        "gate_version": GATE_VERSION,
        "production_cache_write_allowed": False,
        "production_cache_written": False,
        "production_cache_path_candidate": str(_production_cache_path()),
        "production_cache_path_safety": validate_managed_cache_path_safety(),
        "precondition_checks": [],
        "linked_research_cache_path": "",
        "linked_backfill_plan_path": str(_diagnostics_path("managed_data_backfill_planner_report.json")),
        "linked_pit_replay_path": str(_diagnostics_path("managed_pit_replay_report.json")),
        "linked_audit_path": str(_diagnostics_path("managed_data_audit_manifest.json")),
        "linked_quality_path": str(_diagnostics_path("managed_data_quality_scorecard.json")),
        "linked_manual_approval_path": str(_model_research_path("manual_approval_report.json")),
        "dry_run_plan": {},
        "human_approval_checklist": _human_approval_checklist(),
        "rollback_plan": _rollback_plan(),
        "feature_store_v12_allowed": False,
        "blocking_reasons": [],
        "warning_reasons": [],
        "training_invoked": False,
        "active_updated": False,
        "customer_prediction_generated": False,
        "report_path": str(_report_path()),
    }


def build_production_cache_gate_report() -> dict[str, Any]:
    run = start_research_run(
        service_name="managed_data_production_cache_gate",
        run_type="report_write",
        input_paths=[
            _diagnostics_path("managed_proxy_endpoint_smoke_report.json"),
            _diagnostics_path("managed_proxy_quarantine_contract_report.json"),
            _diagnostics_path("managed_data_backfill_planner_report.json"),
            _diagnostics_path("managed_pit_replay_report.json"),
            _diagnostics_path("managed_data_audit_manifest.json"),
            _diagnostics_path("managed_data_quality_scorecard.json"),
            _model_research_path("manual_approval_report.json"),
        ],
        output_paths=[_report_path()],
    )
    try:
        preconditions = validate_production_cache_promotion_preconditions()
        path_safety = validate_managed_cache_path_safety()
        boundary = validate_production_cache_write_boundary()
        dry_run = build_production_cache_promotion_dry_run()
        blocking = list(preconditions.get("blocking_reasons") or []) + list(path_safety.get("blocking_reasons") or [])
        payload = _base_payload()
        payload.update(
            {
                "status": "ready" if not blocking else "blocked",
                "generated_at": _now(),
                "production_cache_path_safety": path_safety,
                "precondition_checks": preconditions.get("precondition_checks", []),
                "linked_research_cache_path": preconditions.get("linked_research_cache_path", ""),
                "linked_backfill_plan_path": preconditions.get("linked_backfill_plan_path", ""),
                "linked_pit_replay_path": preconditions.get("linked_pit_replay_path", ""),
                "linked_audit_path": preconditions.get("linked_audit_path", ""),
                "linked_quality_path": preconditions.get("linked_quality_path", ""),
                "linked_manual_approval_path": preconditions.get("linked_manual_approval_path", ""),
                "dry_run_plan": dry_run,
                "write_boundary": boundary,
                "blocking_reasons": sorted({reason for reason in blocking if reason}),
                "warning_reasons": ["dry_run_only_no_production_cache_write_performed", "research cache is not production cache"],
                "production_cache_write_allowed": False,
                "production_cache_written": False,
                "feature_store_v12_allowed": False,
                "training_invoked": False,
                "active_updated": False,
                "customer_prediction_generated": False,
            }
        )
        report = _write_json(_report_path(), payload)
        append_run_ledger(finalize_research_run(run))
        return report
    except Exception as exc:
        append_run_ledger(finalize_research_run(run, error_summary=str(exc)))
        raise


def get_latest_production_cache_gate_report() -> dict[str, Any]:
    payload = _read_json(_report_path())
    if isinstance(payload, Mapping):
        return sanitize_for_json(dict(payload))
    base = _base_payload()
    base["blocking_reasons"] = ["production_cache_gate_report_missing"]
    return sanitize_for_json(base)
