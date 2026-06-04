from __future__ import annotations

import json
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping, Sequence

from ..api.json_utils import sanitize_for_json
from ..runtime import get_user_output_dir
from ..utils.secret_sanitizer import sanitize_mapping


PREFLIGHT_VERSION = "candidate_v10_remediation_preflight_v1"
REPORT_FILENAME = "candidate_v10_remediation_preflight.json"
REPEATED_PRIMARY_METRIC_LIMIT = 3


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _output_dir() -> Path:
    return get_user_output_dir()


def _research_dir() -> Path:
    path = _output_dir() / "model_research" / "candidate_v10"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _report_path() -> Path:
    return _research_dir() / REPORT_FILENAME


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


def _as_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value if str(item or "").strip()]
    if value is None:
        return []
    text = str(value).strip()
    return [text] if text else []


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _first_existing(paths: Sequence[Path]) -> Path:
    for path in paths:
        if path.exists():
            return path
    return paths[0]


def _load_report(label: str) -> tuple[Any, str, str]:
    output = _output_dir()
    paths: dict[str, list[Path]] = {
        "remediation": [
            output / "model_research" / "candidate_v10" / "v10_cost_failure_research_report.json",
            Path("outputs") / "model_research" / "candidate_v10" / "v10_cost_failure_research_report.json",
        ],
        "hypothesis_registry": [
            output / "model_research" / "hypothesis_registry.json",
            Path("outputs") / "model_research" / "hypothesis_registry.json",
        ],
        "anti_p_hacking_ledger": [
            output / "model_research" / "anti_p_hacking_ledger.json",
            Path("outputs") / "model_research" / "anti_p_hacking_ledger.json",
        ],
        "cost_attribution": [
            output / "model_research" / "candidate_v10" / "cost_stress_attribution_v10.json",
            output / "model_research" / "cost_stress_attribution.json",
            Path("outputs") / "model_research" / "candidate_v10" / "cost_stress_attribution_v10.json",
            Path("outputs") / "model_research" / "cost_stress_attribution.json",
        ],
        "year_evidence": [
            output / "model_research" / "year_concentration_evidence.json",
            output / "model_research" / "candidate_v10" / "year_concentration_evidence_v10.json",
            Path("outputs") / "model_research" / "year_concentration_evidence.json",
            Path("outputs") / "model_research" / "candidate_v10" / "year_concentration_evidence_v10.json",
        ],
        "cpcv": [
            output / "validation" / "cpcv" / "cpcv_report.json",
            output / "model_research" / "candidate_v10" / "cpcv_validation_v10.json",
            Path("outputs") / "validation" / "cpcv" / "cpcv_report.json",
            Path("outputs") / "model_research" / "candidate_v10" / "cpcv_validation_v10.json",
        ],
        "candidate_v10": [
            output / "model_research" / "candidate_v10" / "candidate_v10_gated_research_report.json",
            Path("outputs") / "model_research" / "candidate_v10" / "candidate_v10_gated_research_report.json",
        ],
        "decision_board": [
            output / "model_research" / "research_decision_board.json",
            Path("outputs") / "model_research" / "research_decision_board.json",
        ],
    }
    selected = _first_existing(paths[label])
    payload = _read_json(selected)
    state = "present" if isinstance(payload, Mapping) else "missing"
    return payload, str(selected), state


