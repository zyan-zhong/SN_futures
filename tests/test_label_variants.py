import pandas as pd
import sys

sys.path.insert(0, "src")

from sn_futures.services.label_variants import add_label_variants


def test_low_return_thresholded_label_becomes_no_trade():
    frame = pd.DataFrame(
        {
            "y_return": [0.00001, 0.00003, 0.002, -0.003],
            "y_direction": [1, 1, 1, -1],
        }
    )

    labelled, report = add_label_variants(frame, cost=0.0002, noise_quantile=0.5)

    assert labelled.loc[0, "direction_thresholded"] == 0
    assert labelled.loc[1, "direction_thresholded"] == 0
    assert labelled.loc[2, "direction_thresholded"] == 1
    assert labelled.loc[3, "direction_thresholded"] == -1
    assert "direction_thresholded" in report["label_distribution"]
    assert report["message_zh"]
