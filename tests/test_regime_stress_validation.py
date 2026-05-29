import json
import sys

sys.path.insert(0, "src")

from sn_futures.services.institutional_validation_service import run_institutional_validation


def test_single_regime_dominance_is_reported(tmp_path, monkeypatch):
    monkeypatch.setenv("SN_DATA_DIR", str(tmp_path))
    exp_id = "research-20990103-000000-regime"
    exp_dir = tmp_path / "outputs" / "model_research" / "experiments" / exp_id
    exp_dir.mkdir(parents=True)
    folds = []
    for idx in range(1, 6):
        folds.append(
            {
                "fold": idx,
                "horizon": "20d",
                "validation_samples": 100,
                "directional_accuracy": 0.60,
                "calibration_error": 0.04,
                "threshold_optimization": {"by_coverage": {"top_20pct": {"expectancy_at_coverage": 0.02, "sample_count": 30}}},
                "feature_importance": {"atr_14": 0.2},
            }
        )
    (exp_dir / "experiment_summary.json").write_text(json.dumps({"experiment_id": exp_id, "created_at": "2099-01-03T00:00:00"}), encoding="utf-8")
    (exp_dir / "walk_forward_results.json").write_text(json.dumps({"horizons": {"20d": {"folds": folds}}}), encoding="utf-8")

    report = run_institutional_validation()

    assert "high_volatility" in report["regime_stress"]
    assert report["dominance_checks"]["single_regime_dominates"] is True
    assert "单一 regime 贡献过高" in report["promotion_eligibility"]["failure_reasons"]
