from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


DISCLAIMER = "仅供沪锡期货量化投研参考，不构成投资建议，不承诺收益，不接实盘交易。"


@dataclass(slots=True)
class TerminalSummary:
    system_status: str = "运行中"
    data_quality_score: float | None = None
    data_quality_label: str = "数据暂缺"
    main_contract: str = "数据暂缺"
    latest_price: float | None = None
    price_change: float | None = None
    price_change_pct: float | None = None
    current_signal: str = "观望"
    model_status: str = "模型状态待验证"
    backtest_status: str = "回测状态待验证"
    risk_level: str = "中性"
    last_update_time: str = "本周期未更新"
    disclaimer: str = DISCLAIMER


@dataclass(slots=True)
class PredictionCard:
    horizon: str
    horizon_zh: str
    direction: str = "观望"
    signal: str = "观望"
    calibrated_prob_up: float | None = None
    raw_prob_up: float | None = None
    expected_return: float | None = None
    predicted_range: list[float | None] = field(default_factory=lambda: [None, None])
    confidence_score: float | None = None
    decision_explanation: str = "方向优势不足，维持研究观察。"
    top_factors: list[str] = field(default_factory=list)
    event_evidence: list[str] = field(default_factory=list)
    risk_notes: list[str] = field(default_factory=list)
    data_quality: float | None = None
    model_status: str = "模型状态待验证"
    backtest_summary: dict[str, Any] = field(default_factory=dict)
    path_guard_summary: str = "路径守门待验证"
    entry: float | None = None
    stop_loss: float | None = None
    take_profit: float | None = None


@dataclass(slots=True)
class ModelHealth:
    active_model: str = "暂无可用 active 模型"
    candidate_model: str = "暂未运行"
    degraded_models: list[str] = field(default_factory=list)
    promotion_status: str = "待验证"
    degradation_status: str = "未触发"
    metrics_by_horizon: dict[str, Any] = field(default_factory=dict)
    failure_reasons: list[str] = field(default_factory=list)
    last_check_time: str = "本周期未更新"


@dataclass(slots=True)
class LearningStatus:
    latest_market_refresh: str = "暂未运行"
    latest_prediction: str = "暂未运行"
    latest_validation: str = "暂未运行"
    latest_calibration: str = "暂未运行"
    latest_candidate_training: str = "暂未运行"
    latest_walk_forward: str = "暂未运行"
    latest_event_ablation: str = "暂未运行"
    latest_promotion_check: str = "暂未运行"
    next_task: str = "暂未计划"
    active_candidate_state: str = "暂无可用 active 模型"
    failure_reasons: list[str] = field(default_factory=list)


@dataclass(slots=True)
class BacktestDiagnostics:
    horizon: str = "all"
    walk_forward_metrics: dict[str, Any] = field(default_factory=dict)
    baseline_comparison: dict[str, Any] = field(default_factory=dict)
    cost_sensitivity: dict[str, Any] = field(default_factory=dict)
    by_regime: dict[str, Any] = field(default_factory=dict)
    by_signal_strength: dict[str, Any] = field(default_factory=dict)
    drawdown_periods: list[dict[str, Any]] = field(default_factory=list)
    promotion_gate_result: str = "待验证"
    failure_reasons: list[str] = field(default_factory=list)


@dataclass(slots=True)
class PositionScenario:
    input: dict[str, Any] = field(default_factory=dict)
    notional_exposure: float | None = None
    margin_required: float | None = None
    var_95: float | None = None
    stress_var: float | None = None
    max_loss_ratio: float | None = None
    observation_zone: list[dict[str, Any]] = field(default_factory=list)
    risk_zone: list[dict[str, Any]] = field(default_factory=list)
    horizon_resonance: str = "周期共振待验证"
    event_evidence: list[str] = field(default_factory=list)
    uncertainty_notes: list[str] = field(default_factory=list)
    disclaimer: str = DISCLAIMER


@dataclass(slots=True)
class DataSourceStatus:
    source_name: str
    enabled: bool = False
    configured: bool = False
    attempted: bool = False
    success: bool = False
    from_cache: bool = False
    message_zh: str = "本周期未更新"
    last_update: str = "本周期未更新"
    stale: bool = True
    status_code: str = "not_updated"
    status_zh: str = "本周期未更新"
    freshness_label: str = "本周期未更新"
    last_success_time: str = "本周期未更新"
    last_attempt_time: str = "本周期未更新"
    ttl_seconds: int | None = None
    ttl_zh: str = "本周期未更新"
    next_expected_update_time: str | None = None
    next_expected_update: str | None = None
    row_count: int = 0
    error_code: str = ""
    error_message_zh: str = ""
    next_actions_zh: list[str] = field(default_factory=list)
    suggested_action_zh: str = "查看运行期诊断"


@dataclass(slots=True)
class SystemHealth:
    api_status: str = "正常"
    data_status: str = "待验证"
    model_status: str = "待验证"
    storage_status: str = "待验证"
    report_status: str = "待验证"
    frontend_status: str = "legacy UI 可用"
    warnings: list[str] = field(default_factory=list)
    last_check_time: str = "本周期未更新"


def schema_to_dict(value: Any) -> Any:
    if hasattr(value, "__dataclass_fields__"):
        return asdict(value)
    return value
