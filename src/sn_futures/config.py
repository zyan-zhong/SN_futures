from __future__ import annotations

import json
import os
from dataclasses import dataclass, replace
from pathlib import Path

from .runtime import get_user_data_dir, get_user_output_dir
from .user_data import secrets_path


_ENV_LOADED = False


def _strip_env_value(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value


def load_project_env(path: str | Path | None = None, *, override: bool = False) -> dict[str, str]:
    """Load a local .env file without adding a heavyweight dependency.

    Values already present in the process environment win by default.  This
    keeps packaged/runtime settings and CI secrets authoritative while still
    making local development reproducible.
    """

    global _ENV_LOADED
    if _ENV_LOADED and path is None and not override:
        return {}

    env_path = Path(path) if path else Path(__file__).resolve().parents[2] / ".env"
    loaded: dict[str, str] = {}
    if env_path.exists():
        for raw_line in env_path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            if not key:
                continue
            value = _strip_env_value(value)
            if override or key not in os.environ:
                os.environ[key] = value
            loaded[key] = os.environ.get(key, value)
    if path is None:
        _ENV_LOADED = True
    return loaded


def load_user_secrets(*, override: bool = False) -> dict[str, str]:
    """Load packaged-user secrets from the per-user config directory.

    Environment variables remain authoritative by default.  Missing or
    malformed secrets files are non-fatal so first launch can still show clear
    "未配置" provider states.
    """

    path = secrets_path()
    if not path.exists():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    if not isinstance(raw, dict):
        return {}
    loaded: dict[str, str] = {}
    for key in ("SN_ALPHA_VANTAGE_KEY", "SN_NEWSAPI_KEY", "SN_MANAGED_DATA_PROXY_TOKEN", "SN_TUSHARE_TOKEN"):
        value = str(raw.get(key, "") or "").strip()
        if not value:
            continue
        if override or key not in os.environ:
            os.environ[key] = value
        loaded[key] = os.environ.get(key, value)
    return loaded


load_project_env()


@dataclass(frozen=True)
class SourceConfigStatus:
    name: str
    enabled: bool
    success: bool
    message: str


@dataclass(frozen=True)
class EnvironmentConfig:
    alpha_vantage: SourceConfigStatus
    newsapi: SourceConfigStatus
    data_dir: str
    log_level: str


def mask_secret(value: str | None) -> str:
    text = str(value or "")
    if not text:
        return ""
    if len(text) <= 8:
        return "***"
    return f"{text[:2]}***{text[-2:]}"


def _api_key_status(env_name: str) -> SourceConfigStatus:
    value = os.getenv(env_name, "").strip()
    if not value:
        return SourceConfigStatus(
            name=env_name,
            enabled=False,
            success=False,
            message=f"未配置 {env_name}",
        )
    return SourceConfigStatus(
        name=env_name,
        enabled=True,
        success=True,
        message=f"{env_name} 已配置（{mask_secret(value)}）",
    )


def load_environment_config() -> EnvironmentConfig:
    load_project_env()
    # User settings page secrets are the runtime authority.  They intentionally
    # override development .env values and inherited process variables here so
    # terminal status mirrors what the user configured in the app.
    load_user_secrets(override=True)
    return EnvironmentConfig(
        alpha_vantage=_api_key_status("SN_ALPHA_VANTAGE_KEY"),
        newsapi=_api_key_status("SN_NEWSAPI_KEY"),
        data_dir=os.getenv("SN_DATA_DIR") or os.getenv("SN_INSIGHT_DATA_DIR") or "app_data",
        log_level=(os.getenv("SN_LOG_LEVEL") or "INFO").upper(),
    )


@dataclass(frozen=True)
class ProjectPaths:
    root: Path = Path(__file__).resolve().parents[2]
    user_data_dir: Path = get_user_data_dir()
    output_dir: Path = get_user_output_dir()
    report_dir: Path = output_dir / "reports"
    backup_dir: Path = user_data_dir / "backups"
    settings_path: Path = user_data_dir / "config" / "settings.json"
    api_keys_path: Path = user_data_dir / "config" / "secrets.json"
    live_predictions_path: Path = output_dir / "sn_live_predictions.json"


@dataclass(frozen=True)
class RiskConfig:
    contract_size: float = 1.0
    tick_size: float = 10.0
    default_fee_per_lot: float = 3.0
    default_margin_rate: float = 0.14
    single_trade_risk_pct: float = 0.01
    single_side_margin_pct: float = 0.20
    total_margin_pct: float = 0.40
    weekly_circuit_breaker_pct: float = 0.05
    daily_red_alert_loss_pct: float = 0.03
    confidence_threshold: float = 85.0
    prob_up_threshold: float = 0.62
    prob_down_threshold: float = 0.38
    vol_reduce_quantile: float = 0.95
    default_slippage_ticks: int = 1
    stressed_slippage_ticks: int = 2
    reward_risk_ratio: float = 2.5
    account_equity: float = 1_000_000.0


@dataclass(frozen=True)
class TrainingConfig:
    train_window: int = 126
    retrain_every: int = 10
    meta_window: int = 63
    min_history: int = 180
    seq_len: int = 12
    lstm_epochs: int = 3
    lstm_hidden_size: int = 16
    random_state: int = 42
    adaptive_window_days: int = 63
    drift_monitor_days: int = 10


@dataclass(frozen=True)
class FactorConfig:
    ic_threshold: float = 0.06
    icir_threshold: float = 0.60
    p_value_threshold: float = 0.05
    max_vif: float = 3.0
    min_features: int = 14
    max_features: int = 24


@dataclass(frozen=True)
class ParameterPreset:
    key: str
    label: str
    description: str
    confidence_threshold: float
    prob_up_threshold: float
    prob_down_threshold: float
    reward_risk_ratio: float
    single_trade_risk_pct: float
    vol_reduce_quantile: float


@dataclass(frozen=True)
class RiskProfile:
    key: str
    label: str
    description: str
    recommended_preset: str
    signal_floor: float
    single_trade_risk_cap: float


@dataclass(frozen=True)
class AppSettings:
    theme: str = "light"
    user_mode: str = "ordinary"
    selected_preset: str = "balanced"
    selected_risk_profile: str = "balanced"
    compute_profile: str = "auto"
    default_report_type: str = "daily"
    layout_locked: bool = False
    auto_backup: bool = True
    qna_enabled: bool = True
    voice_alerts: bool = False
    font_scale: int = 100
    live_data_enabled: bool = True
    cache_only_mode: bool = False
    live_refresh_seconds: int = 600
    stress_test_contracts: int = 1
    sina_symbols: tuple[str, ...] = ("nf_SN0",)


PRESET_LIBRARY: dict[str, ParameterPreset] = {
    "conservative": ParameterPreset(
        key="conservative",
        label="保守型",
        description="更高置信度阈值、更低风险预算、更严格的回撤控制。",
        confidence_threshold=90.0,
        prob_up_threshold=0.68,
        prob_down_threshold=0.32,
        reward_risk_ratio=2.2,
        single_trade_risk_pct=0.0075,
        vol_reduce_quantile=0.90,
    ),
    "balanced": ParameterPreset(
        key="balanced",
        label="平衡型",
        description="机构默认参数，兼顾方向命中、盈亏比与回撤控制。",
        confidence_threshold=85.0,
        prob_up_threshold=0.62,
        prob_down_threshold=0.38,
        reward_risk_ratio=2.8,
        single_trade_risk_pct=0.0100,
        vol_reduce_quantile=0.95,
    ),
    "aggressive": ParameterPreset(
        key="aggressive",
        label="进取型",
        description="更灵活的信号参与阈值，并通过动态风控限制尾部风险。",
        confidence_threshold=75.0,
        prob_up_threshold=0.58,
        prob_down_threshold=0.42,
        reward_risk_ratio=3.0,
        single_trade_risk_pct=0.0120,
        vol_reduce_quantile=0.97,
    ),
}


RISK_PROFILE_LIBRARY: dict[str, RiskProfile] = {
    "cautious": RiskProfile(
        key="cautious",
        label="谨慎",
        description="适合需要更严格阈值与更低信号频率的用户。",
        recommended_preset="conservative",
        signal_floor=88.0,
        single_trade_risk_cap=0.0075,
    ),
    "balanced": RiskProfile(
        key="balanced",
        label="平衡",
        description="适合多数用户的默认画像，兼顾研究参考价值与回撤约束。",
        recommended_preset="balanced",
        signal_floor=85.0,
        single_trade_risk_cap=0.0100,
    ),
    "active": RiskProfile(
        key="active",
        label="活跃",
        description="适合能够承受更高波动、希望获得更多研究信号的专业用户。",
        recommended_preset="aggressive",
        signal_floor=75.0,
        single_trade_risk_cap=0.0120,
    ),
}


def available_presets() -> list[ParameterPreset]:
    return list(PRESET_LIBRARY.values())


def available_risk_profiles() -> list[RiskProfile]:
    return list(RISK_PROFILE_LIBRARY.values())


def get_preset(key: str | None) -> ParameterPreset:
    return PRESET_LIBRARY.get(key or "balanced", PRESET_LIBRARY["balanced"])


def get_risk_profile(key: str | None) -> RiskProfile:
    return RISK_PROFILE_LIBRARY.get(key or "balanced", RISK_PROFILE_LIBRARY["balanced"])


def resolve_risk_config(
    preset_name: str | None = None,
    risk_profile_name: str | None = None,
    base: RiskConfig | None = None,
) -> RiskConfig:
    base_cfg = base or RiskConfig()
    preset = get_preset(preset_name)
    profile = get_risk_profile(risk_profile_name)
    confidence_threshold = max(preset.confidence_threshold, profile.signal_floor)
    single_trade_risk = min(preset.single_trade_risk_pct, profile.single_trade_risk_cap)
    return replace(
        base_cfg,
        confidence_threshold=confidence_threshold,
        prob_up_threshold=preset.prob_up_threshold,
        prob_down_threshold=preset.prob_down_threshold,
        reward_risk_ratio=preset.reward_risk_ratio,
        single_trade_risk_pct=single_trade_risk,
        vol_reduce_quantile=preset.vol_reduce_quantile,
    )


def resolve_app_settings(raw: dict[str, object] | None = None) -> AppSettings:
    raw = raw or {}
    default = AppSettings()
    raw_symbols = raw.get("sina_symbols", default.sina_symbols)
    if isinstance(raw_symbols, str):
        sina_symbols = tuple(part.strip() for part in raw_symbols.split(",") if part.strip()) or default.sina_symbols
    elif isinstance(raw_symbols, (list, tuple)):
        sina_symbols = tuple(str(part).strip() for part in raw_symbols if str(part).strip()) or default.sina_symbols
    else:
        sina_symbols = default.sina_symbols
    return AppSettings(
        theme=str(raw.get("theme", default.theme)),
        user_mode=str(raw.get("user_mode", default.user_mode)),
        selected_preset=str(raw.get("selected_preset", default.selected_preset)),
        selected_risk_profile=str(raw.get("selected_risk_profile", default.selected_risk_profile)),
        compute_profile=str(raw.get("compute_profile", default.compute_profile)),
        default_report_type=str(raw.get("default_report_type", default.default_report_type)),
        layout_locked=bool(raw.get("layout_locked", default.layout_locked)),
        auto_backup=bool(raw.get("auto_backup", default.auto_backup)),
        qna_enabled=bool(raw.get("qna_enabled", default.qna_enabled)),
        voice_alerts=bool(raw.get("voice_alerts", default.voice_alerts)),
        font_scale=int(raw.get("font_scale", default.font_scale)),
        live_data_enabled=bool(raw.get("live_data_enabled", default.live_data_enabled)),
        cache_only_mode=bool(raw.get("cache_only_mode", default.cache_only_mode)),
        live_refresh_seconds=max(60, int(raw.get("live_refresh_seconds", default.live_refresh_seconds))),
        stress_test_contracts=max(1, int(raw.get("stress_test_contracts", default.stress_test_contracts))),
        sina_symbols=sina_symbols,
    )
