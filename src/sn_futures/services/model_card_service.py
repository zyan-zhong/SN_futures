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


MODEL_CARD_VERSION = "model_card_v1"
SYSTEM_NAME = "SNInsightTerminal"
RAW_EVIDENCE_KEYS = {
    "rows",
    "data",
    "records",
    "raw_rows",
    "managed_rows",
    "oof_rows",
    "oof_trace",
    "predictions",
    "customer_predictions",
    "trades",
}
SECRET_RE = re.compile(
    r"(?i)(authorization\s*[:=]\s*[^\s,;\"']+|bearer\s+[A-Za-z0-9._\-]{8,}|token\s*[:=]\s*[^\s,;\"']+|secret\s*[:=]\s*[^\s,;\"']+)"
)
LONG_HEX_RE = re.compile(r"\b[a-fA-F0-9]{32,}\b")
URL_RE = re.compile(r"https?://[^\s\"'<>]+")


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _output_dir() -> Path:
    return get_user_output_dir()


def _report_path() -> Path:
    path = _output_dir() / "model_research" / "model_card.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _model_card_md_path() -> Path:
    path = _output_dir() / "model_research" / "model_card.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _risk_disclosure_path() -> Path:
    path = _output_dir() / "model_research" / "risk_disclosure.md"
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


def _source_paths() -> dict[str, Path]:
    return {
        "research_decision_board": _resolve_output_path("model_research/research_decision_board.json"),
        "governance_maturity_matrix": _resolve_output_path("model_research/governance_maturity_matrix.json"),
        "evidence_bundle": _resolve_output_path("model_research/evidence_bundle_index.json"),
        "evidence_freshness": _resolve_output_path("model_research/evidence_freshness_report.json"),
        "external_audit_export": _resolve_output_path("governance/external_audit_export/audit_index.json"),
        "managed_proxy_setup": _resolve_output_path("diagnostics/managed_proxy_setup_report.json"),
        "managed_proxy_schema_mapping": _resolve_output_path("diagnostics/managed_proxy_schema_mapping_report.json"),
        "managed_pit_replay": _resolve_output_path("diagnostics/managed_pit_replay_report.json"),
        "managed_data_audit": _resolve_output_path("diagnostics/managed_data_audit_manifest.json"),
        "managed_data_quality": _resolve_output_path("diagnostics/managed_data_quality_scorecard.json"),
        "feature_store_v12_manifest": _resolve_output_path("feature_store/v12/feature_store_manifest.json"),
        "training_dataset_v12_manifest": _resolve_output_path("training_dataset_manifest_v12.json"),
        "candidate_v10_report": _resolve_output_path("model_research/candidate_v10/candidate_v10_gated_research_report.json"),
        "candidate_v12_report": _resolve_output_path("model_research/candidate_v12/candidate_v12_gated_research_report.json"),
        "year_concentration_evidence": _resolve_output_path("model_research/year_concentration_evidence.json"),
        "cost_stress_attribution": _resolve_output_path("model_research/cost_stress_attribution.json"),
        "shadow_replay": _resolve_output_path("model_research/shadow_replay_report.json"),
        "shadow_output_contract": _resolve_output_path("model_research/shadow_output_contract_report.json"),
        "post_release_monitoring_spec": _resolve_output_path("model_research/post_release_monitoring_spec_report.json"),
        "rollback_rehearsal": _resolve_output_path("model_research/rollback_rehearsal_report.json"),
        "manual_approval": _resolve_output_path("model_research/manual_approval_report.json"),
        "model_registry_safety": _resolve_output_path("model_research/model_registry_safety_report.json"),
        "production_cutover": _resolve_output_path("model_research/production_cutover_checklist_report.json"),
    }


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


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(sanitize_text(text), encoding="utf-8")


def _status(payload: Any) -> str:
    if not isinstance(payload, Mapping):
        return "missing"
    return str(payload.get("status") or "missing").lower()


def _generated_at(payload: Any) -> str:
    if not isinstance(payload, Mapping):
        return ""
    for key in ("generated_at", "report_generated_at", "updated_at", "created_at"):
        if payload.get(key):
            return str(payload.get(key))
    return ""


def _safe_scalar(value: Any) -> Any:
    if isinstance(value, str):
        value = URL_RE.sub("[redacted_endpoint]", value)
        value = LONG_HEX_RE.sub("***", value)
        value = SECRET_RE.sub("***", value)
        return sanitize_text(value)
    return value


