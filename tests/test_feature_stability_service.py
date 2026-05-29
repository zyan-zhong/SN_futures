import sys

sys.path.insert(0, "src")

from sn_futures.services.feature_stability_service import build_feature_stability_report


def test_feature_stability_outputs_blacklist_and_shap_status():
    report = build_feature_stability_report(
        [
            {"fold": 1, "feature_importance": {"roc_5": 0.1, "noise_feature": 0.001}},
            {"fold": 2, "feature_importance": {"roc_5": 0.11, "noise_feature": 0.3}},
            {"fold": 3, "feature_importance": {"roc_5": 0.09}},
        ],
        feature_cols=["roc_5", "noise_feature", "missing_feature"],
        missing_rate_by_feature={"missing_feature": 0.9},
    )

    assert report["feature_stability"]
    assert "missing_feature" in report["high_missing_feature_removal"]
    assert "missing_feature" in report["unstable_feature_blacklist"]
    assert report["shap_status"] == "optional_not_required"
