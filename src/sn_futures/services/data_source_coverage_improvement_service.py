from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping

from ..api.json_utils import safe_json_dumps, sanitize_for_json
from ..runtime import get_user_output_dir
from ..utils.secret_sanitizer import sanitize_mapping, sanitize_text
from .feature_coverage_service import build_feature_coverage_report
from .feature_store_v5_service import build_feature_store_v5
from .managed_data_proxy_service import managed_proxy_status, refresh_managed_data_proxy
from .online_cross_market_service import refresh_online_cross_market_data
from .refresh_service import refresh_event_store, refresh_news_data
from .news_relevance_service import refresh_news_relevance
from .provider_status_canonical_service import build_canonical_provider_status
from .tushare_futures_service import refresh_tushare_futures_data


REPORT_JSON_NAME = "data_source_coverage_improvement.json"
REPORT_MD_NAME = "data_source_coverage_improvement.md"
FORBIDDEN_MODEL_OUTPUTS = (
    ("model_registry", "active_model.json"),
    ("models", "active_model.json"),
    ("sn_live_predictions.json",),
    ("customer_predictions.json",),
    ("sn_unified_forecast.json",),
)


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _diagnostics_dir() -> Path:
    path = get_user_output_dir() / "diagnostics"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    clean = sanitize_for_json(sanitize_mapping(payload))
    safe_json_dumps(clean)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(clean, ensure_ascii=False, indent=2), encoding="utf-8")


def _status_of(payload: Mapping[str, Any] | None, fallback: str = "unknown") -> str:
    if not isinstance(payload, Mapping):
        return fallback
    return str(payload.get("status") or payload.get("error_code") or fallback)


def _group_rates(report: Mapping[str, Any] | None) -> dict[str, float]:
    groups = report.get("groups") if isinstance(report, Mapping) else []
    if not isinstance(groups, list):
        return {}
    rates: dict[str, float] = {}
    for group in groups:
        if not isinstance(group, Mapping):
            continue
        name = str(group.get("group") or "")
        if not name:
            continue
        try:
            rates[name] = float(group.get("coverage_rate") or 0.0)
        except Exception:
            rates[name] = 0.0
    return rates


def _coverage_delta(before: Mapping[str, Any], after: Mapping[str, Any]) -> dict[str, dict[str, float]]:
    before_rates = _group_rates(before)
    after_rates = _group_rates(after)
    out: dict[str, dict[str, float]] = {}
    for group in sorted(set(before_rates) | set(after_rates)):
        before_value = before_rates.get(group, 0.0)
        after_value = after_rates.get(group, 0.0)
        out[group] = {
            "before": round(before_value, 6),
            "after": round(after_value, 6),
            "delta": round(after_value - before_value, 6),
        }
    return out


def _as_float(value: Any) -> float:
    try:
        return float(value or 0.0)
    except Exception:
        return 0.0


def _as_int(value: Any) -> int:
    try:
        return int(value or 0)
    except Exception:
        return 0


def _compact_coverage(report: Mapping[str, Any]) -> dict[str, Any]:
    groups = report.get("groups") if isinstance(report.get("groups"), list) else []
    compact_groups: list[dict[str, Any]] = []
    for group in groups:
        if not isinstance(group, Mapping):
            continue
        compact_groups.append(
            {
                "group": str(group.get("group") or ""),
                "feature_count": _as_int(group.get("feature_count")),
                "available_feature_count": _as_int(group.get("available_feature_count")),
                "partial_feature_count": _as_int(group.get("partial_feature_count")),
                "missing_feature_count": _as_int(group.get("missing_feature_count")),
                "coverage_rate": round(_as_float(group.get("coverage_rate")), 6),
            }
        )
    return {
        "generated_at": report.get("generated_at"),
        "sample_count": _as_int(report.get("sample_count")),
        "date_start": report.get("date_start"),
        "date_end": report.get("date_end"),
        "groups": compact_groups,
        "usable_feature_cols": list(report.get("usable_feature_cols") or []),
        "partial_feature_cols": list(report.get("partial_feature_cols") or []),
        "not_usable_feature_cols": list(report.get("not_usable_feature_cols") or []),
        "blocking_missing_fields": list(report.get("blocking_missing_fields") or []),
        "training_readiness": report.get("training_readiness") or {},
        "warnings": list(report.get("warnings") or []),
        "data_quality_score": report.get("data_quality_score"),
        "cross_market_diagnostics": report.get("cross_market_diagnostics") or {},
    }


