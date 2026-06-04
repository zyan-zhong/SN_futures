from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping, Sequence

from ..runtime import get_user_output_dir
from ..utils.secret_sanitizer import sanitize_text
from .research_run_ledger_service import append_run_ledger, finalize_research_run, start_research_run


ACCESS_CONTROL_VERSION = "governance_access_control_v1"

PERMISSION_CATEGORIES = (
    "safe_read",
    "safe_refresh",
    "safe_dry_run",
    "report_write",
    "heavy_build",
    "research_train",
    "promotion_dry_run",
    "active_write",
    "customer_prediction_write",
    "secret_write",
)

API_ACTIONS: tuple[dict[str, Any], ...] = (
    {"id": "read_decision_board", "method": "GET", "path": "/api/terminal/research/decision-board"},
    {"id": "refresh_decision_board", "method": "POST", "path": "/api/terminal/research/refresh-decision-board"},
    {"id": "read_readiness_dag", "method": "GET", "path": "/api/terminal/research/readiness-dag"},
    {"id": "refresh_readiness_dag", "method": "POST", "path": "/api/terminal/research/refresh-readiness-dag"},
    {"id": "run_safe_readiness_checks", "method": "POST", "path": "/api/terminal/research/run-safe-readiness-checks"},
    {"id": "read_evidence_freshness", "method": "GET", "path": "/api/terminal/research/evidence-freshness"},
    {"id": "refresh_evidence_freshness", "method": "POST", "path": "/api/terminal/research/refresh-evidence-freshness"},
    {"id": "read_evidence_bundle", "method": "GET", "path": "/api/terminal/research/evidence-bundle"},
    {"id": "refresh_evidence_bundle", "method": "POST", "path": "/api/terminal/research/refresh-evidence-bundle"},
    {"id": "read_run_ledger", "method": "GET", "path": "/api/terminal/research/run-ledger"},
    {"id": "refresh_run_ledger", "method": "POST", "path": "/api/terminal/research/refresh-run-ledger"},
    {"id": "read_hypothesis_registry", "method": "GET", "path": "/api/terminal/research/hypothesis-registry"},
    {"id": "refresh_anti_p_hacking_ledger", "method": "POST", "path": "/api/terminal/research/refresh-anti-p-hacking-ledger"},
    {"id": "read_shadow_mode", "method": "GET", "path": "/api/terminal/research/shadow-mode-readiness"},
    {"id": "refresh_shadow_mode", "method": "POST", "path": "/api/terminal/research/refresh-shadow-mode-readiness"},
    {"id": "read_shadow_output_contract", "method": "GET", "path": "/api/terminal/governance/shadow-output-contract"},
    {"id": "refresh_shadow_output_contract", "method": "POST", "path": "/api/terminal/governance/refresh-shadow-output-contract"},
    {"id": "build_shadow_output_dry_run", "method": "POST", "path": "/api/terminal/governance/build-shadow-output-dry-run"},
    {"id": "read_shadow_replay", "method": "GET", "path": "/api/terminal/governance/shadow-replay"},
    {"id": "refresh_shadow_replay", "method": "POST", "path": "/api/terminal/governance/refresh-shadow-replay"},
    {"id": "read_post_release_monitoring_spec", "method": "GET", "path": "/api/terminal/governance/post-release-monitoring-spec"},
    {"id": "refresh_post_release_monitoring_spec", "method": "POST", "path": "/api/terminal/governance/refresh-post-release-monitoring-spec"},
    {"id": "read_rollback_rehearsal", "method": "GET", "path": "/api/terminal/governance/rollback-rehearsal"},
    {"id": "refresh_rollback_rehearsal", "method": "POST", "path": "/api/terminal/governance/refresh-rollback-rehearsal"},
    {"id": "simulate_artifact_quarantine", "method": "POST", "path": "/api/terminal/governance/simulate-artifact-quarantine"},
    {"id": "read_external_audit_export", "method": "GET", "path": "/api/terminal/governance/external-audit-export"},
    {"id": "refresh_external_audit_export", "method": "POST", "path": "/api/terminal/governance/refresh-external-audit-export"},
    {"id": "read_production_cutover_checklist", "method": "GET", "path": "/api/terminal/governance/production-cutover-checklist"},
    {"id": "refresh_production_cutover_checklist", "method": "POST", "path": "/api/terminal/governance/refresh-production-cutover-checklist"},
    {"id": "build_noop_release_plan", "method": "POST", "path": "/api/terminal/governance/build-noop-release-plan"},
    {"id": "read_promotion_dry_run_evidence", "method": "GET", "path": "/api/terminal/governance/promotion-dry-run-evidence"},
    {"id": "refresh_promotion_dry_run_evidence", "method": "POST", "path": "/api/terminal/governance/refresh-promotion-dry-run-evidence"},
    {"id": "read_production_cache_gate", "method": "GET", "path": "/api/terminal/managed-proxy/production-cache-gate"},
    {"id": "refresh_production_cache_gate", "method": "POST", "path": "/api/terminal/managed-proxy/refresh-production-cache-gate"},
    {"id": "build_production_cache_dry_run", "method": "POST", "path": "/api/terminal/managed-proxy/build-production-cache-dry-run"},
    {"id": "read_registry_safety", "method": "GET", "path": "/api/terminal/research/model-registry-safety"},
    {"id": "refresh_registry_safety", "method": "POST", "path": "/api/terminal/research/refresh-model-registry-safety"},
    {"id": "read_access_control", "method": "GET", "path": "/api/terminal/governance/access-control"},
    {"id": "refresh_access_control", "method": "POST", "path": "/api/terminal/governance/refresh-access-control"},
    {"id": "build_feature_store_v12", "method": "POST", "path": "/api/terminal/feature-store/build-v12"},
    {"id": "build_training_dataset_v12", "method": "POST", "path": "/api/terminal/training-dataset/build-v12"},
    {"id": "train_candidate", "method": "POST", "path": "/api/terminal/models/train-candidate"},
    {"id": "run_candidate_v12", "method": "POST", "path": "/api/terminal/research/run-candidate-v12"},
    {"id": "promotion_dry_run", "method": "POST", "path": "/api/terminal/models/promote-candidate", "dry_run_required": True},
    {"id": "approve_active", "method": "POST", "path": "/api/terminal/models/approve-active"},
    {"id": "refresh_predictions", "method": "POST", "path": "/api/terminal/refresh/predictions"},
    {"id": "save_local_secrets", "method": "POST", "path": "/api/terminal/settings/secrets", "raw_secret_input_allowed": False},
)

