from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import numpy as np
import pandas as pd

from .backtest import build_backtest_diagnostics, build_research_signals, run_backtest
from .config import (
    FactorConfig,
    ProjectPaths,
    RiskConfig,
    TrainingConfig,
    resolve_risk_config,
)
from .data import load_market_data
from .directional_v2 import apply_direction_first_calibration
from .features import build_factor_frame, factor_diagnostics, select_feature_subset
from .hardware import detect_hardware_profile, resolve_compute_profile, save_hardware_profile
from .market_data_hub import (
    apply_live_snapshot_overlay,
    build_live_snapshot,
    enrich_live_snapshot_with_history,
    history_symbol_from_snapshot,
    persist_live_snapshot,
)
from .forecast_math import cohere_directional_forecast
from .multimodal import build_live_prediction_cards, multimodal_adjustment
from .modeling import walk_forward_stacking
from .policy_bandit import apply_contextual_bandit
from .prediction_history import (
    append_prediction_snapshot,
    apply_history_calibration,
    build_model_memory,
    build_calibration_profile,
    build_walk_forward_calibration_profile,
    evaluate_prediction_history,
    model_memory_path,
    save_model_memory,
    summarize_prediction_evaluation,
)
from .prediction_display import apply_direction_gate
from .price_risk import apply_realistic_price_gates
from .regime import rolling_regime_detection
from .research_v2 import persist_v2_artifacts
from .scenario import build_position_risk_snapshot, build_scenario_matrix
from .reporting import build_markdown_report, build_report_bundle, save_outputs
from .unified_forecast import build_unified_forecast

MODELING_HISTORY_CAP = 720


