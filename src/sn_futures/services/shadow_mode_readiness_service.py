from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping, Sequence

from ..api.json_utils import sanitize_for_json
from ..runtime import get_user_output_dir
from ..utils.secret_sanitizer import sanitize_mapping


SPEC_VERSION = "shadow_mode_readiness_v1"
SPEC_FILENAME = "shadow_mode_readiness_spec.json"


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _output_dir() -> Path:
    return get_user_output_dir()


def _spec_path() -> Path:
    path = _output_dir() / "model_research" / SPEC_FILENAME
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _read_json(path: Path) -> Any:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _safe_payload(payload: Any) -> Any:
    return sanitize_for_json(sanitize_mapping(payload))


def _write_json(path: Path, payload: Mapping[str, Any]) -> dict[str, Any]:
    safe = _safe_payload(dict(payload))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(safe, ensure_ascii=False, indent=2), encoding="utf-8")
    return safe


def _first_existing(paths: Sequence[Path]) -> Path:
    for path in paths:
        if path.exists():
            return path
    return paths[0]


def _path(relative_path: str, *fallbacks: str) -> Path:
    output = _output_dir()
    paths = [output / relative_path]
    paths.extend(Path("outputs") / item for item in fallbacks or (relative_path,))
    return _first_existing(paths)


def _load(label: str, relative_path: str, *fallbacks: str) -> tuple[dict[str, Any], str, str]:
    path = _path(relative_path, *fallbacks)
    payload = _read_json(path)
    if isinstance(payload, Mapping):
        return dict(payload), str(path), "present"
    return {}, str(path), "missing"


def _status(payload: Mapping[str, Any] | None) -> str:
    if not isinstance(payload, Mapping):
        return "missing"
    return str(payload.get("status") or "missing").lower()


def _as_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value if str(item or "").strip()]
    if value is None:
        return []
    text = str(value).strip()
    return [text] if text else []


def _normalise_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"true", "1", "yes", "pass", "ready", "success"}
    return bool(value)


def _gate(name: str, passed: bool, reason: str, evidence_path: str = "") -> dict[str, Any]:
    return {
        "gate": name,
        "passed": bool(passed),
        "status": "pass" if passed else "blocked",
        "reason": "" if passed else reason,
        "evidence_path": evidence_path,
    }


def _blocked_gates(gates: Sequence[Mapping[str, Any]]) -> list[str]:
    return [str(gate.get("reason") or gate.get("gate")) for gate in gates if not bool(gate.get("passed"))]


def _candidate_cost_attribution(candidate: Mapping[str, Any]) -> dict[str, Any]:
    cost = candidate.get("cost_stress_attribution")
    return dict(cost) if isinstance(cost, Mapping) else {}


def _cost_attribution(payload: Mapping[str, Any], candidate_v10: Mapping[str, Any]) -> dict[str, Any]:
    candidate_cost = _candidate_cost_attribution(candidate_v10)
    if candidate_cost:
        return candidate_cost
    if payload.get("candidate_version") == "v10" or payload.get("failure_drivers"):
        return dict(payload)
    candidate = payload.get("candidate_v10")
    if isinstance(candidate, Mapping):
        cost = candidate.get("cost_stress_attribution")
        if isinstance(cost, Mapping):
            return dict(cost)
    return {}


def _cpcv_pass(cpcv_report: Mapping[str, Any], candidate_v10: Mapping[str, Any] | None = None) -> tuple[bool, str]:
    if not cpcv_report and not candidate_v10:
        return False, "cpcv_evidence_missing"
    status = _status(cpcv_report)
    pbo = cpcv_report.get("pbo") if isinstance(cpcv_report.get("pbo"), Mapping) else {}
    reality = cpcv_report.get("reality_check") if isinstance(cpcv_report.get("reality_check"), Mapping) else {}
    if status in {"fail", "failed", "blocked"}:
        return False, "cpcv_or_pbo_failed"
    if pbo or reality:
        pbo_ok = bool(pbo.get("passed", True))
        reality_ok = bool(reality.get("passed", True))
        return (pbo_ok and reality_ok), "cpcv_or_pbo_failed"
    gates = candidate_v10.get("v10_gate_checks") if isinstance(candidate_v10, Mapping) and isinstance(candidate_v10.get("v10_gate_checks"), Mapping) else {}
    if gates:
        return bool(gates.get("pbo_lt_0_2", False) and gates.get("reality_check_pass", False)), "cpcv_or_pbo_failed"
    return False, "cpcv_evidence_missing"


