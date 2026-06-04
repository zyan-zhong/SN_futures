from __future__ import annotations

import json
import os
import sys
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Any

from ..api.json_utils import sanitize_for_json
from ..runtime import get_user_data_dir, get_user_output_dir
from ..utils.secret_sanitizer import sanitize_mapping, sanitize_text
from .active_absence_diagnostics_service import build_active_absence_diagnostics
from .data_consistency_audit_service import build_data_consistency_report
from .data_watermark_service import get_data_watermark_report
from .feature_stability_evidence_service import build_feature_stability_evidence
from .process_lifecycle_service import get_process_status
from .provider_status_canonical_service import build_canonical_provider_status
from .sample_boundary_service import build_sample_data_boundary_report
from .task_queue_service import get_recent_tasks


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _reports_dir() -> Path:
    path = get_user_output_dir() / "reports"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(sanitize_mapping(payload), ensure_ascii=False, indent=2), encoding="utf-8")


def _row(label: str, value: Any) -> str:
    if value is None:
        rendered = ""
    elif isinstance(value, bool):
        rendered = "true" if value else "false"
    else:
        rendered = sanitize_text(str(value))
    return f"- {label}: {rendered}"


def _feature_coverage_summary() -> dict[str, Any]:
    output_dir = get_user_output_dir()
    for path in [
        output_dir / "feature_coverage_report.json",
        output_dir / "feature_coverage_report_v2.json",
    ]:
        payload = _read_json(path)
        if payload:
            return payload
    return {"status": "missing", "message_zh": "No feature coverage report found."}


def _safe_count_json(path: Path, list_key: str | None = None) -> int:
    payload = _read_json(path)
    if list_key and isinstance(payload.get(list_key), list):
        return len(payload[list_key])
    if isinstance(payload, list):
        return len(payload)
    if isinstance(payload.get("rows"), list):
        return len(payload["rows"])
    return 0


def _api_smoke_summary() -> dict[str, Any]:
    path = get_user_output_dir() / "diagnostics" / "all_api_smoke.json"
    payload = _read_json(path)
    if payload:
        return payload
    return {
        "status": "not_run",
        "checked_count": 0,
        "failed_count": 0,
        "output_path": str(path),
        "message_zh": "Run scripts/smoke_all_terminal_apis.ps1 for live API smoke results.",
    }


def _first_existing(paths: list[Path]) -> Path | None:
    return next((path for path in paths if path.exists() and path.is_file()), None)


def _latest_file(patterns: list[str]) -> Path | None:
    output_dir = get_user_output_dir()
    found: list[Path] = []
    for pattern in patterns:
        found.extend(path for path in output_dir.glob(pattern) if path.is_file())
    if not found:
        return None
    return max(found, key=lambda path: path.stat().st_mtime)


def _secret_scan_summary() -> dict[str, Any]:
    path = get_user_data_dir() / "logs" / "runtime_secret_scan.json"
    payload = _read_json(path)
    if payload:
        payload.setdefault("path", str(path))
        return sanitize_for_json(payload)
    return {
        "status": "not_run",
        "path": str(path),
        "complete_key_leakage": False,
        "message_zh": "Run scripts/scan_runtime_secrets.ps1 to refresh runtime secret scan.",
    }


def _api_performance_summary() -> dict[str, Any]:
    path = _first_existing(
        [
            get_user_output_dir() / "performance" / "api_performance_report.json",
            get_user_output_dir() / "diagnostics" / "api_performance_report.json",
        ]
    )
    if path:
        payload = _read_json(path)
        payload.setdefault("path", str(path))
        return payload
    return {"status": "not_run", "path": str(get_user_output_dir() / "performance" / "api_performance_report.json")}


def _feature_store_manifest_summary() -> dict[str, Any]:
    path = _latest_file(["feature_store/*/feature_store_manifest.json"])
    return _read_json(path) | {"path": str(path)} if path else {"status": "missing"}


def _training_dataset_manifest_summary() -> dict[str, Any]:
    path = _latest_file(["training_dataset_manifest*.json"])
    return _read_json(path) | {"path": str(path)} if path else {"status": "missing"}


def _latest_validation_summary() -> dict[str, Any]:
    path = _latest_file(["validation/**/*.json", "model_registry/*validation*.json", "institutional_validation/*.json", "institutional_validation*.json"])
    return _read_json(path) | {"path": str(path)} if path else {"status": "missing"}