def _apply_rolling_direction_calibration(predictions: pd.DataFrame, lookback: int = 60, min_samples: int = 30) -> pd.DataFrame:
    """Calibrate direction using only prior walk-forward prediction outcomes.

    If the recent model direction is persistently inverted, the current forecast is
    inverted and attenuated. This is deliberately lightweight and causal: row t is
    calibrated only with rows strictly before t, avoiding future leakage.
    """
    if not isinstance(predictions, pd.DataFrame) or predictions.empty:
        return predictions
    work = predictions.copy()
    prob_col = "prob_up_multimodal" if "prob_up_multimodal" in work.columns else "prob_up"
    conf_col = "confidence_multimodal" if "confidence_multimodal" in work.columns else "confidence"
    work["predicted_return_pre_dircal"] = pd.to_numeric(work.get("predicted_return", 0.0), errors="coerce").fillna(0.0)
    work["prob_up_pre_dircal"] = pd.to_numeric(work.get(prob_col, 0.5), errors="coerce").fillna(0.5)
    work["direction_calibration_action"] = "保持"
    work["direction_calibration_hit_rate"] = pd.NA

    for pos in range(len(work)):
        prior = work.iloc[max(0, pos - lookback):pos].copy()
        if len(prior) < min_samples:
            continue
        prior_prob = pd.to_numeric(prior.get(prob_col, prior.get("prob_up", 0.5)), errors="coerce").fillna(0.5)
        prior_actual = pd.to_numeric(prior.get("actual_return", 0.0), errors="coerce").fillna(0.0)
        prior_predicted = pd.to_numeric(prior.get("predicted_return", 0.0), errors="coerce").fillna(0.0)
        pred_direction = ((prior_prob >= 0.5) | (prior_predicted >= 0)).astype(int).replace({0: -1})
        actual_direction = (prior_actual >= 0).astype(int).replace({0: -1})
        hit_rate = float((pred_direction.to_numpy() == actual_direction.to_numpy()).mean())

        old_return = float(work.iloc[pos].get("predicted_return", 0.0) or 0.0)
        old_prob = float(work.iloc[pos].get(prob_col, work.iloc[pos].get("prob_up", 0.5)) or 0.5)
        candidate_cols = [
            col
            for col in work.columns
            if col.startswith("base_pred_") and any(key in col for key in ("momentum_prior", "reversion_prior", "fundamental_prior", "cross_market_prior", "dynamic_blend"))
        ]
        best_candidate = ""
        best_candidate_hit = hit_rate
        for col in candidate_cols:
            prior_candidate = pd.to_numeric(prior.get(col), errors="coerce").fillna(0.0)
            candidate_direction = (prior_candidate >= 0).astype(int).replace({0: -1})
            candidate_hit = float((candidate_direction.to_numpy() == actual_direction.to_numpy()).mean())
            if candidate_hit > best_candidate_hit:
                best_candidate_hit = candidate_hit
                best_candidate = col
        chosen_prior_return = float(work.iloc[pos].get(best_candidate, 0.0) or 0.0) if best_candidate else 0.0
        action = "保持"
        if best_candidate and best_candidate_hit >= max(0.54, hit_rate + 0.04):
            blend = 0.70 if hit_rate < 0.50 else 0.45
            new_return = (1.0 - blend) * old_return + blend * chosen_prior_return
            prior_prob = 0.5 + np.tanh(chosen_prior_return / max(float(work.iloc[pos].get("ewma_vol_20", 0.18) or 0.18) / (252 ** 0.5), 1e-4)) * 0.30
            new_prob = (1.0 - blend) * old_prob + blend * prior_prob
            action = f"候选融合:{best_candidate.replace('base_pred_', '')}"
        elif hit_rate < 0.46:
            new_return = -0.75 * old_return
            new_prob = 1.0 - old_prob
            action = "反向校准"
        elif hit_rate < 0.50:
            new_return = 0.55 * old_return
            new_prob = 0.5 + (old_prob - 0.5) * 0.55
            action = "降权观望"
        elif hit_rate > 0.58:
            new_return = 1.05 * old_return
            new_prob = 0.5 + (old_prob - 0.5) * 1.05
            action = "顺势增强"
        else:
            new_return = old_return
            new_prob = old_prob

        annualized_vol = float(work.iloc[pos].get("ewma_vol_20", 0.18) or 0.18)
        daily_vol = max(annualized_vol / (252 ** 0.5), 1e-4)
        coherent_return, coherent_prob = cohere_directional_forecast(new_return, new_prob, daily_vol)
        close = float(work.iloc[pos].get("close", 0.0) or 0.0)
        work.iat[pos, work.columns.get_loc("predicted_return")] = coherent_return
        work.iat[pos, work.columns.get_loc("prob_up")] = coherent_prob
        if "prob_up_multimodal" in work.columns:
            work.iat[pos, work.columns.get_loc("prob_up_multimodal")] = coherent_prob
        if conf_col in work.columns:
            old_conf = float(work.iloc[pos].get(conf_col, 50.0) or 50.0)
            conf_shift = -8.0 if action == "反向校准" else -4.0 if action == "降权观望" else 2.0 if action == "顺势增强" else 0.0
            work.iat[pos, work.columns.get_loc(conf_col)] = max(5.0, min(99.0, old_conf + conf_shift))
        if close > 0:
            work.iat[pos, work.columns.get_loc("pred_center")] = close * (1.0 + coherent_return)
            work.iat[pos, work.columns.get_loc("pred_low")] = close * (1.0 + coherent_return - 1.28 * daily_vol)
            work.iat[pos, work.columns.get_loc("pred_high")] = close * (1.0 + coherent_return + 1.28 * daily_vol)
        work.iat[pos, work.columns.get_loc("direction_calibration_action")] = action
        work.iat[pos, work.columns.get_loc("direction_calibration_hit_rate")] = max(hit_rate, best_candidate_hit)
    return work


def _training_candidates(base: TrainingConfig) -> list[TrainingConfig]:
    return [
        base,
        replace(base, train_window=168, retrain_every=5, seq_len=10),
        replace(base, train_window=252, retrain_every=10, seq_len=16),
        replace(base, train_window=189, retrain_every=5, seq_len=12),
    ]


def _training_config_signature(config: TrainingConfig) -> tuple[int, int, int, int, int]:
    return (
        int(config.train_window),
        int(config.retrain_every),
        int(config.seq_len),
        int(config.lstm_hidden_size),
        int(config.lstm_epochs),
    )


def _training_config_from_payload(payload: object) -> TrainingConfig | None:
    if not isinstance(payload, dict):
        return None
    try:
        base = TrainingConfig()
        return replace(
            base,
            train_window=max(90, int(payload.get("train_window", base.train_window))),
            retrain_every=max(3, int(payload.get("retrain_every", base.retrain_every))),
            seq_len=max(4, int(payload.get("seq_len", base.seq_len))),
            lstm_hidden_size=max(8, int(payload.get("lstm_hidden_size", base.lstm_hidden_size))),
            lstm_epochs=max(1, int(payload.get("lstm_epochs", base.lstm_epochs))),
        )
    except Exception:
        return None


def _load_prior_training_config(paths: ProjectPaths) -> TrainingConfig | None:
    path = model_memory_path(paths.output_dir)
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return _training_config_from_payload(payload.get("best_training_config"))


