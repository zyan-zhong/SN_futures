from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping

from ..api.json_utils import sanitize_for_json
from ..runtime import get_user_output_dir


REQUIRED_APPROVAL_PHRASE = "我确认仅作为研究预测，不构成投资建议"


def _output_dir() -> Path:
    return get_user_output_dir()


def _registry_dir() -> Path:
    path = _output_dir() / "model_registry"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _normalise_version(version: str | None) -> str:
    value = str(version or "v5").strip().lower()
    return value or "v5"


def _promotion_report_path(candidate_version: str) -> Path:
    version = _normalise_version(candidate_version)
    if version == "v1":
        return _registry_dir() / "promotion_report.json"
    return _registry_dir() / f"promotion_report_{version}.json"


def _validation_report_path(candidate_version: str) -> Path:
    version = _normalise_version(candidate_version)
    base = _output_dir() / "institutional_validation"
    if version == "v1":
        return base / "institutional_validation_report.json"
    return base / f"institutional_validation_report_{version}.json"


def _active_model_path() -> Path:
    return _registry_dir() / "active_model.json"


def _audit_path() -> Path:
    return _registry_dir() / "active_release_audit.json"


def _active_artifact_dir() -> Path:
    path = _registry_dir() / "model_artifacts"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _read_json(path: Path) -> Any:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(sanitize_for_json(dict(payload)), ensure_ascii=False, indent=2), encoding="utf-8")


def _passed_flag(payload: Mapping[str, Any], *keys: str) -> bool:
    for key in keys:
        value = payload.get(key)
        if isinstance(value, Mapping):
            if bool(value.get("passed")):
                return True
        elif isinstance(value, bool):
            if value:
                return True
        elif isinstance(value, str) and value.strip().lower() in {"pass", "passed", "success", "true"}:
            return True
    return False


def _float_value(value: Any, *keys: str) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value.strip())
        except ValueError:
            return None
    if isinstance(value, Mapping):
        for key in keys:
            parsed = _float_value(value.get(key))
            if parsed is not None:
                return parsed
    return None


def _report_passed(report: Mapping[str, Any]) -> bool:
    if "passed" in report:
        return bool(report.get("passed"))
    return str(report.get("status") or "").strip().lower() in {"pass", "passed", "success"}


def _promotion_passed(promotion: Mapping[str, Any]) -> bool:
    if not _report_passed(promotion):
        return False
    if promotion.get("dry_run") is False:
        return False
    if promotion.get("active_updated") is True:
        return False
    return True


def _dsr_passed(validation: Mapping[str, Any]) -> bool:
    for key in ("deflated_sharpe_ratio", "dsr", "dsr_result"):
        value = validation.get(key)
        if isinstance(value, Mapping):
            if "passed" in value:
                return bool(value.get("passed"))
            score = _float_value(value, "deflated_sharpe_ratio", "dsr", "value", "score")
            if score is not None:
                return score > 0
        elif isinstance(value, bool):
            return value
        else:
            score = _float_value(value)
            if score is not None:
                return score > 0
    return _passed_flag(validation, "deflated_sharpe_ratio_passed", "dsr_passed")


def _pbo_passed(validation: Mapping[str, Any]) -> bool:
    payload = validation.get("probability_of_backtest_overfitting") or validation.get("pbo")
    if isinstance(payload, Mapping):
        if "passed" in payload:
            return bool(payload.get("passed"))
        value = _float_value(payload, "pbo", "value", "probability")
        return bool(value is not None and value < 0.2)
    value = _float_value(payload)
    if value is not None:
        return value < 0.2
    return bool(validation.get("pbo_passed"))


def _reality_check_passed(validation: Mapping[str, Any]) -> bool:
    payload = validation.get("reality_check") or validation.get("reality_check_result")
    if isinstance(payload, Mapping):
        if "passed" in payload:
            return bool(payload.get("passed"))
        p_value = _float_value(payload, "p_value", "pvalue", "p")
        return bool(p_value is not None and p_value < 0.05)
    if isinstance(payload, bool):
        return payload
    return bool(validation.get("reality_check_passed"))