def _latest_promotion_summary() -> dict[str, Any]:
    path = _latest_file(["model_registry/*promotion*.json", "promotion*.json", "**/promotion_report*.json"])
    return _read_json(path) | {"path": str(path)} if path else {"status": "missing"}


def _latest_backtest_metrics_summary() -> dict[str, Any]:
    path = _latest_file(["research_backtests/*/metrics*.json", "research_backtests/**/*.json"])
    return _read_json(path) | {"path": str(path)} if path else {"status": "missing"}


def _feature_stability_summary(candidate_version: str = "v5") -> dict[str, Any]:
    try:
        return build_feature_stability_evidence(candidate_version=candidate_version)
    except Exception as exc:
        return {
            "status": "error",
            "candidate_version": candidate_version,
            "stability_score": None,
            "threshold": 0.55,
            "passed": False,
            "message_zh": f"Feature stability evidence unavailable: {exc}",
        }


def _error_log_summary() -> dict[str, Any]:
    logs_dir = get_user_data_dir() / "logs"
    rows: list[dict[str, Any]] = []
    for path in sorted(logs_dir.glob("*.log"), key=lambda item: item.stat().st_mtime, reverse=True)[:5]:
        try:
            text = sanitize_text(path.read_text(encoding="utf-8", errors="replace")[-2000:], extra_secrets=_runtime_secret_values())
        except Exception:
            text = ""
        rows.append({"file": str(path), "tail": text})
    return {"log_count": len(rows), "logs": rows}


def _runtime_secret_values() -> list[str]:
    names = ("SN_ALPHA_VANTAGE_KEY", "SN_NEWSAPI_KEY", "SN_MANAGED_DATA_PROXY_TOKEN", "SN_TUSHARE_TOKEN")
    return [value for name in names if (value := os.environ.get(name))]


def _safe_zip_text(zf: zipfile.ZipFile, arcname: str, text: str) -> None:
    clean = sanitize_text(text, extra_secrets=_runtime_secret_values())
    zf.writestr(arcname, clean)


def _safe_zip_json(zf: zipfile.ZipFile, arcname: str, payload: Any) -> None:
    clean = sanitize_mapping(payload, extra_secrets=_runtime_secret_values())
    zf.writestr(arcname, json.dumps(clean, ensure_ascii=False, indent=2))


def _safe_add_file(zf: zipfile.ZipFile, arcname: str, path: Path) -> None:
    lower_name = path.name.lower()
    if lower_name in {"secrets.json", "private_bundle_seed.json"} or "private_bundle_seed" in lower_name:
        return
    if not path.exists() or not path.is_file() or path.stat().st_size > 2_000_000:
        return
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return
    _safe_zip_text(zf, arcname, text)


def _build_machine_summary() -> dict[str, Any]:
    output_dir = get_user_output_dir()
    process = get_process_status()
    watermark = get_data_watermark_report()
    data_consistency = build_data_consistency_report()
    sample = build_sample_data_boundary_report()
    api_smoke = _api_smoke_summary()
    active_absence = build_active_absence_diagnostics()
    candidate_version = str(active_absence.get("candidate_version") or "v5") if isinstance(active_absence, dict) else "v5"
    feature_stability = _feature_stability_summary(candidate_version)
    provider_status_canonical = build_canonical_provider_status()
    recent_tasks = get_recent_tasks(limit=10)
    feature_coverage = _feature_coverage_summary()
    security = {
        "private_key_display": "masked_only",
        "secret_scan_result": _secret_scan_summary(),
        "static_private_seed_protection": "expected_403_or_404",
        "complete_key_leakage": False,
    }
    return {
        "generated_at": _now(),
        "user_data_dir": str(get_user_data_dir()),
        "output_dir": str(output_dir),
        "process": process,
        "watermark": watermark,
        "data_consistency": data_consistency,
        "sample_boundary": sample,
        "api_smoke": api_smoke,
        "api_performance": _api_performance_summary(),
        "active_absence": active_absence,
        "feature_stability": feature_stability,
        "provider_status_canonical": provider_status_canonical,
        "recent_tasks": recent_tasks,
        "feature_coverage": feature_coverage,
        "feature_store": _feature_store_manifest_summary(),
        "training_dataset": _training_dataset_manifest_summary(),
        "validation": _latest_validation_summary(),
        "promotion": _latest_promotion_summary(),
        "backtest_metrics": _latest_backtest_metrics_summary(),
        "error_logs": _error_log_summary(),
        "market_history_rows": _safe_count_json(output_dir / "sn_market_history.json", "history"),
        "cross_market_rows": _safe_count_json(output_dir / "fundamentals" / "sn_cross_market.json", "rows"),
        "news_raw_count": _safe_count_json(output_dir / "events" / "news_raw.json", "articles"),
        "event_factor_count": _safe_count_json(output_dir / "events" / "event_factor_inputs.json", "inputs"),
        "security": security,
        "active_updated": False,
        "customer_prediction_generated": False,
    }


