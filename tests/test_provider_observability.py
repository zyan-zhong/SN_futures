from __future__ import annotations

import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from sn_futures.api.terminal_api import handle_terminal_api
from sn_futures.services.refresh_service import run_refresh_steps


def test_refresh_last_error_api_is_accessible(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("SN_DATA_DIR", str(tmp_path))
    monkeypatch.delenv("SN_NEWSAPI_KEY", raising=False)
    run_refresh_steps(["news"])

    status, payload = handle_terminal_api("/api/terminal/refresh/last-error", "GET")
    assert status == 200
    assert "message_zh" in payload
    assert "next_actions_zh" in payload


def test_provider_test_does_not_leak_key(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("SN_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("SN_NEWSAPI_KEY", "TEST_NEWS_SECRET_1234567890")

    status, payload = handle_terminal_api(
        "/api/terminal/providers/test",
        "POST",
        body={"provider": "newsapi"},
    )
    text = str(payload)
    assert status == 200
    assert "TEST_NEWS_SECRET_1234567890" not in text
    assert "message_zh" in payload


def test_failed_refresh_step_has_next_actions(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("SN_DATA_DIR", str(tmp_path))
    monkeypatch.delenv("SN_NEWSAPI_KEY", raising=False)
    result = run_refresh_steps(["news"])
    step = result["steps"][0]
    assert step["status"] == "skipped"
    assert step["next_actions_zh"]
    assert "error_message_zh" in step


def test_provider_status_detail_api_is_accessible(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("SN_DATA_DIR", str(tmp_path))
    status, payload = handle_terminal_api("/api/terminal/providers/status-detail", "GET")
    assert status == 200
    assert payload["success"] is True
    assert "data_status" in payload
