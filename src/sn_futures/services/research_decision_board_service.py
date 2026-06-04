from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Mapping

from ..api.json_utils import sanitize_for_json
from ..runtime import get_user_output_dir
from .evidence_freshness_service import attach_freshness_to_decision_board, get_evidence_freshness_report


BOARD_FILENAME = "research_decision_board.json"


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _output_dir() -> Path:
    return get_user_output_dir()


def _board_path() -> Path:
    path = _output_dir() / "model_research" / BOARD_FILENAME
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _governance_observability_path() -> Path:
    return _output_dir() / "model_research" / "governance_observability_report.json"


def _incident_drill_path() -> Path:
    return _output_dir() / "model_research" / "incident_drill_report.json"


def _manual_approval_path() -> Path:
    return _output_dir() / "model_research" / "manual_approval_report.json"


def _read_json(path: Path) -> Any:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _write_json(path: Path, payload: Mapping[str, Any]) -> dict[str, Any]:
    safe = sanitize_for_json(dict(payload))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(safe, ensure_ascii=False, indent=2), encoding="utf-8")
    return safe


def _safe_float(value: Any, default: float | None = None) -> float | None:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return default
    return parsed if parsed == parsed and parsed not in {float("inf"), float("-inf")} else default


def _normalise_reasons(reasons: Iterable[Any]) -> list[str]:
    return sorted({str(reason) for reason in reasons if str(reason or "").strip()})


def _split_reasons(values: Iterable[Any]) -> list[str]:
    out: list[str] = []
    for value in values:
        for item in str(value or "").split(";"):
            item = item.strip()
            if item:
                out.append(item)
    return out


