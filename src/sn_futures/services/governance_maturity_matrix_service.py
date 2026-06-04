from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Mapping

from ..api.json_utils import sanitize_for_json
from ..runtime import get_user_output_dir
from ..utils.secret_sanitizer import contains_secret_like_value, sanitize_text
from .research_run_ledger_service import append_run_ledger, finalize_research_run, start_research_run


MATRIX_VERSION = "governance_maturity_matrix_v1"
SECRET_RE = re.compile(
    r"(?i)(authorization\s*[:=]\s*[^\s,;\"']+|bearer\s+[A-Za-z0-9._\-]{8,}|token\s*[:=]\s*[^\s,;\"']+|secret\s*[:=]\s*[^\s,;\"']+)"
)
DOMAIN_ORDER = (
    "Managed Proxy Configuration",
    "Schema Mapping",
    "PIT / No-Lookahead",
    "Managed Data Quality",
    "Managed Data Backfill",
    "Production Managed Cache Gate",
    "Feature Store v12",
    "Training Dataset v12",
    "Candidate v12",
    "Candidate v10 Research",
    "Cost Robustness",
    "Year Evidence",
    "CPCV / PBO / Reality Check",
    "Evidence Freshness",
    "Evidence Bundle / Audit Export",
    "Access Control",
    "Observability / SLO",
    "Incident Response",
    "Manual Approval",
    "Shadow Mode",
    "Shadow Replay",
    "Post-Release Monitoring Spec",
    "Rollback / Quarantine",
    "Model Registry Safety",
    "Production Cutover",
    "Model Card / Risk Disclosure",
    "Run Ledger / Reproducibility",
)
REPORT_SPECS: dict[str, tuple[str, str]] = {
    "operator_runbook": ("diagnostics/managed_proxy_operator_runbook_report.json", "Managed Proxy Configuration"),
    "config_wizard": ("diagnostics/managed_proxy_config_wizard_report.json", "Managed Proxy Configuration"),
    "managed_proxy_setup": ("diagnostics/managed_proxy_setup_report.json", "Managed Proxy Configuration"),
    "schema_mapping": ("diagnostics/managed_proxy_schema_mapping_report.json", "Schema Mapping"),
    "pit_replay": ("diagnostics/managed_pit_replay_report.json", "PIT / No-Lookahead"),
    "managed_data_audit": ("diagnostics/managed_data_audit_manifest.json", "PIT / No-Lookahead"),
    "managed_data_quality": ("diagnostics/managed_data_quality_scorecard.json", "Managed Data Quality"),
    "managed_data_backfill_plan": ("diagnostics/managed_data_backfill_planner_report.json", "Managed Data Backfill"),
    "managed_data_production_cache_gate": ("diagnostics/managed_data_production_cache_gate_report.json", "Production Managed Cache Gate"),
    "managed_proxy_reliability": ("diagnostics/managed_proxy_reliability_report.json", "Managed Proxy Configuration"),
    "feature_store_v12_input_contract": ("diagnostics/feature_store_v12_input_contract_report.json", "Feature Store v12"),
    "feature_store_v12_build_plan": ("diagnostics/feature_store_v12_build_plan_report.json", "Feature Store v12"),
    "feature_store_v12_controlled_build": ("diagnostics/feature_store_v12_controlled_build_report.json", "Feature Store v12"),
    "feature_store_v12": ("feature_store/v12/feature_store_manifest.json", "Feature Store v12"),
    "training_dataset_v12": ("training_dataset_manifest_v12.json", "Training Dataset v12"),
    "candidate_v12": ("model_research/candidate_v12/candidate_v12_gated_research_report.json", "Candidate v12"),
    "candidate_v10": ("model_research/candidate_v10/candidate_v10_gated_research_report.json", "Candidate v10 Research"),
    "cost_stress_attribution": ("model_research/cost_stress_attribution.json", "Cost Robustness"),
    "year_concentration": ("model_research/year_concentration_evidence.json", "Year Evidence"),
    "cpcv_report": ("validation/cpcv/cpcv_report.json", "CPCV / PBO / Reality Check"),
    "evidence_freshness": ("model_research/evidence_freshness_report.json", "Evidence Freshness"),
    "evidence_bundle": ("model_research/evidence_bundle_index.json", "Evidence Bundle / Audit Export"),
    "external_audit_export": ("governance/external_audit_export/audit_index.json", "Evidence Bundle / Audit Export"),
    "access_control": ("model_research/governance_access_control_report.json", "Access Control"),
    "observability": ("model_research/governance_observability_report.json", "Observability / SLO"),
    "incident_drill": ("model_research/incident_drill_report.json", "Incident Response"),
    "manual_approval": ("model_research/manual_approval_report.json", "Manual Approval"),
    "shadow_mode": ("model_research/shadow_mode_readiness_report.json", "Shadow Mode"),
    "shadow_output_contract": ("model_research/shadow_output_contract_report.json", "Shadow Mode"),
    "shadow_replay": ("model_research/shadow_replay_report.json", "Shadow Replay"),
    "post_release_monitoring": ("model_research/post_release_monitoring_spec_report.json", "Post-Release Monitoring Spec"),
    "rollback_rehearsal": ("model_research/rollback_rehearsal_report.json", "Rollback / Quarantine"),
    "model_registry_safety": ("model_research/model_registry_safety_report.json", "Model Registry Safety"),
    "production_cutover": ("model_research/production_cutover_checklist_report.json", "Production Cutover"),
    "model_card": ("model_research/model_card.json", "Model Card / Risk Disclosure"),
    "run_ledger": ("model_research/run_ledger/research_run_ledger_report.json", "Run Ledger / Reproducibility"),
    "decision_board": ("model_research/research_decision_board.json", "Run Ledger / Reproducibility"),
}
CRITICAL_REPORTS = (
    "decision_board",
    "managed_proxy_setup",
    "schema_mapping",
    "pit_replay",
    "managed_data_quality",
    "feature_store_v12",
    "training_dataset_v12",
    "candidate_v12",
    "candidate_v10",
    "cost_stress_attribution",
    "year_concentration",
    "model_card",
)
REPORT_CONTROL_NAMES = {
    "decision_board": "research_decision_board",
}


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _output_dir() -> Path:
    return get_user_output_dir()