def _safe_path_scalar(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    return sanitize_text(value)


def _safe_list(value: Any, *, limit: int = 20) -> list[str]:
    if not isinstance(value, list):
        return []
    out: list[str] = []
    for item in value[:limit]:
        text = str(_safe_scalar(item) or "").strip()
        if text:
            out.append(text)
    return out


def _omit_raw_payload(payload: Any) -> Any:
    if isinstance(payload, Mapping):
        out: dict[str, Any] = {}
        for key, value in payload.items():
            text_key = str(key)
            lowered = text_key.lower()
            if lowered in RAW_EVIDENCE_KEYS:
                out[text_key] = {"omitted": True, "reason": "raw_rows_oof_or_predictions_not_in_model_card"}
                continue
            if any(fragment in lowered for fragment in ("authorization", "token", "secret", "password", "api_key", "apikey")):
                out[text_key] = "[redacted]" if value else value
                continue
            if "endpoint" in lowered or "url" in lowered:
                out[text_key] = "[redacted_endpoint]" if value else value
                continue
            if "path" in lowered:
                out[text_key] = _safe_path_scalar(value)
                continue
            out[text_key] = _omit_raw_payload(value)
        return out
    if isinstance(payload, list):
        return [_omit_raw_payload(item) for item in payload[:20]]
    return _safe_scalar(payload)


def _source_summary(name: str, payload: Any) -> dict[str, Any]:
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
        "active_write_allowed",
        "customer_prediction_generated",
        "training_invoked",
        "active_updated",
        "report_path",
    )
    summary = {key: payload.get(key) for key in keys if key in payload}
    if name == "model_card":
        summary.update(
            {
                "current_status": payload.get("current_status"),
                "intended_use": payload.get("intended_use"),
                "prohibited_use": payload.get("prohibited_use"),
                "gate_failures": payload.get("gate_failures"),
                "known_limitations": payload.get("known_limitations"),
            }
        )
    return sanitize_for_json(_omit_raw_payload(summary))


def collect_model_card_sources() -> dict[str, dict[str, Any]]:
    sources: dict[str, dict[str, Any]] = {}
    for name, path in _source_paths().items():
        payload = _read_json(path)
        exists = path.exists() and path.is_file()
        issue = ""
        if not exists:
            issue = "missing"
        elif not isinstance(payload, Mapping):
            issue = "incomplete"
        elif not payload.get("status") and name not in {"year_concentration_evidence", "cost_stress_attribution"}:
            issue = "incomplete"
        stat = path.stat() if exists else None
        sources[name] = {
            "name": name,
            "path": str(path),
            "exists": exists,
            "status": _status(payload),
            "generated_at": _generated_at(payload),
            "issue": issue,
            "size_bytes": int(stat.st_size) if stat else 0,
            "summary": _source_summary(name, payload),
        }
    return sanitize_for_json(sources)


