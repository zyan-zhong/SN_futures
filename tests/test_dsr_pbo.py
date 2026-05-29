import sys

sys.path.insert(0, "src")

from sn_futures.services.institutional_validation_service import (
    deflated_sharpe_ratio,
    probability_of_backtest_overfitting,
    white_reality_check,
)


def test_deflated_sharpe_ratio_is_computable():
    result = deflated_sharpe_ratio([0.01, 0.02, -0.005, 0.015, 0.003], trials=5)

    assert result["sample_count"] == 5
    assert "deflated_sharpe_ratio" in result
    assert "selection_penalty" in result


def test_pbo_lightweight_estimate_is_computable():
    result = probability_of_backtest_overfitting(
        {
            "strategy_a": [0.01, 0.02, -0.01, 0.03],
            "strategy_b": [0.02, -0.03, 0.01, -0.02],
            "strategy_c": [-0.01, 0.01, 0.02, 0.00],
        }
    )

    assert 0.0 <= result["pbo"] <= 1.0
    assert result["strategy_count"] == 3


def test_white_reality_check_lightweight_alias():
    result = white_reality_check([0.01, 0.02, 0.01, -0.005, 0.03], bootstrap_samples=50)

    assert result["method"] == "white_reality_check_lightweight_bootstrap"
    assert 0.0 <= result["p_value"] <= 1.0