def _candidate_entries(
    base: TrainingConfig,
    optimization_level: str,
    prior_config: TrainingConfig | None = None,
) -> list[tuple[str, TrainingConfig]]:
    if optimization_level == "fast":
        entries: list[tuple[str, TrainingConfig]] = [
            ("fast_default", replace(base, train_window=144, retrain_every=12, seq_len=8, lstm_epochs=2, lstm_hidden_size=12)),
            ("fast_stability", replace(base, train_window=189, retrain_every=10, seq_len=10, lstm_epochs=1, lstm_hidden_size=12)),
            ("fast_reactive", replace(base, train_window=126, retrain_every=5, seq_len=6, lstm_epochs=1, lstm_hidden_size=10)),
        ]
    elif optimization_level == "balanced":
        entries = [
            ("balanced_default", replace(base, train_window=168, retrain_every=8, seq_len=10, lstm_epochs=2, lstm_hidden_size=16)),
            ("balanced_direction", replace(base, train_window=189, retrain_every=6, seq_len=12, lstm_epochs=2, lstm_hidden_size=18)),
            ("balanced_stability", replace(base, train_window=252, retrain_every=10, seq_len=14, lstm_epochs=2, lstm_hidden_size=18)),
        ]
    elif optimization_level == "gpu_full":
        entries = [
            ("gpu_direction_252", replace(base, train_window=252, retrain_every=5, seq_len=16, lstm_epochs=5, lstm_hidden_size=32)),
            ("gpu_stability_320", replace(base, train_window=320, retrain_every=8, seq_len=20, lstm_epochs=6, lstm_hidden_size=40)),
            ("gpu_reactive_189", replace(base, train_window=189, retrain_every=4, seq_len=12, lstm_epochs=4, lstm_hidden_size=28)),
            ("gpu_long_cycle", replace(base, train_window=378, retrain_every=10, seq_len=24, lstm_epochs=6, lstm_hidden_size=48)),
        ]
    else:
        entries = [(f"full_{idx}", cfg) for idx, cfg in enumerate(_training_candidates(base), start=1)]
    if prior_config is not None:
        entries.insert(0, ("history_best", prior_config))

    deduped: list[tuple[str, TrainingConfig]] = []
    seen: set[tuple[int, int, int, int, int]] = set()
    for source, config in entries:
        signature = _training_config_signature(config)
        if signature in seen:
            continue
        seen.add(signature)
        deduped.append((source, config))
    return deduped


def _monthly_pnl_stability(trades: pd.DataFrame) -> float:
    if not isinstance(trades, pd.DataFrame) or trades.empty:
        return 0.0
    pnl = trades["pnl"].copy()
    monthly = pnl.groupby(pnl.index.to_period("M")).sum()
    if len(monthly) <= 1:
        return 0.5
    dispersion = float(monthly.std(ddof=1))
    center = abs(float(monthly.mean())) + 1e-8
    return float(max(0.0, 1.0 - min(dispersion / center, 1.0)))


def _diagnostic_score(diagnostics: dict[str, object] | None) -> float:
    if not isinstance(diagnostics, dict):
        return 0.0
    rolling_rows = diagnostics.get("rolling_rows", [])
    if not isinstance(rolling_rows, list) or not rolling_rows:
        return 0.0
    weighted_hit = 0.0
    total_weight = 0.0
    for row, weight in zip(rolling_rows[:3], (0.50, 0.32, 0.18)):
        if isinstance(row, dict):
            weighted_hit += weight * float(row.get("direction_hit_rate", 0.0) or 0.0)
            total_weight += weight
    recent = rolling_rows[0] if isinstance(rolling_rows[0], dict) else {}
    hit_rate = weighted_hit / max(total_weight, 1e-8)
    recent_hit = float(recent.get("direction_hit_rate", 0.0) or 0.0)
    avg_error = float(recent.get("avg_abs_error", 0.0) or 0.0)
    signal_rate = float(recent.get("signal_rate", 0.0) or 0.0)
    error_control = max(0.0, min(1.0, 1.0 - avg_error / 0.055))
    signal_balance = max(0.0, min(1.0, 1.0 - abs(signal_rate - 0.22) / 0.22))
    recent_penalty = 0.12 if recent_hit < 0.50 else 0.06 if recent_hit == 0.50 else 0.0
    return float(max(0.0, 0.58 * hit_rate + 0.27 * error_control + 0.15 * signal_balance - recent_penalty))


