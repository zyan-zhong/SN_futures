from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any, Iterable

import pandas as pd


REQUIRED_FIELDS = ("close", "high", "low", "volume", "open_interest", "main_contract")
IMPORTANT_FIELDS = (
    "shfe_inventory",
    "lme_inventory",
    "spot_premium",
    "basis",
    "usd_cny",
    "lme_tin_close",
    "news_event_score",
)


@dataclass(frozen=True)
class ValidationReport:
    required_fields_missing: list[str]
    important_fields_missing: list[str]
    missing_ratio_by_column: dict[str, float]
    data_quality_score: float
    stale_fields: list[str]
    last_update_time: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _is_missing_value(value: Any) -> bool:
    if value is None:
        return True
    try:
        if isinstance(value, float) and not math.isfinite(value):
            return True
        return bool(pd.isna(value))
    except Exception:
        return False


def _last_update_time(frame: pd.DataFrame, timestamp_col: str | None = None) -> str:
    if frame.empty:
        return ""
    if timestamp_col and timestamp_col in frame.columns:
        values = pd.to_datetime(frame[timestamp_col], errors="coerce").dropna()
    else:
        values = pd.to_datetime(frame.index, errors="coerce").dropna()
    if values.empty:
        return ""
    latest = values.max()
    try:
        return latest.isoformat()
    except Exception:
        return str(latest)


def build_validation_report(
    data: pd.DataFrame | dict[str, Any] | None,
    *,
    required_fields: Iterable[str] = REQUIRED_FIELDS,
    important_fields: Iterable[str] = IMPORTANT_FIELDS,
    timestamp_col: str | None = None,
    stale_after_hours: float | None = None,
    now: datetime | pd.Timestamp | None = None,
) -> ValidationReport:
    required = tuple(required_fields)
    important = tuple(important_fields)
    if data is None:
        missing_required = list(required)
        missing_important = list(important)
        return ValidationReport(missing_required, missing_important, {}, 0.0, [], "")

    if isinstance(data, dict):
        frame = pd.DataFrame([data])
    elif isinstance(data, pd.DataFrame):
        frame = data.copy()
    else:
        frame = pd.DataFrame()

    if frame.empty:
        return ValidationReport(list(required), list(important), {}, 0.0, [], "")

    required_missing = [field for field in required if field not in frame.columns]
    important_missing = [field for field in important if field not in frame.columns]
    ratios: dict[str, float] = {}
    for column in frame.columns:
        series = frame[column]
        try:
            ratios[str(column)] = round(float(series.map(_is_missing_value).mean()), 6)
        except Exception:
            ratios[str(column)] = 1.0

    available_required = [field for field in required if field in frame.columns]
    available_important = [field for field in important if field in frame.columns]
    required_missing_ratio = len(required_missing) / max(len(required), 1)
    important_missing_ratio = len(important_missing) / max(len(important), 1)
    required_value_missing = (
        sum(ratios.get(field, 1.0) for field in available_required) / max(len(available_required), 1)
        if available_required
        else 1.0
    )
    important_value_missing = (
        sum(ratios.get(field, 1.0) for field in available_important) / max(len(available_important), 1)
        if available_important
        else 1.0
    )

    last_update = _last_update_time(frame, timestamp_col=timestamp_col)
    stale_fields: list[str] = []
    stale_penalty = 0.0
    if stale_after_hours is not None and last_update:
        latest = pd.to_datetime(last_update, errors="coerce")
        current = pd.Timestamp(now) if now is not None else pd.Timestamp.now(tz=latest.tz if latest.tzinfo else None)
        if latest.tzinfo is None and getattr(current, "tzinfo", None) is not None:
            latest = latest.tz_localize(current.tzinfo)
        try:
            age_hours = (current - latest).total_seconds() / 3600.0
            if age_hours > stale_after_hours:
                stale_fields.append(timestamp_col or "index")
                stale_penalty = 0.15
        except Exception:
            pass

    penalty = (
        0.40 * required_missing_ratio
        + 0.25 * required_value_missing
        + 0.18 * important_missing_ratio
        + 0.12 * important_value_missing
        + stale_penalty
    )
    score = max(0.0, min(1.0, 1.0 - penalty))
    return ValidationReport(
        required_fields_missing=required_missing,
        important_fields_missing=important_missing,
        missing_ratio_by_column=ratios,
        data_quality_score=round(float(score), 6),
        stale_fields=stale_fields,
        last_update_time=last_update,
    )


def display_missing(value: Any, *, reason: str = "数据暂缺") -> str:
    if _is_missing_value(value):
        return reason
    return str(value)