def _cost_stress_passed(validation: Mapping[str, Any], multiplier: str) -> bool:
    aliases = {
        "2x": ("2x", "cost_2x", "2x_cost", "cost_multiplier_2"),
        "3x": ("3x", "cost_3x", "3x_cost", "cost_multiplier_3"),
    }[multiplier]
    direct_flag = validation.get(f"cost_{multiplier}_passed") or validation.get(f"{multiplier}_cost_passed")
    if isinstance(direct_flag, bool):
        return direct_flag
    candidates: list[Any] = [validation.get(alias) for alias in aliases]
    for key in ("cost_stress", "cost_stress_tests", "cost_stress_validation", "stress_tests"):
        payload = validation.get(key)
        if not isinstance(payload, Mapping):
            continue
        candidates.extend(payload.get(alias) for alias in aliases)
    for value in candidates:
        if isinstance(value, Mapping):
            if "passed" in value:
                return bool(value.get("passed"))
            if value.get("active_eligibility_under_cost_stress") is False:
                return False
            expectancy = _float_value(value, "expectancy", "cost_adjusted_expectancy", "expected_return")
            if expectancy is not None:
                return expectancy >= 0
            if value.get("active_eligibility_under_cost_stress") is True:
                return True
        elif isinstance(value, bool):
            return value
        else:
            expectancy = _float_value(value)
            if expectancy is not None:
                return expectancy >= 0
    return False


def _cost_2x_passed(validation: Mapping[str, Any]) -> bool:
    return _cost_stress_passed(validation, "2x")


def _feature_stability_passed(validation: Mapping[str, Any]) -> bool:
    payload = validation.get("feature_stability")
    if isinstance(payload, Mapping):
        if "passed" in payload:
            return bool(payload.get("passed"))
        if "feature_stability_passed" in payload:
            return bool(payload.get("feature_stability_passed"))
        score = _float_value(payload, "stability_score", "stability_rate", "score")
        threshold = _float_value(payload, "threshold")
        if score is not None:
            return score >= (threshold if threshold is not None else 0.55)
    return bool(validation.get("feature_stability_passed"))


def _promotion_eligibility(validation: Mapping[str, Any]) -> tuple[bool, list[Mapping[str, Any]], list[Any]]:
    payload = validation.get("promotion_eligibility")
    if not isinstance(payload, Mapping):
        return False, [], ["promotion_eligibility missing"]
    checks = [item for item in payload.get("checks") or [] if isinstance(item, Mapping)]
    failures = list(payload.get("failure_reasons") or [])
    if payload.get("eligible") is False:
        return False, checks, failures
    failed_checks = [item for item in checks if item.get("passed") is False]
    return not failures and not failed_checks, checks, failures


def _check_name_passed(checks: list[Mapping[str, Any]], *words: str) -> bool | None:
    expected = [word.lower() for word in words]
    for item in checks:
        name = str(item.get("name") or "").lower()
        if all(word in name for word in expected):
            if "passed" in item:
                return bool(item.get("passed"))
            return True
    return None


def _dominance_passed(validation: Mapping[str, Any], slice_name: str) -> bool:
    payload = validation.get("dominance_checks")
    if isinstance(payload, Mapping):
        dominates_key = f"single_{slice_name}_dominates"
        contribution_key = f"single_{slice_name}_contribution"
        if dominates_key in payload:
            return not bool(payload.get(dominates_key))
        contribution = _float_value(payload.get(contribution_key))
        if contribution is not None:
            threshold = {"fold": 0.6, "year": 0.6, "regime": 0.7}[slice_name]
            return contribution <= threshold
    _, checks, _ = _promotion_eligibility(validation)
    named = _check_name_passed(checks, "single", slice_name)
    if named is not None:
        return named
    return False


