from __future__ import annotations

import warnings

import numpy as np
import pandas as pd

from sn_futures.services.feature_coverage_service import _merge_fundamental_rows


def test_merge_fundamental_rows_skips_non_numeric_columns_without_future_warning() -> None:
    frame = pd.DataFrame({"status": [np.nan, np.nan]}, index=pd.to_datetime(["2024-01-01", "2024-01-02"]))
    rows = [
        {"trade_date": "2024-01-01", "status": None, "fee_rate": "0.001"},
        {"trade_date": "2024-01-02", "status": None, "fee_rate": "0.002"},
    ]

    with warnings.catch_warnings():
        warnings.simplefilter("error", FutureWarning)
        _merge_fundamental_rows(frame, rows)

    assert frame["status"].isna().all()
    assert frame["fee_rate"].tolist() == [0.001, 0.002]
