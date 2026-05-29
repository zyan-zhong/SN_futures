import json
import sys
from pathlib import Path

sys.path.insert(0, "src")

from sn_futures.services.institutional_validation_service import run_institutional_validation


def _write_experiment(root: Path, expectancies: list[float]) -> str:
    exp_id = "research-20990101-000000-testcase"
    exp_dir = root / "outputs" / "model_research" / "experiments" / exp_id
    exp_dir.mkdir(parents=True, exist_ok=True)
    folds = []
    for idx, exp in enumerate(expectancies, start=1):
        folds.append(
            {
                "fold": idx,
                "horizon": "1d",
                "validation_samples": 100,
                "directional_accuracy": 0.55 if exp > 0 else 0.45,
                "calibration_error": 0.05,
                "threshold_optimization": {
                    "by_coverage": {
                        "top_20pct": {
                            "expectancy_at_coverage": exp,
                            "sample_count": 30,
                            "coverage": 0.2,
                            "accuracy_at_coverage": 0.6 if exp > 0 else 0.4,
                        }
                    }
                },
                "feature_importance": {"roc_5": 0.1 + idx * 0.01, "atr_14": 0.05},
            }
        )
    summary = {
        "experiment_id": exp_id,
        "status": "success",
        "created_at": "2099-01-01T00:00:00",
        "active_updated": False,
    }
    walk = {"experiment_id": exp_id, "horizons": {"1d": {"folds": folds}}}
    (exp_dir / "experiment_summary.json").write_text(json.dumps(summary), encoding="utf-8")
    (exp_dir / "walk_forward_results.json").write_text(json.dumps(walk), encoding="utf-8")
    return exp_id


def test_institutional_validation_does_not_generate_active(tmp_path, monkeypatch):
    monkeypatch.setenv("SN_DATA_DIR", str(tmp_path))
    _write_experiment(tmp_path, [0.01, -0.02, 0.005, -0.01])

    report = run_institutional_validation()

    assert report["active_updated"] is False
    assert report["promotion_gate_lowered"] is False
    assert report["customer_prediction_generated"] is False
    assert not (tmp_path / "outputs" / "model_registry" / "active_model.json").exists()
    assert "deflated_sharpe_ratio" in report
    assert "probability_of_backtest_overfitting" in report
    assert "reality_check" in report


def test_single_fold_dominance_rejects_candidate(tmp_path, monkeypatch):
    monkeypatch.setenv("SN_DATA_DIR", str(tmp_path))
    _write_experiment(tmp_path, [1.0, 0.01, 0.01, 0.01])

    report = run_institutional_validation()

    assert report["promotion_eligibility"]["eligible"] is False
    assert report["dominance_checks"]["single_fold_dominates"] is True