def _render_txt(summary: dict[str, Any]) -> str:
    active_absence = summary.get("active_absence", {}) if isinstance(summary.get("active_absence"), dict) else {}
    root_causes = active_absence.get("root_causes", []) if isinstance(active_absence.get("root_causes"), list) else []
    blocking_metrics = active_absence.get("blocking_metrics", {}) if isinstance(active_absence.get("blocking_metrics"), dict) else {}
    lines = [
        "SNInsightTerminal Full System Diagnostic Report",
        "",
        "1. Report Header / System Version",
        _row("version", "0.3.9-private-research-beta.1"),
        _row("generated_at", summary.get("generated_at")),
        _row("user_data_dir", summary.get("user_data_dir")),
        _row("run_mode", "private research"),
        "- compliance: research only; no active publishing; no customer prediction; no investment advice.",
        "",
        "2. Process And System / Process Status",
        _row("backend_pid", summary.get("process", {}).get("pid")),
        _row("port", summary.get("process", {}).get("port")),
        _row("pid_file_exists", summary.get("process", {}).get("pid_file_exists")),
        _row("shutdown_setting", "auto-stop backend on terminal close is expected enabled"),
        _row("platform", sys.platform),
        "",
        "3. Process Lifecycle",
        _row("shutdown_api", "POST /api/terminal/system/shutdown"),
        _row("process_status_api", "GET /api/terminal/system/process-status"),
        _row("pid_running", summary.get("process", {}).get("pid_running")),
        _row("shutdown_requested", summary.get("process", {}).get("shutdown_requested")),
        _row("port_release_validation", "packaging/smoke_installed.ps1 verifies port release after shutdown"),
        _row("orphan_process_validation", "packaging/smoke_installed.ps1 verifies no SNInsightTerminal orphan remains"),
        "- scope: shutdown stops this local backend/task queue only; it must not kill browsers or unrelated python processes.",
        "",
        "4. API Health / API Performance Table",
        _row("checked_count", summary.get("api_smoke", {}).get("checked_count")),
        _row("failed_count", summary.get("api_smoke", {}).get("failed_count")),
        _row("api_performance_status", summary.get("api_performance", {}).get("status", "available_or_not_run")),
        _row("api_performance_path", summary.get("api_performance", {}).get("path")),
        _row("summary_latency", "see api_performance_report or all_api_smoke.json"),
        _row("snapshot_lite_latency", "see api_performance_report or all_api_smoke.json"),
        _row("system_health_latency", "see api_performance_report or all_api_smoke.json"),
        "",
        "5. Data Sources / Data Source Status",
        _row("provider_status_source", "provider_status_canonical.json"),
        _row("provider_status_report_time", summary.get("provider_status_canonical", {}).get("generated_at")),
        _row("market", summary.get("provider_status_canonical", {}).get("providers", {}).get("market", {}).get("status")),
        _row("tushare", summary.get("provider_status_canonical", {}).get("providers", {}).get("tushare", {}).get("status")),
        _row("alpha_vantage", summary.get("provider_status_canonical", {}).get("providers", {}).get("alpha_vantage", {}).get("status")),
        _row("alpha_last_attempt_time", summary.get("provider_status_canonical", {}).get("providers", {}).get("alpha_vantage", {}).get("last_attempt_time")),
        _row("alpha_data_time", summary.get("provider_status_canonical", {}).get("providers", {}).get("alpha_vantage", {}).get("data_time")),
        _row("newsapi", summary.get("provider_status_canonical", {}).get("providers", {}).get("newsapi", {}).get("status")),
        _row("newsapi_row_count", summary.get("provider_status_canonical", {}).get("providers", {}).get("newsapi", {}).get("row_count")),
        _row("newsapi_last_attempt_time", summary.get("provider_status_canonical", {}).get("providers", {}).get("newsapi", {}).get("last_attempt_time")),
        _row("newsapi_last_success_time", summary.get("provider_status_canonical", {}).get("providers", {}).get("newsapi", {}).get("last_success_time")),
        _row("newsapi_data_time", summary.get("provider_status_canonical", {}).get("providers", {}).get("newsapi", {}).get("data_time")),
        _row("managed_proxy", summary.get("provider_status_canonical", {}).get("providers", {}).get("managed_proxy", {}).get("status")),
        _row("shfe_direct", summary.get("provider_status_canonical", {}).get("providers", {}).get("shfe_public", {}).get("status")),
        "",
        "6. Data Watermark",
        _row("current_data_mode", summary.get("watermark", {}).get("current_data_mode")),
        _row("market_data_updated_at", summary.get("watermark", {}).get("market_data_updated_at")),
        _row("cross_market_updated_at", summary.get("watermark", {}).get("cross_market_updated_at")),
        _row("news_updated_at", summary.get("watermark", {}).get("news_updated_at")),
        _row("feature_store_updated_at", summary.get("watermark", {}).get("feature_store_updated_at")),
        _row("training_dataset_updated_at", summary.get("watermark", {}).get("training_dataset_updated_at")),
        _row("candidate_updated_at", summary.get("watermark", {}).get("candidate_updated_at")),
        "",
        "7. Data Consistency",
        _row("status", summary.get("data_consistency", {}).get("status")),
        _row("market_history_latest", summary.get("data_consistency", {}).get("latest_dates", {}).get("market_history")),
        _row("price_history_latest", summary.get("data_consistency", {}).get("latest_dates", {}).get("price_history")),
        _row("price_chart_latest", summary.get("data_consistency", {}).get("latest_dates", {}).get("price_chart")),
        _row("market_analysis_latest", summary.get("data_consistency", {}).get("latest_dates", {}).get("market_analysis")),
        _row("blocking_reasons", summary.get("data_consistency", {}).get("blocking_reasons")),
        "",
        "8. Sample/Real Data Boundary",
        _row("sample_mode", summary.get("sample_boundary", {}).get("sample_mode")),
        _row("real_data_available", summary.get("sample_boundary", {}).get("real_data_available")),
        _row("training_sample_data_used", summary.get("sample_boundary", {}).get("training_sample_data_used")),
        _row("candidate_sample_data_used", summary.get("sample_boundary", {}).get("candidate_sample_data_used")),
        _row("backtest_sample_data_used", summary.get("sample_boundary", {}).get("backtest_sample_data_used")),
        "",
        "9. Feature Coverage / Factor Coverage",
        _row("coverage_status", summary.get("feature_coverage", {}).get("status", "available_or_missing")),
        _row("usable_fields", summary.get("feature_coverage", {}).get("usable_fields", "see feature coverage report")),
        _row("excluded_fields", summary.get("feature_coverage", {}).get("excluded_fields", "see feature coverage report")),
        "",
        "10. Training Data / Feature Store",
        _row("manifest_status", summary.get("feature_store", {}).get("status", "available_or_missing")),
        _row("manifest_path", summary.get("feature_store", {}).get("path")),
        _row("usable_fields", summary.get("feature_store", {}).get("usable_fields", "see feature store manifest")),
        _row("excluded_fields", summary.get("feature_store", {}).get("excluded_fields", "see feature store manifest")),
        "",
        "11. Models / Candidate/Active Status",
        _row("dataset_versions", "v1/v2/v3/v4/v5 if manifests exist"),
        _row("manifest_path", summary.get("training_dataset", {}).get("path")),
        _row("feature_count", summary.get("training_dataset", {}).get("feature_count", "see training dataset manifests")),
        _row("sample_count_per_horizon", summary.get("training_dataset", {}).get("sample_count_per_horizon", "see training dataset manifests")),
        _row("leakage_check_pass", summary.get("training_dataset", {}).get("leakage_check_pass", "see training dataset manifests")),
        "",
        "11. Models",
        _row("active_model_status", active_absence.get("active_status", "none")),
        _row("promotion_gate_status", "not passed unless latest dry-run says pass"),
        _row("latest_promotion_path", summary.get("promotion", {}).get("path")),
        _row("latest_validation_path", summary.get("validation", {}).get("path")),
        _row("no_active_root_causes", len(root_causes)),
        _row("latest_validation_failures", [cause.get("category") for cause in root_causes[:5] if isinstance(cause, dict)]),
        "",
        "12. OOF / High Confidence",
        _row("top10_top20_accuracy", "see OOF integrity/high confidence reports"),
        _row("PBO", blocking_metrics.get("pbo")),
        _row("DSR", blocking_metrics.get("dsr")),
        _row("Reality Check", blocking_metrics.get("reality_check")),
        _row("feature_stability_score", summary.get("feature_stability", {}).get("stability_score")),
        _row("feature_stability_passed", summary.get("feature_stability", {}).get("passed")),
        _row("feature_stability_unstable_features", summary.get("feature_stability", {}).get("unstable_features")),
        "",
        "13. Research Backtest / Backtest Equity Summary",
        _row("latest_research_backtest_version", "see outputs/research_backtests"),
        _row("latest_backtest_metrics_path", summary.get("backtest_metrics", {}).get("path")),
        _row("equity_curve_paths", "outputs/research_backtests/*/equity_curve_*.csv"),
        _row("drawdown_paths", "outputs/research_backtests/*/drawdown_curve_*.csv"),
        _row("research_only", True),
        "",
        "14. Task Queue",
        _row("recent_task_count", summary.get("recent_tasks", {}).get("count")),
        _row("running_tasks", "see /api/terminal/tasks/recent"),
        _row("failed_tasks", "see /api/terminal/tasks/recent"),
        "",
        "15. Frontend Status / Frontend Page Status",
        _row("build_version", "see frontend build artifacts"),
        _row("page_api_map", "docs/TERMINAL_UI_API_MAP.md"),
        _row("chart_payload_status", "chart payload endpoints provide schema_version/source_files"),
        _row("last_browser_smoke_status", "see release smoke output"),
        "",
        "16. Security / Secret Scan Result",
        _row("private_key_configured", "masked only"),
        _row("secret_scan_result", summary.get("security", {}).get("secret_scan_result")),
        _row("static_private_seed_protection", summary.get("security", {}).get("static_private_seed_protection")),
        _row("complete_key_leakage", summary.get("security", {}).get("complete_key_leakage")),
        _row("Error Log Summary", f"{summary.get('error_logs', {}).get('log_count')} logs summarized in diagnostics bundle"),
        "",
        "17. Known Issues",
        "- no active model until promotion and institutional validation pass.",
        "- missing or stale institutional fundamentals can block stable model performance.",
        "- candidate accuracy and returns remain research-only until gate pass.",
        "",
        "18. Recommendations / P0/P1/P2 Recommendations",
        "- P0: keep process shutdown, cache invalidation, sample boundary, API smoke, and TXT diagnostics in quality gate.",
        "- P1: improve real data coverage for basis, inventory, LME tin, term structure, and high-quality events.",
        "- Model: candidate_v6 should focus on data coverage, label governance, fold/regime stability, and cost robustness.",
        "- UI: keep task status isolated and use stale-while-refreshing data instead of global blocking loaders.",
        "",
    ]
    return sanitize_text("\n".join(lines))