def validate_shadow_mode_entry_gates(
    *,
    decision_board: Mapping[str, Any],
    evidence_freshness: Mapping[str, Any],
    cost_attribution: Mapping[str, Any],
    cpcv_report: Mapping[str, Any],
    pit_audit: Mapping[str, Any],
    data_quality: Mapping[str, Any],
    evidence_bundle: Mapping[str, Any] | None = None,
    candidate_v10: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    candidate_v10 = candidate_v10 or {}
    evidence_bundle = evidence_bundle or {}
    manual = bool(decision_board.get("manual_approval_recommended") or candidate_v10.get("manual_approval_recommended"))
    active_locked = not bool(decision_board.get("active_publish_allowed"))

    stale_reports = _as_list(evidence_freshness.get("stale_reports"))
    missing_timestamps = _as_list(evidence_freshness.get("missing_timestamps"))
    timestamp_inversions = _as_list(evidence_freshness.get("timestamp_inversions"))
    freshness_status = _status(evidence_freshness)
    freshness_present = bool(evidence_freshness)
    freshness_ok = freshness_present and freshness_status not in {"blocked", "fail", "failed", "missing"} and not stale_reports and not missing_timestamps and not timestamp_inversions

    missing_reports = _as_list(evidence_bundle.get("missing_reports"))
    incomplete_reports = _as_list(evidence_bundle.get("incomplete_reports"))
    bundle_status = _status(evidence_bundle)
    bundle_ok = (
        not evidence_bundle
        or bundle_status not in {"blocked", "fail", "failed", "missing"}
        and not missing_reports
        and not incomplete_reports
    )

    cost_status = _status(cost_attribution)
    failure_drivers = _as_list(cost_attribution.get("failure_drivers"))
    cost_ok = bool(cost_attribution) and cost_status in {"pass", "ready", "success"} and _normalise_bool(cost_attribution.get("passed", True)) and not failure_drivers
    cpcv_ok, cpcv_reason = _cpcv_pass(cpcv_report, candidate_v10)

    leakage = pit_audit.get("leakage_checks") if isinstance(pit_audit.get("leakage_checks"), Mapping) else {}
    pit_ok = bool(pit_audit) and _status(pit_audit) in {"ready", "pass", "success"} and bool(leakage.get("point_in_time_join_ready", pit_audit.get("point_in_time_join_ready", False)))

    quality_ok = bool(data_quality) and (_status(data_quality) in {"ready", "pass", "success"} and _normalise_bool(data_quality.get("gate_passed", False)))
    gates = [
        _gate("manual_approval_recommended", manual, "manual_approval_missing"),
        _gate("active_publish_locked", active_locked, "active_publish_must_remain_locked_for_shadow"),
        _gate("evidence_freshness", freshness_ok, "stale_evidence_present" if freshness_present else "evidence_freshness_missing"),
        _gate("evidence_bundle_complete", bundle_ok, "evidence_bundle_incomplete_or_missing"),
        _gate("cost_attribution", cost_ok, "cost_attribution_fail_or_missing"),
        _gate("cpcv_pbo_reality", cpcv_ok, cpcv_reason),
        _gate("pit_audit", pit_ok, "pit_or_data_quality_evidence_missing"),
        _gate("data_quality", quality_ok, "pit_or_data_quality_evidence_missing"),
    ]
    blocked = _blocked_gates(gates)
    return _safe_payload(
        {
            "status": "pass" if not blocked else "blocked",
            "entry_gates": gates,
            "blocked_gates": sorted(set(blocked)),
        }
    )


def _active_paths() -> list[Path]:
    out = _output_dir()
    return [
        out / "model_registry" / "active_model.json",
        out / "models" / "active_model.json",
        Path("outputs") / "model_registry" / "active_model.json",
        Path("outputs") / "models" / "active_model.json",
    ]


def _prediction_paths() -> list[Path]:
    out = _output_dir()
    return [
        out / "customer_predictions",
        out / "customer_predictions.json",
        Path("outputs") / "customer_predictions",
        Path("outputs") / "customer_predictions.json",
    ]


def _normalise_path(path: Path) -> str:
    return str(path.resolve(strict=False)).replace("\\", "/").lower()


def build_shadow_output_contract() -> dict[str, Any]:
    output = _output_dir()
    shadow_root = output / "shadow_mode"
    customer_root = output / "customer_predictions"
    shadow_norm = _normalise_path(shadow_root)
    customer_norm = _normalise_path(customer_root)
    separate = shadow_norm != customer_norm and not shadow_norm.startswith(f"{customer_norm}/")
    return _safe_payload(
        {
            "shadow_output_root": str(shadow_root),
            "customer_predictions_root": str(customer_root),
            "paths_are_separate": separate,
            "allowed_shadow_outputs": [
                "research-only shadow observations",
                "shadow readiness reports",
                "non-customer shadow audit logs",
            ],
            "forbidden_outputs": [
                "customer_predictions",
                "customer_predictions.json",
                "active_model.json",
                "trade_point_predictions",
            ],
            "isolation_rule": "Shadow mode outputs must stay under outputs/shadow_mode and must never be written under customer_predictions or active model paths.",
        }
    )


def validate_prediction_isolation(output_contract: Mapping[str, Any] | None = None) -> dict[str, Any]:
    contract = dict(output_contract or build_shadow_output_contract())
    existing_predictions = [str(path) for path in _prediction_paths() if path.exists()]
    existing_active = [str(path) for path in _active_paths() if path.exists()]
    paths_are_separate = bool(contract.get("paths_are_separate"))
    customer_predictions_absent = not existing_predictions
    active_model_absent = not existing_active
    blocked: list[str] = []
    if not paths_are_separate:
        blocked.append("shadow_output_not_isolated")
    if not customer_predictions_absent:
        blocked.append("customer_predictions_present")
    if not active_model_absent:
        blocked.append("active_model_present")
    return _safe_payload(
        {
            "status": "pass" if not blocked else "blocked",
            "paths_are_separate": paths_are_separate,
            "customer_predictions_absent": customer_predictions_absent,
            "active_model_absent": active_model_absent,
            "existing_customer_prediction_paths": existing_predictions,
            "existing_active_model_paths": existing_active,
            "blocked_gates": blocked,
        }
    )


def _collect_reports() -> dict[str, Any]:
    decision_board, decision_path, decision_state = _load("decision_board", "model_research/research_decision_board.json")
    evidence_bundle, bundle_path, bundle_state = _load("evidence_bundle", "model_research/evidence_bundle_index.json")
    evidence_freshness, freshness_path, freshness_state = _load("evidence_freshness", "model_research/evidence_freshness_report.json")
    cost_payload, cost_path, cost_state = _load("cost_attribution", "model_research/cost_stress_attribution.json")
    cpcv, cpcv_path, cpcv_state = _load("cpcv", "validation/cpcv/cpcv_report.json", "model_research/candidate_v10/cpcv_validation_v10.json")
    candidate_v10, candidate_v10_path, candidate_v10_state = _load("candidate_v10", "model_research/candidate_v10/candidate_v10_gated_research_report.json")
    candidate_v12, candidate_v12_path, candidate_v12_state = _load("candidate_v12", "model_research/candidate_v12/candidate_v12_gated_research_report.json")
    run_ledger, run_ledger_path, run_ledger_state = _load("run_ledger", "model_research/run_ledger/research_run_ledger_report.json")
    pit_audit, pit_path, pit_state = _load("pit_audit", "diagnostics/managed_data_audit_manifest.json")
    quality, quality_path, quality_state = _load("data_quality", "diagnostics/managed_data_quality_scorecard.json")
    return {
        "reports": {
            "decision_board": decision_board,
            "evidence_bundle": evidence_bundle,
            "evidence_freshness": evidence_freshness,
            "cost_attribution": _cost_attribution(cost_payload, candidate_v10),
            "cpcv": cpcv,
            "candidate_v10": candidate_v10,
            "candidate_v12": candidate_v12,
            "run_ledger": run_ledger,
            "pit_audit": pit_audit,
            "data_quality": quality,
        },
        "evidence_paths": {
            "decision_board": {"path": decision_path, "status": decision_state},
            "evidence_bundle": {"path": bundle_path, "status": bundle_state},
            "evidence_freshness": {"path": freshness_path, "status": freshness_state},
            "cost_attribution": {"path": cost_path, "status": cost_state},
            "cpcv": {"path": cpcv_path, "status": cpcv_state},
            "candidate_v10": {"path": candidate_v10_path, "status": candidate_v10_state},
            "candidate_v12": {"path": candidate_v12_path, "status": candidate_v12_state},
            "run_ledger": {"path": run_ledger_path, "status": run_ledger_state},
            "pit_audit": {"path": pit_path, "status": pit_state},
            "data_quality": {"path": quality_path, "status": quality_state},
        },
    }


def build_shadow_mode_readiness_spec(*, write: bool = True) -> dict[str, Any]:
    collected = _collect_reports()
    reports = collected["reports"]
    output_contract = build_shadow_output_contract()
    isolation = validate_prediction_isolation(output_contract)
    entry = validate_shadow_mode_entry_gates(
        decision_board=reports["decision_board"],
        evidence_freshness=reports["evidence_freshness"],
        evidence_bundle=reports["evidence_bundle"],
        cost_attribution=reports["cost_attribution"],
        cpcv_report=reports["cpcv"],
        pit_audit=reports["pit_audit"],
        data_quality=reports["data_quality"],
        candidate_v10=reports["candidate_v10"],
    )
    blocked = sorted(set(_as_list(entry.get("blocked_gates")) + _as_list(isolation.get("blocked_gates"))))
    shadow_allowed = not blocked
    payload = {
        "status": "ready" if shadow_allowed else "blocked",
        "generated_at": _now(),
        "shadow_mode_version": SPEC_VERSION,
        "report_path": str(_spec_path()),
        "shadow_mode_allowed": shadow_allowed,
        "entry_gates": entry.get("entry_gates", []),
        "blocked_gates": blocked,
        "output_isolation_contract": output_contract,
        "prediction_isolation": isolation,
        "forbidden_outputs": output_contract.get("forbidden_outputs", []),
        "approval_required": True,
        "active_publish_allowed": False,
        "evidence_paths": collected["evidence_paths"],
        "run_ledger_status": reports["run_ledger"].get("status", "missing"),
        "active_updated": False,
        "customer_prediction_generated": False,
    }
    return _write_json(_spec_path(), payload) if write else _safe_payload(payload)


def get_shadow_mode_readiness_spec() -> dict[str, Any]:
    payload = _read_json(_spec_path())
    if isinstance(payload, Mapping):
        return _safe_payload(dict(payload))
    return build_shadow_mode_readiness_spec(write=False)
