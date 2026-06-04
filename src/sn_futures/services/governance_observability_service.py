from __future__ import annotations

import json
import math
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping, Sequence

from ..runtime import get_user_output_dir
from ..utils.secret_sanitizer import sanitize_text
from .research_run_ledger_service import append_run_ledger, finalize_research_run, start_research_run


OBSERVABILITY_VERSION = "governance_observability_v1"
SAFE_CHECK_SUCCESS_RATE_SLO = 0.95
P95_LATENCY_SLO_MS = 10_000


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _output_dir() -> Path:
    return get_user_output_dir()


def _report_path() -> Path:
    path = _output_dir() / "model_research" / "governance_observability_report.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _run_ledger_path() -> Path:
    return _output_dir() / "model_research" / "run_ledger" / "research_run_ledger.jsonl"


def _run_ledger_report_path() -> Path:
    return _output_dir() / "model_research" / "run_ledger" / "research_run_ledger_report.json"


def _freshness_path() -> Path:
    return _output_dir() / "model_research" / "evidence_freshness_report.json"


def _access_control_path() -> Path:
    return _output_dir() / "model_research" / "governance_access_control_report.json"


def _secret_scan_paths() -> list[Path]:
    return [
        _output_dir() / "diagnostics" / "runtime_secret_scan.json",
        Path("app_data") / "runtime_secret_scan" / "SNInsightTerminal" / "logs" / "runtime_secret_scan.json",
        Path("outputs") / "diagnostics" / "runtime_secret_scan.json",
    ]


def _scrub_payload(payload: Any) -> Any:
    if isinstance(payload, Mapping):
        return {sanitize_text(str(key)): _scrub_payload(value) for key, value in payload.items()}
    if isinstance(payload, list):
        return [_scrub_payload(item) for item in payload]
    if isinstance(payload, str):
        return sanitize_text(payload)
    return payload


def _json_compatible(payload: Any) -> Any:
    try:
        return json.loads(json.dumps(payload, ensure_ascii=False, default=str))
    except Exception:
        return str(payload)


def _safe_payload(payload: Any) -> Any:
    return _scrub_payload(_json_compatible(payload))


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return {}
    return dict(payload) if isinstance(payload, Mapping) else {}


def _read_run_ledger_entries() -> list[dict[str, Any]]:
    path = _run_ledger_path()
    if not path.exists():
        report = _read_json(_run_ledger_report_path())
        latest = report.get("latest_runs")
        if isinstance(latest, list):
            return [dict(item) for item in latest if isinstance(item, Mapping)]
        return []
    entries: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except Exception:
            continue
        if isinstance(payload, Mapping):
            entries.append(dict(payload))
    return entries