def _metric_score(metrics: dict[str, float], trades: pd.DataFrame, diagnostics: dict[str, object] | None = None) -> float:
    win_rate = float(metrics.get("win_rate", 0.0))
    reward_risk = min(float(metrics.get("reward_risk_ratio", 0.0)) / 3.0, 1.0)
    sharpe = min(max(float(metrics.get("sharpe", 0.0)), 0.0) / 2.8, 1.0)
    calmar = min(max(float(metrics.get("calmar", 0.0)), 0.0) / 1.8, 1.0)
    drawdown_penalty = min(abs(float(metrics.get("max_drawdown", 0.0))) / 0.15, 1.5)
    stability = _monthly_pnl_stability(trades)
    trade_count = min(float(metrics.get("trade_count", 0.0)) / 24.0, 1.0)
    prediction_quality = _diagnostic_score(diagnostics)
    score = (
        0.22 * win_rate
        + 0.20 * sharpe
        + 0.16 * reward_risk
        + 0.10 * calmar
        + 0.10 * stability
        + 0.07 * trade_count
        + 0.15 * prediction_quality
        - 0.20 * drawdown_penalty
    )
    return float(score)


def _auto_optimize_model(
    modeling_frame: pd.DataFrame,
    selected_features: list[str],
    target_col: str,
    risk_cfg: RiskConfig,
    live_snapshot: dict[str, object] | None,
    optimization_level: str = "full",
    prior_training_config: TrainingConfig | None = None,
) -> dict[str, object]:
    candidate_entries = _candidate_entries(TrainingConfig(), optimization_level, prior_training_config)
    candidate_rows: list[dict[str, float | int | str]] = []
    best_bundle: dict[str, object] | None = None
    best_score = float("-inf")
    prior_signature = _training_config_signature(prior_training_config) if prior_training_config is not None else None
    selected_source = ""

    for idx, (candidate_source, cfg) in enumerate(candidate_entries, start=1):
        predictions, importance = walk_forward_stacking(
            modeling_frame,
            selected_features,
            target_col=target_col,
            config=cfg,
        )
        if live_snapshot:
            text_summary = live_snapshot.get("text_summary", {}) if isinstance(live_snapshot, dict) else {}
            predictions = multimodal_adjustment(predictions, article_summary=text_summary)
        predictions = _apply_rolling_direction_calibration(predictions)
        predictions, direction_summary = apply_direction_first_calibration(predictions)
        predictions, bandit_summary = apply_contextual_bandit(predictions, risk=risk_cfg)
        signals = build_research_signals(predictions, risk_cfg)
        trades, metrics = run_backtest(signals, risk_cfg)
        backtest_diagnostics = build_backtest_diagnostics(signals, trades, metrics)
        score = _metric_score(metrics, trades, backtest_diagnostics)
        rolling_rows = backtest_diagnostics.get("rolling_rows", []) if isinstance(backtest_diagnostics, dict) else []
        latest_quality = rolling_rows[0] if isinstance(rolling_rows, list) and rolling_rows and isinstance(rolling_rows[0], dict) else {}
        candidate_rows.append(
            {
                "candidate": f"cfg_{idx}",
                "candidate_source": candidate_source,
                "train_window": cfg.train_window,
                "retrain_every": cfg.retrain_every,
                "seq_len": cfg.seq_len,
                "lstm_hidden_size": cfg.lstm_hidden_size,
                "lstm_epochs": cfg.lstm_epochs,
                "win_rate": float(metrics.get("win_rate", 0.0)),
                "sharpe": float(metrics.get("sharpe", 0.0)),
                "reward_risk_ratio": float(metrics.get("reward_risk_ratio", 0.0)),
                "max_drawdown": float(metrics.get("max_drawdown", 0.0)),
                "recent_direction_hit_rate": float(latest_quality.get("direction_hit_rate", 0.0) or 0.0),
                "recent_avg_abs_error": float(latest_quality.get("avg_abs_error", 0.0) or 0.0),
                "score": score,
                "latest_policy_action": str(bandit_summary.get("latest_action", "平衡")),
                "latest_direction_state": str(direction_summary.get("latest_state", "")),
            }
        )
        if score > best_score:
            best_score = score
            best_bundle = {
                "training_config": cfg,
                "predictions": predictions,
                "importance": importance,
                "signals": signals,
                "trades": trades,
                "metrics": metrics,
                "backtest_diagnostics": backtest_diagnostics,
                "bandit_summary": bandit_summary,
                "direction_summary": direction_summary,
                "selected_candidate_source": candidate_source,
            }
            selected_source = candidate_source

    if best_bundle is None:
        raise ValueError("Auto-optimization failed to produce a valid model bundle.")

    optimization_table = pd.DataFrame(candidate_rows).sort_values("score", ascending=False).reset_index(drop=True)
    best_cfg: TrainingConfig = best_bundle["training_config"]  # type: ignore[assignment]
    best_signature = _training_config_signature(best_cfg)
    rollback_applied = bool(prior_signature is not None and best_signature == prior_signature)
    optimization_summary = {
        "best_score": best_score,
        "best_config": {
            "train_window": best_cfg.train_window,
            "retrain_every": best_cfg.retrain_every,
            "seq_len": best_cfg.seq_len,
            "lstm_hidden_size": best_cfg.lstm_hidden_size,
            "lstm_epochs": best_cfg.lstm_epochs,
        },
        "candidate_count": len(candidate_entries),
        "selected_candidate_source": str(best_bundle.get("selected_candidate_source", selected_source)),
        "rollback_applied": rollback_applied,
        "rollback_reason": "历史最优配置在本轮最新真实数据回测中得分最高" if rollback_applied else "",
        "candidates": optimization_table.to_dict(orient="records"),
    }
    best_bundle["optimization_table"] = optimization_table
    best_bundle["optimization_summary"] = optimization_summary
    return best_bundle


