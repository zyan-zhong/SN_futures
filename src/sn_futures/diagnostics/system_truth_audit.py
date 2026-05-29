from __future__ import annotations

from typing import Any, Mapping

from .data_reality_audit import audit_data_reality
from .forecast_path_audit import audit_forecast_paths
from .latency_audit import audit_latency
from .model_independence_audit import audit_model_independence
from .neutral_rate_audit import audit_neutral_rates
from .resource_profile_audit import audit_resource_profile


def run_system_truth_audit(
    *,
    registry_rows: list[dict[str, Any]],
    live_payload: Mapping[str, Any],
    chart_payloads: Mapping[str, Mapping[str, Any]],
    watermark: Mapping[str, Any],
    trading_session: Mapping[str, Any],
    scheduler_state: Mapping[str, Any] | None = None,
    hardware_profile: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    cards = live_payload.get("cards", {}) if isinstance(live_payload.get("cards", {}), Mapping) else {}
    model_independence = audit_model_independence(
        registry_rows=registry_rows,
        live_cards=cards,
        chart_payloads=chart_payloads,
    )
    forecast_path = audit_forecast_paths(chart_payloads)
    data_reality = audit_data_reality(watermark, trading_session)
    latency = audit_latency(data_reality=data_reality, scheduler_state=scheduler_state or {})
    neutral_rate = audit_neutral_rates(cards)
    resource_profile = audit_resource_profile(hardware_profile)
    sections = {
        "model_independence": model_independence,
        "forecast_path": forecast_path,
        "data_reality": data_reality,
        "latency": latency,
        "neutral_rate": neutral_rate,
        "resource_profile": resource_profile,
    }
    critical_failed = [
        name
        for name, section in sections.items()
        if not bool(section.get("ok")) and section.get("severity") == "red"
    ]
    warning_sections = [
        name
        for name, section in sections.items()
        if section.get("severity") in {"yellow", "red"} and name not in critical_failed
    ]
    ok = not critical_failed
    summary = (
        "系统真实性审计通过；可继续作为量化投研参考。"
        if ok
        else "系统真实性审计发现关键风险，当前预测应降级参考。"
    )
    return {
        "ok": ok,
        "status": "passed" if ok else "failed",
        "severity": "normal" if ok and not warning_sections else ("yellow" if ok else "red"),
        "summary": summary,
        "critical_failed": critical_failed,
        "warning_sections": warning_sections,
        "sections": sections,
        "disclaimer": "本审计仅用于模型与数据链路质量控制，不构成任何投资建议。",
    }
