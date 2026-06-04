from __future__ import annotations

from sn_futures.api_server import V2ApiHandler


class _DisconnectingWriter:
    def write(self, _body: bytes) -> None:
        raise ConnectionAbortedError("client disconnected")


class _DummyHandler(V2ApiHandler):
    wfile = _DisconnectingWriter()

    def __init__(self) -> None:
        self.status: int | None = None
        self.headers: list[tuple[str, str]] = []

    def send_response(self, status: int) -> None:
        self.status = status

    def send_header(self, key: str, value: str) -> None:
        self.headers.append((key, value))

    def end_headers(self) -> None:
        return None


def test_api_response_send_ignores_client_disconnect() -> None:
    handler = _DummyHandler()

    V2ApiHandler._send(handler, 200, {"status": "ok"})

    assert handler.status == 200
    assert ("Content-Type", "application/json; charset=utf-8") in handler.headers
