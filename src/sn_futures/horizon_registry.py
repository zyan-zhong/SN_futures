from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class HorizonConfig:
    key: str
    display_name: str
    canonical_name: str
    bar_interval: str
    forecast_steps: int
    forecast_interval_minutes: int | None
    forecast_trading_day_interval: int | None
    model_family: str
    chart_history_points: int
    backtest_window: str
    lookback_window: str
    validation_requires_intraday: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


HORIZON_ORDER = [
    "next_5m",
    "next_15m",
    "next_30m",
    "next_hour",
    "tomorrow",
    "one_to_two_weeks",
    "one_to_three_months",
]

HORIZON_ALIASES = {
    "h5m": "next_5m",
    "h15m": "next_15m",
    "h30m": "next_30m",
    "h1h": "next_hour",
    "h1d": "tomorrow",
    "h10d": "one_to_two_weeks",
    "h60d": "one_to_three_months",
}


DEFAULT_HORIZONS: dict[str, HorizonConfig] = {
    "next_5m": HorizonConfig(
        key="next_5m",
        display_name="5分钟",
        canonical_name="h5m",
        bar_interval="5m",
        forecast_steps=12,
        forecast_interval_minutes=5,
        forecast_trading_day_interval=None,
        model_family="intraday_micro",
        chart_history_points=240,
        backtest_window="最近3-6个月",
        lookback_window="最近10个交易日分钟数据；训练窗口最近90个交易日",
        validation_requires_intraday=True,
    ),
    "next_15m": HorizonConfig(
        key="next_15m",
        display_name="15分钟",
        canonical_name="h15m",
        bar_interval="15m",
        forecast_steps=16,
        forecast_interval_minutes=15,
        forecast_trading_day_interval=None,
        model_family="intraday_short",
        chart_history_points=360,
        backtest_window="最近6-9个月",
        lookback_window="最近20个交易日分钟数据；训练窗口最近180个交易日",
        validation_requires_intraday=True,
    ),
    "next_30m": HorizonConfig(
        key="next_30m",
        display_name="30分钟",
        canonical_name="h30m",
        bar_interval="30m",
        forecast_steps=16,
        forecast_interval_minutes=30,
        forecast_trading_day_interval=None,
        model_family="intraday_session",
        chart_history_points=480,
        backtest_window="最近9-12个月",
        lookback_window="最近30个交易日分钟数据；训练窗口最近270个交易日",
        validation_requires_intraday=True,
    ),
    "next_hour": HorizonConfig(
        key="next_hour",
        display_name="1小时",
        canonical_name="h1h",
        bar_interval="1h",
        forecast_steps=12,
        forecast_interval_minutes=60,
        forecast_trading_day_interval=None,
        model_family="session_swing",
        chart_history_points=520,
        backtest_window="最近12-18个月",
        lookback_window="最近60个交易日；训练窗口最近1-2年",
        validation_requires_intraday=True,
    ),
    "tomorrow": HorizonConfig(
        key="tomorrow",
        display_name="1日",
        canonical_name="h1d",
        bar_interval="1d",
        forecast_steps=5,
        forecast_interval_minutes=None,
        forecast_trading_day_interval=1,
        model_family="daily_short",
        chart_history_points=260,
        backtest_window="最近2-3年",
        lookback_window="最近1年展示；训练窗口最近3-5年",
        validation_requires_intraday=False,
    ),
    "one_to_two_weeks": HorizonConfig(
        key="one_to_two_weeks",
        display_name="1-2周",
        canonical_name="h10d",
        bar_interval="1d",
        forecast_steps=10,
        forecast_interval_minutes=None,
        forecast_trading_day_interval=1,
        model_family="medium_swing",
        chart_history_points=780,
        backtest_window="最近3-5年",
        lookback_window="最近3年展示；训练窗口最近5-8年",
        validation_requires_intraday=False,
    ),
    "one_to_three_months": HorizonConfig(
        key="one_to_three_months",
        display_name="1-3个月",
        canonical_name="h60d",
        bar_interval="1d",
        forecast_steps=60,
        forecast_interval_minutes=None,
        forecast_trading_day_interval=1,
        model_family="macro_regime",
        chart_history_points=1200,
        backtest_window="最近5-8年",
        lookback_window="最近5年展示；训练窗口尽可能长，至少8-10年",
        validation_requires_intraday=False,
    ),
}


def normalize_horizon_key(key: str) -> str:
    return HORIZON_ALIASES.get(str(key), str(key))


def get_horizon_config(key: str) -> HorizonConfig:
    normalized = normalize_horizon_key(key)
    return DEFAULT_HORIZONS.get(normalized, DEFAULT_HORIZONS["tomorrow"])


def list_horizon_configs() -> list[dict[str, Any]]:
    return [DEFAULT_HORIZONS[key].to_dict() for key in HORIZON_ORDER]


def horizon_config_path(project_root: Path | None = None) -> Path:
    root = project_root or Path.cwd()
    return root / "config" / "horizons.yaml"