def _extract_cost_attribution(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        return {}
    if payload.get("candidate_version") == "v10" or payload.get("failure_drivers") or payload.get("by_horizon"):
        return dict(payload)
    candidate = payload.get("candidate_v10")
    if isinstance(candidate, Mapping):
        attribution = candidate.get("cost_stress_attribution")
        if isinstance(attribution, Mapping):
            return dict(attribution)
    attribution = payload.get("cost_stress_attribution")
    return dict(attribution) if isinstance(attribution, Mapping) else {}


def _primary_metrics(entry: Mapping[str, Any]) -> list[str]:
    rule = entry.get("primary_decision_rule")
    if isinstance(rule, Mapping):
        return _as_list(rule.get("primary_metrics"))
    return []


def _open_hypotheses(registry: Mapping[str, Any] | None) -> list[dict[str, Any]]:
    if not isinstance(registry, Mapping):
        return []
    return [
        dict(item)
        for item in registry.get("hypotheses", [])
        if isinstance(item, Mapping) and str(item.get("status") or "open") == "open"
    ]


def _remediation_rows(remediation_report: Mapping[str, Any] | None) -> list[dict[str, Any]]:
    if not isinstance(remediation_report, Mapping):
        return []
    rows = remediation_report.get("ranked_hypotheses")
    if isinstance(rows, list):
        return [dict(item) for item in rows if isinstance(item, Mapping)]
    recommended = remediation_report.get("recommended_next_experiment")
    return [{"id": str(recommended), "title": str(recommended), "rank_score": 0.0}] if recommended else []


def _remediation_id(row: Mapping[str, Any]) -> str:
    return str(row.get("id") or row.get("hypothesis_id") or "").replace("template-", "").replace("hyp-", "")


def _entry_text(entry: Mapping[str, Any]) -> str:
    parts = [
        entry.get("hypothesis_id"),
        entry.get("title"),
        entry.get("motivation"),
        entry.get("linked_blocker"),
        entry.get("dataset_version_allowed"),
        entry.get("candidate_version_allowed"),
    ]
    parts.extend(_as_list(entry.get("allowed_metrics")))
    return " ".join(str(part).lower() for part in parts if part is not None)


def _entry_matches_remediation(entry: Mapping[str, Any], remediation_row: Mapping[str, Any]) -> bool:
    rid = _remediation_id(remediation_row)
    if not rid:
        return False
    text = _entry_text(entry).replace("-", "_")
    return rid.lower().replace("-", "_") in text


def validate_hypothesis_links(
    hypotheses: Sequence[Mapping[str, Any]],
    remediation_report: Mapping[str, Any] | None,
    cost_attribution: Mapping[str, Any] | None,
) -> dict[str, Any]:
    rows = _remediation_rows(remediation_report)
    drivers = set(_as_list((cost_attribution or {}).get("failure_drivers")))
    linked: list[dict[str, Any]] = []
    unlinked: list[dict[str, Any]] = []
    for entry in hypotheses:
        linked_blocker = str(entry.get("linked_blocker") or "")
        matches_driver = any(driver in linked_blocker for driver in drivers) or "cost_attribution" in linked_blocker
        matched_row = next((row for row in rows if _entry_matches_remediation(entry, row)), None)
        if matches_driver or matched_row:
            item = dict(entry)
            item["matched_remediation_id"] = _remediation_id(matched_row or {}) or ""
            linked.append(item)
        else:
            unlinked.append({"hypothesis_id": entry.get("hypothesis_id", ""), "reason": "linked_blocker_not_in_cost_attribution"})
    return _safe_payload(
        {
            "status": "linked" if linked else "blocked",
            "linked_hypotheses": linked,
            "unlinked_hypotheses": unlinked,
            "blocking_reasons": [] if linked else ["no_hypothesis_linked_to_v10_cost_blocker"],
        }
    )


def check_metric_budget(hypotheses: Sequence[Mapping[str, Any]], ledger: Mapping[str, Any] | None = None) -> dict[str, Any]:
    metric_counts: Counter[str] = Counter()
    blocker_counts: Counter[str] = Counter()
    for entry in hypotheses:
        for metric in _primary_metrics(entry):
            metric_counts[metric] += 1
        blocker_counts[str(entry.get("linked_blocker") or "unlinked")] += 1

    repeated_metrics = {
        metric: count
        for metric, count in metric_counts.items()
        if count > REPEATED_PRIMARY_METRIC_LIMIT
    }
    ledger_risk = str((ledger or {}).get("p_hacking_risk_level") or "none")
    over_budget_blockers = {
        blocker: count
        for blocker, count in blocker_counts.items()
        if count > REPEATED_PRIMARY_METRIC_LIMIT
    }
    risk_level = "high" if repeated_metrics or over_budget_blockers or ledger_risk == "high" else ("medium" if ledger_risk == "medium" or any(count > 1 for count in metric_counts.values()) else "low")
    warnings: list[str] = []
    if repeated_metrics:
        warnings.extend([f"repeated_primary_metric:{metric}" for metric in sorted(repeated_metrics)])
    if over_budget_blockers:
        warnings.extend([f"experiment_budget_exceeded:{blocker}" for blocker in sorted(over_budget_blockers)])
    return _safe_payload(
        {
            "status": "high_risk" if risk_level == "high" else "within_budget",
            "p_hacking_risk_level": risk_level,
            "primary_metric_counts": dict(metric_counts),
            "blocker_counts": dict(blocker_counts),
            "repeated_primary_metrics": repeated_metrics,
            "warning_reasons": warnings,
        }
    )


def _affected_year_values(remediation_report: Mapping[str, Any] | None) -> list[str]:
    years: list[str] = []
    for row in _remediation_rows(remediation_report):
        value = row.get("affected_year")
        if value is not None and str(value).strip():
            years.append(str(value))
    return years


def estimate_overfitting_risk(
    *,
    hypotheses: Sequence[Mapping[str, Any]],
    remediation_report: Mapping[str, Any] | None,
    metric_budget_status: Mapping[str, Any],
) -> dict[str, Any]:
    reasons = list(metric_budget_status.get("warning_reasons") or [])
    risk_level = str(metric_budget_status.get("p_hacking_risk_level") or "low")
    risk_score = {"none": 0.0, "low": 0.2, "medium": 0.5, "high": 0.9}.get(risk_level, 0.5)
    years = _affected_year_values(remediation_report)
    unique_years = {year for year in years if year and year.lower() != "none"}
    if len(unique_years) == 1:
        year = sorted(unique_years)[0]
        reasons.append(f"single_year_improvement_risk:{year}")
        risk_score = max(risk_score, 0.65)
        if risk_level == "low":
            risk_level = "medium"
    if any(str(entry.get("risk_of_overfitting") or "").lower() == "high" for entry in hypotheses):
        reasons.append("registered_high_overfitting_hypothesis")
        risk_score = max(risk_score, 0.8)
        risk_level = "high" if risk_level in {"none", "low", "medium"} and metric_budget_status.get("p_hacking_risk_level") == "high" else risk_level
    return _safe_payload(
        {
            "risk_level": risk_level,
            "risk_score": round(risk_score, 3),
            "risk_reasons": sorted(set(reasons)),
        }
    )


def _requires_v12(entry: Mapping[str, Any]) -> bool:
    text = f"{entry.get('dataset_version_allowed', '')} {entry.get('candidate_version_allowed', '')}".lower()
    return "v12" in text


def _board_v12_allowed(board: Mapping[str, Any] | None) -> bool:
    if not isinstance(board, Mapping):
        return False
    return bool(board.get("candidate_v12_allowed") or board.get("feature_store_v12_allowed") or board.get("v12_allowed"))


def _blocked_experiments(hypotheses: Sequence[Mapping[str, Any]], board: Mapping[str, Any] | None) -> list[dict[str, Any]]:
    blocked: list[dict[str, Any]] = []
    v12_allowed = _board_v12_allowed(board)
    for entry in hypotheses:
        reasons: list[str] = []
        if _requires_v12(entry) and not v12_allowed:
            reasons.append("v12_data_blocked")
        if bool(entry.get("training_allowed", False)):
            reasons.append("hypothesis_training_allowed_must_be_false_for_preflight")
        if bool(entry.get("active_allowed", False)):
            reasons.append("hypothesis_active_allowed_must_be_false_for_preflight")
        if bool(entry.get("prediction_allowed", False)):
            reasons.append("hypothesis_prediction_allowed_must_be_false_for_preflight")
        if reasons:
            blocked.append(
                {
                    "hypothesis_id": entry.get("hypothesis_id", ""),
                    "title": entry.get("title", ""),
                    "blocking_reasons": reasons,
                }
            )
    return blocked


def rank_experiments_for_next_round(
    *,
    linked_hypotheses: Sequence[Mapping[str, Any]],
    remediation_report: Mapping[str, Any] | None,
    blocked_experiments: Sequence[Mapping[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    blocked_ids = {str(item.get("hypothesis_id")) for item in blocked_experiments or [] if isinstance(item, Mapping)}
    rows = _remediation_rows(remediation_report)
    ranked: list[dict[str, Any]] = []
    for entry in linked_hypotheses:
        hypothesis_id = str(entry.get("hypothesis_id") or "")
        if hypothesis_id in blocked_ids:
            continue
        matched = next((row for row in rows if _entry_matches_remediation(entry, row)), None)
        fallback = rows[0] if rows else {}
        remediation = matched or fallback
        risk = str(entry.get("risk_of_overfitting") or remediation.get("risk_of_overfitting") or "medium")
        risk_penalty = {"low": 0.0, "medium": 0.1, "high": 0.3}.get(risk, 0.1)
        rank_score = _safe_float(remediation.get("rank_score"), 0.0) - risk_penalty
        ranked.append(
            _safe_payload(
                {
                    "hypothesis_id": hypothesis_id,
                    "title": entry.get("title", ""),
                    "linked_blocker": entry.get("linked_blocker", ""),
                    "matched_remediation_id": _remediation_id(remediation),
                    "affected_horizon": remediation.get("affected_horizon", "unknown"),
                    "affected_regime": remediation.get("affected_regime", "unknown"),
                    "affected_year": remediation.get("affected_year", "unknown"),
                    "risk_of_overfitting": risk,
                    "rank_score": round(rank_score, 6),
                    "research_only": True,
                }
            )
        )
    return sorted(ranked, key=lambda row: _safe_float(row.get("rank_score"), -999.0), reverse=True)


def _evidence_dependency(label: str, path: str, state: str) -> dict[str, Any]:
    return {"name": label, "path": path, "status": state}


def _collect_inputs() -> dict[str, Any]:
    remediation, remediation_path, remediation_state = _load_report("remediation")
    registry, registry_path, registry_state = _load_report("hypothesis_registry")
    ledger, ledger_path, ledger_state = _load_report("anti_p_hacking_ledger")
    cost_payload, cost_path, cost_state = _load_report("cost_attribution")
    year_evidence, year_path, year_state = _load_report("year_evidence")
    cpcv, cpcv_path, cpcv_state = _load_report("cpcv")
    candidate, candidate_path, candidate_state = _load_report("candidate_v10")
    decision_board, board_path, board_state = _load_report("decision_board")
    cost_attribution = _extract_cost_attribution(cost_payload)
    if not cost_attribution:
        cost_state = "missing"
    return {
        "reports": {
            "remediation": remediation if isinstance(remediation, Mapping) else {},
            "hypothesis_registry": registry if isinstance(registry, Mapping) else {},
            "anti_p_hacking_ledger": ledger if isinstance(ledger, Mapping) else {},
            "cost_attribution": cost_attribution,
            "year_evidence": year_evidence if isinstance(year_evidence, Mapping) else {},
            "cpcv": cpcv if isinstance(cpcv, Mapping) else {},
            "candidate_v10": candidate if isinstance(candidate, Mapping) else {},
            "decision_board": decision_board if isinstance(decision_board, Mapping) else {},
        },
        "dependencies": [
            _evidence_dependency("v10_cost_remediation_report", remediation_path, remediation_state),
            _evidence_dependency("hypothesis_registry", registry_path, registry_state),
            _evidence_dependency("anti_p_hacking_ledger", ledger_path, ledger_state),
            _evidence_dependency("cost_attribution", cost_path, cost_state),
            _evidence_dependency("year_evidence", year_path, year_state),
            _evidence_dependency("cpcv_report", cpcv_path, cpcv_state),
            _evidence_dependency("candidate_v10_report", candidate_path, candidate_state),
            _evidence_dependency("research_decision_board", board_path, board_state),
        ],
    }


def build_remediation_preflight(*, write: bool = True) -> dict[str, Any]:
    inputs = _collect_inputs()
    reports = inputs["reports"]
    remediation = reports["remediation"]
    registry = reports["hypothesis_registry"]
    ledger = reports["anti_p_hacking_ledger"]
    cost_attribution = reports["cost_attribution"]
    decision_board = reports["decision_board"]
    hypotheses = _open_hypotheses(registry)
    link_result = validate_hypothesis_links(hypotheses, remediation, cost_attribution)
    linked_hypotheses = [dict(item) for item in link_result.get("linked_hypotheses", []) if isinstance(item, Mapping)]
    metric_budget = check_metric_budget(hypotheses, ledger=ledger)
    overfitting = estimate_overfitting_risk(hypotheses=hypotheses, remediation_report=remediation, metric_budget_status=metric_budget)
    blocked_experiments = _blocked_experiments(linked_hypotheses, decision_board)
    recommended = rank_experiments_for_next_round(
        linked_hypotheses=linked_hypotheses,
        remediation_report=remediation,
        blocked_experiments=blocked_experiments,
    )

    blocking_reasons: list[str] = []
    if not hypotheses:
        blocking_reasons.append("hypothesis_registry_empty")
    if not cost_attribution:
        blocking_reasons.append("cost_attribution_missing")
    if not isinstance(remediation, Mapping) or not remediation:
        blocking_reasons.append("v10_cost_remediation_report_missing")
    if link_result.get("status") == "blocked" and hypotheses:
        blocking_reasons.extend(_as_list(link_result.get("blocking_reasons")))
    if blocked_experiments:
        blocking_reasons.append("blocked_experiments_present")

    warnings = sorted(
        set(
            _as_list(metric_budget.get("warning_reasons"))
            + _as_list(overfitting.get("risk_reasons"))
        )
    )
    status = "blocked" if blocking_reasons else "ready"
    payload = {
        "status": status,
        "candidate_version": "v10",
        "generated_at": _now(),
        "preflight_version": PREFLIGHT_VERSION,
        "report_path": str(_report_path()),
        "linked_hypotheses": linked_hypotheses,
        "evidence_dependencies": inputs["dependencies"],
        "overfitting_risk": overfitting,
        "metric_budget_status": metric_budget,
        "recommended_experiment_order": recommended,
        "blocked_experiments": blocked_experiments,
        "warnings": warnings,
        "blocking_reasons": sorted(set(blocking_reasons)),
        "training_invoked": False,
        "active_updated": False,
        "customer_prediction_generated": False,
    }
    return _write_json(_report_path(), payload) if write else _safe_payload(payload)


def get_v10_remediation_preflight() -> dict[str, Any]:
    payload = _read_json(_report_path())
    if isinstance(payload, Mapping):
        return _safe_payload(dict(payload))
    return build_remediation_preflight(write=False)
