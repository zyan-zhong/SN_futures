import sys

sys.path.insert(0, "src")

from sn_futures.services.selective_threshold_optimizer import build_calibration_bins


def test_calibration_bins_report_brier_and_ece():
    report = build_calibration_bins(
        y_true=[1, 1, 0, 0, 1, 0],
        prob=[0.9, 0.7, 0.4, 0.2, 0.6, 0.3],
        bins=5,
    )

    assert report["sample_count"] == 6
    assert len(report["bins"]) == 5
    assert report["ece"] is not None
    assert report["brier_score"] is not None
    assert any(row.get("sample_count", 0) > 0 for row in report["bins"])
