from __future__ import annotations

from ..router_registry import RouterRegistry
from ...services.research_backtest_engine_service import get_auditable_research_backtest_view, reject_display_payload_backtest_input


_FORBIDDEN_INPUT_SOURCES = {"display_payload", "chart_payload", "ui_chart_payload", "terminal_chart_payload"}


def _auditable_backtest(request):
    input_source = request.query_value("input_source", "").strip().lower()
    if input_source in _FORBIDDEN_INPUT_SOURCES:
        return 400, reject_display_payload_backtest_input(input_source=input_source)
    return get_auditable_research_backtest_view(
        run_id=request.query_value("run_id", "") or None,
        input_id=request.query_value("input_id", "sn_main") or "sn_main",
    )


def register_routes(registry: RouterRegistry) -> None:
    registry.route(
        "GET",
        "/api/terminal/backtest/auditable",
        _auditable_backtest,
    )
