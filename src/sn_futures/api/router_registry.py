from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Callable, Mapping

from .json_utils import safe_json_dumps, sanitize_for_json


RouteHandler = Callable[["RouterRequest"], Any]


class InvalidJsonError(Exception):
    status_code = 400

    def __init__(self, message: str = "Request body is not valid JSON.") -> None:
        super().__init__(message)
        self.payload = {
            "error": "invalid_json",
            "message": message,
            "message_zh": "request body is not valid JSON",
        }


@dataclass(frozen=True)
class RouterRequest:
    method: str
    path: str
    query: Mapping[str, list[str]]
    body: Any = None

    def query_value(self, key: str, default: str = "") -> str:
        values = self.query.get(key)
        if not values:
            return default
        return str(values[0])

    def json_body(self) -> dict[str, Any]:
        body = self.body
        if body is None or body == "":
            return {}
        if isinstance(body, dict):
            return body
        if isinstance(body, (bytes, bytearray)):
            body = body.decode("utf-8", errors="replace")
        if isinstance(body, str):
            try:
                parsed = json.loads(body) if body.strip() else {}
            except Exception as exc:
                raise InvalidJsonError() from exc
            if not isinstance(parsed, dict):
                raise InvalidJsonError("Request body must be a JSON object.")
            return parsed
        raise InvalidJsonError("Request body format is not supported.")


class RouterRegistry:
    def __init__(self) -> None:
        self._routes: dict[tuple[str, str], RouteHandler] = {}
        self._paths: set[str] = set()

    def route(self, method: str, path: str, handler: RouteHandler) -> None:
        normalized_method = str(method or "").upper()
        normalized_path = str(path or "")
        self._routes[(normalized_method, normalized_path)] = handler
        self._paths.add(normalized_path)

    def path_registered(self, path: str) -> bool:
        return str(path or "") in self._paths

    def dispatch(
        self,
        method: str,
        path: str,
        query: Mapping[str, list[str]] | None = None,
        body: Any = None,
    ) -> tuple[int, dict[str, Any]]:
        normalized_method = str(method or "").upper()
        normalized_path = str(path or "")
        handler = self._routes.get((normalized_method, normalized_path))
        if handler is None:
            if normalized_path in self._paths:
                return 405, {
                    "error": "method_not_allowed",
                    "message": "Method is not allowed for this terminal API route.",
                    "path": normalized_path,
                    "method": normalized_method,
                }
            return 404, {
                "error": "not_found",
                "message": "Unknown terminal API route.",
                "path": normalized_path,
            }

        request = RouterRequest(
            method=normalized_method,
            path=normalized_path,
            query=query or {},
            body=body,
        )
        try:
            result = handler(request)
        except InvalidJsonError as exc:
            return exc.status_code, sanitize_for_json(exc.payload)
        except Exception:
            return 500, {
                "error": "handler_failed",
                "message": "Terminal API handler failed.",
                "path": normalized_path,
            }

        status, payload = self._normalize_result(result)
        try:
            safe_json_dumps(payload)
        except Exception:
            return 500, {
                "error": "handler_not_json_serializable",
                "message": "Terminal API handler output must be JSON serializable.",
                "path": normalized_path,
            }
        return status, sanitize_for_json(payload)

    @staticmethod
    def _normalize_result(result: Any) -> tuple[int, dict[str, Any]]:
        if isinstance(result, tuple) and len(result) == 2:
            status_raw, payload = result
            status = int(status_raw)
        else:
            status = 200
            payload = result
        if payload is None:
            payload = {}
        if not isinstance(payload, dict):
            payload = {"data": payload}
        return status, payload
