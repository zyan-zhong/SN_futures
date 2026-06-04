from __future__ import annotations

import json
import re
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping, Sequence

from ..api.json_utils import sanitize_for_json
from ..runtime import get_user_output_dir
from ..utils.secret_sanitizer import sanitize_mapping


REGISTRY_VERSION = "experiment_hypothesis_registry_v1"
LEDGER_VERSION = "anti_p_hacking_ledger_v1"
MAX_PRIMARY_METRICS = 2
SECRET_TEXT_RE = re.compile(r"(?i)\b[A-Za-z0-9._-]*(?:token|secret|authorization|password)[A-Za-z0-9._-]{4,}\b")


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _output_dir() -> Path:
    return get_user_output_dir()


def _research_dir() -> Path:
    path = _output_dir() / "model_research"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _registry_path() -> Path:
    return _research_dir() / "hypothesis_registry.json"


def _ledger_path() -> Path:
    return _research_dir() / "anti_p_hacking_ledger.json"


def _v10_remediation_path() -> Path:
    primary = _output_dir() / "model_research" / "candidate_v10" / "v10_cost_failure_research_report.json"
    if primary.exists():
        return primary
    fallback = Path("outputs") / "model_research" / "candidate_v10" / "v10_cost_failure_research_report.json"
    return fallback if fallback.exists() else primary


def _decision_board_path() -> Path:
    primary = _output_dir() / "model_research" / "research_decision_board.json"
    if primary.exists():
        return primary
    fallback = Path("outputs") / "model_research" / "research_decision_board.json"
    return fallback if fallback.exists() else primary


def _read_json(path: Path) -> Any:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _write_json(path: Path, payload: Mapping[str, Any]) -> dict[str, Any]:
    safe = _safe_payload(dict(payload))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(safe, ensure_ascii=False, indent=2), encoding="utf-8")
    return safe


def _safe_payload(payload: Any) -> Any:
    cleaned = sanitize_for_json(sanitize_mapping(payload))
    return _scrub_free_text(cleaned)


def _scrub_free_text(payload: Any) -> Any:
    if isinstance(payload, Mapping):
        return {str(key): _scrub_free_text(value) for key, value in payload.items()}
    if isinstance(payload, list):
        return [_scrub_free_text(item) for item in payload]
    if isinstance(payload, str):
        return SECRET_TEXT_RE.sub("***", payload)
    return payload


def _as_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value if str(item or "").strip()]
    if value is None:
        return []
    text = str(value).strip()
    return [text] if text else []


def _primary_metrics(rule: Any) -> list[str]:
    if isinstance(rule, Mapping):
        return _as_list(rule.get("primary_metrics"))
    return []


def _load_entries() -> list[dict[str, Any]]:
    payload = _read_json(_registry_path())
    if isinstance(payload, Mapping) and isinstance(payload.get("hypotheses"), list):
        return [dict(item) for item in payload["hypotheses"] if isinstance(item, Mapping)]
    return []


