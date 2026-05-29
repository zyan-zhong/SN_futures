from __future__ import annotations

import json
import sys

sys.path.insert(0, "src")

from sn_futures.api.terminal_api import handle_terminal_api


def test_oof_integrity_apis_are_documented() -> None:
    status, docs = handle_terminal_api("/api/terminal/docs", "GET", {}, None)
    paths = {item.get("path") for item in docs.get("endpoints", [])}

    assert status == 200
    assert "/api/terminal/models/oof-integrity-report" in paths
    assert "/api/terminal/models/high-confidence-report" in paths


def test_oof_integrity_report_api_is_safe_and_research_only() -> None:
    status, payload = handle_terminal_api("/api/terminal/models/oof-integrity-report", "GET", {}, None)
    text = json.dumps(payload, ensure_ascii=False)

    assert status == 200
    assert "horizons" in payload
    assert payload.get("active_updated") is False
    assert payload.get("customer_prediction_generated") is False
    assert "active_model.json" not in text


def test_high_confidence_report_api_is_not_customer_prediction() -> None:
    status, payload = handle_terminal_api(
        "/api/terminal/models/high-confidence-report",
        "GET",
        {"horizon": ["1d"]},
        None,
    )

    assert status == 200
    assert payload.get("horizon") == "1d"
    assert payload.get("customer_prediction_generated") is False
    assert "客户预测" in json.dumps(payload, ensure_ascii=False) or "瀹㈡埛" in json.dumps(payload, ensure_ascii=False)