def _build_checklist(
    *,
    promotion: Mapping[str, Any],
    validation: Mapping[str, Any],
    approval_phrase: str,
) -> list[dict[str, Any]]:
    promotion_pass = bool(promotion.get("passed") or promotion.get("status") in {"pass", "passed", "success"})
    institutional_pass = bool(validation.get("passed") or validation.get("status") in {"pass", "passed", "success"})
    dsr_pass = _passed_flag(validation, "deflated_sharpe_ratio", "dsr", "dsr_result")
    pbo_payload = validation.get("probability_of_backtest_overfitting") or validation.get("pbo")
    pbo_pass = bool(isinstance(pbo_payload, Mapping) and (pbo_payload.get("passed") or float(pbo_payload.get("pbo", 1.0) or 1.0) < 0.2))
    cost_pass = _cost_2x_passed(validation)
    stability_pass = _feature_stability_passed(validation)
    no_mock_sample = not bool(
        promotion.get("sample_data_used")
        or promotion.get("mock_data_used")
        or validation.get("sample_data_used")
        or validation.get("mock_data_used")
        or validation.get("baseline_used")
        or promotion.get("baseline_used")
    )
    phrase_pass = approval_phrase.strip() == REQUIRED_APPROVAL_PHRASE
    return [
        {"name": "promotion dry-run pass", "passed": promotion_pass, "failure_reason_zh": "" if promotion_pass else "promotion dry-run 未通过。"},
        {"name": "institutional validation pass", "passed": institutional_pass, "failure_reason_zh": "" if institutional_pass else "institutional validation 未通过。"},
        {"name": "DSR pass", "passed": dsr_pass, "failure_reason_zh": "" if dsr_pass else "DSR 未通过。"},
        {"name": "PBO pass", "passed": pbo_pass, "failure_reason_zh": "" if pbo_pass else "PBO 未通过。"},
        {"name": "2x cost pass", "passed": cost_pass, "failure_reason_zh": "" if cost_pass else "2x 成本压力未通过。"},
        {"name": "feature stability pass", "passed": stability_pass, "failure_reason_zh": "" if stability_pass else "feature stability 未通过。"},
        {"name": "no mock/sample data", "passed": no_mock_sample, "failure_reason_zh": "" if no_mock_sample else "mock/sample/baseline 数据不可发布 active。"},
        {"name": "human approval phrase", "passed": phrase_pass, "failure_reason_zh": "" if phrase_pass else "human approval phrase 不匹配。"},
    ]


def _build_candidate_checklist(
    *,
    promotion: Mapping[str, Any],
    validation: Mapping[str, Any],
    approval_phrase: str,
    candidate_version: str,
) -> list[dict[str, Any]]:
    version = _normalise_version(candidate_version)
    promotion_pass = _promotion_passed(promotion)
    institutional_pass = _report_passed(validation)
    dsr_pass = _dsr_passed(validation)
    pbo_pass = _pbo_passed(validation)
    cost_2x_pass = _cost_2x_passed(validation)
    stability_pass = _feature_stability_passed(validation)
    no_mock_sample = not bool(
        promotion.get("sample_data_used")
        or promotion.get("mock_data_used")
        or promotion.get("baseline_used")
        or promotion.get("customer_prediction_generated")
        or validation.get("sample_data_used")
        or validation.get("mock_data_used")
        or validation.get("baseline_used")
        or validation.get("customer_prediction_generated")
    )
    phrase_pass = approval_phrase.strip() == REQUIRED_APPROVAL_PHRASE
    checklist = [
        {"name": "promotion dry-run pass", "passed": promotion_pass, "failure_reason_zh": "" if promotion_pass else "promotion dry-run 未通过。"},
        {"name": "institutional validation pass", "passed": institutional_pass, "failure_reason_zh": "" if institutional_pass else "institutional validation 未通过。"},
        {"name": "DSR pass", "passed": dsr_pass, "failure_reason_zh": "" if dsr_pass else "DSR 未通过。"},
        {"name": "PBO pass", "passed": pbo_pass, "failure_reason_zh": "" if pbo_pass else "PBO 未通过。"},
        {"name": "2x cost pass", "passed": cost_2x_pass, "failure_reason_zh": "" if cost_2x_pass else "2x cost stress 未通过。"},
        {"name": "feature stability pass", "passed": stability_pass, "failure_reason_zh": "" if stability_pass else "feature stability 未通过。"},
        {"name": "no mock/sample data", "passed": no_mock_sample, "failure_reason_zh": "" if no_mock_sample else "mock/sample/baseline 数据不可发布 active。"},
        {"name": "human approval phrase", "passed": phrase_pass, "failure_reason_zh": "" if phrase_pass else "human approval phrase 不匹配。"},
    ]
    if version == "v9":
        reality_pass = _reality_check_passed(validation)
        cost_3x_pass = _cost_stress_passed(validation, "3x")
        fold_pass = _dominance_passed(validation, "fold")
        year_pass = _dominance_passed(validation, "year")
        regime_pass = _dominance_passed(validation, "regime")
        eligibility_pass, _, failures = _promotion_eligibility(validation)
        checklist.extend(
            [
                {"name": "Reality Check pass", "passed": reality_pass, "failure_reason_zh": "" if reality_pass else "Reality Check 未通过。"},
                {"name": "3x cost acceptable", "passed": cost_3x_pass, "failure_reason_zh": "" if cost_3x_pass else "3x cost stress 未达 active 条件。"},
                {"name": "worst fold pass", "passed": fold_pass, "failure_reason_zh": "" if fold_pass else "worst fold / single fold concentration 未通过。"},
                {"name": "worst year pass", "passed": year_pass, "failure_reason_zh": "" if year_pass else "worst year / single year concentration 未通过。"},
                {"name": "worst regime pass", "passed": regime_pass, "failure_reason_zh": "" if regime_pass else "worst regime / single regime concentration 未通过。"},
                {
                    "name": "institutional promotion eligibility pass",
                    "passed": eligibility_pass,
                    "failure_reason_zh": "" if eligibility_pass else "institutional promotion eligibility 未通过：" + "; ".join(str(item) for item in failures),
                },
            ]
        )
    return checklist


