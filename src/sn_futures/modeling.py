from __future__ import annotations

import importlib
from dataclasses import dataclass

import numpy as np
import pandas as pd

from .config import TrainingConfig
from .forecast_math import cohere_directional_forecast
from .features import FEATURE_GROUPS
from .light_ml import (
    LogisticRegressionLite,
    RandomSubspaceRegressorLite,
    RidgeRegressorLite,
    StandardScalerLite,
    StagewiseBoostingRegressorLite,
)


def _optional_import(module_name: str):
    try:
        return importlib.import_module(module_name)
    except Exception:  # pragma: no cover
        return None


@dataclass
class ModelBank:
    scaler: StandardScalerLite
    feature_cols: list[str]
    regime_models: dict[str, dict[str, object]]
    global_models: dict[str, object]
    lstm_model: "SequenceLSTMRegressor | None"
    train_frame: pd.DataFrame
    regime_sample_size: dict[str, int]
    seq_len: int


class SequenceLSTMRegressor:
    def __init__(self, seq_len: int, input_size: int, hidden_size: int = 16, epochs: int = 8) -> None:
        self.seq_len = seq_len
        self.epochs = epochs
        self.enabled = False
        self.torch = _optional_import("torch")
        self.nn = _optional_import("torch.nn") if self.torch is not None else None
        self.model = None
        self.loss_fn = None
        self.optimizer = None
        self.device = None

        if self.torch is None or self.nn is None:
            return

        nn_mod = self.nn
        torch_mod = self.torch

        class TinyLSTM(nn_mod.Module):
            def __init__(self, in_features: int, hidden_features: int) -> None:
                super().__init__()
                self.lstm = nn_mod.LSTM(input_size=in_features, hidden_size=hidden_features, batch_first=True)
                self.head = nn_mod.Sequential(
                    nn_mod.Linear(hidden_features, hidden_features),
                    nn_mod.ReLU(),
                    nn_mod.Linear(hidden_features, 1),
                )

            def forward(self, x):
                output, _ = self.lstm(x)
                return self.head(output[:, -1, :]).squeeze(-1)

        self.device = torch_mod.device("cuda" if torch_mod.cuda.is_available() else "cpu")
        self.model = TinyLSTM(input_size, hidden_size).to(self.device)
        self.loss_fn = nn_mod.MSELoss()
        self.optimizer = torch_mod.optim.Adam(self.model.parameters(), lr=0.01)
        self.enabled = True

    def _to_sequences(self, x: np.ndarray, y: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        xs, ys = [], []
        for idx in range(self.seq_len, len(x)):
            xs.append(x[idx - self.seq_len : idx])
            ys.append(y[idx])
        return np.asarray(xs, dtype=np.float32), np.asarray(ys, dtype=np.float32)

    def fit(self, x: np.ndarray, y: np.ndarray) -> None:
        if not self.enabled or self.torch is None or self.model is None or self.loss_fn is None or self.optimizer is None:
            return
        if len(x) <= self.seq_len + 5:
            return
        seq_x, seq_y = self._to_sequences(x, y)
        inputs = self.torch.tensor(seq_x, device=self.device)
        targets = self.torch.tensor(seq_y, device=self.device)
        self.model.train()
        for _ in range(self.epochs):
            self.optimizer.zero_grad()
            preds = self.model(inputs)
            loss = self.loss_fn(preds, targets)
            loss.backward()
            self.optimizer.step()

    def predict(self, history: np.ndarray) -> float:
        if not self.enabled or self.torch is None or self.model is None:
            return float("nan")
        if len(history) < self.seq_len:
            return float("nan")
        self.model.eval()
        with self.torch.no_grad():
            x = self.torch.tensor(history[-self.seq_len :], dtype=self.torch.float32, device=self.device).unsqueeze(0)
            return float(self.model(x).detach().cpu().item())


def _fit_base_models(x_train: np.ndarray, y_train: np.ndarray, random_state: int) -> dict[str, object]:
    models: dict[str, object] = {
        "ridge_ar": RidgeRegressorLite(alpha=1.5),
        "rf": RandomSubspaceRegressorLite(
            n_estimators=48,
            max_features=max(2, int(np.sqrt(x_train.shape[1]))),
            random_state=random_state,
        ),
        "gbr": StagewiseBoostingRegressorLite(
            learning_rate=0.05,
            n_estimators=32,
            random_state=random_state,
        ),
    }

    xgboost_module = _optional_import("xgboost")
    if xgboost_module is not None and hasattr(xgboost_module, "XGBRegressor"):
        models["xgb"] = xgboost_module.XGBRegressor(
            n_estimators=160,
            max_depth=3,
            learning_rate=0.05,
            subsample=0.9,
            colsample_bytree=0.9,
            reg_alpha=0.5,
            reg_lambda=1.0,
            random_state=random_state,
        )

    lightgbm_module = _optional_import("lightgbm")
    if lightgbm_module is not None and hasattr(lightgbm_module, "LGBMRegressor"):
        models["lgbm"] = lightgbm_module.LGBMRegressor(
            n_estimators=180,
            max_depth=4,
            learning_rate=0.05,
            subsample=0.9,
            colsample_bytree=0.9,
            random_state=random_state,
            verbose=-1,
        )

    fitted = {}
    for name, model in models.items():
        model.fit(x_train, y_train)
        fitted[name] = model
    return fitted


def fit_model_bank(
    train_frame: pd.DataFrame,
    feature_cols: list[str],
    target_col: str,
    config: TrainingConfig,
) -> ModelBank:
    scaler = StandardScalerLite()
    train_clean = train_frame.dropna(subset=feature_cols + [target_col, "regime"]).copy()
    x_train = scaler.fit_transform(train_clean[feature_cols])
    y_train = train_clean[target_col].to_numpy()

    global_models = _fit_base_models(x_train, y_train, config.random_state)
    regime_models: dict[str, dict[str, object]] = {}
    regime_sample_size: dict[str, int] = {}

    for regime in ("UPTREND", "DOWNTREND", "WIDE_RANGE", "NARROW_RANGE"):
        subset = train_clean[train_clean["regime"] == regime]
        regime_sample_size[regime] = len(subset)
        if len(subset) < 40:
            regime_models[regime] = global_models
            continue
        x_regime = scaler.transform(subset[feature_cols])
        y_regime = subset[target_col].to_numpy()
        regime_models[regime] = _fit_base_models(x_regime, y_regime, config.random_state)

    lstm_model = SequenceLSTMRegressor(
        seq_len=config.seq_len,
        input_size=len(feature_cols),
        hidden_size=config.lstm_hidden_size,
        epochs=config.lstm_epochs,
    )
    lstm_model.fit(x_train, y_train)

    return ModelBank(
        scaler=scaler,
        feature_cols=feature_cols,
        regime_models=regime_models,
        global_models=global_models,
        lstm_model=lstm_model,
        train_frame=train_clean,
        regime_sample_size=regime_sample_size,
        seq_len=config.seq_len,
    )


def _predict_base(bank: ModelBank, current_row: pd.Series, history_frame: pd.DataFrame) -> tuple[dict[str, float], float]:
    x_now = bank.scaler.transform(current_row[bank.feature_cols].to_frame().T)
    regime = current_row["regime"]
    chosen_models = bank.regime_models.get(regime, bank.global_models)

    predictions = {f"pred_{name}": float(model.predict(x_now)[0]) for name, model in chosen_models.items()}
    history = history_frame.dropna(subset=bank.feature_cols).copy()
    if len(history) >= bank.seq_len and bank.lstm_model is not None:
        seq_x = bank.scaler.transform(history[bank.feature_cols])
        predictions["pred_lstm"] = bank.lstm_model.predict(seq_x)

    sample_size = bank.regime_sample_size.get(regime, 0)
    regime_fit = min(100.0, 40.0 + 60.0 * sample_size / max(1, len(bank.train_frame)))
    return predictions, regime_fit


def _safe_row_float(row: pd.Series, key: str, default: float = 0.0) -> float:
    try:
        value = float(row.get(key, default))
    except Exception:
        return default
    if not np.isfinite(value):
        return default
    return value


def _heuristic_directional_predictions(row: pd.Series) -> dict[str, float]:
    """Tin-specific lightweight priors used as extra base learners.

    These are not standalone trading rules. They give the stacker interpretable
    priors for momentum, mean reversion, inventory pressure and cross-market gaps.
    """
    annualized_vol = max(_safe_row_float(row, "ewma_vol_20", 0.18), 0.05)
    daily_cap = max(annualized_vol / np.sqrt(252) * 2.2, 0.006)
    ret_1 = _safe_row_float(row, "ret_1")
    ret_5 = _safe_row_float(row, "ret_5")
    roc_10 = _safe_row_float(row, "roc_10")
    ma_bias_20 = _safe_row_float(row, "ma_bias_20")
    rsi = _safe_row_float(row, "rsi_14", 50.0)
    choppiness = _safe_row_float(row, "choppiness_14", 50.0)
    inventory_pressure = _safe_row_float(row, "inventory_pressure_z")
    basis_momentum = np.tanh(_safe_row_float(row, "basis_mom_5") / 5000.0) * 0.004
    cross_market = _safe_row_float(row, "overnight_lme_domestic_gap") + 0.35 * _safe_row_float(row, "lme_overnight_return")
    order_accel = 0.003 * np.tanh(_safe_row_float(row, "downstream_order_accel"))

    trend_weight = max(0.20, min(0.85, (62.0 - choppiness) / 34.0))
    pred_momentum = trend_weight * (0.42 * ret_1 + 0.38 * ret_5 + 0.20 * roc_10)
    reversion_pressure = -0.0035 * np.tanh((rsi - 50.0) / 18.0) - 0.18 * ma_bias_20
    pred_reversion = (1.0 - trend_weight) * reversion_pressure
    pred_fundamental = -0.0028 * np.tanh(inventory_pressure / 1.8) + basis_momentum + order_accel
    pred_cross_market = 0.45 * cross_market
    return {
        "pred_momentum_prior": float(np.clip(pred_momentum, -daily_cap, daily_cap)),
        "pred_reversion_prior": float(np.clip(pred_reversion, -daily_cap, daily_cap)),
        "pred_fundamental_prior": float(np.clip(pred_fundamental, -daily_cap, daily_cap)),
        "pred_cross_market_prior": float(np.clip(pred_cross_market, -daily_cap, daily_cap)),
    }


def aggregate_feature_importance(bank: ModelBank, regime: str) -> pd.Series:
    models = bank.regime_models.get(regime, bank.global_models)
    importance = pd.Series(0.0, index=bank.feature_cols)

    for model in models.values():
        if hasattr(model, "feature_importances_"):
            scores = pd.Series(model.feature_importances_, index=bank.feature_cols)
        elif hasattr(model, "coef_"):
            scores = pd.Series(np.abs(np.ravel(model.coef_)), index=bank.feature_cols)
        else:
            continue
        scores = scores / max(scores.sum(), 1e-8)
        importance = importance.add(scores, fill_value=0.0)

    if importance.sum() == 0:
        importance = pd.Series(1 / len(bank.feature_cols), index=bank.feature_cols)
    else:
        importance = importance / importance.sum()
    return importance.sort_values(ascending=False)


def _group_strength(row: pd.Series, group_name: str) -> float:
    cols = [col for col in FEATURE_GROUPS[group_name] if col in row.index]
    if not cols:
        return 50.0
    values = pd.Series(row[cols], dtype=float).replace([np.inf, -np.inf], np.nan).dropna()
    if values.empty:
        return 50.0
    strength = values.clip(-3, 3).abs().mean()
    return float(np.clip(35 + 65 * np.tanh(1.8 * strength), 0, 100))


def _model_agreement(pred_values: list[float]) -> float:
    valid = np.asarray([value for value in pred_values if np.isfinite(value)], dtype=float)
    if len(valid) <= 1:
        return 50.0
    dispersion = np.std(valid)
    center = np.abs(np.mean(valid)) + 1e-6
    sign_consensus = np.abs(np.mean(np.sign(valid))) * 100
    dispersion_score = np.clip(100 - 60 * dispersion / center, 0, 100)
    return float(0.6 * sign_consensus + 0.4 * dispersion_score)


def _local_contributions(row: pd.Series, importance: pd.Series) -> str:
    overlap = importance.index.intersection(row.index)
    numeric_row = pd.to_numeric(row[overlap], errors="coerce").fillna(0.0)
    contributions = (numeric_row * importance[overlap]).sort_values(
        key=lambda s: s.abs(), ascending=False
    )
    top = contributions.head(3)
    return "; ".join(f"{factor}:{value:+.3f}" for factor, value in top.items())


def _dynamic_regime_blend(row: pd.Series, pred_cols: list[str]) -> float:
    valid = {col: float(row[col]) for col in pred_cols if pd.notna(row[col])}
    if not valid:
        return 0.0

    regime = str(row.get("regime", "NARROW_RANGE"))
    weights = {col: 1.0 for col in valid}

    for col in valid:
        if "lstm" in col:
            weights[col] = 1.4 if regime in ("UPTREND", "DOWNTREND") else 0.8
        elif "gbr" in col:
            weights[col] = 1.1 if regime in ("UPTREND", "DOWNTREND") else 0.9
        elif "rf" in col:
            weights[col] = 1.3 if regime in ("WIDE_RANGE", "NARROW_RANGE") else 0.9
        elif "xgb" in col or "lgbm" in col:
            weights[col] = 1.25 if abs(float(row.get("regime_confidence", 50.0))) >= 65 else 1.0
        else:
            weights[col] = 1.0

    total = sum(weights.values())
    return float(sum(valid[col] * weights[col] for col in valid) / max(total, 1e-8))


def walk_forward_stacking(
    frame: pd.DataFrame,
    feature_cols: list[str],
    target_col: str = "target_return_1d",
    config: TrainingConfig | None = None,
) -> tuple[pd.DataFrame, pd.Series]:
    config = config or TrainingConfig()
    required = feature_cols + [target_col, "regime", "regime_confidence", "close", "atr_14", "ewma_vol_20"]
    work = frame.dropna(subset=required).copy()
    if len(work) < config.min_history:
        raise ValueError("Not enough rows after preprocessing to run walk-forward training.")

    current_bank: ModelBank | None = None
    latest_importance = pd.Series(dtype=float)
    base_rows = []

    for idx in range(config.train_window, len(work)):
        if current_bank is None or (idx - config.train_window) % config.retrain_every == 0:
            current_bank = fit_model_bank(work.iloc[idx - config.train_window : idx], feature_cols, target_col, config)

        current_row = work.iloc[idx]
        history = work.iloc[max(0, idx - config.seq_len - 5) : idx + 1]
        base_preds, regime_fit = _predict_base(current_bank, current_row, history)
        base_preds.update(_heuristic_directional_predictions(current_row))
        importance = aggregate_feature_importance(current_bank, current_row["regime"])
        latest_importance = importance

        base_rows.append(
            {
                "date": work.index[idx],
                "actual_return": float(current_row[target_col]),
                "close": float(current_row["close"]),
                "atr_14": float(current_row["atr_14"]),
                "ewma_vol_20": float(current_row["ewma_vol_20"]),
                "regime": current_row["regime"],
                "regime_fit": regime_fit,
                "regime_confidence": float(current_row["regime_confidence"]),
                "driver_summary": _local_contributions(current_row, importance),
                **base_preds,
            }
        )

    base_df = pd.DataFrame(base_rows).set_index("date")
    pred_cols = [col for col in base_df.columns if col.startswith("pred_")]
    base_df["pred_dynamic_blend"] = base_df.apply(lambda row: _dynamic_regime_blend(row, pred_cols), axis=1)
    pred_cols = pred_cols + ["pred_dynamic_blend"]
    meta_rows = []

    for idx in range(config.meta_window, len(base_df)):
        meta_train = base_df.iloc[idx - config.meta_window : idx]
        if len(meta_train) < 30:
            continue
        x_cols = pred_cols + ["atr_14", "ewma_vol_20", "regime_fit", "regime_confidence"]
        x_train = meta_train[x_cols].fillna(0.0)
        y_reg = meta_train["actual_return"]
        y_cls = (y_reg > 0).astype(int)

        reg_model = RidgeRegressorLite(alpha=2.0).fit(x_train, y_reg)
        cls_model = LogisticRegressionLite(C=0.7, max_iter=400).fit(x_train, y_cls) if y_cls.nunique() > 1 else None

        row = base_df.iloc[[idx]]
        x_now = row[x_cols].fillna(0.0)
        predicted_return = float(reg_model.predict(x_now)[0])
        prob_up = float(cls_model.predict_proba(x_now)[0, 1]) if cls_model is not None else float(y_cls.iloc[-1])

        model_agreement = _model_agreement([row.iloc[0][col] for col in pred_cols])
        feature_row = frame.loc[row.index[0]]
        technical_score = _group_strength(feature_row, "technical")
        fundamental_score = _group_strength(feature_row, "fundamental")
        event_score = _group_strength(feature_row, "macro_event")
        regime_fit_score = float(min(100.0, 0.5 * row.iloc[0]["regime_fit"] + 0.5 * row.iloc[0]["regime_confidence"]))
        confidence = (
            0.30 * model_agreement
            + 0.20 * fundamental_score
            + 0.20 * technical_score
            + 0.15 * event_score
            + 0.15 * regime_fit_score
        )
        confidence = float(np.clip(10 + confidence, 0, 100))

        annualized_vol = max(float(row.iloc[0]["ewma_vol_20"]), 0.05)
        daily_vol = annualized_vol / np.sqrt(252)
        close = float(row.iloc[0]["close"])
        coherent_return, coherent_prob = cohere_directional_forecast(predicted_return, prob_up, daily_vol)

        meta_rows.append(
            {
                "date": row.index[0],
                "predicted_return": coherent_return,
                "prob_up": coherent_prob,
                "confidence": confidence,
                "pred_center": close * (1 + coherent_return),
                "pred_low": close * (1 + coherent_return - 1.28 * daily_vol),
                "pred_high": close * (1 + coherent_return + 1.28 * daily_vol),
                "model_agreement": model_agreement,
                "technical_score": technical_score,
                "fundamental_score": fundamental_score,
                "event_score": event_score,
                "regime_fit_score": regime_fit_score,
                "driver_summary": row.iloc[0]["driver_summary"],
                "actual_return": float(row.iloc[0]["actual_return"]),
                "close": close,
                "atr_14": float(row.iloc[0]["atr_14"]),
                "ewma_vol_20": annualized_vol,
                "regime": row.iloc[0]["regime"],
                **{f"base_{col}": float(row.iloc[0][col]) for col in pred_cols if col in row.columns},
            }
        )

    return pd.DataFrame(meta_rows).set_index("date"), latest_importance