UI_SCAN_PATHS = (
    Path("frontend/src/pages/GovernanceConsolePage.tsx"),
    Path("frontend/src/pages/ResearchLabPage.tsx"),
    Path("frontend/src/pages/DataStatusPage.tsx"),
    Path("frontend/src/pages/TrainingDataPage.tsx"),
    Path("frontend/src/pages/FactorPage.tsx"),
)


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _output_dir() -> Path:
    return get_user_output_dir()


def _report_path() -> Path:
    path = _output_dir() / "model_research" / "governance_access_control_report.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _safe_payload(payload: Any) -> Any:
    return _scrub_payload(payload)


def _scrub_payload(payload: Any) -> Any:
    if isinstance(payload, Mapping):
        return {sanitize_text(str(key)): _scrub_payload(value) for key, value in payload.items()}
    if isinstance(payload, list):
        return [_scrub_payload(item) for item in payload]
    if isinstance(payload, str):
        return sanitize_text(payload)
    return payload


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return dict(payload) if isinstance(payload, Mapping) else {}


def _decision_board_path() -> Path:
    return _output_dir() / "model_research" / "research_decision_board.json"


def _current_decision_board() -> dict[str, Any]:
    return _read_json(_decision_board_path())


def build_permission_matrix() -> dict[str, dict[str, Any]]:
    matrix = {
        "safe_read": {
            "default_allowed": True,
            "requires": ["read_only"],
            "forbidden_side_effects": ["training", "active_update", "customer_output", "secret_write"],
        },
        "safe_refresh": {
            "default_allowed": True,
            "requires": ["declared_report_outputs_only"],
            "forbidden_side_effects": ["training", "active_update", "customer_output", "secret_write"],
        },
        "safe_dry_run": {
            "default_allowed": True,
            "requires": ["dry_run_only"],
            "forbidden_side_effects": ["downstream_build", "training", "active_update", "customer_output"],
        },
        "report_write": {
            "default_allowed": True,
            "requires": ["governance_report_output"],
            "forbidden_side_effects": ["training", "active_update", "customer_output"],
        },
        "heavy_build": {
            "default_allowed": False,
            "requires": ["decision_board_explicit_allowed"],
            "forbidden_when": ["managed_data_blocked", "stale_evidence", "missing_permissions"],
        },
        "research_train": {
            "default_allowed": False,
            "requires": ["candidate_training_allowed_true"],
            "forbidden_when": ["dataset_blocked", "candidate_gate_blocked", "missing_permissions"],
        },
        "promotion_dry_run": {
            "default_allowed": True,
            "requires": ["dry_run_true", "active_updated_false"],
            "forbidden_side_effects": ["active_update", "customer_output"],
        },
        "active_write": {
            "default_allowed": False,
            "requires": ["explicit_manual_approval_outside_default_policy"],
            "forbidden_side_effects": ["unapproved_active_update"],
        },
        "customer_prediction_write": {
            "default_allowed": False,
            "requires": ["active_and_shadow_policy_outside_default_policy"],
            "forbidden_side_effects": ["customer_output"],
        },
        "secret_write": {
            "default_allowed": False,
            "requires": ["local_ignored_config_only"],
            "forbidden_side_effects": ["raw_secret_from_api_or_ui"],
        },
    }
    return _safe_payload(matrix)