def _copy_artifact(path_value: Any) -> str:
    source = Path(str(path_value or ""))
    if not source.exists() or not source.is_file():
        return str(source) if str(source) else ""
    target = _active_artifact_dir() / f"active_{source.name}"
    shutil.copyfile(source, target)
    return str(target)


def approve_active_release(
    *,
    candidate_version: str = "v5",
    approval_phrase: str = "",
    approver: str = "",
    notes: str = "",
) -> dict[str, Any]:
    version = _normalise_version(candidate_version)
    promotion = _read_json(_promotion_report_path(version))
    validation = _read_json(_validation_report_path(version))
    if not isinstance(promotion, Mapping):
        promotion = {}
    if not isinstance(validation, Mapping):
        validation = {}

    checklist = _build_candidate_checklist(
        promotion=promotion,
        validation=validation,
        approval_phrase=approval_phrase,
        candidate_version=version,
    )
    blocking = [item["failure_reason_zh"] for item in checklist if not item["passed"]]
    base = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "candidate_version": version,
        "approver": str(approver or ""),
        "notes": str(notes or ""),
        "approval_checklist": checklist,
        "blocking_reasons": blocking,
        "live_trading_enabled": False,
        "customer_order_routing_enabled": False,
        "disclaimer": "仅作为研究预测展示，不构成投资建议，不承诺收益，不接实盘交易。",
    }
    if blocking:
        payload = {
            **base,
            "status": "rejected",
            "active_updated": False,
            "message_zh": "人工审批 active 发布被拒绝；请先完成 promotion dry-run、机构级验证和审批短语。",
            "audit_path": str(_audit_path()),
        }
        _write_json(_audit_path(), payload)
        return sanitize_for_json(payload)

    active_models: list[dict[str, Any]] = []
    for item in promotion.get("passed_candidates") or []:
        if not isinstance(item, Mapping):
            continue
        active_models.append(
            {
                "model_id": item.get("model_id"),
                "horizon": item.get("horizon"),
                "status": "active",
                "activated_at": datetime.now().isoformat(timespec="seconds"),
                "artifact_path": _copy_artifact(item.get("artifact_path")),
                "metrics": item.get("metrics", {}),
                "promotion_checks": item.get("checks", []),
                "feature_columns": item.get("feature_columns", []),
                "label_columns": item.get("label_columns", []),
            }
        )
    active_payload = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "candidate_version": version,
        "status": "active_available",
        "release_mode": "manual_human_approval",
        "active_models": active_models,
        "approver": str(approver or ""),
        "approval_audit_path": str(_audit_path()),
        "live_trading_enabled": False,
        "customer_order_routing_enabled": False,
        "disclaimer": "仅作为研究预测展示，不构成投资建议，不承诺收益，不接实盘交易。",
    }
    _write_json(_active_model_path(), active_payload)
    audit = {
        **base,
        "status": "active_released",
        "active_updated": True,
        "active_model_path": str(_active_model_path()),
        "audit_path": str(_audit_path()),
        "released_models": active_models,
        "message_zh": "人工审批通过，已写入 active_model.json；仍不接实盘交易。",
    }
    _write_json(_audit_path(), audit)
    return sanitize_for_json(audit)
