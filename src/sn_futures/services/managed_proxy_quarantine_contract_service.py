from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping, Sequence

from ..api.json_utils import sanitize_for_json
from ..runtime import get_user_output_dir
from ..utils.secret_sanitizer import contains_secret_like_value
from .managed_data_audit_service import validate_managed_point_in_time_rows
from .managed_data_quality_service import build_managed_data_quality_scorecard
from .managed_pit_replay_service import build_pit_replay_report
from .managed_proxy_quarantine_snapshot_service import get_latest_quarantine_snapshot_report
from .managed_proxy_schema_mapper_service import build_schema_mapping_report


CONTRACT_VERSION = "managed_proxy_quarantine_contract_v1"
CONTRACT_REPORT_FILENAME = "managed_proxy_quarantine_contract_report.json"
RESEARCH_CACHE_VERSION = "managed_proxy_research_cache_v1"
FORBIDDEN_SOURCE_PATH_PARTS = {
    "customer_predictions",
    "feature_store",
    "training_datasets",
    "model_registry",
    "fundamentals",
}


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _output_dir() -> Path:
    return get_user_output_dir()


def _report_path() -> Path:
    path = _output_dir() / "diagnostics" / CONTRACT_REPORT_FILENAME
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _quarantine_root() -> Path:
    return _output_dir() / "managed_proxy_quarantine"


def _research_cache_root() -> Path:
    return _output_dir() / "managed_proxy_research_cache"


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


def _write_report(payload: Mapping[str, Any]) -> dict[str, Any]:
    return _write_json(_report_path(), payload)


def _rows_from_payload(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, Mapping):
        rows = payload.get("rows") or payload.get("data") or payload.get("history") or []
    else:
        rows = payload
    if not isinstance(rows, list):
        return []
    return [dict(row) for row in rows if isinstance(row, Mapping)]


