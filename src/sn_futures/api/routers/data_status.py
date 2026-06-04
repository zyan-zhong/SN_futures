from __future__ import annotations

from ..router_registry import RouterRegistry
from ...services.api_response_cache import cached_call
from ...services.terminal_service import build_terminal_data_status


def register_routes(registry: RouterRegistry) -> None:
    registry.route(
        "GET",
        "/api/terminal/data-status",
        lambda request: cached_call("terminal:data-status", 10, build_terminal_data_status),
    )
