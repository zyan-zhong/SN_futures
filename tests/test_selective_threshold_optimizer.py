import sys

sys.path.insert(0, "src")

from sn_futures.services.selective_threshold_optimizer import optimize_selective_thresholds


def test_threshold_optimizer_reports_coverage_and_does_not_train_on_test_set():
    result = optimize_selective_thresholds(
        calibrated_prob=[0.9, 0.8, 0.55, 0.45, 0.2, 0.1],
        expected_return=[0.02, 0.01, 0.001, -0.001, -0.01, -0.02],
        realized_return=[0.02, -0.01, 0.001, -0.001, 0.01, -0.02],
        realized_direction=[1, -1, 1, -1, 1, -1],
        cost=0.0002,
    )

    assert result["uses_test_for_training"] is False
    assert result["fit_scope"] == "validation_only"
    assert "top_20pct" in result["by_coverage"]
    assert result["by_coverage"]["top_20pct"]["sample_count"] >= 1
    assert "accuracy_at_coverage" in result
    assert "expected_coverage" in result