def _compact_diagnostics(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        return {}
    out: dict[str, Any] = {}
    for key in (
        "status",
        "success",
        "configured",
        "enabled",
        "from_cache",
        "row_count",
        "field_count",
        "stale",
        "cache_hit",
        "cooldown_until",
        "missing_fields",
        "blocking_reasons",
        "usable_fields",
    ):
        if key in payload:
            out[key] = payload.get(key)
    return out


def _compact_feature_store(manifest: Mapping[str, Any]) -> dict[str, Any]:
    date_range = manifest.get("date_range") if isinstance(manifest.get("date_range"), Mapping) else {}
    return {
        "version": manifest.get("version"),
        "status": manifest.get("status"),
        "generated_at": manifest.get("generated_at"),
        "row_count": _as_int(manifest.get("row_count")),
        "date_start": manifest.get("date_start") or date_range.get("start"),
        "date_end": manifest.get("date_end") or date_range.get("end"),
        "feature_store_path": manifest.get("feature_store_path"),
        "manifest_path": manifest.get("manifest_path"),
        "usable_fields": list(manifest.get("usable_fields") or []),
        "excluded_fields": list(manifest.get("excluded_fields") or []),
        "group_coverage": manifest.get("group_coverage") or {},
        "source_quality": manifest.get("source_quality") or {},
        "cross_market_diagnostics": _compact_diagnostics(manifest.get("cross_market_diagnostics")),
        "event_factor_diagnostics": _compact_diagnostics(manifest.get("event_factor_diagnostics")),
        "no_lookahead_pass": bool(manifest.get("no_lookahead_pass")),
        "leakage_check_pass": bool(manifest.get("leakage_check_pass")),
        "mock_data_used": bool(manifest.get("mock_data_used")),
        "sample_data_used": bool(manifest.get("sample_data_used")),
        "baseline_used": bool(manifest.get("baseline_used")),
        "customer_prediction_generated": bool(manifest.get("customer_prediction_generated")),
        "active_model_written": bool(manifest.get("active_model_written")),
    }


def _candidate_v6_readiness(coverage: Mapping[str, Any], feature_store: Mapping[str, Any]) -> dict[str, Any]:
    rates = _group_rates(coverage)
    required_groups = ("basis", "inventory", "cross_market", "event")
    missing = [group for group in required_groups if rates.get(group, 0.0) < 0.7]
    coverage_ready = bool((coverage.get("training_readiness") or {}).get("can_train_full_fundamental_model")) if isinstance(coverage.get("training_readiness"), Mapping) else False
    leakage_ok = bool(feature_store.get("leakage_check_pass"))
    no_mock_or_sample = not bool(feature_store.get("sample_data_used") or feature_store.get("mock_data_used") or feature_store.get("baseline_used"))
    ready = bool(coverage_ready and leakage_ok and no_mock_or_sample and not missing)
    return {
        "ready": ready,
        "candidate_version": "v6",
        "missing_or_low_groups": missing,
        "coverage_ready": coverage_ready,
        "feature_store_leakage_check_pass": leakage_ok,
        "no_mock_sample_or_baseline": no_mock_or_sample,
        "reason": "candidate_v6 data gate is ready; no training was run." if ready else "candidate_v6 data gate is not ready; this run only refreshed data coverage.",
        "reason_zh": "具备 candidate_v6 训练前置数据条件；本轮未训练。" if ready else "暂不具备 candidate_v6 训练前置数据条件；本轮只做数据覆盖修复。",
    }


def _mutation_files_present() -> list[str]:
    output_dir = get_user_output_dir()
    return [str(output_dir.joinpath(*parts)) for parts in FORBIDDEN_MODEL_OUTPUTS if output_dir.joinpath(*parts).exists()]


def _render_markdown(report: Mapping[str, Any]) -> str:
    source_status = report.get("source_status") if isinstance(report.get("source_status"), Mapping) else {}
    lines = [
        "# SNInsightTerminal Data Source Coverage Improvement",
        "",
        f"- generated_at: {report.get('generated_at')}",
        f"- status: {report.get('status')}",
        f"- training_invoked: {str(report.get('training_invoked')).lower()}",
        f"- active_updated: {str(report.get('active_updated')).lower()}",
        f"- customer_prediction_generated: {str(report.get('customer_prediction_generated')).lower()}",
        "",
        "## Source Status",
    ]
    for name in ("tushare", "managed_proxy", "alpha", "newsapi"):
        payload = source_status.get(name) if isinstance(source_status, Mapping) else {}
        if not isinstance(payload, Mapping):
            payload = {}
        lines.append(f"- {name}: {payload.get('status', 'unknown')} / rows={payload.get('row_count', 0)} / cache={str(payload.get('from_cache', False)).lower()}")
    lines.extend(["", "## Feature Coverage Delta"])
    delta = report.get("feature_coverage_delta") if isinstance(report.get("feature_coverage_delta"), Mapping) else {}
    for group, payload in delta.items():
        if isinstance(payload, Mapping):
            lines.append(f"- {group}: {payload.get('before')} -> {payload.get('after')} ({payload.get('delta')})")
    readiness = report.get("candidate_v6_readiness") if isinstance(report.get("candidate_v6_readiness"), Mapping) else {}
    lines.extend(["", "## Candidate V6 Readiness", f"- ready: {str(readiness.get('ready', False)).lower()}", f"- reason: {readiness.get('reason') or readiness.get('reason_zh', '')}", ""])
    return "\n".join(lines)


def improve_real_data_source_coverage(
    *,
    force: bool = False,
    tushare_client: Any | None = None,
    managed_client: Any | None = None,
    alpha_provider: Any | None = None,
    news_provider: Any | None = None,
) -> dict[str, Any]:
    """Refresh real data sources and rebuild coverage artifacts without training or publishing."""

    before = build_feature_coverage_report(report_version="before_data_source_improvement")
    tushare = refresh_tushare_futures_data(client=tushare_client, force=force)
    managed = refresh_managed_data_proxy(force=force, client=managed_client)
    if not isinstance(managed, Mapping):
        managed = managed_proxy_status()
    alpha = refresh_online_cross_market_data(provider=alpha_provider, force=force)
    news = refresh_news_data(force=force, provider=news_provider)
    if _status_of(news) in {"success", "using_cache", "skipped"}:
        try:
            refresh_news_relevance()
            refresh_event_store()
        except Exception:
            pass
    after = build_feature_coverage_report(report_version="after_data_source_improvement")
    feature_store = build_feature_store_v5()
    before_compact = _compact_coverage(before)
    after_compact = _compact_coverage(after)
    feature_store_compact = _compact_feature_store(feature_store)
    news_status = _status_of(news, "skipped")
    canonical = build_canonical_provider_status()
    canonical_providers = canonical.get("providers") if isinstance(canonical, Mapping) else {}
    canonical_providers = canonical_providers if isinstance(canonical_providers, Mapping) else {}

    def canonical_or_local(canonical_id: str, local: Mapping[str, Any]) -> dict[str, Any]:
        row = canonical_providers.get(canonical_id)
        if isinstance(row, Mapping):
            return {
                "status": str(row.get("status") or _status_of(local)),
                "success": str(row.get("status") or "") == "success",
                "configured": bool(row.get("configured")),
                "enabled": bool(row.get("enabled")),
                "row_count": int(row.get("row_count") or 0),
                "from_cache": bool(row.get("from_cache")),
                "last_attempt_time": str(row.get("last_attempt_time") or ""),
                "last_success_time": str(row.get("last_success_time") or ""),
                "status_time": str(row.get("status_time") or ""),
                "data_time": str(row.get("data_time") or ""),
                "report_time": str(row.get("report_time") or ""),
                "source_file": str(row.get("source_file") or ""),
                "message_zh": str(row.get("message_zh") or ""),
            }
        return dict(local)

    diagnostics_dir = _diagnostics_dir()
    json_path = diagnostics_dir / REPORT_JSON_NAME
    md_path = diagnostics_dir / REPORT_MD_NAME
    report: dict[str, Any] = {
        "status": "success",
        "generated_at": _now(),
        "source_status": {
            "tushare": canonical_or_local("tushare", {
                "status": _status_of(tushare),
                "success": bool(tushare.get("success")) if isinstance(tushare, Mapping) else False,
                "configured": bool(tushare.get("configured")) if isinstance(tushare, Mapping) else False,
                "row_count": int(tushare.get("row_count") or 0) if isinstance(tushare, Mapping) else 0,
                "from_cache": bool(tushare.get("from_cache")) if isinstance(tushare, Mapping) else False,
                "message_zh": str(tushare.get("message_zh") or "") if isinstance(tushare, Mapping) else "",
            }),
            "managed_proxy": canonical_or_local("managed_proxy", {
                "status": _status_of(managed),
                "success": bool(managed.get("success")) if isinstance(managed, Mapping) else False,
                "enabled": bool(managed.get("enabled")) if isinstance(managed, Mapping) else False,
                "configured": bool(managed.get("configured")) if isinstance(managed, Mapping) else False,
                "row_count": int(managed.get("row_count") or 0) if isinstance(managed, Mapping) else 0,
                "from_cache": bool(managed.get("from_cache")) if isinstance(managed, Mapping) else False,
                "message_zh": str(managed.get("message_zh") or "") if isinstance(managed, Mapping) else "",
            }),
            "alpha": canonical_or_local("alpha_vantage", {
                "status": _status_of(alpha),
                "success": bool(alpha.get("success")) if isinstance(alpha, Mapping) else False,
                "configured": bool(alpha.get("configured")) if isinstance(alpha, Mapping) else False,
                "row_count": int(alpha.get("row_count") or 0) if isinstance(alpha, Mapping) else 0,
                "from_cache": bool(alpha.get("from_cache")) if isinstance(alpha, Mapping) else False,
                "cooldown_until": str(alpha.get("cooldown_until") or "") if isinstance(alpha, Mapping) else "",
                "message_zh": str(alpha.get("message_zh") or "") if isinstance(alpha, Mapping) else "",
            }),
            "newsapi": canonical_or_local("newsapi", {
                "status": news_status,
                "success": (bool(news.get("success")) or news_status in {"success", "using_cache"}) if isinstance(news, Mapping) else False,
                "configured": (bool(news.get("configured")) or news_status in {"success", "using_cache"}) if isinstance(news, Mapping) else False,
                "row_count": int(news.get("row_count") or news.get("inserted_count") or 0) if isinstance(news, Mapping) else 0,
                "from_cache": bool(news.get("from_cache")) if isinstance(news, Mapping) else False,
                "message_zh": str(news.get("message_zh") or "") if isinstance(news, Mapping) else "",
            }),
        },
        "provider_status_canonical": canonical,
        "feature_coverage_before": before_compact,
        "feature_coverage_after": after_compact,
        "feature_coverage_delta": _coverage_delta(before_compact, after_compact),
        "feature_store_v5": feature_store_compact,
        "candidate_v6_readiness": _candidate_v6_readiness(after_compact, feature_store_compact),
        "json_path": str(json_path),
        "markdown_path": str(md_path),
        "training_invoked": False,
        "active_updated": False,
        "customer_prediction_generated": False,
        "mutation_files_present": _mutation_files_present(),
    }
    report["markdown"] = _render_markdown(report)
    _write_json(json_path, report)
    md_path.write_text(sanitize_text(str(report["markdown"])), encoding="utf-8")
    return sanitize_for_json(sanitize_mapping(report))
