from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Mapping

from ..api.json_utils import safe_json_dumps, sanitize_for_json
from ..runtime import get_user_output_dir
from ..utils.secret_sanitizer import sanitize_mapping, sanitize_text


PLAN_JSON_NAME = "system_repair_plan.json"
PLAN_MD_NAME = "system_repair_plan.md"
PREDICTION_MUTATION_PATHS = (
    ("model_registry", "active_model.json"),
    ("models", "active_model.json"),
    ("sn_live_predictions.json",),
    ("sn_unified_forecast.json",),
    ("customer_predictions.json",),
)


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _diagnostics_dir() -> Path:
    path = get_user_output_dir() / "diagnostics"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists() or not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _read_text(path: Path) -> str:
    if not path.exists() or not path.is_file():
        return ""
    try:
        return sanitize_text(path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return ""


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    clean = sanitize_for_json(sanitize_mapping(payload))
    safe_json_dumps(clean)
    path.write_text(json.dumps(clean, ensure_ascii=False, indent=2), encoding="utf-8")


def _latest_file(patterns: Iterable[str]) -> Path | None:
    output_dir = get_user_output_dir()
    found: list[Path] = []
    for pattern in patterns:
        found.extend(path for path in output_dir.glob(pattern) if path.is_file())
    if not found:
        return None
    return max(found, key=lambda path: path.stat().st_mtime)


def _first_existing(paths: Iterable[Path]) -> Path | None:
    return next((path for path in paths if path.exists() and path.is_file()), None)


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _as_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    return sanitize_text(str(value))


def _bool_failed(value: Any) -> bool:
    if isinstance(value, Mapping):
        if value.get("passed") is False or value.get("within_budget") is False or value.get("success") is False:
            return True
        status = str(value.get("status") or value.get("result") or "").lower()
        return status in {"failed", "fail", "error", "blocked", "missing"}
    return False


def _metric_evidence(name: str, value: Any) -> str:
    if isinstance(value, Mapping):
        details = []
        for key in ("value", "threshold", "passed", "status", "elapsed_ms", "target_ms"):
            if key in value:
                details.append(f"{key}={_as_text(value.get(key))}")
        return f"{name}: {', '.join(details) if details else _as_text(value)}"
    return f"{name}: {_as_text(value)}"


def _join(values: Iterable[Any], fallback: str = "No detailed evidence found.") -> str:
    rendered = [item for item in (_as_text(value).strip() for value in values) if item]
    return "; ".join(rendered) if rendered else fallback


def _issue(
    issue_id: str,
    priority: str,
    category: str,
    title: str,
    evidence: str,
    impact: str,
    fix_plan: str,
    owner: str,
    expected_gain: str,
) -> dict[str, str]:
    return {
        "id": issue_id,
        "priority": priority,
        "category": category,
        "title": sanitize_text(title),
        "evidence": sanitize_text(evidence),
        "impact": sanitize_text(impact),
        "fix_plan": sanitize_text(fix_plan),
        "owner": owner,
        "expected_gain": sanitize_text(expected_gain),
    }


def _source_snapshot() -> dict[str, Any]:
    output_dir = get_user_output_dir()
    report_txt = output_dir / "reports" / "full_system_report_latest.txt"
    report_json = output_dir / "reports" / "full_system_report_latest.json"
    api_smoke = output_dir / "diagnostics" / "all_api_smoke.json"
    performance = _first_existing(
        [
            output_dir / "performance" / "api_performance_report.json",
            output_dir / "diagnostics" / "api_performance_report.json",
        ]
    )
    active_absence = output_dir / "model_registry" / "active_absence_diagnostics.json"
    promotion = _latest_file(["model_registry/promotion_report*.json", "model_registry/*promotion*.json", "promotion*.json"])
    research_backtest = _latest_file(["research_backtests/**/metrics_*.json", "research_backtests/**/metrics*.json"])
    return {
        "output_dir": str(output_dir),
        "report_txt_path": str(report_txt),
        "report_json_path": str(report_json),
        "api_smoke_path": str(api_smoke),
        "performance_path": str(performance) if performance else "",
        "active_absence_path": str(active_absence),
        "promotion_path": str(promotion) if promotion else "",
        "research_backtest_metrics_path": str(research_backtest) if research_backtest else "",
        "report_txt": _read_text(report_txt),
        "report_json": _read_json(report_json),
        "api_smoke": _read_json(api_smoke),
        "performance": _read_json(performance) if performance else {},
        "active_absence_file": _read_json(active_absence),
        "promotion": _read_json(promotion) if promotion else {},
        "research_backtest": _read_json(research_backtest) if research_backtest else {},
    }


def _active_absence(snapshot: Mapping[str, Any]) -> dict[str, Any]:
    report = _as_dict(snapshot.get("report_json"))
    embedded = _as_dict(report.get("active_absence"))
    active_file = _as_dict(snapshot.get("active_absence_file"))
    merged = dict(embedded or active_file)
    if active_file:
        merged.update({key: value for key, value in active_file.items() if key not in merged or merged.get(key) in (None, "", [], {})})
    if not merged:
        text = str(snapshot.get("report_txt") or "").lower()
        if "active status: none" in text or "active_status: none" in text or "no active model" in text:
            merged["active_status"] = "none"
    return merged


def _active_missing(active: Mapping[str, Any], report_text: str) -> bool:
    status = str(active.get("active_status") or active.get("status") or "").strip().lower()
    text = report_text.lower()
    return status in {"none", "missing", "not_found", "no_active", "inactive"} or "active status: none" in text or "active_status: none" in text or "no active model" in text


def _root_cause_evidence(active: Mapping[str, Any], *categories: str) -> list[str]:
    wanted = {category.lower() for category in categories}
    rows = []
    for item in _as_list(active.get("root_causes")):
        if not isinstance(item, Mapping):
            continue
        category = str(item.get("category") or "").lower()
        if not wanted or category in wanted:
            rows.append(_join([item.get("category"), item.get("severity"), item.get("evidence"), item.get("fix_plan")]))
    return rows


def _missing_factor_groups(active: Mapping[str, Any], report: Mapping[str, Any], report_text: str) -> list[str]:
    metrics = _as_dict(active.get("blocking_metrics"))
    raw = metrics.get("missing_factor_groups") or active.get("missing_factor_groups") or report.get("missing_factor_groups")
    groups = [str(item) for item in _as_list(raw) if str(item).strip()]
    if groups:
        return sorted(set(groups))
    match = re.search(r"missing(?:/low)?(?: coverage)? groups?:\s*([A-Za-z0-9_,\-\s]+)", report_text, re.IGNORECASE)
    if not match:
        return []
    extracted = [item.strip() for item in re.split(r"[, ]+", match.group(1)) if item.strip()]
    return sorted(set(extracted))


def _metric_failures(active: Mapping[str, Any], backtest: Mapping[str, Any]) -> list[str]:
    metrics = _as_dict(active.get("blocking_metrics"))
    failures: list[str] = []
    for key, value in metrics.items():
        if _bool_failed(value):
            failures.append(_metric_evidence(str(key), value))
    pbo = _as_dict(backtest.get("probability_of_backtest_overfitting")).get("pbo")
    if pbo is not None:
        try:
            pbo_value = float(pbo)
        except Exception:
            pbo_value = None
        if pbo_value is None or pbo_value > 0.2:
            failures.append(f"research_backtest_pbo={_as_text(pbo)}")
    worst_fold = backtest.get("worst_fold_accuracy")
    if worst_fold is not None:
        try:
            worst_fold_value = float(worst_fold)
        except Exception:
            worst_fold_value = None
        if worst_fold_value is None or worst_fold_value < 0.52:
            failures.append(f"research_backtest_worst_fold_accuracy={_as_text(worst_fold)}")
    return failures


def _data_consistency_evidence(report: Mapping[str, Any]) -> list[str]:
    rows: list[str] = []
    data_consistency = _as_dict(report.get("data_consistency"))
    status = str(data_consistency.get("status") or "").lower()
    if status and status not in {"success", "consistent", "ok", "pass"}:
        rows.append(f"data_consistency.status={status}")
    for reason in _as_list(data_consistency.get("blocking_reasons")):
        rows.append(f"blocking_reason={reason}")
    watermark = _as_dict(report.get("watermark"))
    missing_watermarks = [
        key
        for key in (
            "cross_market_updated_at",
            "news_updated_at",
            "feature_store_updated_at",
            "training_dataset_updated_at",
            "candidate_updated_at",
        )
        if key in watermark and not watermark.get(key)
    ]
    if missing_watermarks:
        rows.append(f"missing_watermarks={', '.join(missing_watermarks)}")
    sample = _as_dict(report.get("sample_boundary"))
    sample_flags = [key for key, value in sample.items() if "sample" in str(key).lower() and value is True]
    if sample_flags:
        rows.append(f"sample_flags={', '.join(sample_flags)}")
    return rows


def _api_smoke_failures(snapshot: Mapping[str, Any]) -> list[str]:
    report = _as_dict(snapshot.get("report_json"))
    api = _as_dict(snapshot.get("api_smoke")) or _as_dict(report.get("api_smoke"))
    failed_count = api.get("failed_count")
    failures = _as_list(api.get("failures") or api.get("failed") or api.get("errors"))
    try:
        count = int(failed_count)
    except Exception:
        count = len(failures)
    if count <= 0 and not failures:
        return []
    return [f"failed_count={count}", *_as_list(failures)]


def _performance_failures(snapshot: Mapping[str, Any]) -> list[str]:
    report = _as_dict(snapshot.get("report_json"))
    performance = _as_dict(snapshot.get("performance")) or _as_dict(report.get("api_performance"))
    failures: list[str] = []
    endpoints = performance.get("endpoints") or performance.get("results") or performance.get("rows")
    for item in _as_list(endpoints):
        if isinstance(item, Mapping) and _bool_failed(item):
            failures.append(_metric_evidence(str(item.get("path") or item.get("endpoint") or "endpoint"), item))
    if _bool_failed(performance):
        failures.append(_metric_evidence("api_performance", performance))
    return failures


def _security_evidence(report: Mapping[str, Any]) -> tuple[list[str], list[str]]:
    security = _as_dict(report.get("security"))
    p0_rows: list[str] = []
    p2_rows: list[str] = []
    if security.get("complete_key_leakage") is True:
        p0_rows.append("complete_key_leakage=true")
    secret_scan = _as_dict(security.get("secret_scan_result"))
    status = str(secret_scan.get("status") or "").lower()
    if status in {"not_run", "missing", ""}:
        p2_rows.append(f"secret_scan.status={status or 'missing'}")
    return p0_rows, p2_rows


def _task_failures(report: Mapping[str, Any]) -> list[str]:
    recent = report.get("recent_tasks")
    tasks = _as_list(_as_dict(recent).get("tasks")) if isinstance(recent, Mapping) else _as_list(recent)
    failures = []
    for task in tasks:
        if isinstance(task, Mapping) and str(task.get("status") or "").lower() in {"failed", "error"}:
            failures.append(_join([task.get("kind") or task.get("task"), task.get("error_message_zh") or task.get("message_zh")]))
    return failures


def _process_evidence(report: Mapping[str, Any]) -> list[str]:
    process = _as_dict(report.get("process"))
    if process.get("pid_file_exists") is True and process.get("pid_running") is False:
        return ["pid_file_exists=true while pid_running=false"]
    return []


def _build_issues(snapshot: Mapping[str, Any]) -> list[dict[str, str]]:
    report = _as_dict(snapshot.get("report_json"))
    report_text = str(snapshot.get("report_txt") or "")
    active = _active_absence(snapshot)
    issues: list[dict[str, str]] = []

    if _active_missing(active, report_text):
        evidence = _join(
            [
                f"active_status={active.get('active_status') or 'none'}",
                *_root_cause_evidence(active),
            ]
        )
        issues.append(
            _issue(
                "MODEL-001",
                "P0",
                "model",
                "No active model is available",
                evidence,
                "Prediction delivery stays blocked; the system must remain research-only.",
                "Keep active publishing disabled and fix the promotion blockers before any release acceptance for prediction use.",
                "model",
                "Restores a clear path from research validation to a compliant active candidate.",
            )
        )

    missing_groups = _missing_factor_groups(active, report, report_text)
    if missing_groups:
        issues.append(
            _issue(
                "DATA-001",
                "P0",
                "data",
                "Critical data coverage gaps block model promotion",
                _join([f"missing_factor_groups={', '.join(missing_groups)}", *_root_cause_evidence(active, "data_coverage")]),
                "Institutional factors are under-covered, so validation cannot distinguish real edge from technical-only artifacts.",
                "Backfill basis, inventory, LME/cross-market, term-structure, and event-source coverage with real configured providers.",
                "data",
                "Improves feature breadth and reduces false promotion attempts caused by missing factor groups.",
            )
        )

    metric_failures = _metric_failures(active, _as_dict(snapshot.get("research_backtest")))
    if metric_failures:
        overfit_roots = _root_cause_evidence(active, "overfitting", "validation", "feature_stability", "cost")
        priority = "P0" if any("pbo" in row.lower() and "1.0" in row for row in metric_failures + overfit_roots) else "P1"
        issues.append(
            _issue(
                "MODEL-002",
                priority,
                "model",
                "Model stability gates are not passing",
                _join([*metric_failures, *overfit_roots]),
                "High overfitting risk or failed fold stability means active promotion would be misleading.",
                "Diagnose PBO, worst_fold, DSR, Reality Check, feature stability, and cost-stress failures before changing strategy gates.",
                "model",
                "Raises institutional validation credibility before any candidate can be promoted.",
            )
        )

    consistency = _data_consistency_evidence(report)
    if consistency:
        issues.append(
            _issue(
                "DATA-002",
                "P1",
                "data",
                "Data freshness or sample-data boundary needs cleanup",
                _join(consistency),
                "Research diagnostics may mix stale, missing, or sample-derived artifacts if the lineage is not explicit.",
                "Refresh real data artifacts, remove sample flags from research outputs, and rerun the consistency audit.",
                "data",
                "Improves trust in factor coverage, backtest interpretation, and downstream diagnostics.",
            )
        )

    smoke_failures = _api_smoke_failures(snapshot)
    if smoke_failures:
        issues.append(
            _issue(
                "FRONTEND-001",
                "P1",
                "frontend",
                "Terminal API smoke has failing endpoints",
                _join(smoke_failures),
                "Front-end pages can regress to error or empty states if contract endpoints are unstable.",
                "Fix failing endpoint contracts and add E2E mocks for slow or empty responses.",
                "frontend",
                "Reduces page-level E2E failures and improves diagnostics reliability.",
            )
        )

    perf_failures = _performance_failures(snapshot)
    if perf_failures:
        issues.append(
            _issue(
                "PERF-001",
                "P1",
                "performance",
                "API performance budget has regressions",
                _join(perf_failures),
                "Slow terminal endpoints make lazy-loaded pages and Playwright waits less reliable.",
                "Cache heavy reads, avoid synchronous refresh work, and keep summary/snapshot endpoints within budget.",
                "frontend",
                "Stabilizes the terminal shell and shortens E2E runtime.",
            )
        )

    security_p0, security_p2 = _security_evidence(report)
    if security_p0:
        issues.append(
            _issue(
                "SECURITY-001",
                "P0",
                "security",
                "Complete provider key leakage was detected",
                _join(security_p0),
                "Private research builds cannot be accepted while full keys are exposed.",
                "Stop release work, rotate affected keys, and update masking before rerunning quality gates.",
                "release",
                "Restores release privacy compliance.",
            )
        )
    if security_p2:
        issues.append(
            _issue(
                "SECURITY-002",
                "P2",
                "security",
                "Runtime secret scan is not current",
                _join(security_p2),
                "The latest repair plan lacks fresh runtime privacy evidence even if no leak is currently reported.",
                "Run the existing runtime secret scan and include its sanitized result in the next full system report.",
                "release",
                "Improves release evidence completeness without changing model behavior.",
            )
        )

    task_failures = _task_failures(report)
    if task_failures:
        issues.append(
            _issue(
                "TASK-001",
                "P2",
                "release",
                "Recent background tasks include failures",
                _join(task_failures),
                "Failed tasks can leave stale diagnostics or partial artifacts behind.",
                "Inspect recent task logs and rerun only safe read/diagnostic jobs after fixes.",
                "release",
                "Keeps repair evidence reproducible.",
            )
        )

    process_rows = _process_evidence(report)
    if process_rows:
        issues.append(
            _issue(
                "RELEASE-001",
                "P2",
                "release",
                "Process lifecycle evidence is stale",
                _join(process_rows),
                "A stale PID marker can confuse smoke tests and operator troubleshooting.",
                "Clear stale runtime metadata during normal shutdown and rerun process-status smoke.",
                "release",
                "Reduces false alarms in install-after smoke and diagnostics.",
            )
        )

    seen: set[str] = set()
    unique: list[dict[str, str]] = []
    priority_order = {"P0": 0, "P1": 1, "P2": 2}
    for item in sorted(issues, key=lambda issue: (priority_order.get(issue["priority"], 9), issue["id"])):
        if item["id"] in seen:
            continue
        seen.add(item["id"])
        unique.append(item)
    return unique


def _overall_status(issues: list[Mapping[str, str]]) -> str:
    priorities = {issue.get("priority") for issue in issues}
    if "P0" in priorities:
        return "blocked_for_prediction"
    if "P1" in priorities:
        return "degraded"
    return "research_ready"


def _next_prompts(issues: list[Mapping[str, str]]) -> list[str]:
    categories = {str(issue.get("category") or "") for issue in issues}
    prompts = []
    if "data" in categories:
        prompts.append("Run a TDD data-coverage repair pass for basis, inventory, LME/cross-market, term-structure, and news/event inputs without training or publishing active.")
    if "model" in categories:
        prompts.append("Run a TDD model-stability diagnostics pass for PBO, worst_fold, DSR, Reality Check, feature stability, and cost stress without changing model strategy gates.")
    if "frontend" in categories or "performance" in categories:
        prompts.append("Run a TDD frontend/API stability pass for slow or empty diagnostic endpoints and E2E wait conditions.")
    if "security" in categories or "release" in categories:
        prompts.append("Refresh privacy, runtime process, and release evidence using existing smoke scripts without building an installer or publishing active.")
    if not prompts:
        prompts.append("Keep the next pass limited to evidence refresh and release acceptance; do not train, publish active, or generate customer predictions.")
    return prompts


def _render_markdown(plan: Mapping[str, Any]) -> str:
    issues = [issue for issue in _as_list(plan.get("issues")) if isinstance(issue, Mapping)]
    lines = [
        "# SNInsightTerminal System Repair Plan",
        "",
        f"- generated_at: {plan.get('generated_at')}",
        f"- overall_status: {plan.get('overall_status')}",
        f"- active_updated: {str(plan.get('active_updated')).lower()}",
        f"- customer_prediction_generated: {str(plan.get('customer_prediction_generated')).lower()}",
        "",
        "## Summary",
        f"- P0: {sum(1 for issue in issues if issue.get('priority') == 'P0')}",
        f"- P1: {sum(1 for issue in issues if issue.get('priority') == 'P1')}",
        f"- P2: {sum(1 for issue in issues if issue.get('priority') == 'P2')}",
        "",
    ]
    for priority in ("P0", "P1", "P2"):
        rows = [issue for issue in issues if issue.get("priority") == priority]
        lines.extend([f"## {priority}", ""])
        if not rows:
            lines.extend(["- No issues recorded.", ""])
            continue
        for issue in rows:
            lines.extend(
                [
                    f"### {issue.get('id')} - {issue.get('title')}",
                    f"- category: {issue.get('category')}",
                    f"- owner: {issue.get('owner')}",
                    f"- evidence: {issue.get('evidence')}",
                    f"- impact: {issue.get('impact')}",
                    f"- fix_plan: {issue.get('fix_plan')}",
                    f"- expected_gain: {issue.get('expected_gain')}",
                    "",
                ]
            )
    lines.extend(["## Next Prompt Suggestions", ""])
    for item in _as_list(plan.get("next_prompts")):
        lines.append(f"- {sanitize_text(item)}")
    lines.append("")
    return "\n".join(lines)


def _mutation_files_present() -> list[str]:
    output_dir = get_user_output_dir()
    return [str(output_dir.joinpath(*parts)) for parts in PREDICTION_MUTATION_PATHS if output_dir.joinpath(*parts).exists()]


def build_system_repair_plan() -> dict[str, Any]:
    """Build a read-only repair triage plan from existing diagnostic artifacts.

    This service intentionally avoids refresh, training, model promotion, and prediction generation.
    """

    snapshot = _source_snapshot()
    issues = _build_issues(snapshot)
    diagnostics_dir = _diagnostics_dir()
    json_path = diagnostics_dir / PLAN_JSON_NAME
    md_path = diagnostics_dir / PLAN_MD_NAME
    report = _as_dict(snapshot.get("report_json"))
    active = _active_absence(snapshot)
    plan: dict[str, Any] = {
        "status": "success",
        "generated_at": _now(),
        "overall_status": _overall_status(issues),
        "issues": issues,
        "summary": {
            "p0_count": sum(1 for issue in issues if issue["priority"] == "P0"),
            "p1_count": sum(1 for issue in issues if issue["priority"] == "P1"),
            "p2_count": sum(1 for issue in issues if issue["priority"] == "P2"),
            "active_status": active.get("active_status") or "unknown",
            "current_data_mode": _as_dict(report.get("watermark")).get("current_data_mode") or "unknown",
            "api_smoke_failed_count": (_as_dict(snapshot.get("api_smoke")) or _as_dict(report.get("api_smoke"))).get("failed_count", 0),
        },
        "source_files": {
            "full_system_report_txt": snapshot.get("report_txt_path"),
            "full_system_report_json": snapshot.get("report_json_path"),
            "all_api_smoke": snapshot.get("api_smoke_path"),
            "api_performance_report": snapshot.get("performance_path"),
            "active_absence_diagnostics": snapshot.get("active_absence_path"),
            "promotion_report": snapshot.get("promotion_path"),
            "research_backtest_metrics": snapshot.get("research_backtest_metrics_path"),
        },
        "next_prompts": _next_prompts(issues),
        "json_path": str(json_path),
        "markdown_path": str(md_path),
        "active_updated": False,
        "customer_prediction_generated": False,
        "mutation_files_present": _mutation_files_present(),
    }
    plan["markdown"] = _render_markdown(plan)
    _write_json(json_path, plan)
    md_path.write_text(sanitize_text(str(plan["markdown"])), encoding="utf-8")
    return sanitize_for_json(sanitize_mapping(plan))


def get_latest_system_repair_plan() -> dict[str, Any]:
    diagnostics_dir = _diagnostics_dir()
    json_path = diagnostics_dir / PLAN_JSON_NAME
    md_path = diagnostics_dir / PLAN_MD_NAME
    if not json_path.exists():
        return {
            "status": "missing",
            "issues": [],
            "overall_status": "degraded",
            "json_path": str(json_path),
            "markdown_path": str(md_path),
            "message_zh": "尚未生成系统修复计划。",
            "active_updated": False,
            "customer_prediction_generated": False,
        }
    plan = _read_json(json_path)
    plan.setdefault("status", "success")
    plan.setdefault("json_path", str(json_path))
    plan.setdefault("markdown_path", str(md_path))
    plan.setdefault("issues", [])
    plan.setdefault("active_updated", False)
    plan.setdefault("customer_prediction_generated", False)
    if md_path.exists():
        plan["markdown"] = _read_text(md_path)
    return sanitize_for_json(sanitize_mapping(plan))
