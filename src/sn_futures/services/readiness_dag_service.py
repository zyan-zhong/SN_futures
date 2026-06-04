from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Mapping

from ..api.json_utils import sanitize_for_json
from ..runtime import get_user_output_dir
from .evidence_bundle_service import write_evidence_bundle
from .managed_data_quality_service import build_managed_data_quality_scorecard
from .managed_pit_replay_service import run_pit_replay_harness
from .managed_proxy_config_wizard_service import refresh_managed_proxy_config_wizard
from .managed_proxy_health_service import check_managed_proxy_health
from .managed_proxy_reliability_service import run_managed_proxy_canary_check
from .managed_proxy_schema_mapper_service import refresh_schema_mapping_report
from .managed_proxy_setup_service import refresh_managed_proxy_setup, run_managed_proxy_schema_dry_run
from .research_decision_board_service import build_research_decision_board


DAG_VERSION = "readiness_dag_v1"
REPORT_FILENAME = "readiness_dag_report.json"
PASS_STATUSES = {"ready", "success", "pass", "passed", "configured", "warning"}
FAIL_STATUSES = {"blocked", "failed", "fail", "error", "missing", "incomplete", "not_run", "skipped"}
FORBIDDEN_ACTIONS = (
    "build_feature_store_v12",
    "build_training_dataset_v12",
    "run_candidate_v12_research",
    "run_candidate_training",
    "generate_oof_trace",
    "run_promotion",
    "promote_candidate",
    "approve_active_release",
    "write_active_model_json",
    "generate_customer_prediction",
)


@dataclass(frozen=True)
class DagNode:
    node_id: str
    label: str
    dependencies: tuple[str, ...] = ()
    report_path: str = ""
    safe_check: str = ""


NODE_DEFS: tuple[DagNode, ...] = (
    DagNode("config_wizard", "Managed Proxy Configuration Wizard", report_path="diagnostics/managed_proxy_config_wizard_report.json", safe_check="config_wizard"),
    DagNode("managed_proxy_setup", "Managed Proxy Setup", ("config_wizard",), "diagnostics/managed_proxy_setup_report.json", "managed_proxy_setup"),
    DagNode("schema_mapping", "Managed Proxy Schema Mapping", ("managed_proxy_setup",), "diagnostics/managed_proxy_schema_mapping_report.json", "schema_mapping"),
    DagNode("endpoint_contract", "Managed Proxy Endpoint Contract", ("managed_proxy_setup", "schema_mapping"), "diagnostics/managed_proxy_setup_report.json", "endpoint_contract"),
    DagNode("managed_proxy_health", "Managed Proxy Health", ("managed_proxy_setup", "schema_mapping", "endpoint_contract"), "diagnostics/managed_proxy_health.json", "managed_proxy_health"),
    DagNode("reliability_canary", "Managed Proxy Reliability Canary", ("managed_proxy_health",), "diagnostics/managed_proxy_reliability_report.json", "reliability_canary"),
    DagNode("pit_replay", "PIT Replay Harness", ("managed_proxy_health",), "diagnostics/managed_pit_replay_report.json", "pit_replay"),
    DagNode("managed_data_audit", "Managed Point-in-Time Data Audit", ("managed_proxy_health", "schema_mapping", "pit_replay"), "diagnostics/managed_data_audit_manifest.json"),
    DagNode("data_quality", "Managed Data Quality Scorecard", ("managed_proxy_health",), "diagnostics/managed_data_quality_scorecard.json", "data_quality"),
    DagNode("feature_store_v12", "Feature Store v12", ("managed_data_audit", "data_quality", "reliability_canary", "pit_replay"), "feature_store/v12/feature_store_manifest.json"),
    DagNode("training_dataset_v12", "Training Dataset v12", ("feature_store_v12",), "training_dataset_manifest_v12.json"),
    DagNode("candidate_v12", "Candidate v12", ("training_dataset_v12",), "model_research/candidate_v12/candidate_v12_gated_research_report.json"),
    DagNode("year_evidence", "Year Evidence", ("candidate_v12",), "model_research/year_concentration_evidence.json"),
    DagNode("cost_attribution", "Cost Attribution", ("candidate_v12",), "model_research/cost_stress_attribution.json"),
    DagNode("decision_board", "Research Decision Board", ("candidate_v12", "year_evidence", "cost_attribution"), "model_research/research_decision_board.json", "decision_board"),
    DagNode("evidence_bundle", "Evidence Bundle", ("decision_board",), "model_research/evidence_bundle_index.json", "evidence_bundle"),
)
NODE_BY_ID = {node.node_id: node for node in NODE_DEFS}
SAFE_CHECK_ORDER = (
    "config_wizard",
    "managed_proxy_setup",
    "schema_mapping",
    "endpoint_contract",
    "managed_proxy_health",
    "reliability_canary",
    "pit_replay",
    "data_quality",
    "decision_board",
    "evidence_bundle",
)


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _output_dir() -> Path:
    return get_user_output_dir()