def classify_api_action(method: str, path: str) -> dict[str, Any]:
    clean_path = str(path or "").split("?", 1)[0]
    clean_method = str(method or "GET").upper()
    category = "safe_read" if clean_method == "GET" else "report_write"
    if clean_method == "POST":
        category = "safe_refresh" if "/refresh-" in clean_path or clean_path.endswith("/refresh-access-control") else "report_write"
    if clean_path.endswith("/refresh-production-cache-gate"):
        category = "report_write"
    if "run-safe-readiness-checks" in clean_path or "dry-run" in clean_path or "shadow-replay" in clean_path or "noop-release-plan" in clean_path or "simulate-artifact-quarantine" in clean_path or clean_path.endswith("/check"):
        category = "safe_dry_run"
    if any(fragment in clean_path for fragment in ("delete-artifact", "move-artifact", "real-quarantine", "quarantine-artifact-real")):
        category = "active_write"
    if clean_path.endswith("/build-shadow-output"):
        category = "customer_prediction_write"
    if any(fragment in clean_path for fragment in ("/feature-store/build", "/training-dataset/build", "/refresh/managed-proxy-v11")):
        category = "heavy_build"
    if any(fragment in clean_path for fragment in ("deploy-monitoring", "monitoring-daemon", "start-live-monitoring")):
        category = "heavy_build"
    if any(fragment in clean_path for fragment in ("/models/train-candidate", "/research/run-candidate", "/research/run-model-experiment")):
        category = "research_train"
    if "/models/promote-candidate" in clean_path:
        category = "promotion_dry_run"
    if "/models/approve-active" in clean_path:
        category = "active_write"
    if "/refresh/predictions" in clean_path:
        category = "customer_prediction_write"
    if "/settings/secrets" in clean_path or "/settings/reset" in clean_path:
        category = "secret_write"
    return _safe_payload({"method": clean_method, "path": clean_path, "category": category})


def _truthy(payload: Mapping[str, Any], key: str) -> bool:
    return bool(payload.get(key))


