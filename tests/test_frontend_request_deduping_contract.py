from __future__ import annotations

from pathlib import Path


def test_api_client_has_timeout_and_request_deduping() -> None:
    client = Path("frontend/src/api/client.ts").read_text(encoding="utf-8")

    assert "AbortController" in client
    assert "DEFAULT_TIMEOUT_MS" in client
    assert "REQUEST_DEDUPE" in client
    assert "promise.finally(() => REQUEST_DEDUPE.delete(key))" in client
    assert "请求超时" in client
    assert "璇锋眰瓒呮椂" not in client


def test_terminal_client_uses_explicit_snapshot_lite_endpoint() -> None:
    terminal = Path("frontend/src/api/terminal.ts").read_text(encoding="utf-8")
    hook = Path("frontend/src/hooks/useTerminalSnapshot.ts").read_text(encoding="utf-8")

    assert "getTerminalSnapshotLite" in terminal
    assert '"/api/terminal/snapshot-lite"' in terminal
    assert "getTerminalSnapshotLite" in hook