def _dedupe_preserve_order(values: Iterable[Any]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        text = str(value or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        out.append(text)
    return out


def _nested(payload: Mapping[str, Any], *keys: str) -> Any:
    current: Any = payload
    for key in keys:
        if not isinstance(current, Mapping):
            return None
        current = current.get(key)
    return current


def _paths() -> dict[str, Path]:
    out = _output_dir()
    return {
        "managed_proxy_operator_runbook": out / "diagnostics" / "managed_proxy_operator_runbook_report.json",
        "managed_proxy_config_wizard": out / "diagnostics" / "managed_proxy_config_wizard_report.json",
        "managed_proxy_setup": out / "diagnostics" / "managed_proxy_setup_report.json",
        "managed_proxy_endpoint_smoke": out / "diagnostics" / "managed_proxy_endpoint_smoke_report.json",
        "managed_proxy_quarantine_snapshot": out / "diagnostics" / "managed_proxy_quarantine_snapshot_report.json",
        "managed_proxy_quarantine_contract": out / "diagnostics" / "managed_proxy_quarantine_contract_report.json",
        "managed_data_backfill_plan": out / "diagnostics" / "managed_data_backfill_planner_report.json",
        "managed_data_production_cache_gate": out / "diagnostics" / "managed_data_production_cache_gate_report.json",
        "feature_store_v12_build_plan": out / "diagnostics" / "feature_store_v12_build_plan_report.json",
        "feature_store_v12_controlled_build": out / "diagnostics" / "feature_store_v12_controlled_build_report.json",
        "managed_proxy_schema_mapping": out / "diagnostics" / "managed_proxy_schema_mapping_report.json",
        "managed_proxy_health": out / "diagnostics" / "managed_proxy_health.json",
        "managed_proxy_reliability": out / "diagnostics" / "managed_proxy_reliability_report.json",
        "managed_data_quality": out / "diagnostics" / "managed_data_quality_scorecard.json",
        "managed_data_audit": out / "diagnostics" / "managed_data_audit_manifest.json",
        "feature_store_v12_manifest": out / "feature_store" / "v12" / "feature_store_manifest.json",
        "training_dataset_v12_manifest": out / "training_dataset_manifest_v12.json",
        "candidate_v10_report": out / "model_research" / "candidate_v10" / "candidate_v10_gated_research_report.json",
        "candidate_v12_report": out / "model_research" / "candidate_v12" / "candidate_v12_gated_research_report.json",
        "year_concentration_evidence": out / "model_research" / "year_concentration_evidence.json",
        "cost_stress_attribution": out / "model_research" / "cost_stress_attribution.json",
        "cpcv_report": out / "validation" / "cpcv" / "cpcv_report.json",
        "promotion_dry_run_evidence": out / "model_research" / "promotion_dry_run_evidence_report.json",
        "shadow_replay": out / "model_research" / "shadow_replay_report.json",
        "post_release_monitoring_spec": out / "model_research" / "post_release_monitoring_spec_report.json",
        "rollback_rehearsal": out / "model_research" / "rollback_rehearsal_report.json",
        "governance_maturity_matrix": out / "model_research" / "governance_maturity_matrix.json",
        "model_card": out / "model_research" / "model_card.json",
    }


def _manifest_entry(name: str, path: Path) -> dict[str, Any]:
    payload = _read_json(path)
    if not isinstance(payload, Mapping):
        return {"name": name, "path": str(path), "exists": path.exists(), "payload": {}, "issue": "missing"}
    issue = ""
    if "status" not in payload and name not in {"year_concentration_evidence", "cost_stress_attribution"}:
        issue = "incomplete"
    return {"name": name, "path": str(path), "exists": True, "payload": dict(payload), "issue": issue}


def collect_latest_manifests() -> dict[str, Any]:
    entries = {name: _manifest_entry(name, path) for name, path in _paths().items()}
    stale_or_missing = [
        f"{name}:{entry['issue']}"
        for name, entry in entries.items()
        if entry.get("issue")
    ]
    evidence_paths = {
        name: entry["path"]
        for name, entry in entries.items()
        if entry.get("exists") and not entry.get("issue") == "missing"
    }
    return {
        "entries": entries,
        "stale_or_missing_reports": stale_or_missing,
        "evidence_paths": evidence_paths,
    }


def collect_governance_observability_evidence() -> dict[str, Any]:
    path = _governance_observability_path()
    payload = _read_json(path)
    if not isinstance(payload, Mapping):
        return sanitize_for_json(
            {
                "status": "missing",
                "exists": path.exists(),
                "slo_status": "missing",
                "secret_scan_status": "missing",
                "error_budget_status": "missing",
                "blocking_reasons": [],
                "report_path": str(path),
            }
        )
    slo = payload.get("slo_results") if isinstance(payload.get("slo_results"), Mapping) else {}
    telemetry = payload.get("telemetry_summary") if isinstance(payload.get("telemetry_summary"), Mapping) else {}
    budget = payload.get("error_budget") if isinstance(payload.get("error_budget"), Mapping) else {}
    return sanitize_for_json(
        {
            "status": payload.get("status", "missing"),
            "exists": True,
            "slo_status": slo.get("status", payload.get("status", "missing")),
            "secret_scan_status": telemetry.get("secret_scan_status", "missing"),
            "safe_check_success_rate": telemetry.get("safe_check_success_rate"),
            "p95_latency_ms": telemetry.get("p95_latency_ms"),
            "stale_report_count": telemetry.get("stale_report_count"),
            "forbidden_action_violation_count": telemetry.get("forbidden_action_violation_count"),
            "error_budget_status": budget.get("status", "missing"),
            "blocking_reasons": list(payload.get("blocking_reasons") or []),
            "report_path": payload.get("report_path") or str(path),
        }
    )


def collect_governance_lockdown_evidence() -> dict[str, Any]:
    path = _incident_drill_path()
    payload = _read_json(path)
    if not isinstance(payload, Mapping):
        return sanitize_for_json(
            {
                "status": "missing",
                "exists": path.exists(),
                "lockdown_triggered": False,
                "lockdown_reasons": [],
                "manual_unlock_required": False,
                "report_path": str(path),
            }
        )
    real_state = payload.get("real_lockdown_state") if isinstance(payload.get("real_lockdown_state"), Mapping) else {}
    lockdown = bool(real_state.get("lockdown_triggered"))
    reasons = list(real_state.get("lockdown_reasons") or payload.get("lockdown_reasons") or [])
    return sanitize_for_json(
        {
            "status": payload.get("status", "missing"),
            "exists": True,
            "lockdown_triggered": lockdown,
            "lockdown_reasons": reasons,
            "manual_unlock_required": bool(real_state.get("manual_unlock_required")) if real_state else lockdown,
            "simulated_artifacts_only": bool(payload.get("simulated_artifacts_only", True)),
            "report_path": payload.get("report_path") or str(path),
        }
    )


def collect_manual_approval_evidence() -> dict[str, Any]:
    path = _manual_approval_path()
    payload = _read_json(path)
    if not isinstance(payload, Mapping):
        return sanitize_for_json(
            {
                "status": "missing",
                "exists": path.exists(),
                "approval_request_allowed": False,
                "requested_action": "shadow_mode_only",
                "two_person_review_pass": False,
                "active_write_allowed": False,
                "customer_prediction_write_allowed": False,
                "blocking_reasons": [],
                "report_path": str(path),
            }
        )
    return sanitize_for_json(
        {
            "status": payload.get("status", "missing"),
            "exists": True,
            "approval_request_allowed": bool(payload.get("approval_request_allowed")),
            "requested_action": payload.get("requested_action", "shadow_mode_only"),
            "approval_decision": payload.get("approval_decision", "none"),
            "reviewer_count": payload.get("reviewer_count", 0),
            "two_person_review_pass": bool(payload.get("two_person_review_pass")),
            "expires_at": payload.get("expires_at", ""),
            "active_write_allowed": False,
            "customer_prediction_write_allowed": False,
            "blocking_reasons": list(payload.get("blocking_reasons") or []),
            "warning_reasons": list(payload.get("warning_reasons") or []),
            "report_path": payload.get("report_path") or str(path),
        }
    )


def _status(payload: Mapping[str, Any]) -> str:
    return str(payload.get("status") or "missing").lower()


def _ready(payload: Mapping[str, Any]) -> bool:
    return bool(payload.get("ready") or payload.get("v12_allowed") or _status(payload) in {"ready", "success", "pass"})


def collect_data_readiness_evidence(manifests: Mapping[str, Any]) -> dict[str, Any]:
    entries = manifests.get("entries") if isinstance(manifests.get("entries"), Mapping) else {}
    operator_entry = entries.get("managed_proxy_operator_runbook", {}) if isinstance(entries.get("managed_proxy_operator_runbook"), Mapping) else {}
    operator = operator_entry.get("payload", {}) if isinstance(operator_entry, Mapping) else {}
    wizard = entries.get("managed_proxy_config_wizard", {}).get("payload", {}) if isinstance(entries.get("managed_proxy_config_wizard"), Mapping) else {}
    setup = entries.get("managed_proxy_setup", {}).get("payload", {}) if isinstance(entries.get("managed_proxy_setup"), Mapping) else {}
    endpoint_smoke_entry = entries.get("managed_proxy_endpoint_smoke", {}) if isinstance(entries.get("managed_proxy_endpoint_smoke"), Mapping) else {}
    endpoint_smoke = endpoint_smoke_entry.get("payload", {}) if isinstance(endpoint_smoke_entry, Mapping) else {}
    quarantine_snapshot_entry = entries.get("managed_proxy_quarantine_snapshot", {}) if isinstance(entries.get("managed_proxy_quarantine_snapshot"), Mapping) else {}
    quarantine_snapshot = quarantine_snapshot_entry.get("payload", {}) if isinstance(quarantine_snapshot_entry, Mapping) else {}
    quarantine_contract_entry = entries.get("managed_proxy_quarantine_contract", {}) if isinstance(entries.get("managed_proxy_quarantine_contract"), Mapping) else {}
    quarantine_contract = quarantine_contract_entry.get("payload", {}) if isinstance(quarantine_contract_entry, Mapping) else {}
    backfill_plan_entry = entries.get("managed_data_backfill_plan", {}) if isinstance(entries.get("managed_data_backfill_plan"), Mapping) else {}
    backfill_plan = backfill_plan_entry.get("payload", {}) if isinstance(backfill_plan_entry, Mapping) else {}
    production_cache_gate_entry = entries.get("managed_data_production_cache_gate", {}) if isinstance(entries.get("managed_data_production_cache_gate"), Mapping) else {}
    production_cache_gate = production_cache_gate_entry.get("payload", {}) if isinstance(production_cache_gate_entry, Mapping) else {}
    schema_mapping_entry = entries.get("managed_proxy_schema_mapping", {}) if isinstance(entries.get("managed_proxy_schema_mapping"), Mapping) else {}
    schema_mapping = schema_mapping_entry.get("payload", {}) if isinstance(schema_mapping_entry, Mapping) else {}
    health = entries.get("managed_proxy_health", {}).get("payload", {}) if isinstance(entries.get("managed_proxy_health"), Mapping) else {}
    reliability_entry = entries.get("managed_proxy_reliability", {}) if isinstance(entries.get("managed_proxy_reliability"), Mapping) else {}
    reliability = reliability_entry.get("payload", {}) if isinstance(reliability_entry, Mapping) else {}
    quality_entry = entries.get("managed_data_quality", {}) if isinstance(entries.get("managed_data_quality"), Mapping) else {}
    quality = quality_entry.get("payload", {}) if isinstance(quality_entry, Mapping) else {}
    audit = entries.get("managed_data_audit", {}).get("payload", {}) if isinstance(entries.get("managed_data_audit"), Mapping) else {}
    fs = entries.get("feature_store_v12_manifest", {}).get("payload", {}) if isinstance(entries.get("feature_store_v12_manifest"), Mapping) else {}
    td = entries.get("training_dataset_v12_manifest", {}).get("payload", {}) if isinstance(entries.get("training_dataset_v12_manifest"), Mapping) else {}

    operator_exists = bool(operator_entry.get("exists")) and isinstance(operator, Mapping) and bool(operator)
    operator_ready = (not operator_exists) or _status(operator) in {"ready", "ready_with_missing_config", "success", "pass"}
    wizard_ready = _status(wizard) in {"ready", "success", "pass"}
    setup_ready = operator_ready and wizard_ready and (_status(setup) in {"ready", "success", "pass"} or bool(setup.get("managed_proxy_health_allowed")))
    endpoint_smoke_exists = bool(endpoint_smoke_entry.get("exists")) and isinstance(endpoint_smoke, Mapping) and bool(endpoint_smoke)
    endpoint_smoke_ready = _status(endpoint_smoke) in {"pass", "ready", "success"}
    quarantine_snapshot_exists = bool(quarantine_snapshot_entry.get("exists")) and isinstance(quarantine_snapshot, Mapping) and bool(quarantine_snapshot)
    quarantine_snapshot_ready = bool(quarantine_snapshot.get("snapshot_pulled")) and _status(quarantine_snapshot) in {"ready", "success", "pass"}
    quarantine_contract_exists = bool(quarantine_contract_entry.get("exists")) and isinstance(quarantine_contract, Mapping) and bool(quarantine_contract)
    quarantine_contract_ready = _status(quarantine_contract) in {"ready", "success", "pass"} and bool(quarantine_contract.get("research_cache_promotion_allowed"))
    backfill_plan_exists = bool(backfill_plan_entry.get("exists")) and isinstance(backfill_plan, Mapping) and bool(backfill_plan)
    backfill_plan_ready = _status(backfill_plan) in {"ready", "success", "pass"}
    production_cache_gate_exists = bool(production_cache_gate_entry.get("exists")) and isinstance(production_cache_gate, Mapping) and bool(production_cache_gate)
    production_cache_gate_ready = _status(production_cache_gate) in {"ready", "success", "pass"}
    schema_mapping_exists = bool(schema_mapping_entry.get("exists")) and isinstance(schema_mapping, Mapping) and bool(schema_mapping)
    schema_mapping_ready = bool(schema_mapping.get("schema_mapping_ready")) or _status(schema_mapping) in {"ready", "success", "pass"}
    schema_mapping_gate_ready = (not schema_mapping_exists) or schema_mapping_ready
    reliability_exists = bool(reliability_entry.get("exists")) and isinstance(reliability, Mapping) and bool(reliability)
    reliability_ready = (not reliability_exists) or _status(reliability) in {"ready", "success", "pass"}
    quality_exists = bool(quality_entry.get("exists")) and isinstance(quality, Mapping) and bool(quality)
    quality_ready = (not quality_exists) or bool(quality.get("gate_passed")) or _status(quality) in {"ready", "success", "pass", "warning"}
    managed_ready = setup_ready and schema_mapping_gate_ready and _ready(health) and reliability_ready and quality_ready
    audit_ready = _ready(audit)
    fs_ready = _status(fs) in {"ready", "success"} and bool(fs.get("no_lookahead_pass")) and bool(fs.get("point_in_time_join_ready"))
    td_ready = _status(td) in {"ready", "success"} and bool(td.get("leakage_check_pass", td.get("no_lookahead_pass")))
    return {
        "managed_proxy_summary": {
            "wizard_status": wizard.get("status", "missing"),
            "setup_status": setup.get("status", "missing"),
            "endpoint_smoke_status": endpoint_smoke.get("status", "missing"),
            "endpoint_smoke_auth_status": endpoint_smoke.get("auth_status", "not_run"),
            "endpoint_smoke_next_allowed_action": endpoint_smoke.get("next_allowed_action")
            or ("run_managed_proxy_health" if endpoint_smoke_ready else "run_managed_proxy_endpoint_smoke"),
            "endpoint_smoke_exists": bool(endpoint_smoke_exists),
            "endpoint_smoke_ready": bool(endpoint_smoke_ready),
            "quarantine_snapshot_status": quarantine_snapshot.get("status", "missing"),
            "quarantine_snapshot_exists": bool(quarantine_snapshot_exists),
            "quarantine_snapshot_pulled": bool(quarantine_snapshot_ready),
            "quarantine_snapshot_next_allowed_action": "run_quarantine_contract_tests" if quarantine_snapshot_ready else "",
            "quarantine_snapshot_blocking_reasons": list(
                quarantine_snapshot.get("blocking_reasons") or ([] if quarantine_snapshot_ready or not quarantine_snapshot_exists else ["quarantine_snapshot_blocked"])
            ),
            "quarantine_contract_status": quarantine_contract.get("status", "missing"),
            "quarantine_contract_exists": bool(quarantine_contract_exists),
            "quarantine_contract_ready": bool(quarantine_contract_ready),
            "quarantine_contract_schema_status": quarantine_contract.get("schema_contract_status", "missing"),
            "quarantine_contract_pit_replay_status": quarantine_contract.get("pit_replay_status", "missing"),
            "quarantine_contract_pit_audit_status": quarantine_contract.get("pit_audit_status", "missing"),
            "quarantine_contract_data_quality_status": quarantine_contract.get("data_quality_status", "missing"),
            "research_cache_promotion_allowed": bool(quarantine_contract.get("research_cache_promotion_allowed")),
            "research_cache_written": bool(quarantine_contract.get("research_cache_written")),
            "quarantine_contract_blocking_reasons": list(
                quarantine_contract.get("blocking_reasons") or ([] if quarantine_contract_ready or not quarantine_contract_exists else ["quarantine_contract_blocked"])
            ),
            "backfill_plan_status": backfill_plan.get("status", "missing"),
            "backfill_plan_exists": bool(backfill_plan_exists),
            "backfill_plan_ready": bool(backfill_plan_ready),
            "backfill_plan_production_cache_write_allowed": bool(backfill_plan.get("production_cache_write_allowed")),
            "backfill_plan_feature_store_v12_allowed": bool(backfill_plan.get("feature_store_v12_allowed")),
            "backfill_plan_rows_fetched": bool(backfill_plan.get("rows_fetched")),
            "backfill_plan_blocking_reasons": list(
                backfill_plan.get("blocking_reasons") or ([] if backfill_plan_ready or not backfill_plan_exists else ["backfill_plan_missing_or_blocked"])
            ),
            "backfill_plan_next_allowed_action": "review_real_managed_data_backfill_plan" if backfill_plan_ready else "run_real_managed_data_backfill_planner",
            "production_cache_gate_status": production_cache_gate.get("status", "missing"),
            "production_cache_gate_exists": bool(production_cache_gate_exists),
            "production_cache_gate_ready": bool(production_cache_gate_ready),
            "production_cache_write_allowed": bool(production_cache_gate.get("production_cache_write_allowed")),
            "production_cache_written": bool(production_cache_gate.get("production_cache_written")),
            "production_cache_gate_feature_store_v12_allowed": bool(production_cache_gate.get("feature_store_v12_allowed")),
            "production_cache_gate_blocking_reasons": list(
                production_cache_gate.get("blocking_reasons") or ([] if production_cache_gate_ready or not production_cache_gate_exists else ["production_cache_gate_missing_or_blocked"])
            ),
            "production_cache_gate_next_allowed_action": "review_production_cache_dry_run_plan" if production_cache_gate_ready else "run_production_cache_promotion_gate",
            "schema_mapping_status": schema_mapping.get("status", "missing"),
            "schema_mapping_ready": bool(schema_mapping_ready),
            "schema_mapping_exists": bool(schema_mapping_exists),
            "status": health.get("status", "missing"),
            "provider_status": health.get("provider_status", "missing"),
            "reliability_status": reliability.get("status", "missing"),
            "canary_status": reliability.get("canary_status", "missing"),
            "circuit_breaker_status": reliability.get("circuit_breaker_status", "missing"),
            "schema_drift_status": reliability.get("schema_drift_status", "missing"),
            "cache_staleness_status": reliability.get("cache_staleness_status", "missing"),
            "reliability_exists": bool(reliability_exists),
            "quality_status": quality.get("status", "missing"),
            "quality_score": quality.get("quality_score"),
            "quality_gate_passed": bool(quality.get("gate_passed")) if quality_exists else False,
            "quality_exists": bool(quality_exists),
            "configured": bool(health.get("configured")),
            "enabled": bool(health.get("enabled")),
            "v12_allowed": managed_ready,
            "operator_runbook_status": operator.get("status", "missing"),
            "operator_runbook_ready": bool(operator_ready),
            "operator_runbook_blocking_reasons": list(operator.get("blocking_reasons") or ([] if operator_ready else ["managed_proxy_operator_runbook_missing"])),
            "operator_runbook_next_allowed_action": operator.get("next_allowed_action"),
            "wizard_blocking_reasons": list(wizard.get("blocking_reasons") or ([] if wizard_ready else ["managed_proxy_config_wizard_missing"])),
            "setup_blocking_reasons": list(setup.get("blocking_reasons") or ([] if setup_ready else ["managed_proxy_setup_missing"])),
            "endpoint_smoke_blocking_reasons": list(endpoint_smoke.get("blocking_reasons") or ([] if endpoint_smoke_ready else ["managed_proxy_endpoint_smoke_missing"])),
            "schema_mapping_blocking_reasons": list(schema_mapping.get("blocking_reasons") or ([] if schema_mapping_gate_ready else ["managed_proxy_schema_mapping_missing"])),
            "reliability_blocking_reasons": list(reliability.get("blocking_reasons") or ([] if reliability_ready else ["managed_proxy_reliability_missing"])),
            "quality_blocking_reasons": list(quality.get("blocking_reasons") or ([] if quality_ready else ["managed_data_quality_missing"])),
            "quality_warning_reasons": list(quality.get("warning_reasons") or []),
            "blocking_reasons": list(health.get("blocking_reasons") or ([] if _ready(health) else ["managed_proxy_health_missing"])),
            "wizard_next_allowed_action": wizard.get("next_allowed_action"),
            "schema_mapping_next_allowed_action": "fix_managed_proxy_schema_mapping" if schema_mapping_exists and not schema_mapping_ready else "",
            "reliability_next_allowed_action": reliability.get("next_allowed_action") if reliability_exists and not reliability_ready else "",
            "quality_next_allowed_action": "fix_managed_data_quality" if quality_exists and not quality_ready else "",
            "next_allowed_action": setup.get("next_allowed_action") or health.get("next_allowed_action", "configure_managed_proxy"),
        },
        "pit_audit_summary": {
            "status": audit.get("status", "missing"),
            "v12_allowed": audit_ready,
            "blocking_reasons": list(audit.get("blocking_reasons") or ([] if audit_ready else ["managed_audit_missing"])),
            "leakage_checks": audit.get("leakage_checks") if isinstance(audit.get("leakage_checks"), Mapping) else {},
        },
        "feature_store_v12_summary": {
            "status": fs.get("status", "missing"),
            "training_dataset_v12_allowed": fs_ready,
            "no_lookahead_pass": bool(fs.get("no_lookahead_pass")),
            "point_in_time_join_ready": bool(fs.get("point_in_time_join_ready")),
            "blocking_reasons": list(fs.get("blocking_reasons") or ([] if fs_ready else ["feature_store_v12_manifest_missing"])),
        },
        "training_dataset_v12_summary": {
            "status": td.get("status", "missing"),
            "candidate_v12_allowed": td_ready,
            "feature_store_status": td.get("feature_store_status", "missing"),
            "leakage_check_pass": bool(td.get("leakage_check_pass") or td.get("no_lookahead_pass")),
            "blocking_reasons": list(td.get("blocking_reasons") or td.get("blocked_reasons") or ([] if td_ready else ["training_dataset_v12_manifest_missing"])),
        },
        "managed_operator_runbook_ready": operator_ready,
        "managed_wizard_ready": wizard_ready,
        "managed_setup_ready": setup_ready,
        "managed_ready": managed_ready,
        "audit_ready": audit_ready,
        "feature_store_ready": fs_ready,
        "training_dataset_ready": td_ready,
    }


def _worst(table: Mapping[str, Any], key: str) -> Any:
    rows = table.get("rows") if isinstance(table, Mapping) else None
    if not isinstance(rows, list) or not rows:
        return None
    worst = min((row for row in rows if isinstance(row, Mapping)), key=lambda row: _safe_float(row.get("net_expectancy_3x"), 0.0) or 0.0)
    return worst.get(key)


def collect_candidate_gate_evidence(manifests: Mapping[str, Any]) -> dict[str, Any]:
    entries = manifests.get("entries") if isinstance(manifests.get("entries"), Mapping) else {}
    v10 = entries.get("candidate_v10_report", {}).get("payload", {}) if isinstance(entries.get("candidate_v10_report"), Mapping) else {}
    v12 = entries.get("candidate_v12_report", {}).get("payload", {}) if isinstance(entries.get("candidate_v12_report"), Mapping) else {}

    year = v10.get("year_concentration_evidence") if isinstance(v10.get("year_concentration_evidence"), Mapping) else {}
    cost = v10.get("cost_stress_attribution") if isinstance(v10.get("cost_stress_attribution"), Mapping) else {}
    v10_gates = v10.get("v10_gate_checks") if isinstance(v10.get("v10_gate_checks"), Mapping) else {}
    cpcv = v10.get("cpcv_validation") if isinstance(v10.get("cpcv_validation"), Mapping) else {}
    cpcv_reality = cpcv.get("reality_check") if isinstance(cpcv.get("reality_check"), Mapping) else {}
    cpcv_pbo = cpcv.get("pbo") if isinstance(cpcv.get("pbo"), Mapping) else {}

    v12_year = v12.get("year_concentration_evidence") if isinstance(v12.get("year_concentration_evidence"), Mapping) else {}
    v12_cost = v12.get("cost_stress_attribution") if isinstance(v12.get("cost_stress_attribution"), Mapping) else {}
    v12_readiness = v12.get("readiness_checks") if isinstance(v12.get("readiness_checks"), Mapping) else {}

    v10_pbo = _safe_float(v10_gates.get("pbo"), _safe_float(cpcv_pbo.get("pbo"), None))
    v10_reality = cpcv_reality.get("aggregate_p_value") or _nested(v10, "institutional_validation", "reality_check", "p_value")
    return {
        "candidate_v10_summary": {
            "candidate_version": v10.get("candidate_version", "v10"),
            "status": v10.get("status", "missing"),
            "pbo": v10_pbo,
            "reality_check": v10_reality,
            "year_evidence_status": year.get("status", "missing"),
            "cost_attribution_status": cost.get("status", "missing"),
            "main_cost_failure_drivers": list(cost.get("failure_drivers") or []),
            "worst_horizon": _worst(cost.get("by_horizon") if isinstance(cost.get("by_horizon"), Mapping) else {}, "horizon"),
            "worst_regime": _worst(cost.get("by_regime") if isinstance(cost.get("by_regime"), Mapping) else {}, "regime_label"),
            "worst_year": _worst(cost.get("by_year") if isinstance(cost.get("by_year"), Mapping) else {}, "year"),
            "manual_approval_recommended": bool(v10.get("manual_approval_recommended")),
            "pbo_pass": bool(v10_gates.get("pbo_lt_0_2", True)) if v10_gates else False,
            "reality_check_pass": bool(v10_gates.get("reality_check_pass", True)) if v10_gates else False,
            "year_evidence_pass": bool(year.get("status") == "pass" and year.get("passed") is True),
            "cost_attribution_pass": bool(cost.get("status") == "pass" and cost.get("passed") is True),
        },
        "candidate_v12_summary": {
            "candidate_version": v12.get("candidate_version", "v12"),
            "status": v12.get("status", "missing"),
            "training_dataset_status": v12.get("training_dataset_status", "missing"),
            "feature_store_status": v12.get("feature_store_status", "missing"),
            "readiness_checks": dict(v12_readiness),
            "year_evidence_status": v12_year.get("status", "missing"),
            "cost_attribution_status": v12_cost.get("status", "missing"),
            "skipped_reasons": _dedupe_preserve_order(
                _split_reasons(
                    [
                        *(v12.get("blocking_reasons") or []),
                        v12_year.get("skipped_reason"),
                        v12_cost.get("skipped_reason"),
                    ]
                )
            ),
            "manual_approval_recommended": bool(v12.get("manual_approval_recommended")),
        },
    }


def collect_validation_evidence(manifests: Mapping[str, Any], candidate: Mapping[str, Any]) -> dict[str, Any]:
    entries = manifests.get("entries") if isinstance(manifests.get("entries"), Mapping) else {}
    cpcv_payload = entries.get("cpcv_report", {}).get("payload", {}) if isinstance(entries.get("cpcv_report"), Mapping) else {}
    promotion_payload = entries.get("promotion_dry_run_evidence", {}).get("payload", {}) if isinstance(entries.get("promotion_dry_run_evidence"), Mapping) else {}
    shadow_replay_payload = entries.get("shadow_replay", {}).get("payload", {}) if isinstance(entries.get("shadow_replay"), Mapping) else {}
    monitoring_payload = entries.get("post_release_monitoring_spec", {}).get("payload", {}) if isinstance(entries.get("post_release_monitoring_spec"), Mapping) else {}
    rollback_payload = entries.get("rollback_rehearsal", {}).get("payload", {}) if isinstance(entries.get("rollback_rehearsal"), Mapping) else {}
    v10 = candidate.get("candidate_v10_summary") if isinstance(candidate.get("candidate_v10_summary"), Mapping) else {}
    return {
        "cpcv_summary": {
            "status": cpcv_payload.get("status", "missing"),
            "pbo": _nested(cpcv_payload, "pbo", "pbo") or v10.get("pbo"),
            "reality_check": _nested(cpcv_payload, "reality_check", "aggregate_p_value") or v10.get("reality_check"),
            "passed": bool(_nested(cpcv_payload, "reality_check", "passed")) if cpcv_payload else bool(v10.get("pbo_pass") and v10.get("reality_check_pass")),
        },
        "year_concentration_summary": {
            "candidate_v10_status": v10.get("year_evidence_status", "missing"),
            "candidate_v12_status": (candidate.get("candidate_v12_summary") or {}).get("year_evidence_status", "missing") if isinstance(candidate.get("candidate_v12_summary"), Mapping) else "missing",
        },
        "cost_stress_attribution_summary": {
            "candidate_v10_status": v10.get("cost_attribution_status", "missing"),
            "candidate_v10_failure_drivers": v10.get("main_cost_failure_drivers", []),
            "candidate_v12_status": (candidate.get("candidate_v12_summary") or {}).get("cost_attribution_status", "missing") if isinstance(candidate.get("candidate_v12_summary"), Mapping) else "missing",
        },
        "promotion_dry_run_summary": {
            "status": promotion_payload.get("status", "not_allowed"),
            "candidate_version": promotion_payload.get("candidate_version", ""),
            "requested_action": promotion_payload.get("requested_action", "promotion_dry_run_only"),
            "active_publish_allowed": False,
            "active_write_allowed": False,
            "active_updated": False,
            "customer_prediction_generated": False,
            "artifact_boundary_checks": promotion_payload.get("artifact_boundary_checks", {}),
            "blocking_reasons": list(promotion_payload.get("blocking_reasons") or []),
            "report_path": promotion_payload.get("report_path", ""),
            "reason": "promotion dry-run evidence does not grant active publishing.",
        },
        "shadow_replay_summary": {
            "status": shadow_replay_payload.get("status", "missing"),
            "source_candidate_version": shadow_replay_payload.get("source_candidate_version", ""),
            "replay_row_count": shadow_replay_payload.get("replay_row_count", 0),
            "schema_validation_status": shadow_replay_payload.get("schema_validation_status", "missing"),
            "output_isolation_status": shadow_replay_payload.get("output_isolation_status", "missing"),
            "risk_tags": list(shadow_replay_payload.get("risk_tags") or []),
            "top_risk_tags": list(shadow_replay_payload.get("top_risk_tags") or []),
            "skipped_reasons": list(shadow_replay_payload.get("skipped_reasons") or []),
            "blocking_reasons": list(shadow_replay_payload.get("blocking_reasons") or []),
            "training_invoked": False,
            "active_updated": False,
            "customer_prediction_generated": False,
            "report_path": shadow_replay_payload.get("report_path", ""),
            "reason": "shadow replay is research-only evidence and does not grant active publishing.",
        },
        "post_release_monitoring_summary": {
            "status": monitoring_payload.get("status", "missing"),
            "monitoring_mode": monitoring_payload.get("monitoring_mode", "planning_only"),
            "live_monitoring_enabled": bool(monitoring_payload.get("live_monitoring_enabled")),
            "sentinel_count": monitoring_payload.get("sentinel_count", 0),
            "shadow_replay_status": monitoring_payload.get("shadow_replay_status", "missing"),
            "active_model_present": bool(monitoring_payload.get("active_model_present")),
            "readiness_gaps": list(monitoring_payload.get("readiness_gaps") or []),
            "blocking_reasons": list(monitoring_payload.get("blocking_reasons") or []),
            "warning_reasons": list(monitoring_payload.get("warning_reasons") or []),
            "active_publish_allowed": False,
            "active_updated": False,
            "customer_prediction_generated": False,
            "report_path": monitoring_payload.get("report_path", ""),
            "reason": "post-release monitoring spec is a planning contract and does not grant active publishing.",
        },
        "rollback_rehearsal_summary": {
            "status": rollback_payload.get("status", "missing"),
            "quarantine_needed": bool(rollback_payload.get("quarantine_needed")),
            "artifacts_detected_count": len(rollback_payload.get("artifacts_detected") or []),
            "blocking_reasons": list(rollback_payload.get("blocking_reasons") or []),
            "safety_checks": rollback_payload.get("safety_checks", {}),
            "active_publish_allowed": False,
            "active_updated": False,
            "customer_prediction_generated": False,
            "report_path": rollback_payload.get("report_path", ""),
            "reason": "rollback rehearsal is simulation-only evidence and does not grant active publishing.",
        },
    }


def summarize_blocking_reasons(data: Mapping[str, Any], candidate: Mapping[str, Any], manifests: Mapping[str, Any]) -> list[str]:
    reasons: list[str] = []
    managed = data.get("managed_proxy_summary") if isinstance(data.get("managed_proxy_summary"), Mapping) else {}
    audit = data.get("pit_audit_summary") if isinstance(data.get("pit_audit_summary"), Mapping) else {}
    fs = data.get("feature_store_v12_summary") if isinstance(data.get("feature_store_v12_summary"), Mapping) else {}
    td = data.get("training_dataset_v12_summary") if isinstance(data.get("training_dataset_v12_summary"), Mapping) else {}
    v10 = candidate.get("candidate_v10_summary") if isinstance(candidate.get("candidate_v10_summary"), Mapping) else {}
    v12 = candidate.get("candidate_v12_summary") if isinstance(candidate.get("candidate_v12_summary"), Mapping) else {}
    entries = manifests.get("entries") if isinstance(manifests.get("entries"), Mapping) else {}
    promotion = entries.get("promotion_dry_run_evidence", {}).get("payload", {}) if isinstance(entries.get("promotion_dry_run_evidence"), Mapping) else {}
    shadow_replay = entries.get("shadow_replay", {}).get("payload", {}) if isinstance(entries.get("shadow_replay"), Mapping) else {}
    monitoring = entries.get("post_release_monitoring_spec", {}).get("payload", {}) if isinstance(entries.get("post_release_monitoring_spec"), Mapping) else {}
    rollback = entries.get("rollback_rehearsal", {}).get("payload", {}) if isinstance(entries.get("rollback_rehearsal"), Mapping) else {}
    model_card_entry = entries.get("model_card", {}) if isinstance(entries.get("model_card"), Mapping) else {}
    model_card = model_card_entry.get("payload", {}) if isinstance(model_card_entry, Mapping) else {}
    maturity_entry = entries.get("governance_maturity_matrix", {}) if isinstance(entries.get("governance_maturity_matrix"), Mapping) else {}
    maturity = maturity_entry.get("payload", {}) if isinstance(maturity_entry, Mapping) else {}

    for item in managed.get("operator_runbook_blocking_reasons", []):
        if item:
            reasons.extend([str(item), f"managed_proxy_operator_runbook:{item}"])
    for item in managed.get("wizard_blocking_reasons", []):
        if item:
            reasons.extend([str(item), f"managed_proxy_config_wizard:{item}"])
    for item in managed.get("setup_blocking_reasons", []):
        if item:
            reasons.extend([str(item), f"managed_proxy_setup:{item}"])
    for item in managed.get("schema_mapping_blocking_reasons", []):
        if item:
            reasons.extend([str(item), f"managed_proxy_schema_mapping:{item}"])
    for item in managed.get("quarantine_contract_blocking_reasons", []):
        if item:
            reasons.extend([str(item), f"managed_proxy_quarantine_contract:{item}"])
    for item in managed.get("backfill_plan_blocking_reasons", []):
        if item:
            reasons.extend([str(item), f"managed_data_backfill_plan:{item}"])
    for item in managed.get("production_cache_gate_blocking_reasons", []):
        if item:
            reasons.extend([str(item), f"managed_data_production_cache_gate:{item}"])
    for item in managed.get("reliability_blocking_reasons", []):
        if item:
            reasons.extend([str(item), f"managed_proxy_reliability:{item}"])
    for item in managed.get("quality_blocking_reasons", []):
        if item:
            reasons.extend([str(item), f"managed_data_quality:{item}"])
    for item in managed.get("blocking_reasons", []):
        if item:
            reasons.extend([str(item), f"managed_data:{item}"])
    for item in audit.get("blocking_reasons", []):
        if item:
            reasons.extend([str(item), f"pit_audit:{item}"])
    for item in fs.get("blocking_reasons", []):
        if item:
            reasons.extend([str(item), f"feature_store:{item}"])
    for item in td.get("blocking_reasons", []):
        if item:
            reasons.extend([str(item), f"training_dataset:{item}"])
    if v12.get("status") in {"blocked", "missing"}:
        reasons.extend(f"candidate_v12:{item}" for item in v12.get("skipped_reasons", []) if item)
    if promotion and str(promotion.get("status") or "").lower() in {"blocked", "violation"}:
        reasons.extend(f"promotion_dry_run_evidence:{item}" for item in promotion.get("blocking_reasons", []) if item)
    shadow_replay_status = str(shadow_replay.get("status") or "missing").lower()
    if shadow_replay_status in {"missing", "blocked", "fail", "failed", "violation"}:
        replay_reasons = list(shadow_replay.get("blocking_reasons") or shadow_replay.get("skipped_reasons") or [shadow_replay_status])
        reasons.extend(f"shadow_replay:{item}" for item in replay_reasons if item)
    monitoring_status = str(monitoring.get("status") or "missing").lower()
    if monitoring_status in {"missing", "blocked", "fail", "failed", "violation"}:
        monitoring_reasons = list(monitoring.get("blocking_reasons") or [monitoring_status])
        reasons.extend(f"post_release_monitoring:{item}" for item in monitoring_reasons if item)
    if bool(rollback.get("quarantine_needed")):
        rollback_reasons = list(rollback.get("blocking_reasons") or ["unapproved_artifacts_detected"])
        reasons.extend(f"rollback_rehearsal:{item}" for item in rollback_reasons if item)
    model_card_status = str(model_card.get("status") or ("missing" if not model_card_entry.get("exists") else "incomplete")).lower()
    if model_card_status in {"missing", "incomplete", "blocked", "violation", "fail", "failed"}:
        reasons.append(f"model_card:{model_card_status}")
    maturity_status = str(maturity.get("status") or ("missing" if not maturity_entry.get("exists") else "incomplete")).lower()
    if maturity_status in {"missing", "incomplete", "blocked", "violation", "fail", "failed"}:
        reasons.append(f"governance_maturity_matrix:{maturity_status}")
    if not v10.get("pbo_pass"):
        reasons.append("validation:pbo_or_cpcv_missing_or_failed")
    if not v10.get("reality_check_pass"):
        reasons.append("validation:reality_check_missing_or_failed")
    if v10.get("year_evidence_status") not in {"pass"}:
        reasons.append(f"year_evidence:{v10.get('year_evidence_status', 'missing')}")
    if v10.get("cost_attribution_status") != "pass":
        drivers = v10.get("main_cost_failure_drivers") or ["cost_attribution_missing_or_failed"]
        reasons.extend(f"cost_attribution:{driver}" for driver in drivers)
    if not v10.get("manual_approval_recommended"):
        reasons.append("manual_approval:not_recommended")
    reasons.extend(str(item) for item in manifests.get("stale_or_missing_reports", []) if item)
    return _dedupe_preserve_order(reasons)


def compute_candidate_training_allowed(data: Mapping[str, Any]) -> bool:
    return bool(data.get("managed_ready") and data.get("audit_ready") and data.get("feature_store_ready") and data.get("training_dataset_ready"))


def compute_manual_approval_recommendation(candidate: Mapping[str, Any]) -> bool:
    v10 = candidate.get("candidate_v10_summary") if isinstance(candidate.get("candidate_v10_summary"), Mapping) else {}
    v12 = candidate.get("candidate_v12_summary") if isinstance(candidate.get("candidate_v12_summary"), Mapping) else {}
    return bool(
        v10.get("manual_approval_recommended")
        and v10.get("pbo_pass")
        and v10.get("reality_check_pass")
        and v10.get("year_evidence_pass")
        and v10.get("cost_attribution_pass")
        and v12.get("status") == "success"
        and v12.get("manual_approval_recommended")
    )


def compute_active_publish_allowed() -> bool:
    return False


def compute_next_allowed_action(data: Mapping[str, Any], candidate: Mapping[str, Any]) -> tuple[str, str]:
    managed = data.get("managed_proxy_summary") if isinstance(data.get("managed_proxy_summary"), Mapping) else {}
    if not data.get("managed_ready"):
        operator_action = str(managed.get("operator_runbook_next_allowed_action") or "")
        if operator_action == "fix_operator_runbook_templates":
            return "managed_data_blocked", operator_action
        wizard_action = str(managed.get("wizard_next_allowed_action") or "")
        if wizard_action == "fix_managed_proxy_config_templates":
            return "managed_data_blocked", wizard_action
        setup_status = str(managed.get("setup_status") or "").lower()
        if setup_status not in {"ready", "success", "pass", "configured"}:
            if wizard_action == "configure_managed_proxy_endpoint_or_token":
                return "managed_data_blocked", wizard_action
            return "managed_data_blocked", str(managed.get("next_allowed_action") or "configure_managed_proxy")
        quarantine_contract_status = str(managed.get("quarantine_contract_status") or "missing").lower()
        if bool(managed.get("quarantine_contract_exists")) and quarantine_contract_status not in {"ready", "success", "pass"}:
            return "managed_data_blocked", "fix_quarantine_contract_failures"
        if bool(managed.get("quarantine_contract_ready")):
            backfill_plan_status = str(managed.get("backfill_plan_status") or "missing").lower()
            if bool(managed.get("backfill_plan_ready")):
                production_cache_gate_status = str(managed.get("production_cache_gate_status") or "missing").lower()
                if bool(managed.get("production_cache_gate_ready")):
                    return "managed_data_blocked", "review_production_cache_dry_run_plan"
                if bool(managed.get("production_cache_gate_exists")) and production_cache_gate_status not in {"ready", "success", "pass"}:
                    return "managed_data_blocked", "complete_production_cache_gate_preconditions"
                return "managed_data_blocked", "run_production_cache_promotion_gate"
            if bool(managed.get("backfill_plan_exists")) and backfill_plan_status not in {"ready", "success", "pass"}:
                return "managed_data_blocked", "fix_real_managed_data_backfill_plan"
            return "managed_data_blocked", "run_real_managed_data_backfill_planner"
        quarantine_action = str(managed.get("quarantine_snapshot_next_allowed_action") or "")
        if quarantine_action == "run_quarantine_contract_tests":
            return "managed_data_blocked", quarantine_action
        schema_mapping_action = str(managed.get("schema_mapping_next_allowed_action") or "")
        if schema_mapping_action == "fix_managed_proxy_schema_mapping":
            return "managed_data_blocked", schema_mapping_action
        reliability_action = str(managed.get("reliability_next_allowed_action") or "")
        if reliability_action == "fix_managed_proxy_reliability":
            return "managed_data_blocked", reliability_action
        quality_action = str(managed.get("quality_next_allowed_action") or "")
        if quality_action == "fix_managed_data_quality":
            return "managed_data_blocked", quality_action
        endpoint_smoke_action = str(managed.get("endpoint_smoke_next_allowed_action") or "")
        endpoint_smoke_status = str(managed.get("endpoint_smoke_status") or "missing").lower()
        health_status = str(managed.get("status") or "missing").lower()
        downstream_evidence_exists = (
            health_status not in {"", "missing"}
            or bool(managed.get("schema_mapping_exists"))
            or bool(managed.get("reliability_exists"))
            or bool(managed.get("quality_exists"))
        )
        if endpoint_smoke_action and endpoint_smoke_status in {"pass", "ready", "success"} and health_status not in {"ready", "success", "pass"}:
            return "managed_data_blocked", endpoint_smoke_action
        if endpoint_smoke_action and endpoint_smoke_status in {"missing", "blocked", "failed", "fail", "not_run"}:
            if managed.get("endpoint_smoke_exists") or not downstream_evidence_exists:
                return "managed_data_blocked", endpoint_smoke_action
        return "managed_data_blocked", str(managed.get("next_allowed_action") or "configure_managed_proxy")
    if bool(managed.get("backfill_plan_ready")) or bool(managed.get("production_cache_gate_exists")):
        production_cache_gate_status = str(managed.get("production_cache_gate_status") or "missing").lower()
        if bool(managed.get("production_cache_gate_ready")):
            return "managed_data_blocked", "review_production_cache_dry_run_plan"
        if bool(managed.get("production_cache_gate_exists")) and production_cache_gate_status not in {"ready", "success", "pass"}:
            return "managed_data_blocked", "complete_production_cache_gate_preconditions"
        return "managed_data_blocked", "run_production_cache_promotion_gate"
    if not data.get("audit_ready"):
        return "pit_audit_blocked", "run_pit_audit"
    v10 = candidate.get("candidate_v10_summary") if isinstance(candidate.get("candidate_v10_summary"), Mapping) else {}
    if v10.get("cost_attribution_status") == "fail":
        return "candidate_trained_gate_failed", "fix_candidate_v10_cost_failure"
    if not data.get("feature_store_ready"):
        return "feature_store_blocked", "build_feature_store_v12"
    if not data.get("training_dataset_ready"):
        return "training_dataset_blocked", "build_training_dataset_v12"
    v12 = candidate.get("candidate_v12_summary") if isinstance(candidate.get("candidate_v12_summary"), Mapping) else {}
    if v12.get("status") in {"blocked", "missing"}:
        return "candidate_blocked", "run_candidate_v12_research"
    if compute_manual_approval_recommendation(candidate):
        return "ready_for_manual_review", "review_candidate_gate"
    return "active_publish_not_allowed", "review_candidate_gate" if managed.get("status") != "missing" else "no_action_until_data_ready"


def write_research_decision_board(payload: Mapping[str, Any]) -> dict[str, Any]:
    return _write_json(_board_path(), payload)


def build_research_decision_board() -> dict[str, Any]:
    manifests = collect_latest_manifests()
    data = collect_data_readiness_evidence(manifests)
    candidate = collect_candidate_gate_evidence(manifests)
    validation = collect_validation_evidence(manifests, candidate)
    observability = collect_governance_observability_evidence()
    lockdown = collect_governance_lockdown_evidence()
    manual_approval_workflow = collect_manual_approval_evidence()
    current_state, next_action = compute_next_allowed_action(data, candidate)
    candidate_training_allowed = compute_candidate_training_allowed(data)
    observability_status = str(observability.get("status") or "missing").lower()
    observability_blocked = bool(observability.get("exists")) and observability_status in {
        "blocked",
        "fail",
        "failed",
        "missing",
        "violation",
    }
    manual_approval = compute_manual_approval_recommendation(candidate) and not observability_blocked
    active_allowed = compute_active_publish_allowed()
    blocking = summarize_blocking_reasons(data, candidate, manifests)
    entries = manifests.get("entries") if isinstance(manifests.get("entries"), Mapping) else {}
    build_plan_entry = entries.get("feature_store_v12_build_plan", {}) if isinstance(entries.get("feature_store_v12_build_plan"), Mapping) else {}
    build_plan_payload = build_plan_entry.get("payload", {}) if isinstance(build_plan_entry, Mapping) else {}
    build_plan_summary = {
        "status": build_plan_payload.get("status", "missing") if isinstance(build_plan_payload, Mapping) else "missing",
        "feature_store_v12_build_executed": bool(build_plan_payload.get("feature_store_v12_build_executed")) if isinstance(build_plan_payload, Mapping) else False,
        "expected_feature_store_path": build_plan_payload.get("expected_feature_store_path", "") if isinstance(build_plan_payload, Mapping) else "",
        "expected_manifest_path": build_plan_payload.get("expected_manifest_path", "") if isinstance(build_plan_payload, Mapping) else "",
        "blocking_reasons": list(build_plan_payload.get("blocking_reasons") or []) if isinstance(build_plan_payload, Mapping) else [],
        "report_path": build_plan_payload.get("report_path") if isinstance(build_plan_payload, Mapping) else str(_paths()["feature_store_v12_build_plan"]),
    }
    controlled_build_entry = entries.get("feature_store_v12_controlled_build", {}) if isinstance(entries.get("feature_store_v12_controlled_build"), Mapping) else {}
    controlled_build_payload = controlled_build_entry.get("payload", {}) if isinstance(controlled_build_entry, Mapping) else {}
    controlled_build_summary = {
        "status": controlled_build_payload.get("status", "missing") if isinstance(controlled_build_payload, Mapping) else "missing",
        "build_executed": bool(controlled_build_payload.get("build_executed")) if isinstance(controlled_build_payload, Mapping) else False,
        "feature_store_v12_path": controlled_build_payload.get("feature_store_v12_path", "") if isinstance(controlled_build_payload, Mapping) else "",
        "feature_store_v12_manifest_path": controlled_build_payload.get("feature_store_v12_manifest_path", "") if isinstance(controlled_build_payload, Mapping) else "",
        "training_dataset_v12_triggered": bool(controlled_build_payload.get("training_dataset_v12_triggered")) if isinstance(controlled_build_payload, Mapping) else False,
        "candidate_triggered": bool(controlled_build_payload.get("candidate_triggered")) if isinstance(controlled_build_payload, Mapping) else False,
        "blocking_reasons": list(controlled_build_payload.get("blocking_reasons") or []) if isinstance(controlled_build_payload, Mapping) else [],
        "report_path": controlled_build_payload.get("report_path") if isinstance(controlled_build_payload, Mapping) else str(_paths()["feature_store_v12_controlled_build"]),
    }
    rollback_payload = entries.get("rollback_rehearsal", {}).get("payload", {}) if isinstance(entries.get("rollback_rehearsal"), Mapping) else {}
    model_card_entry = entries.get("model_card", {}) if isinstance(entries.get("model_card"), Mapping) else {}
    model_card_payload = model_card_entry.get("payload", {}) if isinstance(model_card_entry, Mapping) else {}
    model_card_status = str(model_card_payload.get("status") or ("missing" if not model_card_entry.get("exists") else "incomplete")).lower()
    model_card_incomplete = model_card_status in {"missing", "incomplete", "blocked", "violation", "fail", "failed"}
    maturity_entry = entries.get("governance_maturity_matrix", {}) if isinstance(entries.get("governance_maturity_matrix"), Mapping) else {}
    maturity_payload = maturity_entry.get("payload", {}) if isinstance(maturity_entry, Mapping) else {}
    maturity_status = str(maturity_payload.get("status") or ("missing" if not maturity_entry.get("exists") else "incomplete")).lower()
    maturity_incomplete = maturity_status in {"missing", "incomplete", "blocked", "violation", "fail", "failed"}
    if observability_blocked:
        blocking.extend(
            f"governance_observability:{reason}"
            for reason in observability.get("blocking_reasons", [])
            if str(reason or "").strip()
        )
        blocking = _dedupe_preserve_order(blocking)
        current_state = "governance_observability_blocked"
        next_action = (
            "fix_secret_scan_violation"
            if str(observability.get("secret_scan_status") or "").lower() == "fail"
            else "fix_governance_observability"
        )
    if bool(lockdown.get("lockdown_triggered")):
        blocking.extend(
            f"governance_lockdown:{reason}"
            for reason in lockdown.get("lockdown_reasons", [])
            if str(reason or "").strip()
        )
        blocking = _dedupe_preserve_order(blocking)
        current_state = "governance_lockdown"
        next_action = "resolve_governance_incident"
        candidate_training_allowed = False
        manual_approval = False
        active_allowed = False
    if bool(rollback_payload.get("quarantine_needed")):
        blocking.extend(
            f"rollback_rehearsal:{reason}"
            for reason in (rollback_payload.get("blocking_reasons") or ["unapproved_artifacts_detected"])
            if str(reason or "").strip()
        )
        blocking = _dedupe_preserve_order(blocking)
        current_state = "governance_lockdown"
        next_action = "resolve_governance_incident"
        candidate_training_allowed = False
        manual_approval = False
        active_allowed = False
    manual_status = str(manual_approval_workflow.get("status") or "missing")
    if manual_status in {"blocked_by_gates", "expired", "rejected"}:
        workflow_reasons = manual_approval_workflow.get("blocking_reasons") or ["manual_approval_blocked"]
        blocking.extend(
            f"manual_approval_workflow:{reason}"
            for reason in workflow_reasons
            if str(reason or "").strip()
        )
        blocking = _dedupe_preserve_order(blocking)
        manual_approval = False
        active_allowed = False
    if manual_status == "pending_review":
        manual_approval = False
        active_allowed = False
    if model_card_incomplete:
        manual_approval = False
        active_allowed = False
    if maturity_incomplete:
        manual_approval = False
        active_allowed = False
    board = {
        "status": "ready_for_manual_review" if manual_approval else "blocked",
        "generated_at": _now(),
        "current_research_state": current_state,
        "next_allowed_action": next_action,
        "candidate_training_allowed": candidate_training_allowed,
        "training_dataset_v12_allowed": bool(data.get("feature_store_ready")),
        "candidate_v12_allowed": bool(data.get("training_dataset_ready") and candidate_training_allowed),
        "manual_approval_recommended": manual_approval,
        "active_publish_allowed": active_allowed,
        **{key: data[key] for key in ("managed_proxy_summary", "pit_audit_summary", "feature_store_v12_summary", "training_dataset_v12_summary")},
        **candidate,
        **validation,
        "governance_observability_summary": observability,
        "governance_lockdown_summary": lockdown,
        "manual_approval_summary": manual_approval_workflow,
        "feature_store_v12_build_plan_summary": sanitize_for_json(build_plan_summary),
        "feature_store_v12_controlled_build_summary": sanitize_for_json(controlled_build_summary),
        "blocking_reasons": blocking,
        "top_blocking_reasons": blocking[:12],
        "warning_reasons": [] if blocking else ["active_publish_still_requires_explicit_human_approval"],
        "evidence_paths": manifests.get("evidence_paths", {}),
        "stale_or_missing_reports": manifests.get("stale_or_missing_reports", []),
        "training_invoked": False,
        "active_updated": False,
        "customer_prediction_generated": False,
        "manifest_path": str(_board_path()),
        "board_path": str(_board_path()),
    }
    board = attach_freshness_to_decision_board(board, get_evidence_freshness_report())
    return write_research_decision_board(board)


def get_research_decision_board() -> dict[str, Any]:
    payload = _read_json(_board_path())
    if isinstance(payload, Mapping):
        return sanitize_for_json(dict(payload))
    return build_research_decision_board()
