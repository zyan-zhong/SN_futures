import json
import sys

sys.path.insert(0, "src")

from sn_futures.services.institutional_validation_service import run_institutional_validation


def test_cost_2x_pressure_blocks_eligibility(tmp_path, monkeypatch):
    monkeypatch.setenv("SN_DATA_DIR", str(tmp_path))
    exp_id = "research-20990102-000000-cost"
    exp_dir = tmp_path / "outputs" / "model_research" / "experiments" / exp_id
    exp_dir.mkdir(parents=True)
    folds = [
        {
            "fold": idx,
            "horizon": "1d",
            "validation_samples": 100,
            "directional_accuracy": 0.52,
            "calibration_error": 0.05,
            "threshold_optimization": {
                "by_coverage": {
                    "top_20pct": {
                        "expectancy_at_coverage": 0.00005,
                        "sample_count": 25,
                        "coverage": 0.2,
                    }
                }
            },
            "feature_importance": {"roc_5": 0.1},
        }
        for idx in range(1, 5)
    ]
    (exp_dir / "experiment_summary.json").write_text(json.dumps({"experiment_id": exp_id, "created_at": "2099-01-02T00:00:00"}), encoding="utf-8")
    (exp_dir / "walk_forward_results.json").write_text(json.dumps({"horizons": {"1d": {"folds": folds}}}), encoding="utf-8")

    report = run_institutional_validation()

    assert report["cost_stress"]["2x_cost"]["expectancy"] < 0
    assert "2x 成本压力下期望为负" in report["promotion_eligibility"]["failure_reasons"]
