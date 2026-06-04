from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping, Sequence

from ..api.json_utils import sanitize_for_json
from ..runtime import get_user_output_dir
from ..utils.secret_sanitizer import sanitize_mapping, sanitize_text


LEDGER_VERSION = "research_run_ledger_v1"
DEFAULT_FORBIDDEN_SIDE_EFFECTS = ("active_model", "customer_prediction")
SAFE_REPORTS: tuple[tuple[str, str, str], ...] = (
    ("managed_proxy_setup", "safe_check", "diagnostics/managed_proxy_setup_report.json"),
    ("managed_proxy_health", "safe_check", "diagnostics/managed_proxy_health.json"),
    ("pit_audit", "safe_check", "diagnostics/managed_data_audit_manifest.json"),
    ("schema_mapping", "safe_check", "diagnostics/managed_proxy_schema_mapping_report.json"),
    ("pit_replay", "safe_check", "diagnostics/managed_pit_replay_report.json"),
    ("reliability", "safe_check", "diagnostics/managed_proxy_reliability_report.json"),
    ("data_quality", "safe_check", "diagnostics/managed_data_quality_scorecard.json"),
    ("decision_board", "report_refresh", "model_research/research_decision_board.json"),
    ("evidence_bundle", "report_refresh", "model_research/evidence_bundle_index.json"),
    ("freshness_auditor", "report_refresh", "model_research/evidence_freshness_report.json"),
    ("cost_attribution", "report_refresh", "model_research/cost_stress_attribution.json"),
    ("year_attribution", "report_refresh", "model_research/year_concentration_evidence.json"),
)


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _output_dir() -> Path:
    return get_user_output_dir()


def _run_dir() -> Path:
    path = _output_dir() / "model_research" / "run_ledger"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _manifest_dir() -> Path:
    path = _run_dir() / "manifests"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _ledger_path() -> Path:
    return _run_dir() / "research_run_ledger.jsonl"


def _report_path() -> Path:
    return _run_dir() / "research_run_ledger_report.json"


def _resolve_output_path(relative_path: str) -> Path:
    primary = _output_dir() / relative_path
    if primary.exists():
        return primary
    fallback = Path("outputs") / relative_path
    if fallback.exists():
        return fallback
    return primary


def _safe_payload(payload: Any) -> Any:
    return _scrub_payload(sanitize_for_json(sanitize_mapping(payload)))


def _scrub_payload(payload: Any) -> Any:
    if isinstance(payload, Mapping):
        return {sanitize_text(str(key)): _scrub_payload(value) for key, value in payload.items()}
    if isinstance(payload, list):
        return [_scrub_payload(item) for item in payload]
    if isinstance(payload, str):
        return sanitize_text(payload)
    return payload


def _hash_file(path: Path) -> dict[str, Any]:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return {
        "sha256": digest.hexdigest(),
        "size_bytes": int(path.stat().st_size),
        "exists": True,
    }


