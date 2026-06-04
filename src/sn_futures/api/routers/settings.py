from __future__ import annotations

from typing import Any

from ..router_registry import RouterRegistry, RouterRequest
from ...services.settings_service import (
    get_terminal_settings_status,
    reset_terminal_secrets,
    save_terminal_secrets,
)


def register_routes(registry: RouterRegistry) -> None:
    registry.route("GET", "/api/terminal/settings/status", lambda request: get_terminal_settings_status())
    registry.route("POST", "/api/terminal/settings/reset", lambda request: reset_terminal_secrets())
    registry.route("POST", "/api/terminal/settings/secrets", _save_secrets)


def _save_secrets(request: RouterRequest) -> tuple[int, dict[str, Any]] | dict[str, Any]:
    try:
        return save_terminal_secrets(request.json_body())
    except ValueError as exc:
        return 400, {"error": "invalid_secret", "message": str(exc)}
