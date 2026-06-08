from __future__ import annotations

import json
import os
import tempfile
from unittest.mock import patch

import pytest

from sn_futures.api.terminal_api import handle_terminal_api


EMPTY_PROVIDER_ENV = {
    "SN_ALPHA_VANTAGE_KEY": "",
    "SN_NEWSAPI_KEY": "",
    "SN_TUSHARE_TOKEN": "",
    "SN_LOCAL_API_PROVIDER_ENABLED": "0",
    "SN_LOCAL_API_PROVIDER_TOKEN": "",
    "SN_LOCAL_API_PROVIDER_BASE_URL": "",
    "SN_MANAGED_PROXY_TOKEN": "",
    "SN_MANAGED_DATA_PROXY_TOKEN": "",
}


@pytest.fixture()
def no_key_runtime():
    with tempfile.TemporaryDirectory() as tmp:
        with patch.dict(os.environ, {**EMPTY_PROVIDER_ENV, "SN_DATA_DIR": tmp, "SN_INSIGHT_DATA_DIR": tmp}, clear=False):
            yield tmp


def test_predictions_no_key_payload_is_blocked_empty(no_key_runtime: str) -> None:
    status, payload = handle_terminal_api("/api/terminal/predictions", "GET", {}, None)

    assert status == 200
    assert payload["status"] == "blocked"
    assert payload["predictions"] == []
    assert payload.get("cards") == {}
    assert payload["baseline_used"] is False
    assert payload["sample_data_used"] is False
    assert payload["customer_prediction_generated"] is False
    assert payload["blocking_reasons"]

    text = json.dumps(payload, ensure_ascii=False)
    assert '"sample": true' not in text
    assert '"sample_mode": true' not in text
    assert '"baseline_used": true' not in text


def test_data_status_exposes_local_first_setup_summary(no_key_runtime: str) -> None:
    status, payload = handle_terminal_api("/api/terminal/data-status", "GET", {}, None)

    assert status == 200
    summary = payload.get("local_setup_summary")
    assert summary == {
        "alpha_vantage_configured": False,
        "newsapi_configured": False,
        "tushare_configured": False,
        "local_api_provider_configured": False,
    }
    assert payload.get("local_first_next_actions")
    assert "provider_setup_matrix" in payload


def test_snapshot_exposes_local_first_summary_without_real_sample_chart_claim(no_key_runtime: str) -> None:
    status, payload = handle_terminal_api("/api/terminal/snapshot", "GET", {}, None)

    assert status == 200
    data_status = payload.get("data_status") or {}
    local_setup_summary = payload.get("local_setup_summary") or data_status.get("local_setup_summary") or {}
    sample_price_history_used_as_real = payload.get("sample_price_history_used_as_real", data_status.get("sample_price_history_used_as_real"))
    assert local_setup_summary.get("local_api_provider_configured") is False
    assert sample_price_history_used_as_real is False

    summary = payload.get("summary") or {}
    assert summary.get("sample_mode") is True
    assert summary.get("sample_price_history_used_as_real") is False
