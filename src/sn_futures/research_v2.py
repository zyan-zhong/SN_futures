from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from .config import ProjectPaths
from .prediction_history import load_prediction_history, prediction_evaluation_path
from .runtime import get_user_data_dir


DISCLAIMER = "本内容仅为沪锡期货量化投研参考，不构成任何投资建议，期货交易有风险，投资需谨慎。"


def _now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        numeric = float(value)
    except Exception:
        return default
    return numeric if np.isfinite(numeric) else default


def _json_clean(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_clean(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_clean(item) for item in value]
    if isinstance(value, tuple):
        return [_json_clean(item) for item in value]
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating, float)):
        numeric = float(value)
        return numeric if np.isfinite(numeric) else None
    if isinstance(value, (np.bool_,)):
        return bool(value)
    return value


def _json_dumps(value: Any) -> str:
    return json.dumps(_json_clean(value), ensure_ascii=False, sort_keys=True)


def _hash_payload(payload: Any, length: int = 16) -> str:
    return hashlib.sha1(_json_dumps(payload).encode("utf-8")).hexdigest()[:length]


def open_source_inspirations() -> list[dict[str, str]]:
    return [
        {
            "project": "Microsoft Qlib",
            "url": "https://github.com/microsoft/qlib",
            "used_as": "研究流水线、实验记录、模型注册表、因子诊断的架构参考",
            "license_note": "仅借鉴思想；未复制代码。正式引入依赖前需复核许可证与打包体积。",
        },
        {
            "project": "AI4Finance FinRL",
            "url": "https://github.com/AI4Finance-Foundation/FinRL",
            "used_as": "金融环境、奖励函数和策略决策层设计参考；本系统只用于阈值与仓位，不直接预测价格",
            "license_note": "仅借鉴思想；默认不引入重型 RL 依赖。",
        },
        {
            "project": "FinRL-X / FinRL-Trading",
            "url": "https://github.com/AI4Finance-Foundation/FinRL-Trading",
            "used_as": "实时交易研究系统的状态、动作、日志面板参考；本软件不接入实盘交易接口",
            "license_note": "仅借鉴思想；保持本地仿真与投研参考边界。",
        },
        {
            "project": "Nixtla NeuralForecast",
            "url": "https://github.com/Nixtla/neuralforecast",
            "used_as": "多周期预测接口、候选模型池和样本外排名机制参考",
            "license_note": "暂不默认依赖，避免普通办公电脑和安装包体积压力。",
        },
        {
            "project": "tft-torch",
            "url": "https://github.com/PlaytikaOSS/tft-torch",
            "used_as": "TFT 多变量时序模型思路参考；深度模型只作为候选，不绕过注册表上线",
            "license_note": "仅借鉴思想；GPU 可用时再进入实验档位。",
        },
    ]


