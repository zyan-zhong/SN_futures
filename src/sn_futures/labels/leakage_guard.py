from __future__ import annotations

from collections.abc import Iterable
from datetime import timedelta
from typing import Any

import pandas as pd


LABEL_PREFIXES = (
    "ret_",
    "direction_",
    "abs_ret_",
    "realized_vol_",
    "max_favorable_excursion_",
    "max_adverse_excursion_",
    "tb_",
    "meta_",
)


def infer_label_columns(columns: Iterable[str]) -> list[str]:
    return [str(col) for col in columns if str(col).startswith(LABEL_PREFIXES)]


def check_feature_label_leakage(
    feature_columns: Iterable[str],
    label_columns: Iterable[str] | None = None,
) -> dict[str, Any]:
    features = [str(col) for col in feature_columns]
    labels = set(str(col) for col in (label_columns or infer_label_columns(features)))
    leaked = sorted(set(features).intersection(labels))
    return {
        "ok": not leaked,
        "leaked_columns": leaked,
        "message": "特征列未包含标签列。" if not leaked else "特征列包含未来标签列，存在泄露风险。",
    }


def check_label_timestamps(
    feature_timestamps: Iterable[Any],
    label_timestamps: Iterable[Any],
) -> dict[str, Any]:
    feature_ts = pd.to_datetime(pd.Series(list(feature_timestamps)), errors="coerce")
    label_ts = pd.to_datetime(pd.Series(list(label_timestamps)), errors="coerce")
    comparable = feature_ts.notna() & label_ts.notna()
    invalid = comparable & (label_ts <= feature_ts)
    return {
        "ok": not bool(invalid.any()),
        "invalid_count": int(invalid.sum()),
        "message": "标签时间均晚于特征时间。" if not bool(invalid.any()) else "存在标签时间不晚于特征时间的样本。",
    }


def check_train_test_label_window_overlap(
    *,
    train_end: Any,
    test_start: Any,
    max_horizon_days: int,
) -> dict[str, Any]:
    train_end_ts = pd.Timestamp(train_end)
    test_start_ts = pd.Timestamp(test_start)
    label_window_end = train_end_ts + timedelta(days=int(max_horizon_days))
    ok = label_window_end < test_start_ts
    return {
        "ok": bool(ok),
        "train_label_window_end": label_window_end.isoformat(),
        "test_start": test_start_ts.isoformat(),
        "message": "训练标签窗口与测试集无重叠。" if ok else "训练标签窗口与测试集重叠，存在泄露风险。",
    }

