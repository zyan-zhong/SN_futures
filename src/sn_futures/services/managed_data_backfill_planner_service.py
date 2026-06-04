from __future__ import annotations

import json
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Mapping

from ..api.json_utils import sanitize_for_json
from ..runtime import get_user_output_dir
from .managed_data_proxy_service import MANAGED_REQUIRED_RESEARCH_FIELDS
from .managed_proxy_setup_service import REQUIRED_TIMESTAMP_FIELDS


PLANNER_VERSION = "managed_data_backfill_planner_v1"
PLANNER_REPORT_FILENAME = "managed_data_backfill_planner_report.json"
TARGET_HORIZONS = ("1d", "5d", "10d", "20d")


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _output_dir() -> Path:
    return get_user_output_dir()


def _report_path() -> Path:
    path = _output_dir() / "diagnostics" / PLANNER_REPORT_FILENAME
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _read_json(path: Path) -> Any:
    if not path.exists():
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


def _diagnostics_path(filename: str) -> Path:
    return _output_dir() / "diagnostics" / filename


def _feature_store_v10_manifest_path() -> Path:
    return _output_dir() / "feature_store" / "v10" / "feature_store_manifest.json"


def _incident_drill_path() -> Path:
    return _output_dir() / "model_research" / "incident_drill_report.json"


def _parse_date(value: Any) -> date | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).date()
    except Exception:
        pass
    for fmt in ("%Y-%m-%d", "%Y%m%d"):
        try:
            return datetime.strptime(text[:10] if fmt == "%Y-%m-%d" else text[:8], fmt).date()
        except Exception:
            continue
    return None


def _status(payload: Any) -> str:
    return str(payload.get("status") if isinstance(payload, Mapping) else "missing" or "missing").lower()


def _base_payload() -> dict[str, Any]:
    return {
        "status": "blocked",
        "generated_at": _now(),
        "planner_version": PLANNER_VERSION,
        "required_date_range": {"date_start": "", "date_end": "", "source": "missing"},
        "target_horizons": list(TARGET_HORIZONS),
        "required_managed_fields": list(MANAGED_REQUIRED_RESEARCH_FIELDS),
        "required_timestamp_fields": list(REQUIRED_TIMESTAMP_FIELDS),
        "coverage_budget": compute_required_coverage_budget(row_count=0),
        "batch_plan": {"status": "blocked", "batches": [], "batch_size_days": 30, "max_rows_per_batch": 500},
        "retry_policy": define_backfill_retry_policy(),
        "abort_conditions": define_backfill_abort_conditions(),
        "human_approval_checklist": [],
        "production_cache_write_allowed": False,
        "feature_store_v12_allowed": False,
        "rows_fetched": False,
        "historical_backfill_executed": False,
        "production_cache_written": False,
        "training_invoked": False,
        "active_updated": False,
        "customer_prediction_generated": False,
        "blocking_reasons": [],
        "warning_reasons": [],
        "report_path": str(_report_path()),
    }


def compute_required_backfill_date_range() -> dict[str, Any]:
    manifest = _read_json(_feature_store_v10_manifest_path())
    if isinstance(manifest, Mapping):
        start = manifest.get("date_start") or manifest.get("start_date")
        end = manifest.get("date_end") or manifest.get("end_date")
        if _parse_date(start) and _parse_date(end):
            return sanitize_for_json(
                {
                    "date_start": _parse_date(start).isoformat(),
                    "date_end": _parse_date(end).isoformat(),
                    "source": "feature_store_v10_manifest",
                    "row_count_source": int(manifest.get("row_count") or 0),
                }
            )
    return sanitize_for_json({"date_start": "", "date_end": "", "source": "missing", "row_count_source": 0})


