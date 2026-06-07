from __future__ import annotations

from ..router_registry import RouterRegistry
from ...services.research_backtest_engine_service import get_auditable_research_backtest_view


def register_routes(registry: RouterRegistry) -> None:
    registry.route(
        "GET",
        "/api/terminal/backtest/auditable",
        lambda request: get_auditable_research_backtest_view(
            run_id=request.query_value("run_id", "") or None,
            input_id=request.query_value("input_id", "sn_main") or "sn_main",
        ),
    )