def _hash_paths(paths: Sequence[Any]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for raw in paths:
        text = str(raw or "")
        if not text:
            continue
        path = Path(text)
        if path.exists() and path.is_file():
            out[text] = _hash_file(path)
        else:
            out[text] = {"sha256": "", "size_bytes": 0, "exists": False}
    return _safe_payload(out)


def compute_run_input_hashes(input_paths: Sequence[Any]) -> dict[str, dict[str, Any]]:
    return _hash_paths(input_paths)


def compute_run_output_hashes(output_paths: Sequence[Any]) -> dict[str, dict[str, Any]]:
    return _hash_paths(output_paths)


def _forbidden_paths() -> dict[str, list[Path]]:
    out = _output_dir()
    return {
        "active_model": [
            out / "model_registry" / "active_model.json",
            out / "models" / "active_model.json",
            Path("outputs") / "model_registry" / "active_model.json",
            Path("outputs") / "models" / "active_model.json",
        ],
        "customer_prediction": [
            out / "customer_predictions",
            out / "customer_predictions.json",
            Path("outputs") / "customer_predictions",
            Path("outputs") / "customer_predictions.json",
        ],
    }


def _path_matches(path: Path, candidate: Path) -> bool:
    try:
        return path.resolve() == candidate.resolve()
    except Exception:
        return str(path) == str(candidate)


def _manifest_path(run_id: str) -> Path:
    return _manifest_dir() / f"{run_id}.json"


def start_research_run(
    *,
    service_name: str,
    run_type: str,
    input_paths: Sequence[Any] | None = None,
    output_paths: Sequence[Any] | None = None,
    allowed_side_effects: Sequence[str] | None = None,
    forbidden_side_effects: Sequence[str] | None = None,
) -> dict[str, Any]:
    run_id = f"run-{uuid.uuid4().hex[:16]}"
    payload = {
        "run_id": run_id,
        "started_at": _now(),
        "finished_at": "",
        "service_name": str(service_name or "unknown"),
        "run_type": str(run_type or "report_refresh"),
        "allowed_side_effects": list(allowed_side_effects or ["write_declared_outputs"]),
        "forbidden_side_effects": list(forbidden_side_effects or DEFAULT_FORBIDDEN_SIDE_EFFECTS),
        "input_paths": [str(item) for item in input_paths or []],
        "output_paths": [str(item) for item in output_paths or []],
        "input_hashes": compute_run_input_hashes(input_paths or []),
        "output_hashes": {},
        "status": "running",
        "error_summary": "",
        "training_invoked": False,
        "active_updated": False,
        "customer_prediction_generated": False,
        "manifest_path": str(_manifest_path(run_id)),
    }
    return _safe_payload(payload)


def validate_no_forbidden_side_effects(run_manifest: Mapping[str, Any]) -> dict[str, Any]:
    run_id = str(run_manifest.get("run_id") or "")
    if not run_id:
        return _safe_payload({"status": "invalid", "blocking_reasons": ["run_id_missing"]})
    forbidden = set(str(item) for item in run_manifest.get("forbidden_side_effects") or DEFAULT_FORBIDDEN_SIDE_EFFECTS)
    output_paths = [Path(str(item)) for item in run_manifest.get("output_paths") or [] if str(item or "")]
    blocking: list[str] = []
    existing_forbidden: list[str] = []
    for effect, paths in _forbidden_paths().items():
        if effect not in forbidden:
            continue
        for candidate in paths:
            if candidate.exists():
                existing_forbidden.append(str(candidate))
            if any(_path_matches(path, candidate) for path in output_paths):
                blocking.append(f"forbidden_output:{effect}")
    for effect in ("active_model", "customer_prediction"):
        if effect in forbidden and existing_forbidden and effect in str(existing_forbidden):
            blocking.append(f"forbidden_side_effect_present:{effect}")
    status = "violation" if blocking or existing_forbidden else "pass"
    return _safe_payload(
        {
            "status": status,
            "blocking_reasons": sorted(set(blocking)),
            "existing_forbidden_outputs": sorted(set(existing_forbidden)),
        }
    )


def finalize_research_run(run_manifest: Mapping[str, Any], *, error_summary: str = "") -> dict[str, Any]:
    if not str(run_manifest.get("run_id") or ""):
        return _safe_payload(
            {
                "status": "invalid",
                "blocking_reasons": ["run_id_missing"],
                "training_invoked": False,
                "active_updated": False,
                "customer_prediction_generated": False,
            }
        )
    run = dict(run_manifest)
    run["finished_at"] = _now()
    run["output_hashes"] = compute_run_output_hashes(run.get("output_paths") or [])
    run["error_summary"] = str(error_summary or "")
    side_effects = validate_no_forbidden_side_effects(run)
    if side_effects["status"] == "violation":
        run["status"] = "violation"
        run["blocking_reasons"] = side_effects.get("blocking_reasons", [])
        run["existing_forbidden_outputs"] = side_effects.get("existing_forbidden_outputs", [])
    else:
        run["status"] = "failed" if error_summary else "success"
        run["blocking_reasons"] = []
        run["existing_forbidden_outputs"] = side_effects.get("existing_forbidden_outputs", [])
    run["training_invoked"] = False
    run["active_updated"] = False
    run["customer_prediction_generated"] = False
    safe = _safe_payload(run)
    path = Path(str(safe.get("manifest_path") or _manifest_path(str(safe["run_id"]))))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(safe, ensure_ascii=False, indent=2), encoding="utf-8")
    return safe


