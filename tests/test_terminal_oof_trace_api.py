import json
import sys

sys.path.insert(0, "src")

from sn_futures.api.terminal_api import handle_terminal_api


def test_oof_trace_apis_are_documented_and_safe():
    status, docs = handle_terminal_api("/api/terminal/docs", "GET", {}, None)
    paths = {item.get("path") for item in docs.get("endpoints", [])}

    assert status == 200
    assert "/api/terminal/models/oof-trace-summary" in paths
    assert "/api/terminal/models/oof-trace-sample" in paths
    assert "/api/terminal/research/oof-trace-summary" in paths


def test_oof_trace_summary_and_sample_are_graceful_without_trace():
    status, summary = handle_terminal_api("/api/terminal/models/oof-trace-summary", "GET", {"horizon": ["1d"]}, None)
    assert status == 200
    assert "客户预测" in json.dumps(summary, ensure_ascii=False) or summary.get("customer_prediction_generated") is False

    status, sample = handle_terminal_api("/api/terminal/models/oof-trace-sample", "GET", {"horizon": ["1d"], "limit": ["10"]}, None)
    assert status == 200
    assert "rows" in sample
