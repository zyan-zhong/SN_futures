from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Iterable


LABEL_VERSION = "label_v1_multi_horizon_pit"
INTRADAY_HORIZONS = frozenset({"next_5m", "next_15m", "next_30m", "next_hour"})


@dataclass(frozen=True)
class LabelSpec:
    horizon: str
    target_return: str
    direction_label: str
    neutral_band: float
    volatility_adjusted_label: str
    label_available_at: str
    required_future_bars: int
    sample_end_exclusion: int


_NAMED_SPECS: dict[str, LabelSpec] = {
    "next_5m": LabelSpec("next_5m", "target_return", "direction_label", 0.0002, "volatility_adjusted_label", "label_available_at", 1, 1),
    "next_15m": LabelSpec("next_15m", "target_return", "direction_label", 0.0003, "volatility_adjusted_label", "label_available_at", 3, 3),
    "next_30m": LabelSpec("next_30m", "target_return", "direction_label", 0.0005, "volatility_adjusted_label", "label_available_at", 6, 6),
    "next_hour": LabelSpec("next_hour", "target_return", "direction_label", 0.0008, "volatility_adjusted_label", "label_available_at", 12, 12),
    "tomorrow": LabelSpec("tomorrow", "target_return", "direction_label", 0.0010, "volatility_adjusted_label", "label_available_at", 1, 1),
    "one_to_two_weeks": LabelSpec("one_to_two_weeks", "target_return", "direction_label", 0.0040, "volatility_adjusted_label", "label_available_at", 10, 10),
    "one_to_three_months": LabelSpec("one_to_three_months", "target_return", "direction_label", 0.0100, "volatility_adjusted_label", "label_available_at", 60, 60),
}

_ALIASES = {
    "next trading day": "tomorrow",
    "next_trading_day": "tomorrow",
    "tomorrow / next trading day": "tomorrow",
}


def label_spec_to_dict(spec: LabelSpec) -> dict[str, Any]:
    return asdict(spec)


def normalise_label_spec(value: int | str) -> LabelSpec:
    if isinstance(value, int):
        if value <= 0:
            raise ValueError("Label horizon must be positive.")
        horizon = f"{value}d"
        return LabelSpec(horizon, "target_return", "direction_label", 0.0, "volatility_adjusted_label", "label_available_at", int(value), int(value))
    raw = str(value).strip().lower()
    key = _ALIASES.get(raw, raw)
    if key in _NAMED_SPECS:
        return _NAMED_SPECS[key]
    if key.endswith("d") and key[:-1].isdigit():
        days = int(key[:-1])
        return normalise_label_spec(days)
    if key.isdigit():
        return normalise_label_spec(int(key))
    raise ValueError(f"Unsupported label horizon: {value}")


def normalise_label_specs(values: Iterable[int | str]) -> list[LabelSpec]:
    specs: list[LabelSpec] = []
    seen: set[str] = set()
    for value in values:
        spec = normalise_label_spec(value)
        if spec.horizon in seen:
            continue
        specs.append(spec)
        seen.add(spec.horizon)
    return specs