def compute_required_coverage_budget(*, row_count: int = 0) -> dict[str, Any]:
    min_rows = max(int(row_count or 0), 252)
    return {
        "min_row_count": min_rows,
        "min_date_coverage_ratio": 0.95,
        "max_missing_rate_by_required_field": {field: 0.05 for field in MANAGED_REQUIRED_RESEARCH_FIELDS},
        "min_timestamp_coverage": 1.0,
        "min_pit_replay_pass_rate": 1.0,
        "min_quality_score": 0.9,
        "allowed_duplicate_key_count": 0,
    }


def define_backfill_batch_plan(date_range: Mapping[str, Any] | None = None, *, batch_size_days: int = 30) -> dict[str, Any]:
    date_range = date_range if isinstance(date_range, Mapping) else compute_required_backfill_date_range()
    start = _parse_date(date_range.get("date_start"))
    end = _parse_date(date_range.get("date_end"))
    if start is None or end is None or end < start:
        return {"status": "blocked", "batch_size_days": batch_size_days, "max_rows_per_batch": 500, "batches": [], "blocking_reasons": ["v12_target_date_range_missing"]}

    batches: list[dict[str, Any]] = []
    cursor = start
    while cursor <= end and len(batches) < 200:
        batch_end = min(cursor + timedelta(days=batch_size_days - 1), end)
        batches.append(
            {
                "batch_id": f"managed_backfill_{len(batches) + 1:03d}",
                "date_start": cursor.isoformat(),
                "date_end": batch_end.isoformat(),
                "max_rows_per_batch": 500,
                "dry_run_only": True,
            }
        )
        cursor = batch_end + timedelta(days=1)
    return {
        "status": "ready" if batches else "blocked",
        "batch_size_days": batch_size_days,
        "max_rows_per_batch": 500,
        "batch_count": len(batches),
        "batches": batches,
        "dry_run_only": True,
    }


def define_backfill_retry_policy() -> dict[str, Any]:
    return {
        "max_attempts_per_batch": 3,
        "backoff_seconds": [5, 30, 120],
        "retryable_failures": ["endpoint_timeout", "temporary_5xx", "rate_limited"],
        "non_retryable_failures": ["token_echo_detected", "auth_failure", "pit_leakage", "schema_drift"],
        "requires_human_review_after_failure_count": 3,
    }


def define_backfill_abort_conditions() -> list[str]:
    return [
        "token echo detected",
        "auth failure",
        "schema drift",
        "PIT leakage",
        "data quality fail",
        "response size over budget",
        "repeated endpoint failures",
        "customer_predictions path appears",
        "active_model.json appears unexpectedly",
    ]


def _human_approval_checklist() -> list[str]:
    return [
        "confirm endpoint/token are configured locally and masked",
        "review endpoint smoke, quarantine snapshot, and quarantine contract reports",
        "approve historical backfill date range and row budget",
        "confirm abort conditions and rollback plan",
        "verify no active model and no customer prediction output before execution",
    ]