def _report_path() -> Path:
    path = _output_dir() / "model_research" / REPORT_FILENAME
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


def _status(payload: Any, node_id: str) -> str:
    if not isinstance(payload, Mapping):
        return "missing"
    if node_id == "endpoint_contract":
        return str(payload.get("endpoint_contract_status") or payload.get("status") or "missing").lower()
    return str(payload.get("status") or "missing").lower()


def _reasons(payload: Any, node_id: str, status: str) -> list[str]:
    if isinstance(payload, Mapping):
        raw = payload.get("blocking_reasons") or payload.get("blocked_reasons") or []
        if isinstance(raw, list):
            reasons = [str(item) for item in raw if str(item or "").strip()]
        else:
            reasons = [str(raw)] if str(raw or "").strip() else []
        if reasons:
            return reasons
    if status == "missing":
        return [f"{node_id}_report_missing"]
    if status in FAIL_STATUSES:
        return [f"{node_id}_{status}"]
    return []


def _passed(node_id: str, payload: Any, status: str) -> bool:
    if not isinstance(payload, Mapping):
        return False
    if node_id == "schema_mapping":
        return bool(payload.get("schema_mapping_ready")) or status in PASS_STATUSES
    if node_id == "endpoint_contract":
        return status in {"pass", "passed", "ready", "success", "configured"}
    if node_id == "managed_proxy_health":
        return bool(payload.get("v12_allowed") or payload.get("ready")) or status in PASS_STATUSES
    if node_id == "reliability_canary":
        return status in PASS_STATUSES and str(payload.get("circuit_breaker_status") or "closed").lower() != "open"
    if node_id == "pit_replay":
        return status in PASS_STATUSES and bool(payload.get("point_in_time_join_ready"))
    if node_id == "managed_data_audit":
        leakage = payload.get("leakage_checks") if isinstance(payload.get("leakage_checks"), Mapping) else {}
        return bool(payload.get("v12_allowed") or leakage.get("point_in_time_join_ready")) and status in PASS_STATUSES
    if node_id == "data_quality":
        return bool(payload.get("gate_passed")) or status in {"pass", "passed", "ready", "success"}
    if node_id == "feature_store_v12":
        return status in {"ready", "success", "pass"} and bool(payload.get("no_lookahead_pass")) and bool(payload.get("point_in_time_join_ready"))
    if node_id == "training_dataset_v12":
        return status in {"ready", "success", "pass"} and bool(payload.get("candidate_v12_allowed") or payload.get("leakage_check_pass") or payload.get("no_lookahead_pass"))
    if node_id == "candidate_v12":
        return status in {"ready", "success", "pass"} and not bool(payload.get("blocking_reasons"))
    if node_id in {"year_evidence", "cost_attribution"}:
        return bool(payload.get("passed")) or status in PASS_STATUSES
    if node_id == "decision_board":
        return status in {"ready", "success", "pass"} and not bool(payload.get("blocking_reasons"))
    if node_id == "evidence_bundle":
        return status in {"ready", "success", "pass"}
    return status in PASS_STATUSES and not bool(_reasons(payload, node_id, status))


def _report_payloads(overrides: Mapping[str, Mapping[str, Any]] | None = None) -> tuple[dict[str, Any], dict[str, str]]:
    overrides = overrides or {}
    payloads: dict[str, Any] = {}
    paths: dict[str, str] = {}
    for node in NODE_DEFS:
        if node.node_id in overrides:
            payloads[node.node_id] = dict(overrides[node.node_id])
            paths[node.node_id] = "in_memory_safe_check"
            continue
        path = _resolve_output_path(node.report_path) if node.report_path else Path()
        payloads[node.node_id] = _read_json(path)
        paths[node.node_id] = str(path) if node.report_path else ""
    return payloads, paths


