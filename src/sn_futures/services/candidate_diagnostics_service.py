from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping

import numpy as np
import pandas as pd

from ..api.json_utils import sanitize_for_json
from ..runtime import get_user_output_dir
from .oof_trace_service import get_oof_trace_summary


DEFAULT_HORIZONS = ("1d", "3d", "5d", "10d", "20d")


def _output_dir() -> Path:
    return get_user_output_dir()


def _read_json(path: Path) -> Any:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return default
    return parsed if np.isfinite(parsed) else default


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def _records_from_candidate_status(status: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    out: dict[str, Mapping[str, Any]] = {}
    for record in status.get("records") or []:
        if isinstance(record, Mapping):
            horizon = str(record.get("horizon") or "")
            if horizon:
                out[horizon] = record
    return out


def _promotion_failures(report: Mapping[str, Any]) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for decision in report.get("decisions") or []:
        if isinstance(decision, Mapping):
            horizon = str(decision.get("horizon") or "")
            reasons = [str(item) for item in decision.get("failure_reasons") or [] if str(item)]
            if horizon:
                out[horizon] = reasons
    return out


def _load_walk_forward(horizon: str) -> Mapping[str, Any]:
    payload = _read_json(_output_dir() / "walk_forward" / f"wf_{horizon}.json")
    return payload if isinstance(payload, Mapping) else {}


def _load_manifest() -> Mapping[str, Any]:
    payload = _read_json(_output_dir() / "training_dataset_manifest.json")
    return payload if isinstance(payload, Mapping) else {}


def _load_candidate_status() -> Mapping[str, Any]:
    payload = _read_json(_output_dir() / "model_registry" / "candidate_training_status.json")
    return payload if isinstance(payload, Mapping) else {}


def _load_promotion_report() -> Mapping[str, Any]:
    payload = _read_json(_output_dir() / "model_registry" / "promotion_report.json")
    return payload if isinstance(payload, Mapping) else {}


def _load_feature_coverage() -> Mapping[str, Any]:
    payload = _read_json(_output_dir() / "feature_coverage_report.json")
    return payload if isinstance(payload, Mapping) else {}


def _dataset_path(manifest: Mapping[str, Any], horizon: str) -> Path | None:
    paths = manifest.get("dataset_paths") or {}
    if not isinstance(paths, Mapping):
        return None
    raw = paths.get(horizon)
    if not raw:
        return None
    path = Path(str(raw))
    return path if path.exists() else None


def _load_dataset(manifest: Mapping[str, Any], horizon: str) -> pd.DataFrame:
    path = _dataset_path(manifest, horizon)
    if path is None:
        return pd.DataFrame()
    try:
        if path.suffix.lower() == ".parquet":
            return pd.read_parquet(path)
        return pd.read_csv(path)
    except Exception:
        return pd.DataFrame()


def _label_distribution(manifest: Mapping[str, Any], horizon: str) -> dict[str, int]:
    all_dist = manifest.get("label_distribution_by_horizon") or {}
    raw = all_dist.get(horizon) if isinstance(all_dist, Mapping) else {}
    if not isinstance(raw, Mapping):
        return {"up": 0, "down": 0, "flat": 0}
    return {
        "up": _safe_int(raw.get("1"), 0),
        "down": _safe_int(raw.get("-1"), 0),
        "flat": _safe_int(raw.get("0"), 0),
    }


def _return_summary(manifest: Mapping[str, Any], horizon: str) -> dict[str, Any]:
    all_summary = manifest.get("return_summary_by_horizon") or {}
    raw = all_summary.get(horizon) if isinstance(all_summary, Mapping) else {}
    return dict(raw) if isinstance(raw, Mapping) else {}


def _confusion_matrix_proxy(metrics: Mapping[str, Any], manifest: Mapping[str, Any], horizon: str) -> dict[str, Any]:
    distribution = _label_distribution(manifest, horizon)
    up_count = max(distribution["up"], 0)
    down_count = max(distribution["down"], 0)
    flat_count = max(distribution["flat"], 0)
    recall_up = _safe_float(metrics.get("recall_up"), 0.0)
    recall_down = _safe_float(metrics.get("recall_down"), 0.0)
    precision_up = _safe_float(metrics.get("precision_up"), 0.0)
    precision_down = _safe_float(metrics.get("precision_down"), 0.0)
    tp_up = recall_up * up_count
    tp_down = recall_down * down_count
    fp_up = (tp_up / precision_up - tp_up) if precision_up > 1e-12 else 0.0
    fp_down = (tp_down / precision_down - tp_down) if precision_down > 1e-12 else 0.0
    total = max(up_count + down_count + flat_count, 1)
    return {
        "source": "estimated_from_aggregate_metrics",
        "note_zh": "当前 walk-forward 产物未保存逐样本预测，因此混淆矩阵由 precision/recall 与标签分布估算；下一轮应保存逐样本验证轨迹以便精确归因。",
        "label_distribution": distribution,
        "estimated": {
            "true_up_pred_up": round(tp_up, 2),
            "true_down_pred_down": round(tp_down, 2),
            "false_up": round(fp_up, 2),
            "false_down": round(fp_down, 2),
        },
        "recall_up": recall_up,
        "recall_down": recall_down,
        "false_up_rate": float(fp_up / total),
        "false_down_rate": float(fp_down / total),
    }


def _calibration_bins_from_folds(folds: list[Mapping[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for fold in folds:
        metrics = fold.get("metrics") if isinstance(fold.get("metrics"), Mapping) else {}
        rows.append(
            {
                "bin": f"fold_{fold.get('fold', len(rows) + 1)}",
                "predicted_probability_mean": None,
                "realized_up_rate": None,
                "sample_count": _safe_int(metrics.get("sample_count"), 0),
                "brier_contribution": _safe_float(metrics.get("brier_score"), 0.0),
                "calibration_error": _safe_float(metrics.get("calibration_error"), 0.0),
                "note_zh": "缺少逐样本概率，当前展示 fold 级校准误差；不是概率 decile。",
            }
        )
    return rows


def _confidence_deciles_proxy(metrics: Mapping[str, Any]) -> list[dict[str, Any]]:
    coverage = _safe_float(metrics.get("coverage_rate"), 0.0)
    accuracy = _safe_float(metrics.get("directional_accuracy"), 0.0)
    expectancy = _safe_float(metrics.get("cost_adjusted_expectancy"), 0.0)
    return [
        {
            "bucket": "top_10pct_confidence",
            "coverage": min(coverage, 0.10),
            "accuracy": accuracy if coverage >= 0.10 else None,
            "average_return": None,
            "cost_adjusted_expectancy": expectancy if coverage >= 0.10 else None,
            "note_zh": "未保存逐样本 confidence；以整体 covered signal 指标代理，需保存验证轨迹后精确计算。",
        },
        {
            "bucket": "top_20pct_confidence",
            "coverage": min(coverage, 0.20),
            "accuracy": accuracy if coverage >= 0.20 else None,
            "average_return": None,
            "cost_adjusted_expectancy": expectancy if coverage >= 0.20 else None,
            "note_zh": "未保存逐样本 confidence；以整体 covered signal 指标代理，需保存验证轨迹后精确计算。",
        },
        {
            "bucket": "covered_signals_all",
            "coverage": coverage,
            "accuracy": accuracy,
            "average_return": None,
            "cost_adjusted_expectancy": expectancy,
            "note_zh": "这是 candidate 实际出信号覆盖样本的整体表现。",
        },
    ]


def _return_bucket_performance(frame: pd.DataFrame) -> list[dict[str, Any]]:
    if frame.empty or "y_return" not in frame.columns:
        return []
    returns = pd.to_numeric(frame["y_return"], errors="coerce").dropna()
    if returns.empty:
        return []
    try:
        buckets = pd.qcut(returns, q=5, duplicates="drop")
    except Exception:
        return []
    grouped = returns.groupby(buckets, observed=True)
    return [
        {
            "bucket": str(bucket),
            "sample_count": int(values.count()),
            "mean_return": float(values.mean()),
            "abs_mean_return": float(values.abs().mean()),
        }
        for bucket, values in grouped
    ]


def _regime_performance(frame: pd.DataFrame, metrics: Mapping[str, Any]) -> list[dict[str, Any]]:
    if frame.empty or "regime_label" not in frame.columns:
        return [{"regime": "UNKNOWN", "sample_count": 0, "message_zh": "训练数据缺少 regime_label，无法做 regime 分层。"}]
    counts = frame["regime_label"].fillna("UNKNOWN").astype(str).value_counts()
    rows: list[dict[str, Any]] = []
    for regime, count in counts.head(12).items():
        row = {
            "regime": regime,
            "sample_count": int(count),
            "sample_enough": bool(count >= 80),
            "directional_accuracy": _safe_float(metrics.get("directional_accuracy"), 0.0) if count >= 80 else None,
            "cost_adjusted_expectancy": _safe_float(metrics.get("cost_adjusted_expectancy"), 0.0) if count >= 80 else None,
            "message_zh": "" if count >= 80 else "样本不足，不能可靠判断该 regime 下的模型表现。",
        }
        rows.append(row)
    return rows


def _drawdown_attribution(wf: Mapping[str, Any], frame: pd.DataFrame) -> dict[str, Any]:
    folds = [fold for fold in wf.get("folds") or [] if isinstance(fold, Mapping)]
    if not folds:
        return {"message_zh": "缺少 walk-forward folds，无法定位回撤窗口。"}
    worst = min(folds, key=lambda item: _safe_float((item.get("metrics") or {}).get("max_drawdown_proxy"), 0.0))
    validation_start = str(worst.get("validation_start") or "")
    validation_end = str(worst.get("validation_end") or "")
    regime = "UNKNOWN"
    if not frame.empty and "label_start_time" in frame.columns and "regime_label" in frame.columns:
        dates = pd.to_datetime(frame["label_start_time"], errors="coerce")
        mask = (dates >= pd.to_datetime(validation_start, errors="coerce")) & (dates <= pd.to_datetime(validation_end, errors="coerce"))
        values = frame.loc[mask, "regime_label"].dropna().astype(str)
        if not values.empty:
            regime = str(values.mode().iloc[0])
    return {
        "fold": worst.get("fold"),
        "validation_start": validation_start,
        "validation_end": validation_end,
        "max_drawdown_proxy": (worst.get("metrics") or {}).get("max_drawdown_proxy"),
        "dominant_regime": regime,
        "error_signal_direction": "无法精确还原；当前产物未保存逐样本信号方向。",
        "event_or_high_vol_window": "HIGH_VOL" in regime or "EVENT" in regime,
    }


def _feature_stability(wf: Mapping[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    aggregate = wf.get("feature_importance") if isinstance(wf.get("feature_importance"), list) else []
    top = [dict(item) for item in aggregate[:12] if isinstance(item, Mapping)]
    per_feature: dict[str, list[float]] = {}
    for fold in wf.get("folds") or []:
        if not isinstance(fold, Mapping):
            continue
        for item in fold.get("feature_importance") or []:
            if isinstance(item, Mapping):
                feature = str(item.get("feature") or "")
                if feature:
                    per_feature.setdefault(feature, []).append(_safe_float(item.get("importance"), 0.0))
    unstable: list[dict[str, Any]] = []
    for feature, values in per_feature.items():
        if len(values) < 2:
            continue
        mean = float(np.mean(values))
        std = float(np.std(values))
        cv = std / max(abs(mean), 1e-9)
        if cv > 1.0 and mean > 0:
            unstable.append({"feature": feature, "mean_importance": mean, "stability_cv": cv})
    unstable = sorted(unstable, key=lambda item: item["stability_cv"], reverse=True)[:12]
    return top, unstable


def _label_difficulty(manifest: Mapping[str, Any], frame: pd.DataFrame, horizon: str) -> dict[str, Any]:
    distribution = _label_distribution(manifest, horizon)
    summary = _return_summary(manifest, horizon)
    low_return_ratio = None
    if not frame.empty and "y_return" in frame.columns:
        returns = pd.to_numeric(frame["y_return"], errors="coerce").abs().dropna()
        if not returns.empty:
            low_return_ratio = float((returns < 0.002).mean())
    total = max(sum(distribution.values()), 1)
    return {
        "class_distribution": distribution,
        "up_ratio": float(distribution["up"] / total),
        "down_ratio": float(distribution["down"] / total),
        "flat_ratio": float(distribution["flat"] / total),
        "return_summary": summary,
        "low_return_noise_ratio": low_return_ratio,
        "diagnosis_zh": _diagnose_label_difficulty(distribution, low_return_ratio),
    }


def _diagnose_label_difficulty(distribution: Mapping[str, int], low_return_ratio: float | None) -> str:
    total = max(sum(distribution.values()), 1)
    imbalance = max(distribution.values() or [0]) / total
    notes: list[str] = []
    if imbalance > 0.60:
        notes.append("方向类别偏斜，朴素方向阈值较难显著超越。")
    if low_return_ratio is not None and low_return_ratio > 0.35:
        notes.append("低波动/小收益样本占比较高，方向标签噪声偏大。")
    return "；".join(notes) if notes else "标签分布未显示极端异常，但仍需结合逐样本错误轨迹验证。"


def _diagnosis_for_horizon(
    horizon: str,
    failure_reasons: list[str],
    metrics: Mapping[str, Any],
    label_difficulty: Mapping[str, Any],
    feature_top: list[dict[str, Any]],
    feature_unstable: list[dict[str, Any]],
) -> tuple[list[str], list[str]]:
    diagnosis: list[str] = []
    actions: list[str] = []
    if any("方向准确率" in item for item in failure_reasons):
        diagnosis.append("方向边际不足：candidate 没有稳定超过朴素方向阈值，说明当前技术/事件因子对该周期方向信息不足或标签噪声偏大。")
        actions.append("增加方向优先标签过滤：剔除低绝对收益/低波动样本，先训练 edge/no-trade，再训练 up/down。")
    if any("Brier" in item for item in failure_reasons) or _safe_float(metrics.get("brier_score"), 0.0) > 0.24:
        diagnosis.append("概率校准不足：Brier 偏高，概率排序和真实兑现率不稳定。")
        actions.append("保存逐样本验证概率，按时间 fold 做 isotonic/sigmoid 对比，并以 ECE/Brier 选择校准器。")
    if any("成本后期望" in item for item in failure_reasons):
        diagnosis.append("成本后期望为负：3d 等周期的信号覆盖样本不足以覆盖手续费、滑点和错误方向损失。")
        actions.append("提高 selective prediction 门槛，增加最小 edge/最小预期收益过滤，并单独评估强信号子集。")
    if any("回撤" in item for item in failure_reasons):
        diagnosis.append("风险集中：中长周期方向命中率不低，但错误窗口亏损集中，回撤代理超过 promotion gate。")
        actions.append("加入波动 regime 风控：高波/事件窗口降仓或禁用信号，并加入 ATR/trailing stop 的 walk-forward 风险约束。")
    if feature_unstable:
        diagnosis.append("特征稳定性不足：部分高重要性因子在 fold 间波动大，可能是噪声或阶段性有效。")
        actions.append("做 feature stability selection：仅保留跨 fold 稳定的技术/趋势因子，事件因子不足时不宣称增益。")
    if label_difficulty.get("low_return_noise_ratio") is not None and _safe_float(label_difficulty.get("low_return_noise_ratio"), 0.0) > 0.35:
        diagnosis.append("标签噪声偏高：低收益区间过多会让方向分类接近随机。")
        actions.append("引入 triple-barrier/meta-labeling 作为强信号筛选，而不是直接预测所有样本方向。")
    if not feature_top:
        diagnosis.append("缺少可解释特征重要性，无法判断因子贡献。")
    if not diagnosis:
        diagnosis.append("主要指标未触发单一明显问题，需保存逐样本预测轨迹做更细粒度错误归因。")
    actions.append("下一轮训练必须保存 out-of-fold prediction trace，用于精确混淆矩阵、confidence decile、regime attribution。")
    return diagnosis, list(dict.fromkeys(actions))


def build_candidate_diagnostics_report() -> dict[str, Any]:
    status = _load_candidate_status()
    manifest = _load_manifest()
    promotion = _load_promotion_report()
    feature_coverage = _load_feature_coverage()

    if not status:
        return sanitize_for_json(
            {
                "status": "no_candidate",
                "message_zh": "暂无 candidate 训练结果，无法做失败归因。",
                "horizons": {},
                "global_findings": ["未发现 candidate_model_registry 或 candidate_training_status。"],
                "recommended_research_plan": ["先构建真实训练数据集，再训练 candidate，并保存 walk-forward 逐样本验证轨迹。"],
                "active_written": False,
                "customer_prediction_generated": False,
            }
        )

    metrics_by_horizon = status.get("metrics_by_horizon") if isinstance(status.get("metrics_by_horizon"), Mapping) else {}
    failures = _promotion_failures(promotion)
    records = _records_from_candidate_status(status)
    horizons: dict[str, Any] = {}

    for horizon in DEFAULT_HORIZONS:
        wf = _load_walk_forward(horizon)
        metrics = dict(metrics_by_horizon.get(horizon) or wf.get("metrics") or {})
        folds = [fold for fold in wf.get("folds") or [] if isinstance(fold, Mapping)]
        frame = _load_dataset(manifest, horizon)
        feature_top, feature_unstable = _feature_stability(wf)
        label_difficulty = _label_difficulty(manifest, frame, horizon)
        failure_reasons = failures.get(horizon, [])
        diagnosis, actions = _diagnosis_for_horizon(
            horizon,
            failure_reasons,
            metrics,
            label_difficulty,
            feature_top,
            feature_unstable,
        )
        oof_summary = get_oof_trace_summary(horizon)
        has_oof = oof_summary.get("status") == "success" and int(oof_summary.get("row_count") or 0) > 0
        horizons[horizon] = {
            "failure_reasons": failure_reasons,
            "metric_summary": metrics,
            "fold_metrics": [
                {
                    "fold": fold.get("fold"),
                    "train_start": fold.get("train_start"),
                    "train_end": fold.get("train_end"),
                    "validation_start": fold.get("validation_start"),
                    "validation_end": fold.get("validation_end"),
                    "train_samples": fold.get("train_samples"),
                    "validation_samples": fold.get("validation_samples"),
                    "purged_samples": fold.get("purged_samples"),
                    "embargo_samples": fold.get("embargo_samples"),
                    "metrics": fold.get("metrics", {}),
                }
                for fold in folds
            ],
            "oof_trace_summary": oof_summary,
            "confusion_matrix": oof_summary.get("confusion_matrix") if has_oof else _confusion_matrix_proxy(metrics, manifest, horizon),
            "calibration_bins": oof_summary.get("calibration_bins") if has_oof else _calibration_bins_from_folds(folds),
            "confidence_deciles": oof_summary.get("confidence_deciles") if has_oof else _confidence_deciles_proxy(metrics),
            "top_confidence_metrics": {
                "top_10pct": oof_summary.get("top_10pct") if has_oof else {},
                "top_20pct": oof_summary.get("top_20pct") if has_oof else {},
            },
            "return_bucket_performance": _return_bucket_performance(frame),
            "regime_performance": oof_summary.get("regime_error_hotspots") if has_oof else _regime_performance(frame, metrics),
            "drawdown_attribution": {
                "samples": oof_summary.get("drawdown_contribution_samples", []),
                "source": "oof_trace",
            } if has_oof else _drawdown_attribution(wf, frame),
            "high_confidence_wrong_samples": oof_summary.get("high_confidence_wrong_samples", []) if has_oof else [],
            "feature_importance_top": feature_top,
            "feature_importance_unstable": feature_unstable,
            "label_difficulty": label_difficulty,
            "record": records.get(horizon, {}),
            "error_diagnosis_zh": diagnosis,
            "next_actions_zh": actions,
        }

    all_failures = [reason for item in horizons.values() for reason in item.get("failure_reasons", [])]
    global_findings = []
    if any("方向准确率" in item for item in all_failures):
        global_findings.append("短周期方向边际不足，当前因子集未稳定超过朴素方向阈值。")
    if any("Brier" in item for item in all_failures):
        global_findings.append("1d/3d 概率误差偏高，概率校准需要优先处理。")
    if any("回撤" in item for item in all_failures):
        global_findings.append("5d/10d/20d 的主要阻断是回撤风险，不是单纯方向命中率。")
    if not feature_coverage:
        global_findings.append("未找到完整 feature coverage 报告；基本面/外盘/库存覆盖仍需单独审计。")
    if manifest.get("sample_data_used") or manifest.get("baseline_used"):
        global_findings.append("数据集 manifest 显示 sample/baseline 标记异常，不能晋级。")
    if not global_findings:
        global_findings.append("当前候选失败不是单一问题，应优先补充逐样本验证轨迹。")

    recommended_research_plan = [
        "保存 out-of-fold 逐样本验证轨迹，包括时间、regime、真实方向、预测方向、raw/calibrated probability、confidence、return 和成本后收益。",
        "先做 edge/no-trade 标签治理，过滤低绝对收益和低波动噪声样本，再训练 up/down 方向头。",
        "对 1d/3d 优先做概率校准和强信号分层；对 5d/10d/20d 优先做高波 regime 风控和回撤约束。",
        "进行 feature stability selection，降低 fold 间不稳定特征权重，基本面/库存/外盘缺失前不要宣称事件或基本面增益。",
        "保持 promotion gate 不变，只有真实 walk-forward、成本后表现和风险约束同时达标后才允许 active。",
    ]

    return sanitize_for_json(
        {
            "status": "success",
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "message_zh": "Candidate 失败归因已生成；本报告不发布 active、不生成客户预测、不降低 promotion gate。",
            "horizons": horizons,
            "global_findings": global_findings,
            "recommended_research_plan": recommended_research_plan,
            "promotion_status": promotion.get("status", "not_run"),
            "active_written": False,
            "customer_prediction_generated": False,
            "gate_changed": False,
            "baseline_customer_prediction_used": False,
            "sample_data_used": bool(manifest.get("sample_data_used", False)),
        }
    )