def _write_registry(entries: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    open_entries = [dict(item) for item in entries if str(item.get("status") or "open") == "open"]
    closed_entries = [dict(item) for item in entries if str(item.get("status") or "open") != "open"]
    payload = {
        "status": "active" if entries else "empty",
        "generated_at": _now(),
        "registry_version": REGISTRY_VERSION,
        "hypothesis_count": len(entries),
        "open_hypotheses": len(open_entries),
        "closed_hypotheses": len(closed_entries),
        "hypotheses": list(entries),
        "training_invoked": False,
        "active_updated": False,
        "customer_prediction_generated": False,
        "registry_path": str(_registry_path()),
    }
    return _write_json(_registry_path(), payload)


def validate_hypothesis_entry(entry: Mapping[str, Any]) -> dict[str, Any]:
    reasons: list[str] = []
    if not str(entry.get("title") or "").strip():
        reasons.append("title_missing")
    if not str(entry.get("linked_blocker") or "").strip():
        reasons.append("linked_blocker_missing")
    rule = entry.get("primary_decision_rule")
    if not rule:
        reasons.append("primary_decision_rule_missing")
    allowed_metrics = set(_as_list(entry.get("allowed_metrics")))
    forbidden_metrics = set(_as_list(entry.get("forbidden_metrics")))
    if not allowed_metrics:
        reasons.append("allowed_metrics_missing")
    primary_metrics = set(_primary_metrics(rule))
    if len(primary_metrics) > MAX_PRIMARY_METRICS:
        reasons.append("too_many_primary_metrics")
    if primary_metrics & forbidden_metrics:
        reasons.append("forbidden_metric_used_as_primary")
    if primary_metrics and not primary_metrics <= allowed_metrics:
        reasons.append("primary_metric_not_in_allowed_metrics")
    return _safe_payload(
        {
            "status": "invalid" if reasons else "valid",
            "blocking_reasons": reasons,
            "training_invoked": False,
            "active_updated": False,
            "customer_prediction_generated": False,
        }
    )


def _new_hypothesis_id(entry: Mapping[str, Any]) -> str:
    value = str(entry.get("hypothesis_id") or "").strip()
    if value:
        return value
    title = re.sub(r"[^a-z0-9]+", "-", str(entry.get("title") or "hypothesis").lower()).strip("-")
    suffix = uuid.uuid4().hex[:8]
    return f"hyp-{title[:48] or 'research'}-{suffix}"


def create_hypothesis_entry(entry: Mapping[str, Any]) -> dict[str, Any]:
    validation = validate_hypothesis_entry(entry)
    if validation["status"] != "valid":
        return validation
    created = {
        "hypothesis_id": _new_hypothesis_id(entry),
        "created_at": _now(),
        "title": entry.get("title"),
        "motivation": entry.get("motivation", ""),
        "linked_blocker": entry.get("linked_blocker"),
        "expected_direction": entry.get("expected_direction", ""),
        "allowed_metrics": _as_list(entry.get("allowed_metrics")),
        "forbidden_metrics": _as_list(entry.get("forbidden_metrics")),
        "primary_decision_rule": entry.get("primary_decision_rule"),
        "secondary_diagnostics": _as_list(entry.get("secondary_diagnostics")),
        "dataset_version_allowed": entry.get("dataset_version_allowed", "research_only"),
        "candidate_version_allowed": entry.get("candidate_version_allowed", "research_only"),
        "training_allowed": bool(entry.get("training_allowed", False)),
        "active_allowed": bool(entry.get("active_allowed", False)),
        "prediction_allowed": bool(entry.get("prediction_allowed", False)),
        "status": str(entry.get("status") or "open"),
    }
    entries = _load_entries()
    entries.append(_safe_payload(created))
    _write_registry(entries)
    return _safe_payload(created)


def list_hypothesis_registry() -> dict[str, Any]:
    entries = _load_entries()
    if not entries:
        return _write_registry([])
    return _write_registry(entries)


def compute_experiment_budget_usage(entries: Sequence[Mapping[str, Any]] | None = None) -> dict[str, Any]:
    entries = list(entries) if entries is not None else _load_entries()
    by_blocker: dict[str, dict[str, Any]] = {}
    for entry in entries:
        blocker = str(entry.get("linked_blocker") or "unlinked")
        budget = by_blocker.setdefault(
            blocker,
            {
                "linked_blocker": blocker,
                "registered_hypotheses": 0,
                "open_hypotheses": 0,
                "closed_hypotheses": 0,
                "budget_limit": 3,
                "remaining_budget": 3,
            },
        )
        budget["registered_hypotheses"] += 1
        if str(entry.get("status") or "open") == "open":
            budget["open_hypotheses"] += 1
        else:
            budget["closed_hypotheses"] += 1
        budget["remaining_budget"] = max(0, int(budget["budget_limit"]) - int(budget["registered_hypotheses"]))
    return _safe_payload(by_blocker)


def _risk_level(repeated_test_count: int, budget_usage: Mapping[str, Mapping[str, Any]]) -> str:
    if not budget_usage:
        return "none"
    if any(int(item.get("remaining_budget") or 0) == 0 and int(item.get("registered_hypotheses") or 0) > int(item.get("budget_limit") or 3) for item in budget_usage.values()):
        return "high"
    if repeated_test_count > 0:
        return "medium"
    return "low"


def _board_manual_approval() -> bool:
    payload = _read_json(_decision_board_path())
    return bool(payload.get("manual_approval_recommended")) if isinstance(payload, Mapping) else False


def build_anti_p_hacking_ledger(*, write: bool = True) -> dict[str, Any]:
    registry = list_hypothesis_registry()
    entries = [dict(item) for item in registry.get("hypotheses", []) if isinstance(item, Mapping)]
    budget_usage = compute_experiment_budget_usage(entries)
    repeated_test_count = sum(max(0, int(item.get("registered_hypotheses") or 0) - 1) for item in budget_usage.values())
    risk_level = _risk_level(repeated_test_count, budget_usage)
    warning_reasons: list[str] = []
    if repeated_test_count:
        warning_reasons.append("repeated_tests_against_same_blocker")
    if _board_manual_approval():
        warning_reasons.append("manual_approval_state_must_not_be_changed_by_registry")
    payload = {
        "status": "active" if entries else "empty",
        "generated_at": _now(),
        "ledger_version": LEDGER_VERSION,
        "ledger_path": str(_ledger_path()),
        "hypothesis_count": len(entries),
        "open_hypotheses": [entry for entry in entries if str(entry.get("status") or "open") == "open"],
        "closed_hypotheses": [entry for entry in entries if str(entry.get("status") or "open") != "open"],
        "experiment_budget_by_blocker": budget_usage,
        "repeated_test_count": repeated_test_count,
        "p_hacking_risk_level": risk_level,
        "warning_reasons": warning_reasons,
        "blocking_reasons": [],
        "training_invoked": False,
        "active_updated": False,
        "customer_prediction_generated": False,
    }
    return _write_json(_ledger_path(), payload) if write else _safe_payload(payload)


def attach_hypothesis_to_future_experiment(experiment: Mapping[str, Any]) -> dict[str, Any]:
    hypothesis_id = str(experiment.get("hypothesis_id") or "").strip()
    if not hypothesis_id:
        return _safe_payload(
            {
                "status": "blocked",
                "blocking_reasons": ["hypothesis_id_missing"],
                "training_allowed": False,
                "active_allowed": False,
                "prediction_allowed": False,
                "training_invoked": False,
                "active_updated": False,
                "customer_prediction_generated": False,
            }
        )
    entries = _load_entries()
    match = next((entry for entry in entries if str(entry.get("hypothesis_id")) == hypothesis_id), None)
    if not match:
        return _safe_payload(
            {
                "status": "blocked",
                "hypothesis_id": hypothesis_id,
                "blocking_reasons": ["hypothesis_id_not_registered"],
                "training_allowed": False,
                "active_allowed": False,
                "prediction_allowed": False,
                "training_invoked": False,
                "active_updated": False,
                "customer_prediction_generated": False,
            }
        )
    return _safe_payload(
        {
            "status": "attached",
            "hypothesis_id": hypothesis_id,
            "linked_blocker": match.get("linked_blocker"),
            "allowed_metrics": match.get("allowed_metrics", []),
            "forbidden_metrics": match.get("forbidden_metrics", []),
            "primary_decision_rule": match.get("primary_decision_rule"),
            "training_allowed": bool(match.get("training_allowed", False)),
            "active_allowed": bool(match.get("active_allowed", False)),
            "prediction_allowed": bool(match.get("prediction_allowed", False)),
            "training_invoked": False,
            "active_updated": False,
            "customer_prediction_generated": False,
        }
    )


def _template_from_cost_hypothesis(item: Mapping[str, Any]) -> dict[str, Any]:
    hypothesis_id = str(item.get("id") or item.get("hypothesis_id") or "v10_cost_remediation")
    return _safe_payload(
        {
            "hypothesis_id": f"template-{hypothesis_id}",
            "created_at": _now(),
            "title": item.get("title") or hypothesis_id.replace("_", " "),
            "motivation": f"Predeclare v10 remediation for {hypothesis_id}; affected horizon={item.get('affected_horizon', 'unknown')}, regime={item.get('affected_regime', 'unknown')}, year={item.get('affected_year', 'unknown')}.",
            "linked_blocker": "cost_attribution:institutional_cost_negative",
            "expected_direction": item.get("expected_tradeoff") or "Improve institutional cost stress without increasing p-hacking risk.",
            "allowed_metrics": ["institutional_3x_cost_expectancy", "trade_count", "turnover"],
            "forbidden_metrics": ["final_backtest_pnl", "manual_approval_recommended"],
            "primary_decision_rule": {
                "primary_metrics": ["institutional_3x_cost_expectancy"],
                "rule": "Pass only if the predeclared OOF-only cost-stress metric improves without using final backtest PnL.",
            },
            "secondary_diagnostics": ["affected_horizon", "affected_regime", "affected_year", "risk_of_overfitting"],
            "dataset_version_allowed": "v10",
            "candidate_version_allowed": "v10",
            "training_allowed": False,
            "active_allowed": False,
            "prediction_allowed": False,
            "status": "template",
            "risk_of_overfitting": item.get("risk_of_overfitting", "medium"),
        }
    )


def build_hypothesis_templates_from_v10_cost_remediation() -> dict[str, Any]:
    report = _read_json(_v10_remediation_path())
    if not isinstance(report, Mapping):
        return _safe_payload(
            {
                "status": "blocked",
                "templates": [],
                "blocking_reasons": ["v10_cost_remediation_report_missing"],
                "training_invoked": False,
                "active_updated": False,
                "customer_prediction_generated": False,
            }
        )
    ranked = [dict(item) for item in report.get("ranked_hypotheses", []) if isinstance(item, Mapping)]
    if not ranked and report.get("recommended_next_experiment"):
        ranked = [{"id": report.get("recommended_next_experiment"), "title": str(report.get("recommended_next_experiment"))}]
    templates = [_template_from_cost_hypothesis(item) for item in ranked]
    return _safe_payload(
        {
            "status": "ready" if templates else "blocked",
            "templates": templates,
            "template_count": len(templates),
            "recommended_next_experiment": report.get("recommended_next_experiment", ""),
            "blocking_reasons": [] if templates else ["v10_cost_remediation_templates_missing"],
            "training_invoked": False,
            "active_updated": False,
            "customer_prediction_generated": False,
        }
    )


def get_hypothesis_registry() -> dict[str, Any]:
    registry = list_hypothesis_registry()
    ledger = build_anti_p_hacking_ledger(write=False)
    templates = build_hypothesis_templates_from_v10_cost_remediation()
    registry["anti_p_hacking_ledger"] = ledger
    registry["hypothesis_templates"] = templates.get("templates", [])
    registry["p_hacking_risk_level"] = ledger.get("p_hacking_risk_level", "none")
    registry["experiment_budget_by_blocker"] = ledger.get("experiment_budget_by_blocker", {})
    return _safe_payload(registry)


def create_hypothesis_template(payload: Mapping[str, Any] | None = None) -> dict[str, Any]:
    payload = payload or {}
    templates = build_hypothesis_templates_from_v10_cost_remediation().get("templates", [])
    if payload.get("hypothesis_id"):
        selected = next((item for item in templates if str(item.get("hypothesis_id")) == str(payload.get("hypothesis_id"))), None)
    elif payload.get("remediation_id"):
        selected = next((item for item in templates if str(item.get("hypothesis_id", "")).endswith(str(payload.get("remediation_id")))), None)
    else:
        selected = templates[0] if templates else None
    if not isinstance(selected, Mapping):
        return _safe_payload(
            {
                "status": "blocked",
                "blocking_reasons": ["hypothesis_template_missing"],
                "training_invoked": False,
                "active_updated": False,
                "customer_prediction_generated": False,
            }
        )
    entry = dict(selected)
    entry.pop("created_at", None)
    entry["status"] = "open"
    entry["hypothesis_id"] = str(entry.get("hypothesis_id", "")).replace("template-", "hyp-")
    return create_hypothesis_entry(entry)