def _parse_dt(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except Exception:
        return None


def _safe_check_entries(entries: Sequence[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    return [item for item in entries if str(item.get("run_type") or "") == "safe_check"]


def _success_status(value: Any) -> bool:
    return str(value or "").lower() in {"success", "pass", "ready", "ok", "completed"}


def _percentile(values: Sequence[float], q: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    rank = max(1, math.ceil(q * len(ordered))) - 1
    return float(ordered[min(rank, len(ordered) - 1)])


def _latency_ms(entry: Mapping[str, Any]) -> float | None:
    started = _parse_dt(entry.get("started_at"))
    finished = _parse_dt(entry.get("finished_at"))
    if not started or not finished:
        return None
    return max(0.0, (finished - started).total_seconds() * 1000.0)


def compute_safe_check_latency_metrics(entries: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    checks = _safe_check_entries(entries)
    latencies = [value for item in checks if (value := _latency_ms(item)) is not None]
    return _safe_payload(
        {
            "safe_check_count": len(checks),
            "latency_sample_count": len(latencies),
            "p50_latency_ms": round(_percentile(latencies, 0.50), 3),
            "p95_latency_ms": round(_percentile(latencies, 0.95), 3),
            "max_latency_ms": round(max(latencies), 3) if latencies else 0.0,
        }
    )


def compute_safe_check_error_rate(entries: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    checks = _safe_check_entries(entries)
    failure_count = sum(1 for item in checks if not _success_status(item.get("status")))
    success_count = len(checks) - failure_count
    error_rate = failure_count / len(checks) if checks else 1.0
    success_rate = success_count / len(checks) if checks else 0.0
    return _safe_payload(
        {
            "safe_check_count": len(checks),
            "safe_check_success_count": success_count,
            "safe_check_failure_count": failure_count,
            "safe_check_error_rate": error_rate,
            "safe_check_success_rate": success_rate,
        }
    )


def compute_report_staleness_metrics(freshness_report: Mapping[str, Any] | None = None) -> dict[str, Any]:
    freshness = dict(freshness_report or _read_json(_freshness_path()))
    stale_reports = [str(item) for item in freshness.get("stale_reports") or [] if str(item or "")]
    missing_reports = [str(item) for item in freshness.get("missing_reports") or [] if str(item or "")]
    missing_timestamps = [str(item) for item in freshness.get("missing_timestamps") or [] if str(item or "")]
    timestamp_inversions = [str(item) for item in freshness.get("timestamp_inversions") or [] if str(item or "")]
    return _safe_payload(
        {
            "freshness_status": str(freshness.get("status") or ("missing" if not freshness else "unknown")),
            "stale_report_count": len(stale_reports),
            "missing_report_count": len(missing_reports),
            "missing_timestamp_count": len(missing_timestamps),
            "timestamp_inversion_count": len(timestamp_inversions),
            "stale_reports": stale_reports,
            "missing_reports": missing_reports,
            "missing_timestamps": missing_timestamps,
            "timestamp_inversions": timestamp_inversions,
            "freshness_source": str(_freshness_path()) if _freshness_path().exists() else "",
        }
    )


def _interpret_secret_scan(payload: Mapping[str, Any], path: Path) -> dict[str, Any]:
    finding_count = int(payload.get("finding_count") or payload.get("leak_count") or payload.get("violation_count") or 0)
    status = str(payload.get("status") or "").lower()
    leak_detected = bool(payload.get("complete_key_leakage_detected") or payload.get("leak_detected"))
    findings = payload.get("findings")
    if isinstance(findings, list):
        finding_count = max(finding_count, len(findings))
    if leak_detected or finding_count > 0 or status in {"fail", "failed", "blocked", "violation"}:
        interpreted = "fail"
    elif status in {"pass", "passed", "success", "ready"} or path.exists():
        interpreted = "pass"
    else:
        interpreted = "missing"
    return _safe_payload(
        {
            "status": interpreted,
            "finding_count": finding_count,
            "source": str(path),
        }
    )


def compute_secret_scan_status() -> dict[str, Any]:
    for path in _secret_scan_paths():
        payload = _read_json(path)
        if payload:
            return _interpret_secret_scan(payload, path)
    return _safe_payload({"status": "missing", "finding_count": 0, "source": ""})


def _active_model_paths() -> list[Path]:
    out = _output_dir()
    return [
        out / "model_registry" / "active_model.json",
        out / "models" / "active_model.json",
        Path("outputs") / "model_registry" / "active_model.json",
        Path("outputs") / "models" / "active_model.json",
    ]


def _customer_prediction_paths() -> list[Path]:
    out = _output_dir()
    return [
        out / "customer_predictions",
        out / "customer_predictions.json",
        Path("outputs") / "customer_predictions",
        Path("outputs") / "customer_predictions.json",
    ]


def _existing_paths(paths: Sequence[Path]) -> list[str]:
    return [str(path) for path in paths if path.exists()]


def _access_control_metrics(access_control: Mapping[str, Any] | None = None) -> dict[str, Any]:
    payload = dict(access_control or _read_json(_access_control_path()))
    violation_count = int(
        payload.get("forbidden_action_violation_count")
        or payload.get("ui_api_violations_count")
        or payload.get("violation_count")
        or 0
    )
    return _safe_payload(
        {
            "access_control_status": str(payload.get("status") or ("missing" if not payload else "unknown")),
            "forbidden_action_violation_count": violation_count,
            "access_control_source": str(_access_control_path()) if _access_control_path().exists() else "",
        }
    )


def collect_governance_telemetry() -> dict[str, Any]:
    entries = _read_run_ledger_entries()
    ledger_present = _run_ledger_path().exists() or _run_ledger_report_path().exists()
    latency = compute_safe_check_latency_metrics(entries)
    error_rate = compute_safe_check_error_rate(entries)
    staleness = compute_report_staleness_metrics()
    secret_scan = compute_secret_scan_status()
    access = _access_control_metrics()
    active_paths = _existing_paths(_active_model_paths())
    prediction_paths = _existing_paths(_customer_prediction_paths())
    ledger_violation_count = sum(1 for item in entries if str(item.get("status") or "").lower() == "violation")
    telemetry = {
        **error_rate,
        **latency,
        "run_ledger_present": ledger_present,
        "run_ledger_entry_count": len(entries),
        "run_ledger_violation_count": ledger_violation_count,
        "stale_report_count": staleness["stale_report_count"],
        "missing_report_count": staleness["missing_report_count"],
        "forbidden_action_violation_count": int(access["forbidden_action_violation_count"]) + ledger_violation_count,
        "secret_scan_status": secret_scan["status"],
        "secret_scan_finding_count": secret_scan["finding_count"],
        "active_model_violation_count": len(active_paths),
        "customer_prediction_violation_count": len(prediction_paths),
        "active_model_paths": active_paths,
        "customer_prediction_paths": prediction_paths,
    }
    return _safe_payload(telemetry)


def _slo_result(name: str, passed: bool, observed: Any, threshold: Any) -> dict[str, Any]:
    return _safe_payload({"name": name, "status": "pass" if passed else "fail", "observed": observed, "threshold": threshold})


def compute_governance_slo_status(telemetry: Mapping[str, Any]) -> dict[str, Any]:
    success_rate = float(telemetry.get("safe_check_success_rate") or 0.0)
    p95 = float(telemetry.get("p95_latency_ms") or 0.0)
    stale_count = int(telemetry.get("stale_report_count") or 0)
    forbidden_count = int(telemetry.get("forbidden_action_violation_count") or 0)
    active_prediction_count = int(telemetry.get("active_model_violation_count") or 0) + int(
        telemetry.get("customer_prediction_violation_count") or 0
    )
    secret_status = str(telemetry.get("secret_scan_status") or "missing").lower()
    ledger_present = bool(telemetry.get("run_ledger_present"))
    results = {
        "run_ledger_present": _slo_result("run_ledger_present", ledger_present, ledger_present, True),
        "safe_check_success_rate": _slo_result("safe_check_success_rate", success_rate >= SAFE_CHECK_SUCCESS_RATE_SLO, success_rate, SAFE_CHECK_SUCCESS_RATE_SLO),
        "p95_safe_check_latency": _slo_result("p95_safe_check_latency", p95 <= P95_LATENCY_SLO_MS, p95, P95_LATENCY_SLO_MS),
        "stale_critical_reports_zero": _slo_result("stale_critical_reports_zero", stale_count == 0, stale_count, 0),
        "secret_scan_pass": _slo_result("secret_scan_pass", secret_status == "pass", secret_status, "pass"),
        "active_prediction_violations_zero": _slo_result("active_prediction_violations_zero", active_prediction_count == 0, active_prediction_count, 0),
        "forbidden_action_exposure_zero": _slo_result("forbidden_action_exposure_zero", forbidden_count == 0, forbidden_count, 0),
    }
    status = "pass" if all(item["status"] == "pass" for item in results.values()) else "fail"
    return _safe_payload({"status": status, **results})


def compute_error_budget_status(telemetry: Mapping[str, Any]) -> dict[str, Any]:
    error_rate = float(telemetry.get("safe_check_error_rate") or 0.0)
    p95 = float(telemetry.get("p95_latency_ms") or 0.0)
    allowed_error_rate = 1.0 - SAFE_CHECK_SUCCESS_RATE_SLO
    if error_rate <= 0:
        remaining = 1.0
    else:
        remaining = max(0.0, 1.0 - (error_rate / allowed_error_rate))
    events: list[str] = []
    status = "healthy"
    if p95 > P95_LATENCY_SLO_MS:
        status = "consumed"
        events.append("latency_budget_consumed")
    if error_rate > allowed_error_rate:
        status = "exhausted"
        events.append("failure_budget_exhausted")
    return _safe_payload(
        {
            "status": status,
            "allowed_error_rate": round(allowed_error_rate, 6),
            "observed_error_rate": round(error_rate, 6),
            "remaining_ratio": round(remaining, 6),
            "budget_events": events,
        }
    )


def _blocking_reasons(telemetry: Mapping[str, Any], slo: Mapping[str, Any]) -> list[str]:
    reasons: list[str] = []
    if not telemetry.get("run_ledger_present"):
        reasons.append("run_ledger_missing")
    if str(telemetry.get("secret_scan_status") or "").lower() != "pass":
        reasons.append("secret_scan_failed" if telemetry.get("secret_scan_status") == "fail" else "secret_scan_missing")
    if int(telemetry.get("stale_report_count") or 0) > 0:
        reasons.append("stale_critical_reports_present")
    if int(telemetry.get("forbidden_action_violation_count") or 0) > 0:
        reasons.append("forbidden_action_violation_present")
    if int(telemetry.get("active_model_violation_count") or 0) > 0:
        reasons.append("active_model_violation_present")
    if int(telemetry.get("customer_prediction_violation_count") or 0) > 0:
        reasons.append("customer_prediction_violation_present")
    if str(slo.get("safe_check_success_rate", {}).get("status") if isinstance(slo.get("safe_check_success_rate"), Mapping) else "") == "fail":
        reasons.append("safe_check_success_rate_below_slo")
    if str(slo.get("p95_safe_check_latency", {}).get("status") if isinstance(slo.get("p95_safe_check_latency"), Mapping) else "") == "fail":
        reasons.append("safe_check_latency_above_slo")
    return list(dict.fromkeys(reasons))


def build_governance_observability_report(*, write: bool = True) -> dict[str, Any]:
    telemetry = collect_governance_telemetry()
    freshness = compute_report_staleness_metrics()
    secret = compute_secret_scan_status()
    access = _access_control_metrics()
    slo = compute_governance_slo_status(telemetry)
    budget = compute_error_budget_status(telemetry)
    blocking = _blocking_reasons(telemetry, slo)
    warnings: list[str] = []
    if int(telemetry.get("missing_report_count") or 0) > 0:
        warnings.append("noncritical_reports_missing")
    status = "missing" if "run_ledger_missing" in blocking else ("pass" if not blocking else "blocked")
    report = {
        "status": status,
        "generated_at": _now(),
        "observability_version": OBSERVABILITY_VERSION,
        "telemetry_summary": telemetry,
        "slo_definitions": {
            "safe_check_success_rate_min": SAFE_CHECK_SUCCESS_RATE_SLO,
            "p95_safe_check_latency_ms_max": P95_LATENCY_SLO_MS,
            "stale_critical_reports_max": 0,
            "secret_scan_status_required": "pass",
            "active_prediction_violation_count_max": 0,
            "forbidden_action_violation_count_max": 0,
        },
        "slo_results": slo,
        "error_budget": budget,
        "run_ledger_source": str(_run_ledger_path()) if _run_ledger_path().exists() else str(_run_ledger_report_path()) if _run_ledger_report_path().exists() else "",
        "freshness_source": freshness.get("freshness_source", ""),
        "access_control_source": access.get("access_control_source", ""),
        "secret_scan_source": secret.get("source", ""),
        "blocking_reasons": blocking,
        "warning_reasons": warnings,
        "training_invoked": False,
        "active_updated": False,
        "customer_prediction_generated": False,
        "report_path": str(_report_path()),
    }
    safe = _safe_payload(report)
    if write:
        _report_path().parent.mkdir(parents=True, exist_ok=True)
        _report_path().write_text(json.dumps(safe, ensure_ascii=False, indent=2), encoding="utf-8")
    return safe


def get_governance_observability_report() -> dict[str, Any]:
    payload = _read_json(_report_path())
    if payload:
        return _safe_payload(payload)
    return build_governance_observability_report(write=False)


def refresh_governance_observability_report() -> dict[str, Any]:
    run = start_research_run(
        service_name="governance_observability",
        run_type="safe_refresh",
        input_paths=[str(_run_ledger_path()), str(_freshness_path()), str(_access_control_path())],
        output_paths=[str(_report_path())],
    )
    error = ""
    try:
        report = build_governance_observability_report(write=True)
    except Exception as exc:  # pragma: no cover - defensive ledger recording
        error = sanitize_text(str(exc))
        report = {
            "status": "blocked",
            "generated_at": _now(),
            "observability_version": OBSERVABILITY_VERSION,
            "blocking_reasons": ["governance_observability_refresh_failed"],
            "error_summary": error,
            "training_invoked": False,
            "active_updated": False,
            "customer_prediction_generated": False,
            "report_path": str(_report_path()),
        }
        _report_path().write_text(json.dumps(_safe_payload(report), ensure_ascii=False, indent=2), encoding="utf-8")
    finalized = finalize_research_run(run, error_summary=error)
    append_run_ledger(finalized)
    return _safe_payload(report)
