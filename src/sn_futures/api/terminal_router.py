from __future__ import annotations

from typing import Any, Mapping

from .router_registry import RouterRegistry
from .routers import backtest, data_status, events, features, market, models, reports, settings, tasks


def build_terminal_router(api_docs: Mapping[str, Any] | None = None) -> RouterRegistry:
    registry = RouterRegistry()
    if api_docs is not None:
        registry.route("GET", "/api/terminal/docs", lambda request: dict(api_docs))

    market.register_routes(registry)
    data_status.register_routes(registry)
    events.register_routes(registry)
    features.register_routes(registry)
    models.register_routes(registry)
    backtest.register_routes(registry)
    reports.register_routes(registry)
    settings.register_routes(registry)
    tasks.register_routes(registry)
    return registry
