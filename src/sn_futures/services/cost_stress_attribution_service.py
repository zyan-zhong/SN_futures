from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Mapping

import numpy as np
import pandas as pd

from ..api.json_utils import sanitize_for_json
from ..runtime import get_user_output_dir
from .year_concentration_service import get_candidate_report_with_year_evidence


TIME_COLUMNS = ("prediction_date", "trading_date", "label_end_time", "label_start_time", "timestamp")
DEFAULT_COST = 0.0002
HIGH_TURNOVER_THRESHOLD = 0.50
HIGH_FLIP_THRESHOLD = 0.40
SHORT_HOLDING_DAYS = 3.0


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _output_dir() -> Path:
    return get_user_output_dir()


def _normalise_version(candidate_version: str | None) -> str:
    value = str(candidate_version or "v10").strip().lower()
    if value.startswith("candidate_"):
        value = value.replace("candidate_", "", 1)
    return value or "v10"


def _candidate_report_path(candidate_version: str) -> Path:
    version = _normalise_version(candidate_version)
    return _output_dir() / "model_research" / f"candidate_{version}" / f"candidate_{version}_gated_research_report.json"


def _candidate_research_dir(candidate_version: str) -> Path:
    version = _normalise_version(candidate_version)
    path = _output_dir() / "model_research" / f"candidate_{version}"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _attribution_path(candidate_version: str) -> Path:
    version = _normalise_version(candidate_version)
    return _candidate_research_dir(version) / f"cost_stress_attribution_{version}.json"


def _summary_path() -> Path:
    return _output_dir() / "model_research" / "cost_stress_attribution.json"


def _read_json(path: Path) -> Any:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _write_json(path: Path, payload: Mapping[str, Any]) -> dict[str, Any]:
    safe = sanitize_for_json(dict(payload))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(safe, ensure_ascii=False, indent=2), encoding="utf-8")
    return safe


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


def _reasons(values: Iterable[Any]) -> list[str]:
    return sorted({str(item) for item in values if str(item or "").strip()})


def _nested(payload: Mapping[str, Any], *keys: str) -> Any:
    current: Any = payload
    for key in keys:
        if not isinstance(current, Mapping):
            return None
        current = current.get(key)
    return current


def load_candidate_report_for_cost_attribution(candidate_version: str) -> tuple[dict[str, Any], str]:
    path = _candidate_report_path(candidate_version)
    payload = _read_json(path)
    return (dict(payload), str(path)) if isinstance(payload, Mapping) else ({}, str(path))


def load_oof_trace_for_cost_attribution(candidate_version: str) -> tuple[pd.DataFrame, list[str]]:
    version = _normalise_version(candidate_version)
    base = _output_dir() / "walk_forward" / version
    paths = sorted(base.glob("oof_trace_*.csv")) if base.exists() else []
    frames: list[pd.DataFrame] = []
    loaded_paths: list[str] = []
    for path in paths:
        try:
            frame = pd.read_csv(path)
        except Exception:
            continue
        if frame.empty:
            continue
        if "horizon" not in frame.columns:
            frame["horizon"] = path.stem.replace("oof_trace_", "")
        frame["_source_oof_trace_path"] = str(path)
        frames.append(frame)
        loaded_paths.append(str(path))
    if not frames:
        return pd.DataFrame(), []
    return pd.concat(frames, ignore_index=True), loaded_paths


def _direction(frame: pd.DataFrame) -> pd.Series:
    for column in ("predicted_direction", "direction", "signal"):
        if column in frame.columns:
            values = pd.to_numeric(frame[column], errors="coerce").fillna(0.0)
            return values.map(lambda item: 1.0 if item > 0 else (-1.0 if item < 0 else 0.0))
    return pd.Series(np.zeros(len(frame)), index=frame.index)


def _time_column(frame: pd.DataFrame) -> tuple[pd.Series, str]:
    for column in TIME_COLUMNS:
        if column not in frame.columns:
            continue
        parsed = pd.to_datetime(frame[column], errors="coerce")
        if not parsed.dropna().empty:
            return parsed, column
    return pd.Series(pd.NaT, index=frame.index), ""