def _build_dag_definition() -> dict[str, Any]:
    nodes = [
        {
            "id": node.node_id,
            "label": node.label,
            "dependencies": list(node.dependencies),
            "safe_check": node.safe_check,
        }
        for node in NODE_DEFS
    ]
    edges = [{"from": dep, "to": node.node_id} for node in NODE_DEFS for dep in node.dependencies]
    return {"dag_version": DAG_VERSION, "nodes": nodes, "edges": edges}


def validate_readiness_dag_dependencies(dag: Mapping[str, Any] | None = None) -> dict[str, Any]:
    dag = dag or _build_dag_definition()
    node_ids = {str(node.get("id")) for node in dag.get("nodes", []) if isinstance(node, Mapping)}
    invalid_edges = [
        edge
        for edge in dag.get("edges", [])
        if isinstance(edge, Mapping) and (str(edge.get("from")) not in node_ids or str(edge.get("to")) not in node_ids)
    ]
    return {"status": "pass" if not invalid_edges else "fail", "invalid_edges": invalid_edges, "node_count": len(node_ids)}


def compute_readiness_dag_state(overrides: Mapping[str, Mapping[str, Any]] | None = None) -> dict[str, Any]:
    dag = _build_dag_definition()
    payloads, paths = _report_payloads(overrides)
    node_statuses: dict[str, dict[str, Any]] = {}
    blocked_nodes: list[str] = []
    skipped_nodes: list[str] = []
    top_blockers: list[str] = []
    critical_path: list[str] = []
    first_blocking_node = ""
    first_next_action = ""

    for node in NODE_DEFS:
        dependency_failures = [dep for dep in node.dependencies if not node_statuses.get(dep, {}).get("passed")]
        payload = payloads.get(node.node_id)
        if dependency_failures:
            status = "skipped"
            passed = False
            reasons = [f"blocked_by:{dep}" for dep in dependency_failures]
            skipped_nodes.append(node.node_id)
        else:
            status = _status(payload, node.node_id)
            passed = _passed(node.node_id, payload, status)
            reasons = [] if passed else _reasons(payload, node.node_id, status)

        if not passed:
            blocked_nodes.append(node.node_id)
            if not first_blocking_node:
                first_blocking_node = node.node_id
                critical_path.append(node.node_id)
                first_next_action = _next_action(node.node_id, payload, reasons)
            elif not first_blocking_node:
                critical_path.append(node.node_id)
            top_blockers.extend(f"{node.node_id}:{reason}" for reason in reasons)
        elif not first_blocking_node:
            critical_path.append(node.node_id)

        node_statuses[node.node_id] = {
            "id": node.node_id,
            "label": node.label,
            "status": status,
            "passed": passed,
            "dependencies": list(node.dependencies),
            "blocked_by": dependency_failures,
            "blocking_reasons": reasons,
            "safe_check": node.safe_check,
            "report_path": paths.get(node.node_id, ""),
        }

    runnable_safe_checks = [
        node.node_id
        for node in NODE_DEFS
        if node.safe_check and all(node_statuses.get(dep, {}).get("passed") for dep in node.dependencies)
    ]
    candidate_training_allowed = bool(node_statuses.get("training_dataset_v12", {}).get("passed"))
    candidate_v12_passed = bool(node_statuses.get("candidate_v12", {}).get("passed"))
    decision_board_passed = bool(node_statuses.get("decision_board", {}).get("passed"))
    manual_approval_allowed = candidate_v12_passed and decision_board_passed
    active_publish_allowed = manual_approval_allowed
    status = "ready" if not blocked_nodes else "blocked"
    evidence_paths = {node_id: path for node_id, path in paths.items() if path and Path(path).exists()}
    return sanitize_for_json(
        {
            "status": status,
            "generated_at": _now(),
            "dag_version": DAG_VERSION,
            "nodes": dag["nodes"],
            "edges": dag["edges"],
            "node_statuses": node_statuses,
            "blocked_nodes": blocked_nodes,
            "skipped_nodes": skipped_nodes,
            "runnable_safe_checks": runnable_safe_checks,
            "forbidden_actions": list(FORBIDDEN_ACTIONS),
            "critical_path": critical_path,
            "next_allowed_action": first_next_action or "review_readiness_dag",
            "top_blockers": sorted(set(top_blockers)),
            "evidence_paths": evidence_paths,
            "candidate_training_allowed": candidate_training_allowed,
            "manual_approval_allowed": manual_approval_allowed,
            "active_publish_allowed": active_publish_allowed,
            "training_invoked": False,
            "active_updated": False,
            "customer_prediction_generated": False,
            "report_path": str(_report_path()),
        }
    )