def validate_action_against_permissions(action: Mapping[str, Any], *, decision_board: Mapping[str, Any] | None = None) -> dict[str, Any]:
    board = decision_board or {}
    category = str(action.get("category") or "")
    reasons: list[str] = []
    allowed = False

    if category in {"safe_read", "report_write", "safe_dry_run"}:
        allowed = True
    elif category == "safe_refresh":
        allowed = not bool(action.get("training_invoked"))
        if not allowed:
            reasons.append("safe_refresh_must_not_train")
    elif category == "heavy_build":
        allowed = bool(board.get("heavy_build_allowed") or board.get("training_dataset_v12_allowed"))
        if str(board.get("current_research_state") or "").lower() == "managed_data_blocked" or not allowed:
            allowed = False
            reasons.append("heavy_build_blocked_by_decision_board")
    elif category == "research_train":
        allowed = _truthy(board, "candidate_training_allowed")
        if not allowed:
            reasons.append("candidate_training_not_allowed")
    elif category == "promotion_dry_run":
        allowed = not bool(action.get("active_updated"))
        if not allowed:
            reasons.append("promotion_dry_run_must_not_write_active")
    elif category == "active_write":
        allowed = False
        reasons.append("active_write_default_forbidden")
    elif category == "customer_prediction_write":
        allowed = False
        reasons.append("customer_prediction_write_default_forbidden")
    elif category == "secret_write":
        allowed = False
        reasons.append("secret_write_from_api_or_ui_forbidden")
    else:
        allowed = False
        reasons.append("unknown_permission_category")

    return _safe_payload(
        {
            "action_id": action.get("id") or action.get("path") or "unknown",
            "category": category or "unknown",
            "allowed": bool(allowed),
            "blocking_reasons": reasons,
        }
    )


def _read_ui_pages() -> dict[str, str]:
    pages: dict[str, str] = {}
    for path in UI_SCAN_PATHS:
        if not path.exists():
            continue
        try:
            pages[str(path)] = path.read_text(encoding="utf-8")
        except Exception:
            continue
    return pages


def detect_forbidden_ui_actions(ui_pages: Mapping[str, str] | None = None) -> dict[str, Any]:
    pages = dict(ui_pages) if ui_pages is not None else _read_ui_pages()
    inventory: list[dict[str, Any]] = []
    violations: list[str] = []
    patterns: tuple[tuple[str, str, str], ...] = (
        ("active_publish_button_exposed", "active_write", "publish active"),
        ("active_publish_button_exposed", "active_write", "approve active"),
        ("active_publish_helper_exposed", "active_write", "approveActiveModel"),
        ("customer_prediction_button_exposed", "customer_prediction_write", "generate customer prediction"),
        ("customer_prediction_helper_exposed", "customer_prediction_write", "refreshPredictions"),
        ("raw_secret_input_field_exposed", "secret_write", "SN_TUSHARE_TOKEN"),
        ("raw_secret_input_field_exposed", "secret_write", "SN_MANAGED_DATA_PROXY_TOKEN"),
        ("raw_secret_input_field_exposed", "secret_write", "raw token"),
        ("raw_secret_input_field_exposed", "secret_write", "Authorization"),
    )
    for page, text in pages.items():
        lowered = text.lower()
        page_hits: list[dict[str, Any]] = []
        for violation, category, pattern in patterns:
            found = pattern in text if pattern.lower() != pattern else pattern in lowered
            if not found:
                continue
            # Existing ResearchLab manual approval remains part of the legacy research workflow;
            # the governance console itself must not expose it as a one-click action.
            is_governance_page = page.endswith("GovernanceConsolePage.tsx")
            is_existing_guarded_surface = (not is_governance_page) and category in {"active_write", "customer_prediction_write"}
            hit = {
                "page": page,
                "category": category,
                "violation": violation,
                "guarded_existing_surface": bool(is_existing_guarded_surface),
            }
            page_hits.append(hit)
            if not is_existing_guarded_surface:
                violations.append(violation)
        if page_hits:
            inventory.extend(page_hits)
    return _safe_payload(
        {
            "ui_action_inventory": inventory,
            "violations": sorted(set(violations)),
            "violation_count": len(set(violations)),
        }
    )