def validate_backfill_preconditions() -> dict[str, Any]:
    smoke = _read_json(_diagnostics_path("managed_proxy_endpoint_smoke_report.json"))
    snapshot = _read_json(_diagnostics_path("managed_proxy_quarantine_snapshot_report.json"))
    contract = _read_json(_diagnostics_path("managed_proxy_quarantine_contract_report.json"))
    incident = _read_json(_incident_drill_path())
    blocking: list[str] = []
    warnings: list[str] = []

    if not (
        isinstance(smoke, Mapping)
        and _status(smoke) in {"pass", "ready", "success"}
        and str(smoke.get("auth_status") or "").lower() == "pass"
        and bool(smoke.get("endpoint_reachable"))
        and str(smoke.get("response_format_status") or "").lower() == "pass"
        and str(smoke.get("token_echo_status") or "").lower() == "pass"
    ):
        blocking.append("endpoint_smoke_not_passed")

    if not (isinstance(snapshot, Mapping) and _status(snapshot) in {"ready", "pass", "success"} and bool(snapshot.get("snapshot_pulled"))):
        blocking.append("quarantine_snapshot_not_passed")

    if not (
        isinstance(contract, Mapping)
        and _status(contract) in {"ready", "pass", "success"}
        and bool(contract.get("research_cache_promotion_allowed"))
        and bool(contract.get("research_cache_written"))
    ):
        blocking.append("quarantine_contract_or_research_cache_not_ready")

    cache_path = Path(str(contract.get("research_cache_path") or "")) if isinstance(contract, Mapping) else Path()
    cache_payload = _read_json(cache_path) if str(cache_path) else None
    if not (
        isinstance(cache_payload, Mapping)
        and bool(cache_payload.get("research_cache"))
        and not bool(cache_payload.get("production_eligible"))
        and not bool(cache_payload.get("feature_store_v12_allowed"))
    ):
        blocking.append("research_cache_missing")

    real_lockdown = incident.get("real_lockdown_state") if isinstance(incident, Mapping) and isinstance(incident.get("real_lockdown_state"), Mapping) else {}
    if bool(real_lockdown.get("lockdown_triggered")):
        blocking.append("governance_lockdown_active")

    warnings.append("manual_approval_required_before_historical_backfill_execution")
    return sanitize_for_json(
        {
            "status": "ready" if not blocking else "blocked",
            "endpoint_smoke_status": smoke.get("status", "missing") if isinstance(smoke, Mapping) else "missing",
            "quarantine_snapshot_status": snapshot.get("status", "missing") if isinstance(snapshot, Mapping) else "missing",
            "quarantine_contract_status": contract.get("status", "missing") if isinstance(contract, Mapping) else "missing",
            "research_cache_path": str(cache_path) if str(cache_path) else "",
            "blocking_reasons": sorted(set(blocking)),
            "warning_reasons": warnings,
        }
    )


def build_real_managed_data_backfill_plan() -> dict[str, Any]:
    preconditions = validate_backfill_preconditions()
    date_range = compute_required_backfill_date_range()
    date_range_missing = not (date_range.get("date_start") and date_range.get("date_end"))
    row_count = int(date_range.get("row_count_source") or 0)
    coverage = compute_required_coverage_budget(row_count=row_count)
    batch_plan = define_backfill_batch_plan(date_range)
    blocking = list(preconditions.get("blocking_reasons") or [])
    warnings = list(preconditions.get("warning_reasons") or [])
    if date_range_missing:
        blocking.append("v12_target_date_range_missing")
    if batch_plan.get("status") != "ready":
        blocking.extend(str(item) for item in (batch_plan.get("blocking_reasons") or []) if item)
    blocking = sorted({reason for reason in blocking if reason})

    payload = _base_payload()
    payload.update(
        {
            "status": "ready" if not blocking else "blocked",
            "generated_at": _now(),
            "required_date_range": date_range,
            "coverage_budget": coverage,
            "batch_plan": batch_plan,
            "retry_policy": define_backfill_retry_policy(),
            "abort_conditions": define_backfill_abort_conditions(),
            "human_approval_checklist": _human_approval_checklist(),
            "precondition_checks": preconditions,
            "blocking_reasons": blocking,
            "warning_reasons": sorted(set(warnings)),
            "production_cache_write_allowed": False,
            "feature_store_v12_allowed": False,
            "rows_fetched": False,
            "historical_backfill_executed": False,
            "production_cache_written": False,
            "training_invoked": False,
            "active_updated": False,
            "customer_prediction_generated": False,
        }
    )
    return sanitize_for_json(payload)


def write_backfill_planner_report() -> dict[str, Any]:
    return _write_json(_report_path(), build_real_managed_data_backfill_plan())


def get_latest_backfill_planner_report() -> dict[str, Any]:
    payload = _read_json(_report_path())
    if isinstance(payload, Mapping):
        return sanitize_for_json(dict(payload))
    return sanitize_for_json({**_base_payload(), "blocking_reasons": ["backfill_planner_report_missing"]})