def _report_path() -> Path:
    path = _output_dir() / "model_research" / "governance_maturity_matrix.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _resolve_output_path(relative_path: str) -> Path:
    primary = _output_dir() / relative_path
    if primary.exists():
        return primary
    fallback = Path("outputs") / relative_path
    if fallback.exists():
        return fallback
    return primary


def _read_json(path: Path) -> Any:
    if not path.exists() or not path.is_file():
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
    return str(payload.get("status") or payload.get("setup_status") or "missing").lower()


def _safe_list(value: Any, *, limit: int = 50) -> list[str]:
    if not isinstance(value, list):
        return []
    return [sanitize_text(str(item)) for item in value[:limit] if str(item or "").strip()]


def _summary(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        return {}
    keys = (
        "status",
        "generated_at",
        "current_research_state",
        "next_allowed_action",
        "blocking_reasons",
        "warning_reasons",
        "manual_approval_recommended",
        "active_publish_allowed",
        "production_readiness",
        "shadow_mode_allowed",
        "cutover_allowed",
        "training_invoked",
        "active_updated",
        "customer_prediction_generated",
        "report_path",
    )
    out = {key: payload.get(key) for key in keys if key in payload}
    return sanitize_for_json(out)


def _missing_issue(path: Path, payload: Any, name: str) -> str:
    if not path.exists():
        return "missing"
    if not isinstance(payload, Mapping):
        return "incomplete"
    if not payload.get("status") and name not in {"year_concentration", "cost_stress_attribution"}:
        return "incomplete"
    return ""


def collect_governance_reports() -> dict[str, dict[str, Any]]:
    reports: dict[str, dict[str, Any]] = {}
    for name, (relative, domain) in REPORT_SPECS.items():
        path = _resolve_output_path(relative)
        payload = _read_json(path)
        exists = path.exists() and path.is_file()
        stat = path.stat() if exists else None
        reports[name] = {
            "name": name,
            "domain": domain,
            "path": str(path),
            "exists": exists,
            "status": _status(payload),
            "issue": _missing_issue(path, payload, name),
            "size_bytes": int(stat.st_size) if stat else 0,
            "summary": _summary(payload),
            "payload": payload if isinstance(payload, Mapping) else {},
        }
    return sanitize_for_json(reports)


def _report_for_domain(reports: Mapping[str, Mapping[str, Any]], domain: str) -> list[Mapping[str, Any]]:
    return [item for item in reports.values() if item.get("domain") == domain]


def _domain_status(items: list[Mapping[str, Any]]) -> str:
    if not items:
        return "missing"
    statuses = [str(item.get("status") or "missing").lower() for item in items]
    issues = [str(item.get("issue") or "") for item in items]
    if any(issue == "missing" for issue in issues):
        return "missing"
    if any(issue == "incomplete" for issue in issues):
        return "incomplete"
    if any(status in {"fail", "failed", "blocked", "violation", "error"} for status in statuses):
        return "blocked"
    if any(status == "planning_only" for status in statuses):
        return "planning_only"
    if any(status == "research_only" for status in statuses):
        return "research_only"
    if any(status in {"warning", "guarded"} for status in statuses):
        return "warning"
    if all(status in {"pass", "passed", "ready", "success", "ok"} for status in statuses):
        return "pass"
    return statuses[0] if statuses else "missing"


def _score_from_status(status: str) -> float:
    if status == "pass":
        return 0.9
    if status == "warning":
        return 0.7
    if status == "guarded":
        return 0.8
    if status == "planning_only":
        return 0.55
    if status == "research_only":
        return 0.55
    if status == "incomplete":
        return 0.2
    if status == "missing":
        return 0.0
    if status == "blocked":
        return 0.15
    return 0.4


def _domain_next_action(domain: str, status: str) -> list[str]:
    mapping = {
        "Managed Proxy Configuration": ["configure_managed_proxy_endpoint_or_token", "rerun_managed_proxy_setup_health"],
        "Schema Mapping": ["refresh_schema_mapping"],
        "PIT / No-Lookahead": ["run_pit_replay", "run_pit_audit"],
        "Managed Data Quality": ["run_managed_data_quality"],
        "Managed Data Backfill": ["run_real_managed_data_backfill_planner"],
        "Production Managed Cache Gate": ["run_production_cache_promotion_gate"],
        "Feature Store v12": ["resolve_feature_store_v12_input_contract_build_plan_or_controlled_build"],
        "Training Dataset v12": ["build_training_dataset_v12_after_fs_ready"],
        "Candidate v12": ["run_candidate_v12_after_td_ready"],
        "Cost Robustness": ["remediate_candidate_v10_cost_failure"],
        "Production Cutover": ["complete_all_preconditions_before_cutover"],
    }
    if status in {"pass", "warning", "research_only", "planning_only"}:
        return []
    return mapping.get(domain, [f"refresh_{domain.lower().replace(' / ', '_').replace(' ', '_')}_evidence"])


def score_governance_domain(domain: str, report: Mapping[str, Any] | list[Mapping[str, Any]]) -> dict[str, Any]:
    items = report if isinstance(report, list) else [report]
    status = _domain_status([item for item in items if isinstance(item, Mapping)])
    if domain == "Access Control" and status == "warning":
        score = 0.8
    elif domain == "Year Evidence" and status == "pass":
        score = 0.85
    elif domain == "Rollback / Quarantine" and status == "pass":
        score = 0.85
    elif domain == "Model Card / Risk Disclosure" and status == "pass":
        score = 0.9
    else:
        score = _score_from_status(status)
    blockers: list[str] = []
    paths: list[str] = []
    for item in items:
        if not isinstance(item, Mapping):
            continue
        paths.append(str(item.get("path") or ""))
        payload = item.get("payload") if isinstance(item.get("payload"), Mapping) else {}
        blockers.extend(_safe_list(item.get("blocking_reasons")))
        blockers.extend(_safe_list(item.get("skipped_reasons")))
        blockers.extend(_safe_list(payload.get("blocking_reasons")))
        blockers.extend(_safe_list(payload.get("skipped_reasons")))
        if item.get("issue"):
            blockers.append(f"{item.get('name', domain)}:{item.get('issue')}")
    if domain == "Cost Robustness" and status == "blocked" and not blockers:
        blockers.append("cost_attribution_failed")
    return sanitize_for_json(
        {
            "domain": domain,
            "score": round(float(score), 3),
            "status": status,
            "blockers": list(dict.fromkeys(blockers)),
            "evidence_paths": [path for path in paths if path],
            "next_actions": _domain_next_action(domain, status),
        }
    )


def identify_hardening_gaps(domain_scores: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    critical: list[str] = []
    immediate: list[str] = []
    data: list[str] = []
    research: list[str] = []
    governance: list[str] = []
    shadow: list[str] = []
    production: list[str] = []
    completed: list[str] = []
    missing: list[str] = []
    for domain, item in domain_scores.items():
        status = str(item.get("status") or "missing")
        blockers = _safe_list(item.get("blockers")) or ([f"{domain}:blocked"] if status in {"blocked", "missing", "incomplete"} else [])
        if status == "pass":
            completed.append(domain)
        if status in {"missing", "incomplete"}:
            missing.append(domain)
        if float(item.get("score") or 0.0) <= 0.25:
            critical.extend(blockers or [f"{domain}:score_low"])
        if domain in {"Managed Proxy Configuration"} and status in {"blocked", "missing", "incomplete"}:
            immediate.extend(blockers)
        if domain in {"Managed Proxy Configuration", "Schema Mapping", "PIT / No-Lookahead", "Managed Data Quality", "Managed Data Backfill", "Production Managed Cache Gate"}:
            data.extend(blockers)
            if domain == "Managed Data Backfill" and status in {"blocked", "missing", "incomplete"}:
                data.append("backfill_plan_missing_or_blocked")
            if domain == "Production Managed Cache Gate" and status in {"blocked", "missing", "incomplete"}:
                data.append("production_cache_gate_missing_or_blocked")
        if domain in {"Feature Store v12", "Training Dataset v12", "Candidate v12", "Candidate v10 Research", "Cost Robustness", "CPCV / PBO / Reality Check"}:
            research.extend(blockers)
        if domain in {"Evidence Freshness", "Evidence Bundle / Audit Export", "Access Control", "Observability / SLO", "Incident Response", "Model Card / Risk Disclosure", "Run Ledger / Reproducibility"}:
            governance.extend(blockers)
        if domain in {"Shadow Mode", "Shadow Replay", "Post-Release Monitoring Spec"}:
            shadow.extend(blockers)
        if domain in {"Production Cutover", "Model Registry Safety", "Manual Approval", "Rollback / Quarantine"}:
            production.extend(blockers)
    return sanitize_for_json(
        {
            "critical_gaps": list(dict.fromkeys(critical)),
            "immediate_blockers": list(dict.fromkeys(immediate)),
            "data_onboarding_blockers": list(dict.fromkeys(data)),
            "research_validation_blockers": list(dict.fromkeys(research)),
            "governance_blockers": list(dict.fromkeys(governance)),
            "shadow_readiness_blockers": list(dict.fromkeys(shadow)),
            "production_cutover_blockers": list(dict.fromkeys(production)),
            "completed_controls": sorted(set(completed)),
            "missing_controls": sorted(set(missing)),
        }
    )


def build_final_hardening_roadmap(gaps: Mapping[str, Any]) -> dict[str, list[str]]:
    return {
        "immediate blockers": _safe_list(gaps.get("immediate_blockers")) or ["configure_managed_proxy_endpoint_or_token"],
        "data onboarding blockers": _safe_list(gaps.get("data_onboarding_blockers")) or ["managed_data_not_ready"],
        "PIT/schema/data quality blockers": [
            *[item for item in _safe_list(gaps.get("data_onboarding_blockers")) if any(key in item for key in ("schema", "pit", "quality", "timestamp", "rows"))],
            "run_schema_pit_quality_sequence",
        ],
        "v12 build blockers": ["feature_store_v12_requires_managed_schema_pit_quality_ready", "training_dataset_v12_requires_feature_store_v12_ready"],
        "candidate research blockers": _safe_list(gaps.get("research_validation_blockers")) or ["candidate_v12_blocked_until_td_v12_ready"],
        "v10 cost robustness blockers": [item for item in _safe_list(gaps.get("research_validation_blockers")) if "cost" in item] or ["cost_attribution_requires_remediation"],
        "governance/reporting blockers": _safe_list(gaps.get("governance_blockers")),
        "shadow readiness blockers": _safe_list(gaps.get("shadow_readiness_blockers")) or ["shadow_mode_requires_manual_approval_after_gates"],
        "production cutover blockers": _safe_list(gaps.get("production_cutover_blockers")) or ["production_cutover_requires_all_preconditions"],
    }


def build_recommended_prompt_sequence(context: Mapping[str, Any]) -> list[dict[str, Any]]:
    state = str(context.get("current_research_state") or "")
    next_action = str(context.get("next_allowed_action") or "")
    operator_status = str(context.get("operator_runbook_status") or "")
    managed_first = state in {"managed_data_blocked", "", "missing"}
    actions = [
        "configure managed proxy endpoint/token",
        "rerun managed proxy setup/health",
        "refresh schema mapping",
        "run PIT replay",
        "run PIT audit",
        "run managed data quality",
        "build Feature Store v12 only if all upstream ready",
        "build Training Dataset v12 only if FS v12 ready",
        "run Candidate v12 research only if TD v12 ready",
        "refresh evidence bundle / freshness / decision board",
        "only then revisit manual approval / shadow mode",
    ]
    if next_action == "fix_operator_runbook_templates" or operator_status == "blocked":
        actions.insert(0, "fix operator runbook templates")
    if not managed_first:
        actions.append("review next gate from decision board")
    deduped = list(dict.fromkeys(actions))
    return [{"priority": index + 1, "action": action} for index, action in enumerate(deduped)]


def _build_domain_scores(reports: Mapping[str, Mapping[str, Any]]) -> dict[str, dict[str, Any]]:
    scores: dict[str, dict[str, Any]] = {}
    for domain in DOMAIN_ORDER:
        scores[domain] = score_governance_domain(domain, _report_for_domain(reports, domain))
    return sanitize_for_json(scores)


def _production_ready(domain_scores: Mapping[str, Mapping[str, Any]]) -> bool:
    return False if domain_scores else False


def _shadow_readiness(domain_scores: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    shadow_domains = ["Shadow Mode", "Shadow Replay", "Shadow Output Contract", "Post-Release Monitoring Spec"]
    blockers: list[str] = []
    scores: list[float] = []
    for domain in ("Shadow Mode", "Shadow Replay", "Post-Release Monitoring Spec"):
        item = domain_scores.get(domain, {})
        scores.append(float(item.get("score") or 0.0))
        blockers.extend(_safe_list(item.get("blockers")))
        if str(item.get("status") or "") in {"blocked", "missing", "incomplete", "planning_only", "research_only"}:
            blockers.append(f"{domain}:{item.get('status')}")
    return {
        "ready": False,
        "score": round(sum(scores) / len(scores), 3) if scores else 0.0,
        "blockers": list(dict.fromkeys(blockers)),
        "domains": shadow_domains,
    }


def _validate_no_secrets(payload: Mapping[str, Any]) -> list[str]:
    serialized = json.dumps(sanitize_for_json(payload), ensure_ascii=False, default=str)
    blockers: list[str] = []
    if contains_secret_like_value(serialized) or SECRET_RE.search(serialized):
        blockers.append("secret_pattern_detected")
    if "Authorization" in serialized or "Bearer " in serialized:
        blockers.append("authorization_header_detected")
    return blockers


def build_governance_maturity_matrix() -> dict[str, Any]:
    reports = collect_governance_reports()
    domain_scores = _build_domain_scores(reports)
    gaps = identify_hardening_gaps(domain_scores)
    roadmap = build_final_hardening_roadmap(gaps)
    decision = reports.get("decision_board", {}).get("payload", {}) if isinstance(reports.get("decision_board"), Mapping) else {}
    current_state = str(decision.get("current_research_state") or "missing")
    next_action = str(decision.get("next_allowed_action") or "configure_managed_proxy_endpoint_or_token")
    operator_payload = reports.get("operator_runbook", {}).get("payload", {}) if isinstance(reports.get("operator_runbook"), Mapping) else {}
    missing_critical = [
        REPORT_CONTROL_NAMES.get(name, name)
        for name in CRITICAL_REPORTS
        if reports.get(name, {}).get("issue") == "missing"
    ]
    incomplete_critical = [
        REPORT_CONTROL_NAMES.get(name, name)
        for name in CRITICAL_REPORTS
        if reports.get(name, {}).get("issue") == "incomplete"
    ]
    status = "incomplete" if missing_critical or incomplete_critical else "ready"
    payload = {
        "status": status,
        "generated_at": _now(),
        "maturity_matrix_version": MATRIX_VERSION,
        "production_readiness": _production_ready(domain_scores),
        "shadow_readiness": _shadow_readiness(domain_scores),
        "current_research_state": current_state,
        "next_allowed_action": next_action,
        "domain_scores": domain_scores,
        "domain_statuses": {domain: item.get("status") for domain, item in domain_scores.items()},
        "completed_controls": gaps["completed_controls"],
        "missing_controls": sorted(set(list(gaps["missing_controls"]) + missing_critical + incomplete_critical)),
        "critical_gaps": gaps["critical_gaps"],
        "immediate_blockers": gaps["immediate_blockers"] or ["configure_managed_proxy_endpoint_or_token"],
        "data_onboarding_blockers": gaps["data_onboarding_blockers"],
        "research_validation_blockers": gaps["research_validation_blockers"],
        "governance_blockers": gaps["governance_blockers"],
        "shadow_readiness_blockers": gaps["shadow_readiness_blockers"],
        "production_cutover_blockers": gaps["production_cutover_blockers"],
        "recommended_prompt_sequence": build_recommended_prompt_sequence(
            {
                "current_research_state": current_state,
                "next_allowed_action": next_action,
                "operator_runbook_status": operator_payload.get("status") if isinstance(operator_payload, Mapping) else "",
            }
        ),
        "roadmap": roadmap,
        "evidence_paths": {name: item.get("path") for name, item in reports.items()},
        "training_invoked": False,
        "active_updated": False,
        "customer_prediction_generated": False,
        "report_path": str(_report_path()),
    }
    secret_blockers = _validate_no_secrets(payload)
    if secret_blockers:
        payload["status"] = "violation"
        payload["critical_gaps"] = list(dict.fromkeys(list(payload["critical_gaps"]) + secret_blockers))
    return sanitize_for_json(payload)


def write_governance_maturity_matrix() -> dict[str, Any]:
    payload = build_governance_maturity_matrix()
    _write_json(_report_path(), payload)
    run = start_research_run(
        service_name="governance_maturity_matrix",
        run_type="report_write",
        input_paths=list(payload.get("evidence_paths", {}).values()) if isinstance(payload.get("evidence_paths"), Mapping) else [],
        output_paths=[str(_report_path())],
    )
    append_run_ledger(finalize_research_run(run))
    latest = _read_json(_report_path())
    return sanitize_for_json(dict(latest) if isinstance(latest, Mapping) else payload)


def get_latest_governance_maturity_matrix() -> dict[str, Any]:
    payload = _read_json(_report_path())
    if isinstance(payload, Mapping):
        return sanitize_for_json(dict(payload))
    return build_governance_maturity_matrix()
