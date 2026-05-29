import sys

sys.path.insert(0, "src")

from sn_futures.api.terminal_api import handle_terminal_api


def test_validation_report_api_is_available_without_running_check():
    status, payload = handle_terminal_api("/api/terminal/validation/report", "GET", {}, None)

    assert status == 200
    assert "status" in payload
    assert payload.get("active_updated") is not True


def test_validation_stress_api_is_available():
    status, payload = handle_terminal_api("/api/terminal/validation/stress-tests", "GET", {}, None)

    assert status == 200
    assert "cost_stress" in payload
    assert "regime_stress" in payload


def test_terminal_docs_include_institutional_validation_api():
    status, payload = handle_terminal_api("/api/terminal/docs", "GET", {}, None)
    paths = {item.get("path") for item in payload.get("endpoints", [])}

    assert status == 200
    assert "/api/terminal/validation/run-institutional-check" in paths
    assert "/api/terminal/validation/report" in paths
    assert "/api/terminal/validation/stress-tests" in paths
