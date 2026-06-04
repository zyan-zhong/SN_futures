from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping

from ..api.json_utils import safe_json_dumps, sanitize_for_json
from ..runtime import get_user_output_dir
from ..utils.secret_sanitizer import sanitize_mapping, sanitize_text
from .candidate_v6_gated_research_service import FACTOR_GROUP_FIELDS
from .feature_coverage_service import build_feature_coverage_report
from .feature_store_service import get_feature_store_status
from .feature_store_v5_service import build_feature_store_v5, build_feature_store_v6
from .managed_data_proxy_service import managed_proxy_status, refresh_managed_data_proxy
from .provider_status_canonical_service import build_canonical_provider_status
from .tushare_futures_service import refresh_tushare_futures_data


REPORT_JSON_NAME = "real_data_coverage_validation.json"
REPORT_MD_NAME = "real_data_coverage_validation.md"
READINESS_JSON_NAME = "candidate_v6_readiness.json"
V6_GROUPS = ("raw_market", "basis", "inventory", "cross_market", "term_structure", "event")
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


def _read_json(path: Path) -> Any:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _parse_time(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text)
    except Exception:
        return None


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


def _group_rates(report: Mapping[str, Any] | None) -> dict[str, float]:
    groups = report.get("groups") if isinstance(report, Mapping) else []
    if not isinstance(groups, list):
        return {}
    rates: dict[str, float] = {}
    for group in groups:
        if isinstance(group, Mapping) and group.get("group"):
            rates[str(group.get("group"))] = _as_float(group.get("coverage_rate"))
    return rates


def _coverage_delta(before: Mapping[str, Any], after: Mapping[str, Any]) -> dict[str, dict[str, float]]:
    before_rates = _group_rates(before)
    after_rates = _group_rates(after)
    delta: dict[str, dict[str, float]] = {}
    for group in sorted(set(before_rates) | set(after_rates)):
        before_value = before_rates.get(group, 0.0)
        after_value = after_rates.get(group, 0.0)
        delta[group] = {
            "before": round(before_value, 6),
            "after": round(after_value, 6),
            "delta": round(after_value - before_value, 6),
        }
    return delta


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
    }


def _compact_feature_store(manifest: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "version": manifest.get("version"),
        "status": manifest.get("status"),
        "generated_at": manifest.get("generated_at"),
        "row_count": _as_int(manifest.get("row_count")),
        "feature_store_path": manifest.get("feature_store_path"),
        "manifest_path": manifest.get("manifest_path"),
        "usable_fields": list(manifest.get("usable_fields") or []),
        "excluded_fields": list(manifest.get("excluded_fields") or []),
        "group_coverage": manifest.get("group_coverage") or {},
        "source_quality": manifest.get("source_quality") or {},
        "tushare_used": bool(manifest.get("tushare_used")),
        "tushare_fields": list(manifest.get("tushare_fields") or []),
        "no_lookahead_pass": bool(manifest.get("no_lookahead_pass")),
        "leakage_check_pass": bool(manifest.get("leakage_check_pass")),
        "mock_data_used": bool(manifest.get("mock_data_used")),
        "sample_data_used": bool(manifest.get("sample_data_used")),
        "baseline_used": bool(manifest.get("baseline_used")),
        "customer_prediction_generated": bool(manifest.get("customer_prediction_generated")),
        "active_model_written": bool(manifest.get("active_model_written")),
    }


def _source_status(provider_id: str, local: Mapping[str, Any] | None, canonical: Mapping[str, Any]) -> dict[str, Any]:
    providers = canonical.get("providers") if isinstance(canonical.get("providers"), Mapping) else {}
    row = providers.get(provider_id) if isinstance(providers, Mapping) else None
    source = row if isinstance(row, Mapping) else local if isinstance(local, Mapping) else {}
    return {
        "status": str(source.get("status") or "unknown"),
        "success": bool(source.get("success")) if "success" in source else str(source.get("status") or "") == "success",
        "configured": bool(source.get("configured")),
        "enabled": bool(source.get("enabled", True)),
        "row_count": _as_int(source.get("row_count")),
        "from_cache": bool(source.get("from_cache") or source.get("cache_used")),
        "last_attempt_time": str(source.get("last_attempt_time") or source.get("status_time") or source.get("generated_at") or ""),
        "last_success_time": str(source.get("last_success_time") or source.get("data_time") or ""),
        "message_zh": str(source.get("message_zh") or source.get("error_message_zh") or ""),
    }


