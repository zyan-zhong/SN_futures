from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from sn_futures.backtest_core import BacktestConfig, CostConfig, run_futures_backtest
from sn_futures.data_validators import build_validation_report
from sn_futures.features_core import build_feature_matrix
from sn_futures.labels import add_forward_return_labels, check_feature_label_leakage
from sn_futures.models.predict import predict_horizon
from sn_futures.models.train import train_horizon_models


def build_mock_sn_frame(rows: int = 180) -> pd.DataFrame:
    idx = pd.date_range("2025-09-01", periods=rows, freq="B")
    t = np.arange(rows, dtype=float)
    ret = 0.0012 * np.sin(t / 6.0) + 0.0008 * np.cos(t / 17.0)
    close = 420_000 * np.exp(np.cumsum(ret))
    high = close * (1.0 + 0.006 + 0.002 * np.sin(t / 5.0))
    low = close * (1.0 - 0.006 - 0.002 * np.cos(t / 7.0))
    open_ = close * (1.0 + 0.001 * np.sin(t / 3.0))
    volume = 12_000 + 1_500 * np.sin(t / 9.0) + 300 * np.cos(t / 2.0)
    event = np.where((t % 37) == 0, 0.65, 0.0)
    return pd.DataFrame(
        {
            "open": open_,
            "high": np.maximum.reduce([high, open_, close]),
            "low": np.minimum.reduce([low, open_, close]),
            "close": close,
            "volume": np.maximum(volume, 1),
            "open_interest": 55_000 + 600 * np.cos(t / 11.0),
            "main_contract": np.where(t < rows * 0.55, "sn2605", "sn2606"),
            "spot_price": close + 900 * np.sin(t / 13.0),
            "spot_premium": 600 * np.sin(t / 19.0),
            "shfe_inventory": 8_000 + 400 * np.cos(t / 21.0),
            "lme_inventory": 5_500 + 350 * np.sin(t / 29.0),
            "bonded_inventory": 1_500 + 120 * np.cos(t / 15.0),
            "lme_tin_close": close / 7.18 + 80 * np.sin(t / 10.0),
            "usd_cny": 7.18 + 0.03 * np.sin(t / 40.0),
            "dxy": 104 + 0.8 * np.sin(t / 31.0),
            "us10y": 4.2 + 0.12 * np.cos(t / 37.0),
            "news_event_score": event,
            "supply_event_score": event * 0.7,
            "macro_event_score": np.where((t % 53) == 0, -0.45, 0.0),
            "delivery_month_flag": np.where((t % 60) > 53, 1, 0),
        },
        index=idx,
    )


def run_smoke_pipeline() -> dict[str, object]:
    raw = build_mock_sn_frame()
    quality = build_validation_report(raw)
    feature_result = build_feature_matrix(raw)
    labelled = add_forward_return_labels(raw[["open", "high", "low", "close", "volume", "open_interest"]], horizons=(1,))
    frame = feature_result.feature_df.join(labelled[["ret_1d", "direction_1d"]], how="inner")

    numeric_cols = [
        col
        for col in feature_result.feature_df.columns
        if pd.api.types.is_numeric_dtype(feature_result.feature_df[col])
        and col not in {"ret_1d", "direction_1d"}
    ]
    feature_cols = [col for col in numeric_cols if col not in set(check_feature_label_leakage(numeric_cols)["leaked_columns"])]
    feature_cols = feature_cols[:32]
    model_frame = frame.copy()
    model_frame[feature_cols] = model_frame[feature_cols].ffill().fillna(0.0)
    model_frame = model_frame.dropna(subset=["ret_1d", "direction_1d"])

    bundle = train_horizon_models(
        model_frame,
        feature_cols,
        horizon="1d",
        direction_col="direction_1d",
        return_col="ret_1d",
        regime_col="regime_label",
        validation_fraction=0.25,
    )

    predictions: list[dict[str, object]] = []
    signal_rows: list[dict[str, object]] = []
    test_rows = model_frame.tail(24)
    for ts, row in test_rows.iterrows():
        pred = predict_horizon(
            bundle,
            row,
            current_price=float(row["close"]),
            data_quality_score=feature_result.data_quality_score,
            volatility_col="atr_14",
        )
        signal = 0
        if pred["signal"] == "多头研究观察" or pred["direction"] == "up" and pred["trade_edge"] > 0:
            signal = 1
        elif pred["signal"] == "空头研究观察" or pred["direction"] == "down" and pred["trade_edge"] > 0:
            signal = -1
        predictions.append({"timestamp": ts.isoformat(), **pred})
        signal_rows.append(
            {
                "signal": signal,
                "trade_edge": pred["trade_edge"],
                "data_quality_score": feature_result.data_quality_score,
                "confidence_score": pred["confidence_score"],
                "horizon": "1d",
                "signal_strength": pred["signal_strength"],
            }
        )

    signal_frame = pd.DataFrame(signal_rows, index=test_rows.index)
    backtest = run_futures_backtest(
        raw.loc[test_rows.index],
        signal_frame,
        config=BacktestConfig(cost=CostConfig(slippage_ticks=0.5, commission_per_contract=3.0, roll_cost_bps=0.5)),
    )
    return {
        "data_quality_score": quality.data_quality_score,
        "feature_count": len(feature_cols),
        "metadata_count": len(feature_result.feature_metadata),
        "missing_feature_count": len(feature_result.missing_feature_report),
        "model_metrics": bundle.metrics,
        "prediction_count": len(predictions),
        "backtest_metrics": backtest["metrics"],
        "trade_count": int(len(backtest["trades"])),
    }


if __name__ == "__main__":
    print(json.dumps(run_smoke_pipeline(), ensure_ascii=False, indent=2, default=str))
