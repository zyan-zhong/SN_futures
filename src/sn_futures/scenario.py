from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

from .config import RiskConfig


@dataclass(frozen=True)
class ScenarioDefinition:
    key: str
    label: str
    return_shift: float
    vol_multiplier: float
    confidence_shift: float
    rationale: str


def default_scenarios() -> list[ScenarioDefinition]:
    return [
        ScenarioDefinition(
            key="base_case",
            label="Base Case",
            return_shift=0.0,
            vol_multiplier=1.0,
            confidence_shift=0.0,
            rationale="Neutral continuation of current supply, demand, and macro regime.",
        ),
        ScenarioDefinition(
            key="myanmar_supply_disruption",
            label="Myanmar Supply Disruption",
            return_shift=0.028,
            vol_multiplier=1.45,
            confidence_shift=-4.0,
            rationale="Mine clearance tightening and ore flow disruption increase spot tension and basis risk.",
        ),
        ScenarioDefinition(
            key="fed_hike_25bp",
            label="Fed Hike 25bp",
            return_shift=-0.018,
            vol_multiplier=1.25,
            confidence_shift=-6.0,
            rationale="Dollar strength and tighter macro liquidity pressure tin beta and valuation support.",
        ),
        ScenarioDefinition(
            key="pv_demand_upside",
            label="PV Demand Upside",
            return_shift=0.016,
            vol_multiplier=1.10,
            confidence_shift=3.0,
            rationale="Stronger photovoltaic and electronics demand lifts solder usage and downstream orders.",
        ),
        ScenarioDefinition(
            key="risk_off_inventory_build",
            label="Risk-Off Inventory Build",
            return_shift=-0.024,
            vol_multiplier=1.35,
            confidence_shift=-5.0,
            rationale="Inventory rebuilding and weaker sentiment compress basis and swing momentum.",
        ),
    ]


def build_scenario_matrix(
    predictions: pd.DataFrame,
    raw: pd.DataFrame,
    risk: RiskConfig | None = None,
    contracts: int = 1,
    live_snapshot: dict[str, Any] | None = None,
) -> pd.DataFrame:
    risk = risk or RiskConfig()
    if predictions.empty or raw.empty:
        return pd.DataFrame()

    latest_pred = predictions.iloc[-1]
    latest_raw = raw.iloc[-1]
    daily_vol = max(float(latest_pred.get("ewma_vol_20", 0.20)) / np.sqrt(252), 0.005)
    close = float(latest_pred.get("close", latest_raw.get("close", 0.0)))
    atr = max(float(latest_pred.get("atr_14", 0.0)), close * 0.01)
    base_confidence = float(latest_pred.get("confidence", 50.0))
    text_summary = (live_snapshot or {}).get("text_summary", {}) if isinstance(live_snapshot, dict) else {}
    text_bias = float(text_summary.get("sentiment_mean", 0.0) or 0.0)
    impact_bias = float(text_summary.get("impact_mean", 0.0) or 0.0)

    rows: list[dict[str, Any]] = []
    for scenario in default_scenarios():
        effective_shift = scenario.return_shift + 0.35 * text_bias * (1.0 if scenario.return_shift >= 0 else -1.0)
        if scenario.key == "base_case":
            effective_shift += 0.10 * text_bias

        shocked_return = float(latest_pred.get("predicted_return", 0.0)) + effective_shift
        shocked_vol = daily_vol * scenario.vol_multiplier * (1.0 + 0.30 * impact_bias)
        prob_up = float(np.clip(latest_pred.get("prob_up_multimodal", latest_pred.get("prob_up", 0.5)) + effective_shift * 4.0, 0.01, 0.99))
        confidence = float(np.clip(latest_pred.get("confidence_multimodal", base_confidence) + scenario.confidence_shift, 5.0, 99.0))
        range_low = close * (1.0 + shocked_return - 1.64 * shocked_vol)
        range_high = close * (1.0 + shocked_return + 1.64 * shocked_vol)
        one_lot_pnl = shocked_return * close * risk.contract_size * contracts
        stop_loss_est = min(-atr * risk.reward_risk_ratio, one_lot_pnl)
        risk_level = "high" if abs(shocked_return) > 2.0 * daily_vol else "medium" if abs(shocked_return) > daily_vol else "low"

        rows.append(
            {
                "scenario_key": scenario.key,
                "scenario_label": scenario.label,
                "expected_return": shocked_return,
                "prob_up": prob_up,
                "confidence": confidence,
                "range_low": range_low,
                "range_high": range_high,
                "estimated_pnl": one_lot_pnl,
                "max_loss_proxy": stop_loss_est,
                "risk_level": risk_level,
                "rationale": scenario.rationale,
            }
        )

    matrix = pd.DataFrame(rows).set_index("scenario_key")
    return matrix


def build_position_risk_snapshot(
    predictions: pd.DataFrame,
    risk: RiskConfig | None = None,
    contracts: int = 1,
) -> dict[str, float]:
    risk = risk or RiskConfig()
    if predictions.empty:
        return {}

    latest = predictions.iloc[-1]
    close = float(latest.get("close", 0.0))
    daily_vol = max(float(latest.get("ewma_vol_20", 0.20)) / np.sqrt(252), 0.005)
    notional = close * risk.contract_size * contracts
    var_95 = 1.65 * daily_vol * notional
    stressed_var = 2.33 * daily_vol * 1.4 * notional
    margin = notional * risk.default_margin_rate
    return {
        "contracts": float(contracts),
        "notional": notional,
        "margin_required": margin,
        "var_95": var_95,
        "stressed_var": stressed_var,
        "margin_usage_ratio": margin / max(risk.account_equity, 1.0),
    }