def _fit_additional_horizon_predictions(
    modeling_frame: pd.DataFrame,
    selected_features: list[str],
    training_config: TrainingConfig,
    live_snapshot: dict[str, object] | None,
    optimization_level: str = "full",
) -> dict[str, pd.DataFrame]:
    if optimization_level == "fast":
        return {}
    horizon_targets = {
        "target_return_10d": "swing_10d",
        "target_return_60d": "trend_60d",
    }
    horizon_frames: dict[str, pd.DataFrame] = {}
    for target_col, horizon_name in horizon_targets.items():
        available = modeling_frame[target_col].dropna() if target_col in modeling_frame.columns else pd.Series(dtype=float)
        if len(available) < max(training_config.min_history, 140):
            continue
        frame, _ = walk_forward_stacking(
            modeling_frame,
            selected_features,
            target_col=target_col,
            config=training_config,
        )
        if live_snapshot:
            text_summary = live_snapshot.get("text_summary", {}) if isinstance(live_snapshot, dict) else {}
            frame = multimodal_adjustment(frame, article_summary=text_summary)
        horizon_frames[horizon_name] = frame
    return horizon_frames


def run_pipeline(
    csv_path: str | Path | None = None,
    preset_name: str | None = None,
    risk_profile_name: str | None = None,
    live_snapshot: dict[str, object] | None = None,
    use_demo: bool = False,
    optimization_level: str = "full",
    raw_override: pd.DataFrame | None = None,
    real_symbol: str | None = None,
) -> dict[str, object]:
    paths = ProjectPaths()
    hardware_profile = detect_hardware_profile()
    optimization_level = resolve_compute_profile(optimization_level, hardware_profile)
    hardware_profile["current_profile"] = optimization_level
    hardware_profile["actual_training_device"] = "cuda:0" if optimization_level == "gpu_full" and hardware_profile.get("cuda_available") else "cpu"
    hardware_profile["last_training_used_gpu"] = bool(optimization_level == "gpu_full" and hardware_profile.get("cuda_available"))
    hardware_profile["gpu_full_enabled"] = bool(optimization_level == "gpu_full" and hardware_profile.get("cuda_available"))
    if optimization_level != "gpu_full" and hardware_profile.get("recommended_profile") == "gpu_full":
        hardware_profile["downgrade_reason"] = f"用户/任务选择 {optimization_level} 档位，本次未启用 GPU-Full。"
    save_hardware_profile(hardware_profile, paths.output_dir)
    raw = raw_override.copy() if isinstance(raw_override, pd.DataFrame) else load_market_data(
        csv_path,
        prefer_real=not use_demo,
        allow_demo=use_demo,
        real_symbol=real_symbol,
    )
    if isinstance(live_snapshot, dict) and live_snapshot:
        raw = apply_live_snapshot_overlay(raw, live_snapshot)
    factor_frame = build_factor_frame(raw)
    modeling_source = factor_frame.tail(MODELING_HISTORY_CAP).copy()
    diagnostics = factor_diagnostics(modeling_source, target_col="target_return_1d")

    factor_cfg = FactorConfig()
    selected_features = select_feature_subset(
        diagnostics,
        ic_threshold=factor_cfg.ic_threshold,
        icir_threshold=factor_cfg.icir_threshold,
        p_value_threshold=factor_cfg.p_value_threshold,
        max_vif=factor_cfg.max_vif,
        min_features=factor_cfg.min_features,
        max_features=factor_cfg.max_features,
    )
    coverage = modeling_source[selected_features].notna().mean().sort_values(ascending=False) if selected_features else pd.Series(dtype=float)
    selected_features = [feature for feature in selected_features if float(coverage.get(feature, 0.0)) >= 0.75]
    if len(selected_features) < 10 and not diagnostics.empty:
        diagnostics_with_coverage = diagnostics.copy()
        diagnostics_with_coverage["coverage"] = diagnostics_with_coverage["factor"].map(lambda col: float(modeling_source[col].notna().mean()) if col in modeling_source.columns else 0.0)
        fallback = diagnostics_with_coverage[diagnostics_with_coverage["coverage"] >= 0.75]["factor"].tolist()
        for feature in fallback:
            if feature not in selected_features:
                selected_features.append(feature)
            if len(selected_features) >= max(10, factor_cfg.min_features):
                break
    if not selected_features:
        raise ValueError("No features selected from diagnostics.")

    regime_frame = rolling_regime_detection(modeling_source)
    modeling_frame = modeling_source.join(regime_frame)

    risk_cfg = resolve_risk_config(preset_name=preset_name, risk_profile_name=risk_profile_name, base=RiskConfig())
    prior_training_config = _load_prior_training_config(paths)
    optimized = _auto_optimize_model(
        modeling_frame,
        selected_features,
        target_col="target_return_1d",
        risk_cfg=risk_cfg,
        live_snapshot=live_snapshot if isinstance(live_snapshot, dict) else None,
        optimization_level=optimization_level,
        prior_training_config=prior_training_config,
    )
    predictions = optimized["predictions"]  # type: ignore[assignment]
    importance = optimized["importance"]  # type: ignore[assignment]
    signals = optimized["signals"]  # type: ignore[assignment]
    trades = optimized["trades"]  # type: ignore[assignment]
    metrics = optimized["metrics"]  # type: ignore[assignment]
    training_config = optimized["training_config"]  # type: ignore[assignment]
    optimization_table = optimized["optimization_table"]  # type: ignore[assignment]
    optimization_summary = optimized["optimization_summary"]  # type: ignore[assignment]
    bandit_summary = optimized.get("bandit_summary", {})
    direction_summary = optimized.get("direction_summary", {})
    backtest_diagnostics = optimized.get("backtest_diagnostics", {})
    horizon_predictions = _fit_additional_horizon_predictions(
        modeling_frame,
        selected_features,
        training_config,
        live_snapshot if isinstance(live_snapshot, dict) else None,
        optimization_level=optimization_level,
    )

    scenario_matrix = build_scenario_matrix(
        predictions,
        raw,
        risk=risk_cfg,
        contracts=1,
        live_snapshot=live_snapshot if isinstance(live_snapshot, dict) else None,
    )
    position_risk = build_position_risk_snapshot(predictions, risk=risk_cfg, contracts=1)
    report = build_markdown_report(predictions, metrics, diagnostics, selected_features)
    report_bundle = build_report_bundle(
        raw,
        predictions,
        metrics,
        diagnostics,
        selected_features,
        signals,
        trades,
        live_snapshot=live_snapshot if isinstance(live_snapshot, dict) else None,
        scenario_matrix=scenario_matrix,
        position_risk=position_risk,
    )

    report_manifest = save_outputs(
        paths.output_dir,
        paths.report_dir,
        report,
        diagnostics,
        predictions,
        trades,
        report_bundle,
        live_snapshot=live_snapshot if isinstance(live_snapshot, dict) else None,
        scenario_matrix=scenario_matrix,
        optimization_table=optimization_table,
        bandit_summary=bandit_summary if isinstance(bandit_summary, dict) else None,
    )
    return {
        "raw": raw,
        "factor_frame": factor_frame,
        "modeling_source": modeling_source,
        "diagnostics": diagnostics,
        "selected_features": selected_features,
        "feature_importance": importance,
        "regimes": regime_frame,
        "predictions": predictions,
        "signals": signals,
        "trades": trades,
        "metrics": metrics,
        "report": report,
        "report_bundle": report_bundle,
        "report_manifest": report_manifest,
        "optimization_table": optimization_table,
        "optimization_summary": optimization_summary,
        "bandit_summary": bandit_summary,
        "direction_summary": direction_summary,
        "backtest_diagnostics": backtest_diagnostics,
        "horizon_predictions": horizon_predictions,
        "live_snapshot": live_snapshot if isinstance(live_snapshot, dict) else None,
        "scenario_matrix": scenario_matrix,
        "position_risk": position_risk,
        "risk_config": risk_cfg,
        "output_dir": paths.output_dir,
        "report_dir": paths.report_dir,
        "optimization_level": optimization_level,
        "hardware_profile": hardware_profile,
    }