def _build_api_inventory(decision_board: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for raw in API_ACTIONS:
        classified = {**raw, **classify_api_action(str(raw["method"]), str(raw["path"]))}
        validation = validate_action_against_permissions(classified, decision_board=decision_board)
        rows.append(
            {
                "id": raw["id"],
                "method": classified["method"],
                "path": classified["path"],
                "category": classified["category"],
                "allowed": validation["allowed"],
                "blocking_reasons": validation["blocking_reasons"],
                "raw_secret_input_allowed": bool(raw.get("raw_secret_input_allowed", True)) if classified["category"] == "secret_write" else None,
                "training_invoked": False,
                "active_updated": False,
                "customer_prediction_generated": False,
            }
        )
    return _safe_payload(rows)


def _partition_actions(api_inventory: Sequence[Mapping[str, Any]]) -> dict[str, list[str]]:
    allowed_safe: list[str] = []
    forbidden: list[str] = []
    blocked_heavy: list[str] = []
    blocked_secret: list[str] = []
    for action in api_inventory:
        action_id = str(action.get("id") or action.get("path") or "unknown")
        category = str(action.get("category") or "")
        allowed = bool(action.get("allowed"))
        if allowed and category in {"safe_read", "safe_refresh", "safe_dry_run", "report_write", "promotion_dry_run"}:
            allowed_safe.append(action_id)
        if category in {"active_write", "customer_prediction_write", "secret_write"}:
            forbidden.append(category)
            if category == "secret_write":
                blocked_secret.append(action_id)
        if category in {"heavy_build", "research_train"} and not allowed:
            blocked_heavy.append(action_id)
    return {
        "allowed_safe_actions": sorted(set(allowed_safe)),
        "forbidden_actions": sorted(set(forbidden)),
        "blocked_heavy_actions": sorted(set(blocked_heavy)),
        "blocked_secret_actions": sorted(set(blocked_secret)),
    }


def build_access_control_report(
    *,
    write: bool = True,
    decision_board: Mapping[str, Any] | None = None,
    ui_pages: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    board = dict(decision_board) if decision_board is not None else _current_decision_board()
    matrix = build_permission_matrix()
    api_inventory = _build_api_inventory(board)
    ui_scan = detect_forbidden_ui_actions(ui_pages)
    partitions = _partition_actions(api_inventory)
    missing_permissions = [category for category in PERMISSION_CATEGORIES if category not in matrix]
    ui_api_violation_count = int(ui_scan.get("violation_count") or 0) + len(missing_permissions)
    status = "violation" if ui_api_violation_count else ("blocked" if not board else "guarded")
    report = {
        "status": status,
        "generated_at": _now(),
        "access_control_version": ACCESS_CONTROL_VERSION,
        "permission_matrix": matrix,
        "api_action_inventory": api_inventory,
        "ui_action_inventory": ui_scan.get("ui_action_inventory", []),
        "forbidden_actions": partitions["forbidden_actions"],
        "allowed_safe_actions": partitions["allowed_safe_actions"],
        "blocked_heavy_actions": partitions["blocked_heavy_actions"],
        "blocked_secret_actions": partitions["blocked_secret_actions"],
        "ui_api_violations": ui_scan.get("violations", []),
        "ui_api_violations_count": ui_api_violation_count,
        "decision_board_state": {
            "status": board.get("status", "missing"),
            "current_research_state": board.get("current_research_state", "missing"),
            "candidate_training_allowed": bool(board.get("candidate_training_allowed")),
            "training_dataset_v12_allowed": bool(board.get("training_dataset_v12_allowed")),
            "next_allowed_action": board.get("next_allowed_action", "missing"),
        },
        "active_write_allowed": False,
        "customer_prediction_write_allowed": False,
        "training_invoked": False,
        "active_updated": False,
        "customer_prediction_generated": False,
        "report_path": str(_report_path()),
    }
    safe = _safe_payload(report)
    if write:
        _report_path().write_text(json.dumps(safe, ensure_ascii=False, indent=2), encoding="utf-8")
    return safe


def refresh_access_control_report() -> dict[str, Any]:
    report = build_access_control_report(write=True)
    run = start_research_run(
        service_name="governance_access_control",
        run_type="safe_refresh",
        output_paths=[str(_report_path())],
    )
    finalized = finalize_research_run(run)
    if int(report.get("ui_api_violations_count") or 0) > 0:
        finalized = {
            **finalized,
            "status": "violation",
            "blocking_reasons": list(report.get("ui_api_violations") or ["governance_access_control_violation"]),
        }
    append_run_ledger(finalized)
    return report


def get_access_control_report() -> dict[str, Any]:
    path = _report_path()
    if path.exists():
        payload = _read_json(path)
        if payload:
            return _safe_payload(payload)
    return build_access_control_report(write=False)