def _payload(name: str, sources: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    path = Path(str((sources.get(name) or {}).get("path") or ""))
    payload = _read_json(path)
    return dict(payload) if isinstance(payload, Mapping) else {}


def _bool(payload: Mapping[str, Any], key: str, default: bool = False) -> bool:
    return bool(payload.get(key, default))


def _active_paths() -> list[Path]:
    out = _output_dir()
    cwd = Path.cwd()
    return [
        out / "model_registry" / "active_model.json",
        out / "models" / "active_model.json",
        cwd / "outputs" / "model_registry" / "active_model.json",
        cwd / "outputs" / "models" / "active_model.json",
    ]


def _prediction_paths() -> list[Path]:
    out = _output_dir()
    cwd = Path.cwd()
    return [
        out / "customer_predictions",
        out / "customer_predictions.json",
        cwd / "outputs" / "customer_predictions",
        cwd / "outputs" / "customer_predictions.json",
    ]


def _confirmation(paths: Iterable[Path]) -> dict[str, Any]:
    existing = [str(path) for path in paths if path.exists()]
    return {"confirmed": not existing, "existing_paths": existing}


def _first_reason(payloads: Iterable[Mapping[str, Any]], fallback: str) -> list[str]:
    reasons: list[str] = []
    for payload in payloads:
        reasons.extend(_safe_list(payload.get("blocking_reasons")))
        reasons.extend(_safe_list(payload.get("skipped_reasons")))
    return reasons or [fallback]


def _worst(table: Any, key: str) -> Any:
    if not isinstance(table, Mapping):
        return None
    rows = table.get("rows")
    if not isinstance(rows, list) or not rows:
        return None
    candidates = [row for row in rows if isinstance(row, Mapping)]
    if not candidates:
        return None
    worst = min(candidates, key=lambda row: float(row.get("net_expectancy_3x") or row.get("net_expectancy_2x") or 0.0))
    return worst.get(key)


def _cost_summary(cost: Mapping[str, Any], board: Mapping[str, Any]) -> dict[str, Any]:
    board_v10 = board.get("candidate_v10_summary") if isinstance(board.get("candidate_v10_summary"), Mapping) else {}
    drivers = _safe_list(cost.get("failure_drivers")) or _safe_list(board_v10.get("main_cost_failure_drivers"))
    return sanitize_for_json(
        {
            "status": cost.get("status") or board_v10.get("cost_attribution_status") or "missing",
            "passed": bool(cost.get("passed")) or bool(board_v10.get("cost_attribution_pass")),
            "failure_drivers": drivers,
            "worst_horizon": _worst(cost.get("by_horizon"), "horizon") or board_v10.get("worst_horizon"),
            "worst_regime": _worst(cost.get("by_regime"), "regime_label") or board_v10.get("worst_regime"),
            "worst_year": _worst(cost.get("by_year"), "year") or board_v10.get("worst_year"),
        }
    )


def _data_readiness_summary(
    *,
    setup: Mapping[str, Any],
    schema: Mapping[str, Any],
    replay: Mapping[str, Any],
    quality: Mapping[str, Any],
    fs: Mapping[str, Any],
    td: Mapping[str, Any],
    candidate_v12: Mapping[str, Any],
) -> dict[str, Any]:
    return sanitize_for_json(
        {
            "managed_proxy": {
                "status": setup.get("status", "missing"),
                "endpoint_configured": bool(setup.get("endpoint_configured")),
                "token_configured": bool(setup.get("token_configured")),
                "blocking_reasons": _safe_list(setup.get("blocking_reasons")),
            },
            "schema_mapping": {
                "status": schema.get("status", "missing"),
                "ready": bool(schema.get("schema_mapping_ready")),
                "blocking_reasons": _safe_list(schema.get("blocking_reasons")),
            },
            "pit_replay": {
                "status": replay.get("status", "missing"),
                "point_in_time_join_ready": bool(replay.get("point_in_time_join_ready")),
                "blocking_reasons": _safe_list(replay.get("blocking_reasons")),
            },
            "data_quality": {
                "status": quality.get("status", "missing"),
                "gate_passed": bool(quality.get("gate_passed")),
                "blocking_reasons": _safe_list(quality.get("blocking_reasons")),
            },
            "feature_store_v12": {
                "status": fs.get("status", "missing"),
                "blocked": str(fs.get("status", "missing")).lower() not in {"ready", "success", "pass"},
                "blocking_reasons": _safe_list(fs.get("blocking_reasons")) or ["managed_proxy_data_not_ready"],
            },
            "training_dataset_v12": {
                "status": td.get("status", "missing"),
                "blocked": str(td.get("status", "missing")).lower() not in {"ready", "success", "pass"},
                "blocking_reasons": _safe_list(td.get("blocking_reasons") or td.get("blocked_reasons")) or ["feature_store_v12_blocked"],
            },
            "candidate_v12": {
                "status": candidate_v12.get("status", "missing"),
                "blocked": str(candidate_v12.get("status", "missing")).lower() in {"missing", "blocked", "skipped"},
                "blocking_reasons": _safe_list(candidate_v12.get("blocking_reasons") or candidate_v12.get("skipped_reasons")) or ["training_dataset_v12_blocked"],
            },
        }
    )


def build_risk_disclosure(blocking_reasons: Iterable[Any] | None = None) -> dict[str, list[str]]:
    blockers = [str(item) for item in blocking_reasons or [] if str(item or "").strip()]
    return {
        "Data readiness risks": [
            "Managed proxy endpoint and token evidence is required before Feature Store v12 can use external fundamentals.",
            "Missing, blocked, or stale data readiness reports are not treated as pass.",
        ],
        "PIT / no-lookahead risks": [
            "PIT replay and audit must prove source/asof timestamps are usable before historical features can be joined.",
            "Ingest timestamp cannot substitute for source availability time.",
        ],
        "Managed proxy / schema mapping risks": [
            "Provider fields must map explicitly to canonical fields and required timestamps.",
            "Schema, reliability, and quality failures block downstream v12 artifacts.",
        ],
        "Cost robustness risks": [
            "Candidate v10 has cost attribution failures and remains research-only.",
            "Worst horizon/regime/year evidence must be remediated before approval.",
        ],
        "Backtest overfitting / CPCV / PBO limitations": [
            "Research backtests and CPCV/PBO evidence are diagnostic only until all institutional gates pass.",
            "Year evidence passing alone is insufficient for approval.",
        ],
        "Shadow replay limitations": [
            "Shadow replay is research-only evidence and is not customer prediction.",
            "Shadow artifacts must remain isolated from customer output paths.",
        ],
        "Monitoring limitations": [
            "Post-release monitoring spec is planning-only and is not deployed monitoring.",
            "SLO and incident drills do not grant active publishing rights.",
        ],
        "Approval / release limitations": [
            "Manual approval is currently false or blocked by gates.",
            "Production cutover and promotion dry-run evidence do not write active pointers.",
        ],
        "Operational safety limitations": [
            "Rollback rehearsal readiness is simulation evidence and does not mean the system is production-ready.",
            "Active publishing and customer prediction writes remain forbidden.",
        ],
        "Current blockers": blockers or ["missing_or_blocked_governance_evidence"],
    }


def validate_model_card_completeness(payload: Mapping[str, Any]) -> dict[str, Any]:
    required = ("research_decision_board", "evidence_bundle", "cost_stress_attribution", "managed_proxy_setup")
    source_status = payload.get("source_status") if isinstance(payload.get("source_status"), Mapping) else {}
    missing: list[str] = []
    incomplete: list[str] = []
    for name in required:
        item = source_status.get(name) if isinstance(source_status.get(name), Mapping) else {}
        if not item or not item.get("exists"):
            missing.append(name)
        elif item.get("issue") == "incomplete" or str(item.get("status") or "").lower() == "missing":
            incomplete.append(name)
    return {
        "status": "complete" if not missing and not incomplete else "incomplete",
        "missing_reports": sorted(set(missing)),
        "incomplete_reports": sorted(set(incomplete)),
    }


def validate_model_card_no_secrets(payload: Any) -> dict[str, Any]:
    serialized = json.dumps(sanitize_for_json(payload), ensure_ascii=False, default=str)
    blocking: list[str] = []
    if contains_secret_like_value(serialized) or SECRET_RE.search(serialized):
        blocking.append("secret_pattern_detected")
    if "Authorization" in serialized or "Bearer " in serialized:
        blocking.append("authorization_header_detected")
    if "raw-secret" in serialized:
        blocking.append("raw_secret_text_detected")
    return sanitize_for_json({"status": "pass" if not blocking else "fail", "blocking_reasons": sorted(set(blocking))})


def build_model_card_payload() -> dict[str, Any]:
    sources = collect_model_card_sources()
    board = _payload("research_decision_board", sources)
    evidence_bundle = _payload("evidence_bundle", sources)
    maturity = _payload("governance_maturity_matrix", sources)
    setup = _payload("managed_proxy_setup", sources)
    schema = _payload("managed_proxy_schema_mapping", sources)
    replay = _payload("managed_pit_replay", sources)
    audit = _payload("managed_data_audit", sources)
    quality = _payload("managed_data_quality", sources)
    fs = _payload("feature_store_v12_manifest", sources)
    td = _payload("training_dataset_v12_manifest", sources)
    candidate_v10 = _payload("candidate_v10_report", sources)
    candidate_v12 = _payload("candidate_v12_report", sources)
    year = _payload("year_concentration_evidence", sources)
    cost = _payload("cost_stress_attribution", sources)
    shadow = _payload("shadow_replay", sources)
    monitoring = _payload("post_release_monitoring_spec", sources)
    rollback = _payload("rollback_rehearsal", sources)
    manual = _payload("manual_approval", sources)
    registry = _payload("model_registry_safety", sources)
    cutover = _payload("production_cutover", sources)
    board_v10 = board.get("candidate_v10_summary") if isinstance(board.get("candidate_v10_summary"), Mapping) else {}
    board_v12 = board.get("candidate_v12_summary") if isinstance(board.get("candidate_v12_summary"), Mapping) else {}
    current_state = str(board.get("current_research_state") or "blocked")
    next_action = str(board.get("next_allowed_action") or setup.get("next_allowed_action") or "review_model_card_evidence")
    blocking = _safe_list(board.get("top_blocking_reasons")) or _safe_list(board.get("blocking_reasons"))
    blocking.extend(_first_reason([setup, fs, td, candidate_v12], "managed_proxy_data_readiness_missing"))
    blocking = list(dict.fromkeys(blocking))
    disclosure = build_risk_disclosure(blocking)
    source_status = {name: {key: item.get(key) for key in ("exists", "status", "issue", "path")} for name, item in sources.items()}
    completeness = validate_model_card_completeness({"source_status": source_status})
    no_active = _confirmation(_active_paths())
    no_prediction = _confirmation(_prediction_paths())
    cost_summary = _cost_summary(cost, board)
    candidate_v10_status = str(candidate_v10.get("status") or board_v10.get("status") or "missing")
    candidate_v12_status = str(candidate_v12.get("status") or board_v12.get("status") or "missing")
    data_readiness = _data_readiness_summary(
        setup=setup,
        schema=schema,
        replay=replay or audit,
        quality=quality,
        fs=fs,
        td=td,
        candidate_v12=candidate_v12,
    )
    status = "ready" if completeness["status"] == "complete" else "incomplete"
    payload = {
        "status": status,
        "model_card_version": MODEL_CARD_VERSION,
        "generated_at": _now(),
        "system_name": SYSTEM_NAME,
        "current_status": f"{current_state} / research_only",
        "intended_use": [
            "research_only",
            "internal model governance review",
            "data readiness / gate diagnosis",
        ],
        "prohibited_use": [
            "production trading",
            "customer prediction",
            "active deployment",
            "automated promotion",
            "investment advice",
            "live risk-taking",
        ],
        "model_or_candidate_scope": {
            "active_model": "none",
            "candidate_v10": "research_only",
            "candidate_v12": "blocked",
            "production_ready": False,
        },
        "active_model_status": {
            "exists": not no_active["confirmed"],
            "active_publish_allowed": False,
            "status": "absent" if no_active["confirmed"] else "unapproved_active_detected",
        },
        "customer_prediction_status": {
            "exists": not no_prediction["confirmed"],
            "customer_visible": False,
            "status": "absent" if no_prediction["confirmed"] else "unapproved_customer_output_detected",
        },
        "data_sources": {
            "managed_proxy": data_readiness["managed_proxy"],
            "tushare": {"status": "available_for_prior_research_if_configured", "scope": "non-v12 managed fundamentals gap remains"},
        },
        "data_readiness": data_readiness,
        "managed_proxy_status": data_readiness["managed_proxy"],
        "pit_readiness": {
            "audit_status": audit.get("status", replay.get("status", "missing")),
            "pit_replay_status": replay.get("status", "missing"),
            "point_in_time_join_ready": bool(replay.get("point_in_time_join_ready") or (audit.get("leakage_checks") or {}).get("point_in_time_join_ready")) if isinstance(audit.get("leakage_checks"), Mapping) else bool(replay.get("point_in_time_join_ready")),
            "blocking_reasons": _safe_list(replay.get("blocking_reasons")) or _safe_list(audit.get("blocking_reasons")) or ["pit_evidence_missing_or_blocked"],
        },
        "feature_store_status": data_readiness["feature_store_v12"],
        "training_dataset_status": data_readiness["training_dataset_v12"],
        "candidate_status": {
            "candidate_v10": {
                "status": candidate_v10_status,
                "scope": "research_only",
                "year_evidence_pass": bool((year.get("passed") if year else None) or board_v10.get("year_evidence_pass") or str(year.get("status", "")).lower() == "pass"),
                "year_evidence_sufficient_for_approval": False,
                "cost_attribution_status": cost_summary["status"],
                "production_ready": False,
            },
            "candidate_v12": {
                "status": candidate_v12_status,
                "scope": "blocked",
                "production_ready": False,
                "blocking_reasons": _safe_list(candidate_v12.get("blocking_reasons") or candidate_v12.get("skipped_reasons")) or ["training_dataset_v12_blocked"],
            },
        },
        "validation_summary": {
            "candidate_v10": {
                "research_only": True,
                "manual_approval_recommended": False,
                "pbo_pass": bool(board_v10.get("pbo_pass")),
                "reality_check_pass": bool(board_v10.get("reality_check_pass")),
                "cost_attribution_pass": False,
            },
            "candidate_v12": {"status": candidate_v12_status, "blocked": True},
        },
        "year_evidence_summary": {
            "status": year.get("status") or board_v10.get("year_evidence_status") or "missing",
            "passed": bool(year.get("passed") or board_v10.get("year_evidence_pass")),
            "sufficient_for_approval": False,
        },
        "cost_attribution_summary": cost_summary,
        "shadow_replay_summary": {
            "status": shadow.get("status", "missing"),
            "mode": "research_only",
            "customer_prediction": False,
            "customer_visible": False,
            "reason": "Shadow replay is research_only and is not a customer prediction.",
        },
        "monitoring_spec_summary": {
            "status": monitoring.get("status", "missing"),
            "mode": str(monitoring.get("monitoring_mode") or "planning_only"),
            "deployed_monitoring": False,
            "reason": "Monitoring spec is planning_only and is not deployed monitoring.",
        },
        "rollback_rehearsal_summary": {
            "status": rollback.get("status", "missing"),
            "quarantine_needed": bool(rollback.get("quarantine_needed")),
            "grants_production_readiness": False,
            "reason": "Rollback rehearsal ready does not imply production readiness.",
        },
        "maturity_matrix_summary": {
            "status": maturity.get("status", "missing"),
            "production_readiness": False,
            "shadow_readiness": maturity.get("shadow_readiness") if isinstance(maturity.get("shadow_readiness"), Mapping) else {},
            "critical_gaps": _safe_list(maturity.get("critical_gaps")),
            "report_path": maturity.get("report_path", ""),
            "reason": "Maturity matrix summarizes gaps and does not grant active publishing.",
        },
        "manual_approval_summary": {
            "status": manual.get("status") or ("blocked" if not board.get("manual_approval_recommended") else "pending_review"),
            "manual_approval_recommended": False,
            "approval_request_allowed": bool(manual.get("approval_request_allowed")),
            "active_publish_allowed": False,
        },
        "registry_safety_summary": {
            "status": registry.get("status", "missing"),
            "active_write_allowed": False,
            "rollback_target_available": bool(registry.get("rollback_target_available")),
            "unapproved_active_detected": bool(registry.get("unapproved_active_detected")),
        },
        "cutover_summary": {
            "status": cutover.get("status", "missing"),
            "cutover_allowed": False,
            "noop_release_plan_ready": bool(cutover.get("noop_release_plan_ready")),
        },
        "known_limitations": [
            "No active model exists and active publishing is not allowed.",
            "No customer prediction exists and customer-facing output generation is forbidden.",
            "Managed proxy endpoint/token is not configured or not validated.",
            "Feature Store v12, Training Dataset v12, and Candidate v12 remain blocked until managed data gates pass.",
            "Candidate v10 is research-only; year evidence pass is insufficient while cost attribution fails.",
            "Shadow replay, monitoring spec, and rollback rehearsal are governance evidence, not production readiness.",
        ],
        "risk_disclosure": disclosure,
        "gate_failures": blocking,
        "next_allowed_action": next_action,
        "no_active_confirmation": no_active,
        "no_prediction_confirmation": no_prediction,
        "evidence_paths": {name: item.get("path") for name, item in sources.items()},
        "source_status": source_status,
        "missing_reports": completeness["missing_reports"],
        "incomplete_reports": completeness["incomplete_reports"],
        "training_invoked": False,
        "active_updated": False,
        "customer_prediction_generated": False,
        "report_path": str(_report_path()),
        "model_card_md_path": str(_model_card_md_path()),
        "risk_disclosure_path": str(_risk_disclosure_path()),
    }
    secret_check = validate_model_card_no_secrets(payload)
    if secret_check["status"] != "pass":
        payload["status"] = "violation"
        payload["gate_failures"] = list(dict.fromkeys(payload["gate_failures"] + list(secret_check["blocking_reasons"])))
    return sanitize_for_json(_omit_raw_payload(payload))


def _render_list(values: Iterable[Any]) -> str:
    items = [str(value) for value in values if str(value or "").strip()]
    return "\n".join(f"- {item}" for item in items) if items else "- none"


def _render_risk_disclosure(disclosure: Mapping[str, Any]) -> str:
    lines = ["# Risk Disclosure", ""]
    for section, values in disclosure.items():
        lines.append(f"## {section}")
        lines.append(_render_list(values if isinstance(values, list) else [values]))
        lines.append("")
    return "\n".join(lines)


def _render_model_card(payload: Mapping[str, Any]) -> str:
    lines = [
        "# Model Card",
        "",
        "## Current Status",
        f"- Status: {payload.get('status', 'missing')}",
        f"- Current status: {payload.get('current_status', 'missing')}",
        f"- Next allowed action: {payload.get('next_allowed_action', 'review_model_card_evidence')}",
        "",
        "## Intended Use",
        _render_list(payload.get("intended_use") or []),
        "",
        "## Prohibited Use",
        _render_list(payload.get("prohibited_use") or []),
        "",
        "## Data Readiness",
        f"- Managed proxy status: {(payload.get('managed_proxy_status') or {}).get('status', 'missing') if isinstance(payload.get('managed_proxy_status'), Mapping) else 'missing'}",
        f"- Feature Store v12 status: {(payload.get('feature_store_status') or {}).get('status', 'missing') if isinstance(payload.get('feature_store_status'), Mapping) else 'missing'}",
        f"- Training Dataset v12 status: {(payload.get('training_dataset_status') or {}).get('status', 'missing') if isinstance(payload.get('training_dataset_status'), Mapping) else 'missing'}",
        "",
        "## Candidate Summary",
        f"- Candidate v10: {((payload.get('candidate_status') or {}).get('candidate_v10') or {}).get('status', 'missing') if isinstance(payload.get('candidate_status'), Mapping) else 'missing'} / research_only",
        f"- Candidate v12: {((payload.get('candidate_status') or {}).get('candidate_v12') or {}).get('status', 'missing') if isinstance(payload.get('candidate_status'), Mapping) else 'missing'}",
        "",
        "## Validation Summary",
        f"- Year evidence: {(payload.get('year_evidence_summary') or {}).get('status', 'missing') if isinstance(payload.get('year_evidence_summary'), Mapping) else 'missing'}",
        f"- Cost attribution: {(payload.get('cost_attribution_summary') or {}).get('status', 'missing') if isinstance(payload.get('cost_attribution_summary'), Mapping) else 'missing'}",
        "",
        "## Risk Disclosure",
        _render_list((payload.get("risk_disclosure") or {}).keys() if isinstance(payload.get("risk_disclosure"), Mapping) else []),
        "",
        "## Gate Failures",
        _render_list(payload.get("gate_failures") or []),
        "",
        "## Evidence Paths",
        _render_list(f"{name}: {path}" for name, path in (payload.get("evidence_paths") or {}).items()) if isinstance(payload.get("evidence_paths"), Mapping) else "- none",
        "",
        "## No-Active / No-Prediction Confirmation",
        f"- active_model.json absent: {bool((payload.get('no_active_confirmation') or {}).get('confirmed')) if isinstance(payload.get('no_active_confirmation'), Mapping) else False}",
        f"- customer predictions absent: {bool((payload.get('no_prediction_confirmation') or {}).get('confirmed')) if isinstance(payload.get('no_prediction_confirmation'), Mapping) else False}",
        "",
        "## Next Allowed Action",
        f"- {payload.get('next_allowed_action', 'review_model_card_evidence')}",
        "",
    ]
    return "\n".join(str(line) for line in lines)


def write_model_card() -> dict[str, Any]:
    payload = build_model_card_payload()
    _write_json(_report_path(), payload)
    _write_text(_model_card_md_path(), _render_model_card(payload))
    _write_text(_risk_disclosure_path(), _render_risk_disclosure(payload.get("risk_disclosure") if isinstance(payload.get("risk_disclosure"), Mapping) else {}))
    run = start_research_run(
        service_name="model_card",
        run_type="report_write",
        input_paths=[str(path) for path in _source_paths().values()],
        output_paths=[str(_report_path()), str(_model_card_md_path()), str(_risk_disclosure_path())],
    )
    append_run_ledger(finalize_research_run(run))
    latest = _read_json(_report_path())
    return sanitize_for_json(dict(latest) if isinstance(latest, Mapping) else payload)


def get_latest_model_card() -> dict[str, Any]:
    payload = _read_json(_report_path())
    if isinstance(payload, Mapping):
        return sanitize_for_json(dict(payload))
    return build_model_card_payload()