def build_readiness_dag() -> dict[str, Any]:
    return compute_readiness_dag_state()


def summarize_readiness_blockers(dag_state: Mapping[str, Any] | None = None) -> dict[str, Any]:
    dag_state = dag_state or compute_readiness_dag_state()
    return {
        "status": dag_state.get("status"),
        "top_blockers": list(dag_state.get("top_blockers") or []),
        "blocked_nodes": list(dag_state.get("blocked_nodes") or []),
        "skipped_nodes": list(dag_state.get("skipped_nodes") or []),
        "next_allowed_action": dag_state.get("next_allowed_action"),
    }


def _next_action(node_id: str, payload: Any, reasons: list[str]) -> str:
    if isinstance(payload, Mapping) and payload.get("next_allowed_action"):
        return str(payload.get("next_allowed_action"))
    if node_id == "config_wizard":
        return "refresh_managed_proxy_config_wizard"
    if node_id == "managed_proxy_setup":
        if any("disabled" in reason for reason in reasons):
            return "enable_managed_proxy"
        return "configure_managed_proxy_endpoint_or_token"
    if node_id == "schema_mapping":
        return "fix_managed_proxy_schema_mapping"
    if node_id == "endpoint_contract":
        return "fix_managed_proxy_endpoint_contract"
    if node_id == "managed_proxy_health":
        return "fix_managed_proxy_health"
    if node_id == "reliability_canary":
        return "fix_managed_proxy_reliability"
    if node_id == "pit_replay":
        return "fix_managed_proxy_pit_replay"
    if node_id == "managed_data_audit":
        return "fix_managed_data_audit"
    if node_id == "data_quality":
        return "fix_managed_data_quality"
    if node_id == "feature_store_v12":
        return "build_feature_store_v12_after_gates"
    if node_id == "training_dataset_v12":
        return "build_training_dataset_v12_after_feature_store"
    if node_id == "candidate_v12":
        return "fix_candidate_v12_gate"
    return "review_readiness_dag"


def write_readiness_dag_report() -> dict[str, Any]:
    return _write_json(_report_path(), compute_readiness_dag_state())


def get_readiness_dag_report() -> dict[str, Any]:
    payload = _read_json(_report_path())
    if isinstance(payload, Mapping):
        return sanitize_for_json(dict(payload))
    return compute_readiness_dag_state()


def _safe_check_functions() -> dict[str, Callable[[], Mapping[str, Any]]]:
    return {
        "config_wizard": refresh_managed_proxy_config_wizard,
        "managed_proxy_setup": refresh_managed_proxy_setup,
        "schema_mapping": refresh_schema_mapping_report,
        "endpoint_contract": run_managed_proxy_schema_dry_run,
        "managed_proxy_health": check_managed_proxy_health,
        "reliability_canary": run_managed_proxy_canary_check,
        "pit_replay": run_pit_replay_harness,
        "data_quality": build_managed_data_quality_scorecard,
        "decision_board": build_research_decision_board,
        "evidence_bundle": write_evidence_bundle,
    }


def run_readiness_checks_dry_run() -> dict[str, Any]:
    overrides: dict[str, Mapping[str, Any]] = {}
    safe_functions = _safe_check_functions()
    executed: list[str] = []
    errors: dict[str, str] = {}

    for node_id in SAFE_CHECK_ORDER:
        node = NODE_BY_ID[node_id]
        current = compute_readiness_dag_state(overrides)
        if any(not current["node_statuses"].get(dep, {}).get("passed") for dep in node.dependencies):
            continue
        try:
            result = dict(safe_functions[node_id]())
        except Exception as exc:  # Safe runner records failures rather than propagating.
            result = {"status": "blocked", "blocking_reasons": [f"{node_id}_safe_check_error"], "error_message": str(exc)}
            errors[node_id] = str(exc)
        overrides[node_id] = result
        if node_id == "endpoint_contract":
            overrides[node_id] = result
        executed.append(node_id)

    final = compute_readiness_dag_state(overrides)
    final["safe_checks_executed"] = executed
    final["safe_check_errors"] = errors
    final["training_invoked"] = False
    final["active_updated"] = False
    final["customer_prediction_generated"] = False
    return _write_json(_report_path(), final)
