import json
import sys

sys.path.insert(0, "src")

from sn_futures.services.model_research_service import (
    get_model_experiment_detail,
    list_model_experiments,
    run_model_experiment,
)


def test_model_research_experiment_without_dataset_does_not_publish_active(tmp_path, monkeypatch):
    monkeypatch.setenv("SN_DATA_DIR", str(tmp_path))

    result = run_model_experiment({"model_family": "sklearn_hist_gradient"})

    assert result["status"] == "failed"
    assert result["active_updated"] is False
    assert result["customer_prediction_generated"] is False
    assert result["promotion_gate_lowered"] is False
    assert not (tmp_path / "outputs" / "model_registry" / "active_model.json").exists()


def test_model_research_experiments_do_not_overwrite_old_runs(tmp_path, monkeypatch):
    monkeypatch.setenv("SN_DATA_DIR", str(tmp_path))

    first = run_model_experiment({"label_variant": "direction_thresholded"})
    second = run_model_experiment({"label_variant": "direction_raw"})
    listing = list_model_experiments()

    assert first["experiment_id"] != second["experiment_id"]
    assert listing["count"] >= 2
    assert (tmp_path / "outputs" / "model_research" / "experiments" / first["experiment_id"] / "config.json").exists()
    assert (tmp_path / "outputs" / "model_research" / "experiments" / second["experiment_id"] / "config.json").exists()


def test_model_research_detail_reads_artifacts(tmp_path, monkeypatch):
    monkeypatch.setenv("SN_DATA_DIR", str(tmp_path))
    result = run_model_experiment({"model_family": "extra_trees"})
    detail = get_model_experiment_detail(result["experiment_id"])

    assert detail["experiment_id"] == result["experiment_id"]
    assert detail["experiment_summary"]["active_updated"] is False
    config_path = tmp_path / "outputs" / "model_research" / "experiments" / result["experiment_id"] / "config.json"
    assert json.loads(config_path.read_text(encoding="utf-8"))["model_family"] == "extra_trees"