def _real_fields_by_group(usable_fields: list[str]) -> dict[str, list[str]]:
    usable = {str(item) for item in usable_fields}
    return {group: sorted(usable.intersection(FACTOR_GROUP_FIELDS[group])) for group in V6_GROUPS}


def _uses_sample_or_mock(feature_store: Mapping[str, Any]) -> bool:
    if feature_store.get("sample_data_used") or feature_store.get("mock_data_used") or feature_store.get("baseline_used"):
        return True
    source_quality = feature_store.get("source_quality")
    if not isinstance(source_quality, Mapping):
        return False
    return any(
        isinstance(item, Mapping)
        and (item.get("sample_data_used") or item.get("mock_data_used") or item.get("status") in {"sample_data", "mock_data"})
        for item in source_quality.values()
    )


def build_candidate_v6_readiness(
    *,
    coverage_before: Mapping[str, Any] | None = None,
    coverage_after: Mapping[str, Any] | None = None,
    feature_store_v5: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    before = coverage_before or {}
    after = coverage_after or build_feature_coverage_report(report_version="candidate_v6_readiness")
    feature_store = feature_store_v5 or build_feature_store_v6()
    delta = _coverage_delta(_compact_coverage(before), _compact_coverage(after))
    usable_fields = list(feature_store.get("usable_fields") or [])
    fields_by_group = _real_fields_by_group([str(item) for item in usable_fields])
    improved_groups = [
        group
        for group in V6_GROUPS
        if _as_float((delta.get(group) or {}).get("delta")) > 0.0 and fields_by_group.get(group)
    ]
    new_fields = sorted({field for group in improved_groups for field in fields_by_group.get(group, [])})
    blocked: list[str] = []
    if not improved_groups:
        blocked.append("new_real_factor_group_missing")
    if not any(_as_float((delta.get(group) or {}).get("delta")) > 0.0 for group in V6_GROUPS):
        blocked.append("feature_coverage_delta_empty")
    if _uses_sample_or_mock(feature_store):
        blocked.append("sample_or_mock_data_detected")
    if not bool(feature_store.get("no_lookahead_pass")):
        blocked.append("feature_store_no_lookahead_failed")
    ready = not blocked
    payload = {
        "status": "ready" if ready else "blocked",
        "ready": ready,
        "candidate_version": "v6",
        "required_groups": list(V6_GROUPS),
        "new_factor_groups": improved_groups,
        "new_fields": new_fields,
        "missing_fields": sorted({field for group in V6_GROUPS for field in FACTOR_GROUP_FIELDS[group] if field not in usable_fields}),
        "coverage_delta": delta,
        "sample_data_used": bool(feature_store.get("sample_data_used")),
        "mock_data_used": bool(feature_store.get("mock_data_used")),
        "baseline_used": bool(feature_store.get("baseline_used")),
        "no_lookahead_pass": bool(feature_store.get("no_lookahead_pass")),
        "feature_store_leakage_check_pass": bool(feature_store.get("leakage_check_pass")),
        "blocked_reasons": sorted(set(blocked)),
        "next_actions_zh": ["训练 candidate_v6 前先构建 training dataset v6 并检查 leakage。"] if ready else ["补齐至少一个真实新增因子组后再评估 candidate_v6。"],
        "training_invoked": False,
        "active_updated": False,
        "customer_prediction_generated": False,
        "generated_at": _now(),
    }
    path = _diagnostics_dir() / READINESS_JSON_NAME
    _write_json(path, payload)
    payload["json_path"] = str(path)
    return sanitize_for_json(payload)


def get_candidate_v6_readiness() -> dict[str, Any]:
    validation = _read_json(_diagnostics_dir() / REPORT_JSON_NAME)
    current_feature_store = get_feature_store_status(version="v6")
    if not isinstance(current_feature_store, Mapping) or not current_feature_store.get("exists"):
        current_feature_store = get_feature_store_status(version="v5")
    if isinstance(validation, Mapping):
        validation_time = _parse_time(validation.get("generated_at"))
        feature_store_time = _parse_time(current_feature_store.get("generated_at") if isinstance(current_feature_store, Mapping) else None)
        if feature_store_time and (validation_time is None or feature_store_time > validation_time):
            return build_candidate_v6_readiness(
                coverage_before=validation.get("feature_coverage_before") if isinstance(validation.get("feature_coverage_before"), Mapping) else {},
                coverage_after=build_feature_coverage_report(report_version="candidate_v6_readiness_current"),
                feature_store_v5=current_feature_store if isinstance(current_feature_store, Mapping) else {},
            )
        return build_candidate_v6_readiness(
            coverage_before=validation.get("feature_coverage_before") if isinstance(validation.get("feature_coverage_before"), Mapping) else {},
            coverage_after=validation.get("feature_coverage_after") if isinstance(validation.get("feature_coverage_after"), Mapping) else {},
            feature_store_v5=validation.get("feature_store_v5") if isinstance(validation.get("feature_store_v5"), Mapping) else {},
        )
    return build_candidate_v6_readiness(
        coverage_before={},
        coverage_after=build_feature_coverage_report(report_version="candidate_v6_readiness_current"),
        feature_store_v5=current_feature_store,
    )


def _mutation_files_present() -> list[str]:
    output_dir = get_user_output_dir()
    return [str(output_dir.joinpath(*parts)) for parts in FORBIDDEN_MODEL_OUTPUTS if output_dir.joinpath(*parts).exists()]


def _render_markdown(report: Mapping[str, Any]) -> str:
    source_status = report.get("source_status") if isinstance(report.get("source_status"), Mapping) else {}
    readiness = report.get("candidate_v6_readiness") if isinstance(report.get("candidate_v6_readiness"), Mapping) else {}
    lines = [
        "# Real Data Coverage Validation",
        "",
        f"- generated_at: {report.get('generated_at')}",
        f"- status: {report.get('status')}",
        f"- training_invoked: {str(report.get('training_invoked')).lower()}",
        f"- active_updated: {str(report.get('active_updated')).lower()}",
        f"- customer_prediction_generated: {str(report.get('customer_prediction_generated')).lower()}",
        "",
        "## Source Status",
    ]
    for key in ("tushare", "managed_proxy"):
        payload = source_status.get(key) if isinstance(source_status, Mapping) else {}
        payload = payload if isinstance(payload, Mapping) else {}
        lines.append(f"- {key}: {payload.get('status', 'unknown')} / rows={payload.get('row_count', 0)} / cache={str(payload.get('from_cache', False)).lower()}")
    lines.extend(
        [
            "",
            "## Candidate V6 Readiness",
            f"- status: {readiness.get('status', 'blocked')}",
            f"- new_factor_groups: {', '.join(readiness.get('new_factor_groups') or []) or 'none'}",
            f"- new_fields: {', '.join((readiness.get('new_fields') or [])[:20]) or 'none'}",
            f"- blocked_reasons: {', '.join(readiness.get('blocked_reasons') or []) or 'none'}",
            "",
        ]
    )
    return "\n".join(lines)


def build_real_data_coverage_validation(
    *,
    force: bool = False,
    tushare_client: Any | None = None,
    managed_client: Any | None = None,
) -> dict[str, Any]:
    before = build_feature_coverage_report(report_version="before_real_data_validation")
    tushare = refresh_tushare_futures_data(client=tushare_client, force=force)
    managed = refresh_managed_data_proxy(force=force, client=managed_client)
    if not isinstance(managed, Mapping):
        managed = managed_proxy_status()
    feature_store = build_feature_store_v5()
    after = build_feature_coverage_report(report_version="after_real_data_validation")
    before_compact = _compact_coverage(before)
    after_compact = _compact_coverage(after)
    feature_store_compact = _compact_feature_store(feature_store)
    canonical = build_canonical_provider_status()
    readiness = build_candidate_v6_readiness(
        coverage_before=before_compact,
        coverage_after=after_compact,
        feature_store_v5=feature_store_compact,
    )
    diagnostics_dir = _diagnostics_dir()
    json_path = diagnostics_dir / REPORT_JSON_NAME
    md_path = diagnostics_dir / REPORT_MD_NAME
    report: dict[str, Any] = {
        "status": "success",
        "generated_at": _now(),
        "source_status": {
            "tushare": _source_status("tushare", tushare if isinstance(tushare, Mapping) else {}, canonical),
            "managed_proxy": _source_status("managed_proxy", managed if isinstance(managed, Mapping) else {}, canonical),
        },
        "provider_status_canonical": canonical,
        "feature_coverage_before": before_compact,
        "feature_coverage_after": after_compact,
        "feature_coverage_delta": _coverage_delta(before_compact, after_compact),
        "feature_store_v5": feature_store_compact,
        "candidate_v6_readiness": readiness,
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