def _horizon_days(value: Any) -> float:
    text = str(value or "").lower().replace("d", "")
    try:
        return max(1.0, float(text))
    except ValueError:
        return 1.0


def _prepare_oof(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return frame.copy()
    work = frame.copy()
    direction = _direction(work)
    realized = pd.to_numeric(work.get("realized_return", pd.Series(np.zeros(len(work)))), errors="coerce").fillna(0.0)
    cost = pd.to_numeric(work.get("cost_assumption", pd.Series([DEFAULT_COST] * len(work))), errors="coerce").fillna(DEFAULT_COST).abs()
    edge = pd.to_numeric(work.get("trade_edge", pd.Series([1.0] * len(work))), errors="coerce").fillna(0.0)
    trade = (direction.abs() > 0) & (edge > 0)
    work["_position"] = np.where(trade, direction, 0.0)
    work["_is_trade"] = trade
    work["_gross_return"] = work["_position"] * realized
    work["_cost_1x"] = np.where(trade, cost, 0.0)
    work["_net_return_1x"] = work["_gross_return"] - work["_cost_1x"]
    work["_net_return_2x"] = work["_gross_return"] - work["_cost_1x"] * 2.0
    work["_net_return_3x"] = work["_gross_return"] - work["_cost_1x"] * 3.0
    if "horizon" not in work.columns:
        work["horizon"] = "unknown"
    parsed_time, source_time_column = _time_column(work)
    work["_parsed_time"] = parsed_time
    work["_year"] = parsed_time.dt.year.astype("Int64") if source_time_column else pd.Series(pd.NA, index=work.index, dtype="Int64")
    starts = pd.to_datetime(work.get("label_start_time", pd.Series(pd.NaT, index=work.index)), errors="coerce")
    ends = pd.to_datetime(work.get("label_end_time", pd.Series(pd.NaT, index=work.index)), errors="coerce")
    horizon_days = work["horizon"].map(_horizon_days)
    holding = (ends - starts).dt.total_seconds() / 86400.0
    work["_holding_period_days"] = holding.where(holding.notna() & (holding > 0), horizon_days)
    work["_time_column"] = source_time_column
    return work.sort_values([col for col in ("_parsed_time", "horizon") if col in work.columns]).reset_index(drop=True)


def _signal_flip_count(group: pd.DataFrame) -> int:
    trades = group.loc[group["_is_trade"], "_position"].astype(float)
    trades = trades.loc[trades.abs() > 0]
    if len(trades) < 2:
        return 0
    return int((trades.diff().fillna(0).abs() > 0).sum())


def _group_row(group: pd.DataFrame, key_name: str, key_value: Any) -> dict[str, Any]:
    sample_count = int(len(group))
    trades = group.loc[group["_is_trade"]].copy()
    trade_count = int(len(trades))
    gross_expectancy = float(trades["_gross_return"].mean()) if trade_count else 0.0
    net_1x = float(trades["_net_return_1x"].mean()) if trade_count else 0.0
    net_2x = float(trades["_net_return_2x"].mean()) if trade_count else 0.0
    net_3x = float(trades["_net_return_3x"].mean()) if trade_count else 0.0
    flip_count = _signal_flip_count(group)
    flip_rate = flip_count / max(trade_count - 1, 1) if trade_count > 1 else 0.0
    avg_holding = float(trades["_holding_period_days"].mean()) if trade_count else 0.0
    driver = "pass"
    if net_3x < 0:
        driver = "institutional_3x_cost_negative"
    elif net_2x < 0:
        driver = "institutional_2x_cost_negative"
    elif trade_count / max(sample_count, 1) > HIGH_TURNOVER_THRESHOLD:
        driver = "high_turnover_horizon" if key_name == "horizon" else "high_turnover_period"
    elif flip_rate > HIGH_FLIP_THRESHOLD:
        driver = "high_signal_flip_rate"
    elif avg_holding and avg_holding <= SHORT_HOLDING_DAYS:
        driver = "short_holding_period"
    row = {
        key_name: key_value,
        "sample_count": sample_count,
        "trade_count": trade_count,
        "gross_expectancy": gross_expectancy,
        "net_expectancy_1x": net_1x,
        "net_expectancy_2x": net_2x,
        "net_expectancy_3x": net_3x,
        "cost_drag_2x": gross_expectancy - net_2x,
        "cost_drag_3x": gross_expectancy - net_3x,
        "cost_drag": gross_expectancy - net_3x,
        "turnover": trade_count / max(sample_count, 1),
        "signal_flip_count": flip_count,
        "signal_flip_rate": flip_rate,
        "avg_holding_period": avg_holding,
        "passed": bool(net_2x >= 0.0 and net_3x >= 0.0),
        "main_failure_driver": driver,
    }
    return sanitize_for_json(row)


def decompose_expectancy_by_horizon(frame: pd.DataFrame) -> dict[str, Any]:
    if frame.empty:
        return {"status": "missing", "rows": [], "blocking_reasons": ["oof_trace_missing"]}
    rows = [_group_row(group, "horizon", str(horizon)) for horizon, group in frame.groupby("horizon", sort=True)]
    return {"status": "pass" if all(row["passed"] for row in rows) else "fail", "rows": rows, "blocking_reasons": []}


def decompose_expectancy_by_regime(frame: pd.DataFrame) -> dict[str, Any]:
    if frame.empty:
        return {"status": "missing", "rows": [], "blocking_reasons": ["oof_trace_missing"]}
    if "regime_label" not in frame.columns:
        return {"status": "missing", "rows": [], "blocking_reasons": ["regime_column_missing"]}
    rows = [_group_row(group, "regime_label", str(regime)) for regime, group in frame.groupby("regime_label", sort=True)]
    return {"status": "pass" if all(row["passed"] for row in rows) else "fail", "rows": rows, "blocking_reasons": []}


def decompose_expectancy_by_year(frame: pd.DataFrame) -> dict[str, Any]:
    if frame.empty:
        return {"status": "missing", "rows": [], "blocking_reasons": ["oof_trace_missing"]}
    time_column = str(frame["_time_column"].iloc[0] or "") if "_time_column" in frame.columns and len(frame) else ""
    if not time_column:
        return {"status": "missing", "rows": [], "blocking_reasons": ["year_time_column_missing"]}
    work = frame.dropna(subset=["_year"]).copy()
    if work.empty:
        return {"status": "missing", "rows": [], "blocking_reasons": ["year_time_column_unparseable"]}
    rows = [_group_row(group, "year", int(year)) for year, group in work.groupby("_year", sort=True)]
    return {"status": "pass" if all(row["passed"] for row in rows) else "fail", "rows": rows, "time_column": time_column, "blocking_reasons": []}


def compute_turnover_diagnostics(frame: pd.DataFrame, by_horizon: Mapping[str, Any], by_regime: Mapping[str, Any], by_year: Mapping[str, Any]) -> dict[str, Any]:
    rows_h = [dict(row) for row in by_horizon.get("rows", []) if isinstance(row, Mapping)]
    rows_r = [dict(row) for row in by_regime.get("rows", []) if isinstance(row, Mapping)]
    rows_y = [dict(row) for row in by_year.get("rows", []) if isinstance(row, Mapping)]
    total_trades = int(frame["_is_trade"].sum()) if not frame.empty and "_is_trade" in frame.columns else 0
    average_turnover = total_trades / max(len(frame), 1) if not frame.empty else 0.0
    high_turnover_periods = [row for row in [*rows_h, *rows_r, *rows_y] if _safe_float(row.get("turnover"), 0.0) > HIGH_TURNOVER_THRESHOLD]
    failed_high = [row for row in high_turnover_periods if not row.get("passed")]
    return {
        "total_trades": total_trades,
        "average_turnover": average_turnover,
        "turnover_by_horizon": {str(row.get("horizon")): row.get("turnover") for row in rows_h},
        "turnover_by_regime": {str(row.get("regime_label")): row.get("turnover") for row in rows_r},
        "turnover_by_year": {str(row.get("year")): row.get("turnover") for row in rows_y},
        "high_turnover_periods": high_turnover_periods,
        "high_turnover_failure_share": len(failed_high) / max(len(high_turnover_periods), 1) if high_turnover_periods else 0.0,
    }


def compute_signal_flip_diagnostics(frame: pd.DataFrame, by_horizon: Mapping[str, Any], by_regime: Mapping[str, Any], by_year: Mapping[str, Any]) -> dict[str, Any]:
    flip_count = _signal_flip_count(frame) if not frame.empty and "_position" in frame.columns else 0
    trade_count = int(frame["_is_trade"].sum()) if not frame.empty and "_is_trade" in frame.columns else 0
    rows_h = [dict(row) for row in by_horizon.get("rows", []) if isinstance(row, Mapping)]
    rows_r = [dict(row) for row in by_regime.get("rows", []) if isinstance(row, Mapping)]
    rows_y = [dict(row) for row in by_year.get("rows", []) if isinstance(row, Mapping)]
    return {
        "signal_flip_count": flip_count,
        "signal_flip_rate": flip_count / max(trade_count - 1, 1) if trade_count > 1 else 0.0,
        "flip_rate_by_horizon": {str(row.get("horizon")): row.get("signal_flip_rate") for row in rows_h},
        "flip_rate_by_regime": {str(row.get("regime_label")): row.get("signal_flip_rate") for row in rows_r},
        "flip_rate_by_year": {str(row.get("year")): row.get("signal_flip_rate") for row in rows_y},
        "flip_cost_drag_estimate": float(frame.loc[frame["_is_trade"], "_cost_1x"].sum() * 2.0) if not frame.empty and "_cost_1x" in frame.columns else 0.0,
    }


def compute_holding_period_diagnostics(frame: pd.DataFrame, by_horizon: Mapping[str, Any], by_regime: Mapping[str, Any]) -> dict[str, Any]:
    trades = frame.loc[frame["_is_trade"]].copy() if not frame.empty and "_is_trade" in frame.columns else pd.DataFrame()
    holding = pd.to_numeric(trades.get("_holding_period_days", pd.Series(dtype=float)), errors="coerce").dropna()
    rows_h = [dict(row) for row in by_horizon.get("rows", []) if isinstance(row, Mapping)]
    rows_r = [dict(row) for row in by_regime.get("rows", []) if isinstance(row, Mapping)]
    return {
        "avg_holding_period": float(holding.mean()) if len(holding) else 0.0,
        "median_holding_period": float(holding.median()) if len(holding) else 0.0,
        "short_holding_period_share": float((holding <= SHORT_HOLDING_DAYS).mean()) if len(holding) else 0.0,
        "holding_period_by_horizon": {str(row.get("horizon")): row.get("avg_holding_period") for row in rows_h},
        "holding_period_by_regime": {str(row.get("regime_label")): row.get("avg_holding_period") for row in rows_r},
    }


def _institutional_cost_stress(report: Mapping[str, Any]) -> dict[str, Any]:
    direct = report.get("institutional_cost_stress")
    if isinstance(direct, Mapping) and direct:
        return dict(direct)
    nested = _nested(report, "institutional_validation", "cost_stress")
    return dict(nested) if isinstance(nested, Mapping) else {}


def identify_cost_failure_drivers(
    *,
    institutional_cost_stress: Mapping[str, Any],
    by_horizon: Mapping[str, Any],
    by_regime: Mapping[str, Any],
    by_year: Mapping[str, Any],
    turnover_diagnostics: Mapping[str, Any],
    signal_flip_diagnostics: Mapping[str, Any],
    holding_period_diagnostics: Mapping[str, Any],
) -> list[str]:
    drivers: list[str] = []
    if _safe_float(_nested(institutional_cost_stress, "2x_cost", "expectancy"), 0.0) < 0:
        drivers.append("institutional_2x_cost_negative")
    if _safe_float(_nested(institutional_cost_stress, "3x_cost", "expectancy"), 0.0) < 0:
        drivers.append("institutional_3x_cost_negative")
    horizon_rows = [dict(row) for row in by_horizon.get("rows", []) if isinstance(row, Mapping)]
    regime_rows = [dict(row) for row in by_regime.get("rows", []) if isinstance(row, Mapping)]
    year_rows = [dict(row) for row in by_year.get("rows", []) if isinstance(row, Mapping)]
    if any(_safe_float(row.get("turnover"), 0.0) > HIGH_TURNOVER_THRESHOLD for row in horizon_rows):
        drivers.append("high_turnover_horizon")
    if _safe_float(signal_flip_diagnostics.get("signal_flip_rate"), 0.0) > HIGH_FLIP_THRESHOLD:
        drivers.append("high_signal_flip_rate")
    if _safe_float(holding_period_diagnostics.get("short_holding_period_share"), 0.0) > 0.5:
        drivers.append("short_holding_period")
    if any(_safe_float(row.get("net_expectancy_3x"), 0.0) < 0 for row in regime_rows):
        drivers.append("regime_specific_cost_drag")
    if any(_safe_float(row.get("net_expectancy_3x"), 0.0) < 0 for row in year_rows):
        drivers.append("year_specific_cost_drag")
    if by_horizon.get("status") == "missing" or by_regime.get("status") == "missing" or by_year.get("status") == "missing":
        drivers.append("insufficient_cost_attribution_evidence")
    return _reasons(drivers)


def _cost_drag_summary(
    frame: pd.DataFrame,
    institutional_cost_stress: Mapping[str, Any],
    by_horizon: Mapping[str, Any],
) -> dict[str, Any]:
    trades = frame.loc[frame["_is_trade"]].copy() if not frame.empty and "_is_trade" in frame.columns else pd.DataFrame()
    return {
        "institutional_2x_expectancy": _nested(institutional_cost_stress, "2x_cost", "expectancy"),
        "institutional_3x_expectancy": _nested(institutional_cost_stress, "3x_cost", "expectancy"),
        "mean_cost_1x": float(trades["_cost_1x"].mean()) if len(trades) and "_cost_1x" in trades.columns else 0.0,
        "total_cost_1x": float(trades["_cost_1x"].sum()) if len(trades) and "_cost_1x" in trades.columns else 0.0,
        "worst_horizon": _worst_row(by_horizon, "horizon"),
    }


def _worst_row(table: Mapping[str, Any], key: str) -> dict[str, Any]:
    rows = [dict(row) for row in table.get("rows", []) if isinstance(row, Mapping)]
    if not rows:
        return {}
    return min(rows, key=lambda row: _safe_float(row.get("net_expectancy_3x"), 0.0))


def _missing_attribution(candidate_version: str, reasons: Iterable[Any], *, report_path: str = "", oof_paths: list[str] | None = None) -> dict[str, Any]:
    version = _normalise_version(candidate_version)
    blocking = _reasons(reasons)
    return {
        "status": "missing",
        "passed": False,
        "candidate_version": version,
        "generated_at": _now(),
        "report_path": str(_attribution_path(version)),
        "source_candidate_report_path": report_path,
        "source_oof_trace_path": (oof_paths or [""])[0] if oof_paths else "",
        "source_oof_trace_paths": oof_paths or [],
        "institutional_cost_stress_source": {},
        "by_horizon": {"status": "missing", "rows": [], "blocking_reasons": blocking},
        "by_regime": {"status": "missing", "rows": [], "blocking_reasons": blocking},
        "by_year": {"status": "missing", "rows": [], "blocking_reasons": blocking},
        "turnover_diagnostics": {},
        "signal_flip_diagnostics": {},
        "holding_period_diagnostics": {},
        "cost_drag_summary": {},
        "failure_drivers": ["insufficient_cost_attribution_evidence"],
        "skipped_reason": "",
        "blocking_reasons": blocking or ["cost_attribution_missing"],
        "training_invoked": False,
        "active_updated": False,
        "customer_prediction_generated": False,
    }


def _skipped_attribution(candidate_version: str, reasons: Iterable[Any], *, report_path: str = "") -> dict[str, Any]:
    version = _normalise_version(candidate_version)
    blocking = _reasons(reasons)
    return {
        "status": "skipped",
        "passed": False,
        "candidate_version": version,
        "generated_at": _now(),
        "report_path": str(_attribution_path(version)),
        "source_candidate_report_path": report_path,
        "source_oof_trace_path": "",
        "source_oof_trace_paths": [],
        "institutional_cost_stress_source": {},
        "by_horizon": {"status": "skipped", "rows": [], "blocking_reasons": blocking},
        "by_regime": {"status": "skipped", "rows": [], "blocking_reasons": blocking},
        "by_year": {"status": "skipped", "rows": [], "blocking_reasons": blocking},
        "turnover_diagnostics": {},
        "signal_flip_diagnostics": {},
        "holding_period_diagnostics": {},
        "cost_drag_summary": {},
        "failure_drivers": [],
        "skipped_reason": ";".join(blocking) if blocking else "skipped",
        "blocking_reasons": blocking or ["cost_attribution_skipped"],
        "training_invoked": False,
        "active_updated": False,
        "customer_prediction_generated": False,
    }


def _candidate_v12_skip_reasons(report: Mapping[str, Any], oof_paths: list[str]) -> list[str]:
    reasons: list[str] = []
    if str(report.get("status") or "").lower() == "blocked":
        reasons.append("candidate_v12_blocked")
    if not bool(report.get("training_invoked")):
        reasons.append("training_not_invoked")
    if not oof_paths:
        reasons.append("oof_trace_missing")
    reasons.extend(str(item) for item in report.get("blocking_reasons", []) if item)
    if "training_dataset_v12_blocked" not in reasons:
        reasons.append("training_dataset_v12_blocked")
    return _reasons(reasons)


def build_cost_stress_attribution(candidate_version: str = "v10") -> dict[str, Any]:
    version = _normalise_version(candidate_version)
    candidate_report, candidate_report_path = load_candidate_report_for_cost_attribution(version)
    frame, oof_paths = load_oof_trace_for_cost_attribution(version)

    if version == "v12" and (str(candidate_report.get("status") or "").lower() == "blocked" or not oof_paths):
        payload = _skipped_attribution(version, _candidate_v12_skip_reasons(candidate_report, oof_paths), report_path=candidate_report_path)
        return _write_json(_attribution_path(version), payload)
    if not candidate_report:
        payload = _missing_attribution(version, ["candidate_report_missing"], report_path=candidate_report_path, oof_paths=oof_paths)
        return _write_json(_attribution_path(version), payload)
    if frame.empty:
        payload = _missing_attribution(version, ["oof_trace_missing"], report_path=candidate_report_path, oof_paths=oof_paths)
        return _write_json(_attribution_path(version), payload)

    work = _prepare_oof(frame)
    by_horizon = decompose_expectancy_by_horizon(work)
    by_regime = decompose_expectancy_by_regime(work)
    by_year = decompose_expectancy_by_year(work)
    turnover = compute_turnover_diagnostics(work, by_horizon, by_regime, by_year)
    flips = compute_signal_flip_diagnostics(work, by_horizon, by_regime, by_year)
    holding = compute_holding_period_diagnostics(work, by_horizon, by_regime)
    institutional_cost_stress = _institutional_cost_stress(candidate_report)
    failure_drivers = identify_cost_failure_drivers(
        institutional_cost_stress=institutional_cost_stress,
        by_horizon=by_horizon,
        by_regime=by_regime,
        by_year=by_year,
        turnover_diagnostics=turnover,
        signal_flip_diagnostics=flips,
        holding_period_diagnostics=holding,
    )
    blocking = _reasons(
        [
            *failure_drivers,
            *(by_horizon.get("blocking_reasons") or []),
            *(by_regime.get("blocking_reasons") or []),
            *(by_year.get("blocking_reasons") or []),
        ]
    )
    status = "pass" if not failure_drivers else "fail"
    payload = {
        "status": status,
        "passed": status == "pass",
        "candidate_version": version,
        "generated_at": _now(),
        "report_path": str(_attribution_path(version)),
        "source_candidate_report_path": candidate_report_path,
        "source_oof_trace_path": oof_paths[0] if oof_paths else "",
        "source_oof_trace_paths": oof_paths,
        "institutional_cost_stress_source": institutional_cost_stress,
        "by_horizon": by_horizon,
        "by_regime": by_regime,
        "by_year": by_year,
        "turnover_diagnostics": turnover,
        "signal_flip_diagnostics": flips,
        "holding_period_diagnostics": holding,
        "cost_drag_summary": _cost_drag_summary(work, institutional_cost_stress, by_horizon),
        "failure_drivers": failure_drivers,
        "skipped_reason": "",
        "blocking_reasons": blocking,
        "training_invoked": False,
        "active_updated": False,
        "customer_prediction_generated": False,
    }
    return _write_json(_attribution_path(version), payload)


def attach_cost_attribution_to_candidate_report(
    candidate_version: str,
    *,
    attribution: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    version = _normalise_version(candidate_version)
    report_path = _candidate_report_path(version)
    report = _read_json(report_path)
    if not isinstance(report, Mapping):
        return {
            "candidate_version": version,
            "report_path": str(report_path),
            "report_rewritten": False,
            "cost_stress_attribution": dict(attribution or build_cost_stress_attribution(version)),
        }
    evidence = dict(attribution or build_cost_stress_attribution(version))
    updated = dict(report)
    updated["cost_stress_attribution"] = sanitize_for_json(evidence)
    if not evidence.get("passed"):
        updated["manual_approval_recommended"] = False
        if "gate_passed" in updated:
            updated["gate_passed"] = False
        gates_key = "v10_gate_checks" if version == "v10" else "gate_checks"
        gates = dict(updated.get(gates_key) or {})
        gates["cost_stress_attribution_pass"] = False
        updated[gates_key] = gates
    updated["active_updated"] = False
    updated["customer_prediction_generated"] = False
    written = _write_json(report_path, updated)
    return {
        "candidate_version": version,
        "report_path": str(report_path),
        "report_rewritten": True,
        "cost_stress_attribution": written.get("cost_stress_attribution"),
        "manual_approval_recommended": bool(written.get("manual_approval_recommended")),
        "training_invoked": False,
        "active_updated": False,
        "customer_prediction_generated": False,
    }


def refresh_cost_stress_attribution() -> dict[str, Any]:
    v10 = attach_cost_attribution_to_candidate_report("v10")
    v12 = attach_cost_attribution_to_candidate_report("v12")
    payload = {
        "status": "success",
        "generated_at": _now(),
        "summary_path": str(_summary_path()),
        "candidate_v10": v10,
        "candidate_v12": v12,
        "reports_rewritten": bool(v10.get("report_rewritten") or v12.get("report_rewritten")),
        "training_invoked": False,
        "active_updated": False,
        "customer_prediction_generated": False,
    }
    return _write_json(_summary_path(), payload)


def get_cost_stress_attribution_report() -> dict[str, Any]:
    payload = _read_json(_summary_path())
    if isinstance(payload, Mapping):
        return sanitize_for_json(dict(payload))
    return {
        "status": "missing",
        "summary_path": str(_summary_path()),
        "candidate_v10": {},
        "candidate_v12": {},
        "training_invoked": False,
        "active_updated": False,
        "customer_prediction_generated": False,
    }


def get_candidate_report_with_cost_attribution(candidate_version: str) -> dict[str, Any]:
    version = _normalise_version(candidate_version)
    report = get_candidate_report_with_year_evidence(version)
    if "cost_stress_attribution" not in report:
        report["cost_stress_attribution"] = build_cost_stress_attribution(version)
        if not report["cost_stress_attribution"].get("passed"):
            report["manual_approval_recommended"] = False
    return sanitize_for_json(report)


def get_candidate_v10_report() -> dict[str, Any]:
    return get_candidate_report_with_cost_attribution("v10")
