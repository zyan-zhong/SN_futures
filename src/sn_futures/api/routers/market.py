from __future__ import annotations

from ..router_registry import RouterRegistry
from ...services.api_response_cache import cached_call
from ...services.terminal_service import build_terminal_summary


def register_routes(registry: RouterRegistry) -> None:
    registry.route(
        "GET",
        "/api/terminal/summary",
        lambda request: cached_call("terminal:summary", 5, build_terminal_summary),
    )