def run_live_prediction_pipeline(
    csv_path: str | Path | None = None,
    preset_name: str | None = None,
    risk_profile_name: str | None = None,
    refresh_scope: str = "all",
    use_remote: bool = True,
    symbols: list[str] | None = None,
    existing_result: dict[str, object] | None = None,
    use_demo: bool = False,
    optimization_level: str = "full",
) -> dict[str, object]:
    paths = ProjectPaths()
    hardware_profile = detect_hardware_profile()
    optimization_level = resolve_compute_profile(optimization_level, hardware_profile)
    hardware_profile["current_profile"] = optimization_level
    hardware_profile["actual_training_device"] = "cuda:0" if optimization_level == "gpu_full" and hardware_profile.get("cuda_available") else "cpu"
    hardware_profile["last_training_used_gpu"] = bool(optimization_level == "gpu_full" and hardware_profile.get("cuda_available"))
    hardware_profile["gpu_full_enabled"] = bool(optimization_level == "gpu_full" and hardware_profile.get("cuda_available"))
    if optimization_level != "gpu_full" and hardware_profile.get("recommended_profile") == "gpu_full":
        hardware_profile["downgrade_reason"] = f"用户/任务选择 {optimization_level} 档位，本次未启用 GPU-Full。"
    save_hardware_profile(hardware_profile, paths.output_dir)
    if refresh_scope == "short" and isinstance(existing_result, dict):
        raw = existing_result.get("raw")
        predictions = existing_result.get("predictions")
        if isinstance(raw, type(None)) or isinstance(predictions, type(None)):
            refresh_scope = "all"

    bootstrap_snapshot = build_live_snapshot(
        raw=None,
        symbols=symbols or ["nf_SN0"],
        use_remote=use_remote,
    )
    history_symbol = history_symbol_from_snapshot(bootstrap_snapshot)

    raw_frame = existing_result.get("raw") if refresh_scope == "short" and isinstance(existing_result, dict) else None
    if isinstance(raw_frame, pd.DataFrame):
        existing_symbol = str(raw_frame.attrs.get("history_symbol") or raw_frame.iloc[-1].get("history_symbol", "") or "").upper()
        if history_symbol and existing_symbol and history_symbol.upper() != existing_symbol:
            refresh_scope = "all"
            raw_frame = None

    if not isinstance(raw_frame, pd.DataFrame):
        raw_frame = load_market_data(
            csv_path,
            prefer_real=not use_demo,
            allow_demo=use_demo,
            real_symbol=history_symbol,
        )
    raw_frame.attrs["history_symbol"] = history_symbol

    live_snapshot = enrich_live_snapshot_with_history(bootstrap_snapshot, raw_frame)
    persist_live_snapshot(live_snapshot)

    if refresh_scope == "short" and isinstance(existing_result, dict):
        result = dict(existing_result)
        result["live_snapshot"] = live_snapshot
        predictions_frame = result.get("predictions")
        if not hasattr(predictions_frame, "empty"):
            result = run_pipeline(
                csv_path=csv_path,
                preset_name=preset_name,
                risk_profile_name=risk_profile_name,
                live_snapshot=live_snapshot,
                use_demo=use_demo,
                optimization_level=optimization_level,
                raw_override=raw_frame,
                real_symbol=history_symbol,
            )
        else:
            scenario_matrix = build_scenario_matrix(
                predictions_frame,  # type: ignore[arg-type]
                raw_frame,  # type: ignore[arg-type]
                risk=result.get("risk_config"),  # type: ignore[arg-type]
                contracts=1,
                live_snapshot=live_snapshot,
            )
            position_risk = build_position_risk_snapshot(
                predictions_frame,  # type: ignore[arg-type]
                risk=result.get("risk_config"),  # type: ignore[arg-type]
                contracts=1,
            )
            result["scenario_matrix"] = scenario_matrix
            result["position_risk"] = position_risk
    else:
        result = run_pipeline(
            csv_path=csv_path,
            preset_name=preset_name,
            risk_profile_name=risk_profile_name,
            live_snapshot=live_snapshot,
            use_demo=use_demo,
            optimization_level=optimization_level,
            raw_override=raw_frame,
            real_symbol=history_symbol,
        )

    live_predictions = build_live_prediction_cards(
        result["raw"],  # type: ignore[index]
        result["predictions"],  # type: ignore[index]
        live_snapshot,
        result.get("horizon_predictions"),  # type: ignore[arg-type]
    )
    evaluated_history = evaluate_prediction_history(paths.output_dir, result["raw"])  # type: ignore[arg-type]
    calibration_profile = build_walk_forward_calibration_profile(
        result["predictions"],  # type: ignore[arg-type]
        result["raw"],  # type: ignore[arg-type]
    )
    calibration_profile.update(build_calibration_profile(evaluated_history))
    live_predictions = apply_history_calibration(live_predictions, calibration_profile)
    latest_raw = result["raw"].iloc[-1] if isinstance(result.get("raw"), pd.DataFrame) and not result["raw"].empty else pd.Series(dtype=float)  # type: ignore[index]
    minute_cols = {"intraday_close", "intraday_high", "intraday_low", "intraday_volume", "intraday_realized_vol"}
    minute_available = isinstance(result.get("raw"), pd.DataFrame) and bool(minute_cols.intersection(result["raw"].columns)) and any(  # type: ignore[index]
        result["raw"][col].notna().any() for col in minute_cols.intersection(result["raw"].columns)  # type: ignore[index]
    )
    live_predictions = build_unified_forecast(
        live_predictions,
        output_dir=paths.output_dir,
        raw=result["raw"],  # type: ignore[arg-type]
        live_snapshot=live_snapshot,
        calibration_profile=calibration_profile,
        hardware_profile=hardware_profile,
        persist=True,
    )
    prediction_history = append_prediction_snapshot(
        output_dir=paths.output_dir,
        live_predictions=live_predictions,
        raw=result["raw"],  # type: ignore[arg-type]
        metrics=result.get("metrics") if isinstance(result.get("metrics"), dict) else None,  # type: ignore[arg-type]
        optimization_summary=result.get("optimization_summary") if isinstance(result.get("optimization_summary"), dict) else None,  # type: ignore[arg-type]
        bandit_summary=result.get("bandit_summary") if isinstance(result.get("bandit_summary"), dict) else None,  # type: ignore[arg-type]
    )
    evaluated_history = evaluate_prediction_history(paths.output_dir, result["raw"])  # type: ignore[arg-type]
    prediction_evaluation_summary = summarize_prediction_evaluation(evaluated_history)
    model_memory = build_model_memory(
        evaluation_summary=prediction_evaluation_summary,
        calibration_profile=calibration_profile,
        backtest_metrics=result.get("metrics") if isinstance(result.get("metrics"), dict) else None,  # type: ignore[arg-type]
        optimization_summary=result.get("optimization_summary") if isinstance(result.get("optimization_summary"), dict) else None,  # type: ignore[arg-type]
        bandit_summary=result.get("bandit_summary") if isinstance(result.get("bandit_summary"), dict) else None,  # type: ignore[arg-type]
    )
    save_model_memory(paths.output_dir, model_memory)
    v2_artifacts = persist_v2_artifacts(
        paths=paths,
        raw=result["raw"],  # type: ignore[arg-type]
        factor_frame=result["factor_frame"],  # type: ignore[arg-type]
        diagnostics=result["diagnostics"],  # type: ignore[arg-type]
        selected_features=list(result.get("selected_features", [])),  # type: ignore[arg-type]
        predictions=result["predictions"],  # type: ignore[arg-type]
        metrics=result.get("metrics") if isinstance(result.get("metrics"), dict) else {},  # type: ignore[arg-type]
        backtest_diagnostics=result.get("backtest_diagnostics") if isinstance(result.get("backtest_diagnostics"), dict) else {},  # type: ignore[arg-type]
        live_snapshot=live_snapshot,
        evaluation_summary=prediction_evaluation_summary,
        calibration_profile=calibration_profile,
        optimization_summary=result.get("optimization_summary") if isinstance(result.get("optimization_summary"), dict) else {},  # type: ignore[arg-type]
        bandit_summary=result.get("bandit_summary") if isinstance(result.get("bandit_summary"), dict) else {},  # type: ignore[arg-type]
        direction_summary=result.get("direction_summary") if isinstance(result.get("direction_summary"), dict) else {},  # type: ignore[arg-type]
    )
    paths.live_predictions_path.parent.mkdir(parents=True, exist_ok=True)
    paths.live_predictions_path.write_text(
        json.dumps(live_predictions, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    result["live_predictions"] = live_predictions
    result["live_snapshot"] = live_snapshot
    result["prediction_history"] = prediction_history
    result["prediction_evaluation"] = evaluated_history
    result["prediction_evaluation_summary"] = prediction_evaluation_summary
    result["calibration_profile"] = calibration_profile
    result["model_memory"] = model_memory
    result["v2_artifacts"] = v2_artifacts
    result["hardware_profile"] = hardware_profile
    return result
