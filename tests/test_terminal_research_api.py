import sys

sys.path.insert(0, "src")

from sn_futures.api.terminal_api import TERMINAL_API_DOCS, handle_terminal_api


def test_research_api_docs_are_registered():
    paths = {item["path"] for item in TERMINAL_API_DOCS["endpoints"]}
    assert "/api/terminal/research/run-model-experiment" in paths
    assert "/api/terminal/research/experiments" in paths
    assert "/api/terminal/research/experiment-detail" in paths
    assert "/api/terminal/research/threshold-optimization" in paths


def test_research_api_does_not_publish_active_when_dataset_missing(tmp_path, monkeypatch):
    monkeypatch.setenv("SN_DATA_DIR", str(tmp_path))

    status, payload = handle_terminal_api("/api/terminal/research/run-model-experiment", "POST", body={})

    assert status == 200
    assert payload["active_updated"] is False
    assert payload["customer_prediction_generated"] is False
    assert payload["promotion_gate_lowered"] is False
    assert not (tmp_path / "outputs" / "model_registry" / "active_model.json").exists()
