import sys
import time

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
    final = _wait_for_task(str(payload["task_id"]))

    assert status == 200
    assert payload["kind"] == "train_candidate"
    result = final.get("result", {})
    assert result.get("active_updated", False) is False
    assert result.get("customer_prediction_generated", False) is False
    assert result.get("promotion_gate_lowered", False) is False
    assert not (tmp_path / "outputs" / "model_registry" / "active_model.json").exists()


def _wait_for_task(task_id: str) -> dict:
    for _ in range(80):
        _, payload = handle_terminal_api("/api/terminal/tasks/status", "GET", query={"id": [task_id]})
        if payload.get("status") in {"success", "failed"}:
            time.sleep(0.05)
            return payload
        time.sleep(0.025)
    return {}
