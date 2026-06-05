from __future__ import annotations

import unittest

from sn_futures.api.router_registry import InvalidJsonError, RouterRegistry, RouterRequest
from sn_futures.api.terminal_api import handle_terminal_api


class TerminalRouterRegistryTest(unittest.TestCase):
    def test_registry_dispatches_registered_route(self) -> None:
        registry = RouterRegistry()
        registry.route("GET", "/api/terminal/example", lambda request: {"ok": True, "path": request.path})

        status, payload = registry.dispatch("GET", "/api/terminal/example", {"q": ["1"]}, None)

        self.assertEqual(status, 200)
        self.assertEqual(payload, {"ok": True, "path": "/api/terminal/example"})

    def test_unknown_path_and_method_errors_are_uniform(self) -> None:
        registry = RouterRegistry()
        registry.route("GET", "/api/terminal/example", lambda request: {"ok": True})

        missing_status, missing = registry.dispatch("GET", "/api/terminal/missing", {}, None)
        method_status, method = registry.dispatch("POST", "/api/terminal/example", {}, None)

        self.assertEqual(missing_status, 404)
        self.assertEqual(missing["error"], "not_found")
        self.assertEqual(method_status, 405)
        self.assertEqual(method["error"], "method_not_allowed")

    def test_invalid_json_returns_400(self) -> None:
        registry = RouterRegistry()

        def handler(request: RouterRequest) -> dict[str, object]:
            return {"body": request.json_body()}

        registry.route("POST", "/api/terminal/example", handler)

        status, payload = registry.dispatch("POST", "/api/terminal/example", {}, "{bad")

        self.assertEqual(status, 400)
        self.assertEqual(payload["error"], "invalid_json")
        self.assertIsInstance(payload["message"], str)

    def test_handler_payload_must_be_json_serializable(self) -> None:
        registry = RouterRegistry()
        payload: dict[str, object] = {}
        payload["self"] = payload
        registry.route("GET", "/api/terminal/bad", lambda request: payload)

        status, response = registry.dispatch("GET", "/api/terminal/bad", {}, None)

        self.assertEqual(status, 500)
        self.assertEqual(response["error"], "handler_not_json_serializable")

    def test_parse_json_error_is_structured(self) -> None:
        error = InvalidJsonError("{bad")

        self.assertEqual(error.status_code, 400)
        self.assertEqual(error.payload["error"], "invalid_json")

    def test_low_risk_terminal_endpoints_still_serve_via_handle_terminal_api(self) -> None:
        for path in (
            "/api/terminal/docs",
            "/api/terminal/summary",
            "/api/terminal/data-status",
            "/api/terminal/settings/status",
            "/api/terminal/tasks/status",
        ):
            status, payload = handle_terminal_api(path, "GET", {}, None)
            self.assertEqual(status, 200, path)
            self.assertIsInstance(payload, dict, path)

    def test_terminal_router_keeps_invalid_json_400_for_migrated_post(self) -> None:
        status, payload = handle_terminal_api("/api/terminal/settings/secrets", "POST", {}, "{bad")

        self.assertEqual(status, 400)
        self.assertEqual(payload["error"], "invalid_json")


if __name__ == "__main__":
    unittest.main()
