from __future__ import annotations

from pathlib import Path


def test_frontend_api_client_has_timeout_deduping_and_stale_error_contract() -> None:
    client = Path("frontend/src/api/client.ts").read_text(encoding="utf-8")

    assert "AbortController" in client
    assert "DEFAULT_TIMEOUT_MS" in client
    assert "REQUEST_DEDUPE" in client
    assert "timeoutMs" in client
    assert "请求超时" in client
    assert "cache_hit" not in client.lower() or "sanitizeRecord" in client


def test_terminal_api_exports_timeout_aware_helpers() -> None:
    terminal = Path("frontend/src/api/terminal.ts").read_text(encoding="utf-8")

    assert "getTerminalSnapshot" in terminal
    assert "getJson<TerminalSnapshot>" in terminal
    assert "timeoutMs" in terminal
    assert "getTerminalSummary" in terminal