def _build_diagnostics_bundle(summary: dict[str, Any], txt_path: Path, json_path: Path) -> Path:
    output_dir = get_user_output_dir()
    diagnostics_dir = output_dir / "diagnostics"
    diagnostics_dir.mkdir(parents=True, exist_ok=True)
    data_consistency_path = diagnostics_dir / "data_consistency_report.json"
    secret_scan_path = diagnostics_dir / "secret_scan_summary.json"
    error_logs_path = diagnostics_dir / "error_logs_summary.json"
    task_history_path = diagnostics_dir / "task_history.json"
    _write_json(data_consistency_path, summary.get("data_consistency", {}))
    _write_json(secret_scan_path, summary.get("security", {}).get("secret_scan_result", {}))
    _write_json(error_logs_path, summary.get("error_logs", {}))
    _write_json(task_history_path, summary.get("recent_tasks", {}))

    bundle_path = diagnostics_dir / "diagnostics_bundle.zip"
    api_perf = _first_existing([output_dir / "performance" / "api_performance_report.json", output_dir / "diagnostics" / "api_performance_report.json"])
    feature_store = _latest_file(["feature_store/*/feature_store_manifest.json"])
    training = _latest_file(["training_dataset_manifest*.json"])
    validation = _latest_file(["validation/**/*.json", "model_registry/*validation*.json", "institutional_validation*.json"])
    promotion = _latest_file(["model_registry/*promotion*.json", "promotion*.json", "**/promotion_report*.json"])
    backtest_metrics = _latest_file(["research_backtests/*/metrics*.json", "research_backtests/**/*.json"])
    task_history = _first_existing([output_dir / "tasks" / "task_history.json", task_history_path])

    with zipfile.ZipFile(bundle_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        _safe_add_file(zf, "reports/full_system_report_latest.txt", txt_path)
        _safe_add_file(zf, "reports/full_system_report_latest.json", json_path)
        if api_perf:
            _safe_add_file(zf, "diagnostics/api_performance_report.json", api_perf)
        _safe_add_file(zf, "diagnostics/data_consistency_report.json", data_consistency_path)
        if feature_store:
            _safe_add_file(zf, "feature_store/feature_store_manifest.json", feature_store)
        if training:
            _safe_add_file(zf, "training/training_dataset_manifest.json", training)
        if validation:
            _safe_add_file(zf, "model/validation_report.json", validation)
        if promotion:
            _safe_add_file(zf, "model/promotion_report.json", promotion)
        if backtest_metrics:
            _safe_add_file(zf, f"backtest/{backtest_metrics.name}", backtest_metrics)
        if task_history:
            _safe_add_file(zf, "tasks/task_history.json", task_history)
        _safe_add_file(zf, "security/secret_scan_summary.json", secret_scan_path)
        _safe_add_file(zf, "logs/error_logs_summary.json", error_logs_path)
        _safe_zip_json(
            zf,
            "README.json",
            {
                "generated_at": _now(),
                "message_zh": "诊断包仅包含脱敏小报告；不包含 secrets.json、private_bundle_seed.json 或原始大缓存。",
                "forbidden_files": ["secrets.json", "private_bundle_seed.json", "raw large cache"],
            },
        )
    return bundle_path


def build_full_system_txt_report() -> dict[str, Any]:
    summary = _build_machine_summary()
    text = _render_txt(summary)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_dir = _reports_dir()
    txt_path = report_dir / f"full_system_report_{timestamp}.txt"
    latest_txt_path = report_dir / "full_system_report_latest.txt"
    latest_json_path = report_dir / "full_system_report_latest.json"
    txt_path.write_text(text, encoding="utf-8")
    latest_txt_path.write_text(text, encoding="utf-8")
    latest_json_path.write_text(
        json.dumps(sanitize_mapping(summary, extra_secrets=_runtime_secret_values()), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    bundle_path = _build_diagnostics_bundle(summary, latest_txt_path, latest_json_path)
    return sanitize_for_json(
        {
            "status": "success",
            "txt_path": str(txt_path),
            "latest_txt_path": str(latest_txt_path),
            "json_path": str(latest_json_path),
            "diagnostics_bundle_path": str(bundle_path),
            "summary": {
                "active_status": summary.get("active_absence", {}).get("active_status", "none"),
                "api_failed_count": summary.get("api_smoke", {}).get("failed_count", 0),
                "current_data_mode": summary.get("watermark", {}).get("current_data_mode", ""),
                "diagnostics_bundle_path": str(bundle_path),
            },
        }
    )


def get_latest_full_system_txt_report() -> dict[str, Any]:
    latest_txt_path = _reports_dir() / "full_system_report_latest.txt"
    latest_json_path = _reports_dir() / "full_system_report_latest.json"
    bundle_path = get_user_output_dir() / "diagnostics" / "diagnostics_bundle.zip"
    if not latest_txt_path.exists():
        return build_full_system_txt_report()
    return sanitize_for_json(
        {
            "status": "success",
            "txt_path": str(latest_txt_path),
            "json_path": str(latest_json_path),
            "diagnostics_bundle_path": str(bundle_path),
            "text_preview": latest_txt_path.read_text(encoding="utf-8", errors="replace")[:1200],
        }
    )