def append_run_ledger(run_manifest: Mapping[str, Any]) -> dict[str, Any]:
    safe = _safe_payload(dict(run_manifest))
    _ledger_path().parent.mkdir(parents=True, exist_ok=True)
    with _ledger_path().open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(safe, ensure_ascii=False, sort_keys=True))
        handle.write("\n")
    return safe


def _read_ledger_entries() -> list[dict[str, Any]]:
    path = _ledger_path()
    if not path.exists():
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


def _existing_run_keys(entries: Sequence[Mapping[str, Any]]) -> set[tuple[str, str, str]]:
    keys: set[tuple[str, str, str]] = set()
    for entry in entries:
        output_hashes = entry.get("output_hashes")
        if not isinstance(output_hashes, Mapping):
            continue
        for path, meta in output_hashes.items():
            digest = str(meta.get("sha256") if isinstance(meta, Mapping) else "")
            if digest:
                keys.add((str(entry.get("service_name") or ""), str(path), digest))
    return keys


def _record_current_safe_reports() -> list[dict[str, Any]]:
    existing_entries = _read_ledger_entries()
    existing_keys = _existing_run_keys(existing_entries)
    appended: list[dict[str, Any]] = []
    for service_name, run_type, relative_path in SAFE_REPORTS:
        path = _resolve_output_path(relative_path)
        if not path.exists() or not path.is_file():
            continue
        digest = _hash_file(path)["sha256"]
        key = (service_name, str(path), digest)
        if key in existing_keys:
            continue
        run = start_research_run(service_name=service_name, run_type=run_type, output_paths=[str(path)])
        finalized = finalize_research_run(run)
        append_run_ledger(finalized)
        appended.append(finalized)
    return appended


def build_run_ledger_report(*, record_current: bool = True, write: bool = True) -> dict[str, Any]:
    if record_current:
        _record_current_safe_reports()
    entries = _read_ledger_entries()
    latest = entries[-20:]
    violation_count = sum(1 for item in entries if str(item.get("status") or "") == "violation")
    safe_check_count = sum(1 for item in entries if str(item.get("run_type") or "") == "safe_check")
    heavy_task_count = sum(1 for item in entries if str(item.get("run_type") or "") == "heavy_task")
    report = {
        "status": "violation" if violation_count else "ready",
        "generated_at": _now(),
        "ledger_version": LEDGER_VERSION,
        "ledger_path": str(_ledger_path()),
        "report_path": str(_report_path()),
        "latest_run_count": len(entries),
        "latest_runs": latest,
        "violation_count": violation_count,
        "safe_check_count": safe_check_count,
        "report_refresh_count": sum(1 for item in entries if str(item.get("run_type") or "") == "report_refresh"),
        "heavy_task_count": heavy_task_count,
        "forbidden_side_effects": list(DEFAULT_FORBIDDEN_SIDE_EFFECTS),
        "training_invoked": False,
        "active_updated": False,
        "customer_prediction_generated": False,
    }
    safe = _safe_payload(report)
    if write:
        _report_path().parent.mkdir(parents=True, exist_ok=True)
        _report_path().write_text(json.dumps(safe, ensure_ascii=False, indent=2), encoding="utf-8")
    return safe


def get_run_ledger_report() -> dict[str, Any]:
    path = _report_path()
    if path.exists():
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(payload, Mapping):
                return _safe_payload(dict(payload))
        except Exception:
            pass
    return build_run_ledger_report(record_current=False, write=False)