def _is_within(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except Exception:
        return False


def _secret_like_payload(payload: Any) -> bool:
    text = json.dumps(payload, ensure_ascii=False, default=str) if isinstance(payload, (Mapping, list)) else str(payload or "")
    if "Authorization" in text or "Bearer " in text:
        return True
    if contains_secret_like_value(text):
        return True

    def _walk(value: Any) -> bool:
        if isinstance(value, Mapping):
            for key, nested in value.items():
                lower = str(key).lower()
                if any(hint in lower for hint in ("authorization", "token", "secret", "password", "api_key", "apikey", "header")):
                    return True
                if _walk(nested):
                    return True
            return False
        if isinstance(value, list):
            return any(_walk(item) for item in value)
        return False

    return _walk(payload)


def _base_payload() -> dict[str, Any]:
    return {
        "status": "blocked",
        "generated_at": _now(),
        "contract_version": CONTRACT_VERSION,
        "source_quarantine_path": "",
        "row_count": 0,
        "schema_contract_status": "not_run",
        "pit_replay_status": "not_run",
        "pit_audit_status": "not_run",
        "data_quality_status": "not_run",
        "schema_contract_summary": {},
        "pit_replay_summary": {},
        "pit_audit_summary": {},
        "data_quality_summary": {},
        "research_cache_promotion_allowed": False,
        "research_cache_path": "",
        "research_cache_written": False,
        "production_eligible": False,
        "feature_store_v12_allowed": False,
        "blocking_reasons": [],
        "warning_reasons": [],
        "training_invoked": False,
        "active_updated": False,
        "customer_prediction_generated": False,
        "report_path": str(_report_path()),
    }


def _blocked_payload(reasons: Sequence[Any] | str, *, source_quarantine_path: str = "", row_count: int = 0, write: bool = True) -> dict[str, Any]:
    reason_list = [reasons] if isinstance(reasons, str) else list(reasons)
    payload = _base_payload()
    payload["source_quarantine_path"] = str(source_quarantine_path or "")
    payload["row_count"] = int(row_count or 0)
    payload["blocking_reasons"] = sorted({str(reason) for reason in reason_list if str(reason or "").strip()})
    return _write_report(payload) if write else sanitize_for_json(payload)


def load_quarantine_snapshot(snapshot_report: Mapping[str, Any] | None = None) -> dict[str, Any]:
    report = dict(snapshot_report) if isinstance(snapshot_report, Mapping) else get_latest_quarantine_snapshot_report()
    blocking: list[str] = []
    status = str(report.get("status") or "missing").lower()
    if status not in {"ready", "success", "pass"} or not bool(report.get("snapshot_pulled")):
        blocking.extend(str(item) for item in (report.get("blocking_reasons") or []) if item)
        if "quarantine_snapshot_report_missing" in blocking:
            pass
        elif status in {"missing", ""}:
            blocking.append("quarantine_snapshot_report_missing")
        else:
            blocking.append("quarantine_snapshot_not_ready")
    if str(report.get("secret_safety_status") or "missing").lower() not in {"pass", "ready", "success"}:
        blocking.append("quarantine_snapshot_secret_safety_failed")

    source_path_text = str(report.get("quarantine_path") or report.get("source_quarantine_path") or "").strip()
    if not source_path_text:
        blocking.append("source_quarantine_path_missing")
        source_path = Path()
    else:
        source_path = Path(source_path_text)

    rows: list[dict[str, Any]] = []
    snapshot_payload: Any = {}
    if source_path_text:
        parts = {part.lower() for part in source_path.parts}
        if any(part in parts for part in FORBIDDEN_SOURCE_PATH_PARTS):
            blocking.append("source_path_not_quarantine_only")
        if not _is_within(source_path, _quarantine_root()):
            blocking.append("source_path_not_under_quarantine_root")
        if not source_path.exists():
            blocking.append("source_quarantine_snapshot_missing")
        else:
            snapshot_payload = _read_json(source_path)
            if not isinstance(snapshot_payload, Mapping):
                blocking.append("source_quarantine_snapshot_unreadable")
            else:
                rows = _rows_from_payload(snapshot_payload)
                if not bool(snapshot_payload.get("quarantine_only", True)):
                    blocking.append("snapshot_not_marked_quarantine_only")
                if bool(snapshot_payload.get("fixture_only")) or bool(snapshot_payload.get("sample_data_used")):
                    blocking.append("sample_fixture_not_allowed")
                if bool(snapshot_payload.get("production_eligible")):
                    blocking.append("snapshot_unexpectedly_production_eligible")
                if _secret_like_payload(snapshot_payload):
                    blocking.append("quarantine_snapshot_secret_safety_failed")

    if int(report.get("snapshot_row_count") or report.get("row_count") or len(rows) or 0) <= 0 or not rows:
        blocking.append("quarantine_snapshot_rows_missing")

    blocking = sorted({reason for reason in blocking if reason})
    return sanitize_for_json(
        {
            "status": "ready" if not blocking else "blocked",
            "source_quarantine_path": source_path_text,
            "row_count": len(rows),
            "rows": rows,
            "snapshot_report": report,
            "blocking_reasons": blocking,
            "training_invoked": False,
            "active_updated": False,
            "customer_prediction_generated": False,
        }
    )


def run_quarantine_schema_contract(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    report = build_schema_mapping_report(sample_rows=[dict(row) for row in rows], field_mapping={}, write=False)
    return sanitize_for_json(
        {
            "status": "ready" if bool(report.get("schema_mapping_ready")) else "blocked",
            "schema_mapping_ready": bool(report.get("schema_mapping_ready")),
            "mapped_fields": report.get("mapped_fields") or [],
            "unmapped_required_fields": report.get("unmapped_required_fields") or [],
            "blocking_reasons": list(report.get("blocking_reasons") or []),
            "warning_reasons": list(report.get("warning_reasons") or []),
        }
    )


def run_quarantine_pit_contract(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    replay = build_pit_replay_report(rows=[dict(row) for row in rows], write=False)
    return sanitize_for_json(
        {
            "status": "ready" if replay.get("status") == "ready" and replay.get("point_in_time_join_ready") else "blocked",
            "cases_run": replay.get("cases_run", 0),
            "cases_passed": replay.get("cases_passed", 0),
            "cases_failed": replay.get("cases_failed", 0),
            "point_in_time_join_ready": bool(replay.get("point_in_time_join_ready")),
            "blocking_reasons": list(replay.get("blocking_reasons") or []),
        }
    )


def _run_quarantine_pit_audit(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    audit = validate_managed_point_in_time_rows([dict(row) for row in rows])
    return sanitize_for_json(
        {
            "status": "ready" if audit.get("status") == "pass" else "blocked",
            "row_count": audit.get("row_count", 0),
            "missing_timestamp_fields": audit.get("missing_timestamp_fields") or [],
            "missing_fundamental_fields": audit.get("missing_fundamental_fields") or [],
            "leakage_checks": audit.get("leakage_checks") or {},
            "blocking_reasons": list(audit.get("blocking_reasons") or []),
        }
    )


def run_quarantine_data_quality_contract(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    quality = build_managed_data_quality_scorecard(rows=[dict(row) for row in rows], write=False)
    return sanitize_for_json(
        {
            "status": "pass" if bool(quality.get("gate_passed")) else "blocked",
            "row_count": quality.get("row_count", 0),
            "quality_score": quality.get("quality_score"),
            "gate_passed": bool(quality.get("gate_passed")),
            "blocking_reasons": list(quality.get("blocking_reasons") or []),
            "warning_reasons": list(quality.get("warning_reasons") or []),
        }
    )


def validate_research_cache_promotion_gate(contract_report: Mapping[str, Any] | None = None) -> dict[str, Any]:
    report = dict(contract_report) if isinstance(contract_report, Mapping) else get_latest_quarantine_contract_report()
    blocking = [str(item) for item in (report.get("blocking_reasons") or []) if item]
    checks = {
        "schema_contract_ready": str(report.get("schema_contract_status") or "").lower() == "ready",
        "pit_replay_ready": str(report.get("pit_replay_status") or "").lower() == "ready",
        "pit_audit_ready": str(report.get("pit_audit_status") or "").lower() == "ready",
        "data_quality_pass": str(report.get("data_quality_status") or "").lower() == "pass",
        "source_quarantine_path_present": bool(str(report.get("source_quarantine_path") or "").strip()),
        "row_count_positive": int(report.get("row_count") or 0) > 0,
    }
    for key, passed in checks.items():
        if not passed:
            blocking.append(key.replace("_ready", "_failed").replace("_pass", "_failed").replace("_present", "_missing").replace("_positive", "_missing"))
    allowed = not sorted(set(blocking))
    return sanitize_for_json(
        {
            "status": "ready" if allowed else "blocked",
            "research_cache_promotion_allowed": allowed,
            "precondition_checks": checks,
            "blocking_reasons": sorted({reason for reason in blocking if reason}),
            "production_eligible": False,
            "feature_store_v12_allowed": False,
            "training_invoked": False,
            "active_updated": False,
            "customer_prediction_generated": False,
        }
    )


def build_quarantine_contract_report(*, write: bool = True, snapshot_report: Mapping[str, Any] | None = None) -> dict[str, Any]:
    snapshot = load_quarantine_snapshot(snapshot_report)
    if snapshot.get("status") != "ready":
        return _blocked_payload(
            snapshot.get("blocking_reasons") or ["quarantine_snapshot_not_ready"],
            source_quarantine_path=str(snapshot.get("source_quarantine_path") or ""),
            row_count=int(snapshot.get("row_count") or 0),
            write=write,
        )

    rows = [dict(row) for row in snapshot.get("rows") or [] if isinstance(row, Mapping)]
    schema = run_quarantine_schema_contract(rows)
    pit = run_quarantine_pit_contract(rows)
    audit = _run_quarantine_pit_audit(rows)
    quality = run_quarantine_data_quality_contract(rows)

    blocking: list[str] = []
    if schema["status"] != "ready":
        blocking.append("managed_proxy_schema_mapping_blocked")
        blocking.extend(str(item) for item in schema.get("blocking_reasons") or [])
    if pit["status"] != "ready":
        blocking.append("pit_replay_failed")
        blocking.extend(str(item) for item in pit.get("blocking_reasons") or [])
    if audit["status"] != "ready":
        blocking.append("pit_audit_failed")
        blocking.extend(str(item) for item in audit.get("blocking_reasons") or [])
    if quality["status"] != "pass":
        blocking.append("managed_data_quality_failed")
        blocking.extend(str(item) for item in quality.get("blocking_reasons") or [])
    blocking = sorted({reason for reason in blocking if reason})
    ready = not blocking
    payload = _base_payload()
    payload.update(
        {
            "status": "ready" if ready else "blocked",
            "source_quarantine_path": snapshot.get("source_quarantine_path", ""),
            "row_count": len(rows),
            "schema_contract_status": schema["status"],
            "pit_replay_status": pit["status"],
            "pit_audit_status": audit["status"],
            "data_quality_status": quality["status"],
            "schema_contract_summary": schema,
            "pit_replay_summary": pit,
            "pit_audit_summary": audit,
            "data_quality_summary": quality,
            "research_cache_promotion_allowed": ready,
            "blocking_reasons": blocking,
            "warning_reasons": list(quality.get("warning_reasons") or []),
        }
    )
    return _write_report(payload) if write else sanitize_for_json(payload)


def _research_cache_path() -> Path:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return _research_cache_root() / f"managed_proxy_research_cache_{stamp}.json"


def promote_quarantine_to_research_cache() -> dict[str, Any]:
    report = build_quarantine_contract_report(write=True)
    gate = validate_research_cache_promotion_gate(report)
    if not gate.get("research_cache_promotion_allowed"):
        blocked = dict(report)
        blocked["research_cache_promotion_allowed"] = False
        blocked["research_cache_written"] = False
        blocked["blocking_reasons"] = sorted({*(blocked.get("blocking_reasons") or []), *(gate.get("blocking_reasons") or [])})
        return _write_report(blocked)

    snapshot = load_quarantine_snapshot({"status": "ready", "snapshot_pulled": True, "secret_safety_status": "pass", "quarantine_path": report.get("source_quarantine_path"), "snapshot_row_count": report.get("row_count")})
    rows = [dict(row) for row in snapshot.get("rows") or [] if isinstance(row, Mapping)]
    if snapshot.get("status") != "ready" or not rows:
        blocked = dict(report)
        blocked["status"] = "blocked"
        blocked["research_cache_promotion_allowed"] = False
        blocked["research_cache_written"] = False
        blocked["blocking_reasons"] = sorted({*(blocked.get("blocking_reasons") or []), *(snapshot.get("blocking_reasons") or ["quarantine_snapshot_not_ready"])})
        return _write_report(blocked)

    cache_path = _research_cache_path()
    cache_payload = {
        "research_cache_version": RESEARCH_CACHE_VERSION,
        "generated_at": _now(),
        "research_cache": True,
        "production_eligible": False,
        "feature_store_v12_allowed": False,
        "source_quarantine_path": report.get("source_quarantine_path", ""),
        "source_contract_report_path": str(_report_path()),
        "row_count": len(rows),
        "rows": rows,
        "training_invoked": False,
        "active_updated": False,
        "customer_prediction_generated": False,
    }
    _write_json(cache_path, cache_payload)
    promoted = dict(report)
    promoted.update(
        {
            "status": "ready",
            "research_cache_promotion_allowed": True,
            "research_cache_written": True,
            "research_cache_path": str(cache_path),
            "production_eligible": False,
            "feature_store_v12_allowed": False,
            "training_invoked": False,
            "active_updated": False,
            "customer_prediction_generated": False,
        }
    )
    return _write_report(promoted)


def get_latest_quarantine_contract_report() -> dict[str, Any]:
    path = _report_path()
    payload = _read_json(path)
    if isinstance(payload, Mapping):
        return sanitize_for_json(dict(payload))
    return sanitize_for_json(
        {
            **_base_payload(),
            "blocking_reasons": ["quarantine_contract_report_missing"],
        }
    )