@dataclass(frozen=True)
class ResearchStore:
    db_path: Path = get_user_data_dir() / "research_v2.sqlite"

    def connect(self) -> sqlite3.Connection:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.db_path)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        self.ensure_schema(conn)
        return conn

    @staticmethod
    def ensure_schema(conn: sqlite3.Connection) -> None:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS experiments (
                experiment_id TEXT PRIMARY KEY,
                created_at TEXT NOT NULL,
                model_type TEXT NOT NULL,
                horizon TEXT NOT NULL,
                data_version TEXT NOT NULL,
                feature_version TEXT NOT NULL,
                training_window TEXT NOT NULL,
                params_json TEXT NOT NULL,
                metrics_json TEXT NOT NULL,
                validation_json TEXT NOT NULL,
                status TEXT NOT NULL,
                notes TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS model_registry (
                model_id TEXT PRIMARY KEY,
                updated_at TEXT NOT NULL,
                status TEXT NOT NULL,
                model_type TEXT NOT NULL,
                horizon TEXT NOT NULL,
                experiment_id TEXT NOT NULL,
                score REAL NOT NULL,
                metrics_json TEXT NOT NULL,
                health_json TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS data_watermarks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL,
                latest_daily TEXT NOT NULL,
                active_contract TEXT NOT NULL,
                history_symbol TEXT NOT NULL,
                source_mode TEXT NOT NULL,
                quality_score REAL NOT NULL,
                payload_json TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS factor_diagnostics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL,
                feature_version TEXT NOT NULL,
                payload_json TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS contract_liquidity (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL,
                active_contract TEXT NOT NULL,
                payload_json TEXT NOT NULL
            );
            """
        )
        conn.commit()


def build_data_watermark(raw: pd.DataFrame, live_snapshot: dict[str, Any] | None) -> dict[str, Any]:
    latest_row = raw.iloc[-1] if isinstance(raw, pd.DataFrame) and not raw.empty else pd.Series(dtype=object)
    meta = (live_snapshot or {}).get("contract_meta", {}) if isinstance(live_snapshot, dict) else {}
    statuses = (live_snapshot or {}).get("source_status", []) if isinstance(live_snapshot, dict) else []
    quotes = (live_snapshot or {}).get("quotes", []) if isinstance(live_snapshot, dict) else []
    enabled = [row for row in statuses if isinstance(row, dict) and row.get("enabled")]
    successes = [row for row in enabled if row.get("success")]
    from_cache = [row for row in enabled if row.get("from_cache")]
    source_mode = str(latest_row.get("data_source_mode", "") or "")
    minute_data_available = False
    if isinstance(raw, pd.DataFrame) and not raw.empty:
        minute_cols = {"intraday_close", "intraday_high", "intraday_low", "intraday_volume", "intraday_realized_vol"}
        minute_data_available = bool(minute_cols.intersection(raw.columns)) and any(
            raw[col].notna().any() for col in minute_cols.intersection(raw.columns)
        )
    base_quality = _safe_float(latest_row.get("data_quality_score", 0.60), 0.60)
    source_quality = len(successes) / max(len(enabled), 1) if enabled else 0.45
    fallback_penalty = 0.12 if "fallback" in source_mode.lower() else 0.0
    cache_penalty = 0.04 * len(from_cache) / max(len(enabled), 1) if enabled else 0.0
    quality = float(np.clip(0.62 * base_quality + 0.38 * source_quality - fallback_penalty - cache_penalty, 0.05, 1.0))
    latest_daily = ""
    if isinstance(raw, pd.DataFrame) and not raw.empty:
        latest_daily = str(pd.Timestamp(raw.index[-1]).date())
    active_symbol = str(meta.get("active_contract_symbol", "") or meta.get("target_contract_symbol", "")) if isinstance(meta, dict) else ""
    live_quote: dict[str, Any] = {}
    if isinstance(quotes, list):
        quote_rows = [row for row in quotes if isinstance(row, dict)]
        preferred = [row for row in quote_rows if active_symbol and str(row.get("symbol", "")) == active_symbol]
        quote = preferred[0] if preferred else (quote_rows[0] if quote_rows else {})
        latest = _safe_float(quote.get("latest", 0.0), 0.0) if quote else 0.0
        prev_close = _safe_float(quote.get("prev_close", 0.0), 0.0) if quote else 0.0
        change = latest - prev_close if latest > 0 and prev_close > 0 else 0.0
        change_pct = change / prev_close if prev_close > 0 else 0.0
        if latest > 0:
            live_quote = {
                "symbol": str(quote.get("symbol", "")),
                "contract_code": str(meta.get("active_contract", meta.get("target_contract", "SN")) if isinstance(meta, dict) else "SN"),
                "name": str(quote.get("name", "")),
                "latest": latest,
                "prev_close": prev_close,
                "change": change,
                "change_pct": change_pct,
                "open": _safe_float(quote.get("open", 0.0), 0.0),
                "high": _safe_float(quote.get("high", 0.0), 0.0),
                "low": _safe_float(quote.get("low", 0.0), 0.0),
                "volume": _safe_float(quote.get("volume", 0.0), 0.0),
                "open_interest": _safe_float(quote.get("open_interest", 0.0), 0.0),
                "quote_time": str((live_snapshot or {}).get("generated_at", "")),
                "from_cache": any(bool(row.get("from_cache")) for row in statuses if isinstance(row, dict) and row.get("name") == "sina_finance"),
            }
    payload = {
        "created_at": _now_iso(),
        "latest_daily": latest_daily,
        "latest_realtime": str((live_snapshot or {}).get("generated_at", "")) if isinstance(live_snapshot, dict) else "",
        "active_contract": str(meta.get("active_contract", meta.get("target_contract", "SN")) if isinstance(meta, dict) else "SN"),
        "target_contract": str(meta.get("target_contract", "SN") if isinstance(meta, dict) else "SN"),
        "history_symbol": str(meta.get("history_symbol", latest_row.get("history_symbol", "SN0")) if isinstance(meta, dict) else latest_row.get("history_symbol", "SN0")),
        "requested_history_symbol": str(meta.get("requested_history_symbol", "") if isinstance(meta, dict) else ""),
        "source_mode": source_mode,
        "using_fallback": "fallback" in source_mode.lower(),
        "is_real_data_only": not any(str(latest_row.get("data_source_mode", "")).startswith(mode) for mode in ("demo", "synthetic")),
        "demo_blocked_reason": "实盘模式禁止使用演示数据；真实数据失败时仅显示失败原因和缓存状态。",
        "minute_data_available": minute_data_available,
        "source_status": statuses,
        "quality_score": quality,
        "rate_limit_policy": (live_snapshot or {}).get("rate_limit_policy", {}) if isinstance(live_snapshot, dict) else {},
        "live_quote": live_quote,
        "live_overlay_used": bool(live_quote),
        "contract_selection_reason": str(meta.get("selection_rule", "") if isinstance(meta, dict) else ""),
        "disclaimer": DISCLAIMER,
    }
    return _json_clean(payload)


def build_factor_diagnostics_v2(
    diagnostics: pd.DataFrame,
    selected_features: list[str],
    factor_frame: pd.DataFrame,
) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    if isinstance(diagnostics, pd.DataFrame) and not diagnostics.empty:
        diag = diagnostics.copy()
        for _, row in diag.head(80).iterrows():
            factor = str(row.get("factor", ""))
            coverage = 0.0
            missing_rate = 1.0
            if factor and isinstance(factor_frame, pd.DataFrame) and factor in factor_frame.columns:
                coverage = float(factor_frame[factor].notna().mean())
                missing_rate = 1.0 - coverage
            rows.append(
                {
                    "factor": factor,
                    "selected": factor in set(selected_features),
                    "ic": _safe_float(row.get("ic", row.get("IC", 0.0))),
                    "icir": _safe_float(row.get("icir", row.get("ICIR", 0.0))),
                    "p_value": _safe_float(row.get("p_value", row.get("pvalue", 1.0)), 1.0),
                    "vif": _safe_float(row.get("vif", 0.0)),
                    "coverage": coverage,
                    "missing_rate": missing_rate,
                    "group": str(row.get("group", "")),
                }
            )
    selected_rows = [row for row in rows if row["selected"]]
    return {
        "created_at": _now_iso(),
        "feature_version": _hash_payload({"selected_features": selected_features, "rows": rows[:30]}),
        "selected_count": len(selected_features),
        "diagnostic_count": len(rows),
        "selected_features": selected_features,
        "coverage_mean": float(np.mean([row["coverage"] for row in selected_rows])) if selected_rows else 0.0,
        "ic_abs_mean": float(np.mean([abs(row["ic"]) for row in selected_rows])) if selected_rows else 0.0,
        "max_vif": float(max([row["vif"] for row in selected_rows], default=0.0)),
        "rows": rows,
        "rules": {
            "split": "严格时间序列切分，禁止随机切分",
            "normalization": "滚动窗口标准化，禁止全样本标准化",
            "selection": "IC/ICIR/VIF/覆盖率联合筛选，结果仅作为投研参考",
        },
        "disclaimer": DISCLAIMER,
    }


def build_model_health_v2(
    metrics: dict[str, Any] | None,
    backtest_diagnostics: dict[str, Any] | None,
    evaluation_summary: dict[str, Any] | None,
    data_watermark: dict[str, Any] | None,
    calibration_profile: dict[str, Any] | None = None,
) -> dict[str, Any]:
    metrics = metrics or {}
    diagnostics = backtest_diagnostics or {}
    rolling = diagnostics.get("rolling_rows", []) if isinstance(diagnostics, dict) else []
    latest_roll = rolling[0] if isinstance(rolling, list) and rolling and isinstance(rolling[0], dict) else {}
    eval_rows = evaluation_summary.get("by_horizon", []) if isinstance(evaluation_summary, dict) else []
    tomorrow_eval = next((row for row in eval_rows if isinstance(row, dict) and row.get("horizon_key") == "tomorrow"), {})
    tomorrow_calibration = (calibration_profile or {}).get("tomorrow", {}) if isinstance(calibration_profile, dict) else {}
    effective_sample_count = int(_safe_float((evaluation_summary or {}).get("sample_count", 0)))
    direction_sample_count = int(_safe_float(tomorrow_eval.get("direction_sample_count", tomorrow_calibration.get("sample_count", 0))))
    true_direction_hit = _safe_float(latest_roll.get("direction_hit_rate", 0.0))
    learning_quality = _safe_float(latest_roll.get("direction_learning_quality", true_direction_hit))
    direction_active_rate = _safe_float(latest_roll.get("direction_active_rate", 0.0))
    neutral_rate = _safe_float(latest_roll.get("neutral_rate", 1.0 - direction_active_rate))
    range_coverage = _safe_float(
        tomorrow_eval.get("range_hit_rate", tomorrow_calibration.get("range_hit_rate", 0.0))
    )
    center_error = _safe_float(
        tomorrow_eval.get("center_mae_pct", tomorrow_calibration.get("center_mae_pct", latest_roll.get("avg_abs_error", 0.0)))
    )
    sharpe_score = float(np.clip(max(_safe_float(metrics.get("sharpe", 0.0)), 0.0) / 2.8, 0.0, 1.0))
    drawdown_score = float(np.clip(1.0 - abs(_safe_float(metrics.get("max_drawdown", 0.0))) / 0.15, 0.0, 1.0))
    data_trust = _safe_float((data_watermark or {}).get("quality_score", 0.50), 0.50)
    direction_score = float(np.clip(0.65 * true_direction_hit + 0.35 * learning_quality, 0.0, 1.0))
    interval_score = float(np.clip(0.55 * range_coverage + 0.45 * (1.0 - center_error / 0.08), 0.0, 1.0))
    risk_score = float(np.clip(0.55 * sharpe_score + 0.45 * drawdown_score, 0.0, 1.0))
    overall = float(np.clip(0.34 * direction_score + 0.22 * interval_score + 0.22 * risk_score + 0.22 * data_trust, 0.0, 1.0))
    return {
        "created_at": _now_iso(),
        "overall_score": overall,
        "true_direction_hit_rate": true_direction_hit,
        "direction_active_rate": direction_active_rate,
        "neutral_rate": neutral_rate,
        "direction_learning_quality": learning_quality,
        "effective_sample_count": effective_sample_count,
        "direction_sample_count": direction_sample_count,
        "recent_validation_window": "最近120条已兑现预测；仅强方向样本计入方向命中。",
        "direction_gate_status": "待刷新",
        "interval_coverage_rate": range_coverage,
        "center_mae_pct": center_error,
        "risk_adjusted_score": risk_score,
        "data_trust_score": data_trust,
        "sharpe": _safe_float(metrics.get("sharpe", 0.0)),
        "max_drawdown": _safe_float(metrics.get("max_drawdown", 0.0)),
        "win_rate": _safe_float(metrics.get("win_rate", 0.0)),
        "reward_risk_ratio": _safe_float(metrics.get("reward_risk_ratio", 0.0)),
        "calibration_profile": calibration_profile or {},
        "status_note": "健康度基于真实可兑现回测和历史预测验证，不代表未来收益或准确率承诺。",
        "disclaimer": DISCLAIMER,
    }


def prediction_history_view(output_dir: Path, status: str = "verified") -> list[dict[str, Any]]:
    status = status.lower().strip()
    if status == "verified":
        path = prediction_evaluation_path(output_dir)
        if not path.exists():
            return []
        try:
            frame = pd.read_csv(path)
        except Exception:
            return []
        if "realized_close" in frame.columns:
            frame = frame[pd.to_numeric(frame["realized_close"], errors="coerce").notna()]
        if "horizon_key" in frame.columns:
            # Intraday horizons require minute/snapshot realized prices. Older
            # daily-only validations are deliberately hidden from verified metrics.
            intraday = {"next_5m", "next_15m", "next_30m", "next_hour"}
            frame = frame[~frame["horizon_key"].astype(str).isin(intraday)]
        sort_col = "target_end" if "target_end" in frame.columns else "generated_at"
        return _json_clean(frame.sort_values(sort_col).tail(300).to_dict(orient="records"))

    history = load_prediction_history(output_dir, max_rows=1000)
    if history.empty:
        return []
    if "realized_close" in history.columns:
        history = history[pd.to_numeric(history["realized_close"], errors="coerce").isna()]
    sort_col = "generated_at" if "generated_at" in history.columns else history.columns[0]
    return _json_clean(history.sort_values(sort_col).tail(300).to_dict(orient="records"))


def evaluate_decision_policy(predictions: pd.DataFrame, bandit_summary: dict[str, Any] | None = None) -> dict[str, Any]:
    if not isinstance(predictions, pd.DataFrame) or predictions.empty:
        return {"created_at": _now_iso(), "sample_count": 0, "actions": [], "disclaimer": DISCLAIMER}
    work = predictions.copy()
    action_col = "bandit_action_label" if "bandit_action_label" in work.columns else "bandit_action"
    reward_col = "bandit_reward_proxy"
    rows = []
    if action_col in work.columns and reward_col in work.columns:
        for action, group in work.groupby(action_col):
            rows.append(
                {
                    "action": str(action),
                    "sample_count": int(len(group)),
                    "mean_reward_proxy": _safe_float(pd.to_numeric(group[reward_col], errors="coerce").mean()),
                    "recent_reward_proxy": _safe_float(pd.to_numeric(group[reward_col].tail(30), errors="coerce").mean()),
                    "position_scale_mean": _safe_float(pd.to_numeric(group.get("bandit_position_scale", pd.Series(dtype=float)), errors="coerce").mean(), 1.0),
                }
            )
    return {
        "created_at": _now_iso(),
        "policy_version": (bandit_summary or {}).get("policy_version", "linucb_sn_v1"),
        "sample_count": int(len(work)),
        "latest_action": (bandit_summary or {}).get("latest_action", ""),
        "latest_thresholds": {
            "confidence": (bandit_summary or {}).get("latest_confidence_threshold"),
            "prob_up": (bandit_summary or {}).get("latest_prob_up_threshold"),
            "prob_down": (bandit_summary or {}).get("latest_prob_down_threshold"),
            "position_scale": (bandit_summary or {}).get("latest_position_scale"),
        },
        "actions": rows,
        "guardrail": "Bandit 只允许调节阈值、仓位、暂停信号和风控距离，不直接修改价格中枢。",
        "disclaimer": DISCLAIMER,
    }


def persist_v2_artifacts(
    *,
    paths: ProjectPaths,
    raw: pd.DataFrame,
    factor_frame: pd.DataFrame,
    diagnostics: pd.DataFrame,
    selected_features: list[str],
    predictions: pd.DataFrame,
    metrics: dict[str, Any],
    backtest_diagnostics: dict[str, Any],
    live_snapshot: dict[str, Any] | None,
    evaluation_summary: dict[str, Any],
    calibration_profile: dict[str, Any],
    optimization_summary: dict[str, Any] | None,
    bandit_summary: dict[str, Any] | None,
    direction_summary: dict[str, Any] | None = None,
) -> dict[str, Any]:
    data_watermark = build_data_watermark(raw, live_snapshot)
    factor_payload = build_factor_diagnostics_v2(diagnostics, selected_features, factor_frame)
    health = build_model_health_v2(metrics, backtest_diagnostics, evaluation_summary, data_watermark, calibration_profile)
    decision_policy = evaluate_decision_policy(predictions, bandit_summary)
    training_config = (optimization_summary or {}).get("best_config", {}) if isinstance(optimization_summary, dict) else {}
    experiment_payload = {
        "model_type": "direction_first_stacking_pool",
        "horizon": "tomorrow",
        "data_version": _hash_payload(data_watermark),
        "feature_version": factor_payload["feature_version"],
        "training_window": str(training_config.get("train_window", "")),
        "params": training_config,
        "metrics": metrics,
        "validation": health,
    }
    experiment_id = "exp_" + _hash_payload(experiment_payload)
    score = _safe_float((optimization_summary or {}).get("best_score", health.get("overall_score", 0.0)), _safe_float(health.get("overall_score", 0.0)))
    registry_status = "active" if health["overall_score"] >= 0.52 and data_watermark["quality_score"] >= 0.50 else "candidate"
    if isinstance(optimization_summary, dict) and optimization_summary.get("rollback_applied"):
        registry_status = "rollback"
    model_id = "sn_v2_" + _hash_payload({"experiment_id": experiment_id, "training_config": training_config}, 12)
    registry_record = {
        "model_id": model_id,
        "updated_at": _now_iso(),
        "status": registry_status,
        "model_type": "direction_first_stacking_pool",
        "horizon": "tomorrow",
        "experiment_id": experiment_id,
        "score": score,
        "metrics": metrics,
        "health": health,
    }

    store = ResearchStore()
    with store.connect() as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO experiments
            (experiment_id, created_at, model_type, horizon, data_version, feature_version, training_window,
             params_json, metrics_json, validation_json, status, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                experiment_id,
                _now_iso(),
                experiment_payload["model_type"],
                experiment_payload["horizon"],
                experiment_payload["data_version"],
                experiment_payload["feature_version"],
                experiment_payload["training_window"],
                _json_dumps(experiment_payload["params"]),
                _json_dumps(metrics),
                _json_dumps(health),
                registry_status,
                "V2 Qlib-style experiment record; local-only research artifact.",
            ),
        )
        conn.execute(
            """
            INSERT OR REPLACE INTO model_registry
            (model_id, updated_at, status, model_type, horizon, experiment_id, score, metrics_json, health_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                model_id,
                registry_record["updated_at"],
                registry_status,
                registry_record["model_type"],
                registry_record["horizon"],
                experiment_id,
                score,
                _json_dumps(metrics),
                _json_dumps(health),
            ),
        )
        conn.execute(
            """
            INSERT INTO data_watermarks
            (created_at, latest_daily, active_contract, history_symbol, source_mode, quality_score, payload_json)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                _now_iso(),
                data_watermark.get("latest_daily", ""),
                data_watermark.get("active_contract", ""),
                data_watermark.get("history_symbol", ""),
                data_watermark.get("source_mode", ""),
                data_watermark.get("quality_score", 0.0),
                _json_dumps(data_watermark),
            ),
        )
        conn.execute(
            "INSERT INTO factor_diagnostics (created_at, feature_version, payload_json) VALUES (?, ?, ?)",
            (_now_iso(), factor_payload["feature_version"], _json_dumps(factor_payload)),
        )
        meta = (live_snapshot or {}).get("contract_meta", {}) if isinstance(live_snapshot, dict) else {}
        if isinstance(meta, dict):
            conn.execute(
                "INSERT INTO contract_liquidity (created_at, active_contract, payload_json) VALUES (?, ?, ?)",
                (_now_iso(), str(meta.get("active_contract", "")), _json_dumps(meta.get("liquidity_table", []))),
            )
        conn.commit()

    v2_payload = {
        "open_source_inspirations": open_source_inspirations(),
        "data_watermark": data_watermark,
        "factor_diagnostics": factor_payload,
        "model_health": health,
        "model_registry": [registry_record],
        "latest_experiment": {"experiment_id": experiment_id, **experiment_payload, "status": registry_status},
        "decision_policy": decision_policy,
        "direction_first": direction_summary or {},
        "history_verified": prediction_history_view(paths.output_dir, "verified")[-80:],
        "history_pending": prediction_history_view(paths.output_dir, "pending")[-80:],
        "public_interfaces": {
            "GET /api/open_source/inspirations": "open_source_inspirations",
            "POST /api/experiments/run": "latest_experiment",
            "GET /api/models/registry": "model_registry",
            "GET /api/models/health": "model_health",
            "GET /api/factors/diagnostics": "factor_diagnostics",
            "POST /api/decision_policy/evaluate": "decision_policy",
            "GET /api/predictions/history?status=verified|pending": "history_verified/history_pending",
            "GET /api/data/watermark": "data_watermark",
            "GET /api/hardware/profile": "hardware_profile",
            "GET /api/learning/status": "learning_status",
            "GET /api/reports/manifest": "reports_manifest",
            "GET /api/reports/content?type=daily|weekly|monthly|event": "report_content",
        },
        "disclaimer": DISCLAIMER,
    }
    paths.output_dir.mkdir(parents=True, exist_ok=True)
    (paths.output_dir / "sn_v2_artifacts.json").write_text(json.dumps(_json_clean(v2_payload), ensure_ascii=False, indent=2), encoding="utf-8")
    return _json_clean(v2_payload)


def load_v2_artifacts(output_dir: Path | None = None) -> dict[str, Any]:
    path = (output_dir or ProjectPaths().output_dir) / "sn_v2_artifacts.json"
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}
