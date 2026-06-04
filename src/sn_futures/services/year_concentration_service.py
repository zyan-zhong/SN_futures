from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Mapping

import numpy as np
import pandas as pd

from ..api.json_utils import sanitize_for_json
from ..runtime import get_user_output_dir


SUPPORTED_TIME_COLUMNS = (
    "prediction_date",
    "trading_date",
    "label_end_time",
    "label_start_time",
    "timestamp",
)
DEFAULT_THRESHOLDS = {
    "min_required_years": 3,
    "max_year_sample_share": 0.5,
    "max_year_pnl_share": 0.6,
    "min_positive_year_count": 2,
}


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _output_dir() -> Path:
    return get_user_output_dir()


def _summary_path() -> Path:
    return _output_dir() / "model_research" / "year_concentration_evidence.json"


def _candidate_report_path(candidate_version: str) -> Path:
    version = str(candidate_version).lower().lstrip("candidate_")
    return _output_dir() / "model_research" / f"candidate_{version}" / f"candidate_{version}_gated_research_report.json"


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


def _as_reason_list(reasons: Iterable[Any]) -> list[str]:
    return sorted({str(reason) for reason in reasons if str(reason or "").strip()})


def infer_year_from_available_time_columns(frame: pd.DataFrame) -> tuple[pd.Series, str]:
    for column in SUPPORTED_TIME_COLUMNS:
        if column not in frame.columns:
            continue
        parsed = pd.to_datetime(frame[column], errors="coerce")
        valid = parsed.dropna()
        if valid.empty:
            continue
        return parsed.dt.year.astype("Int64"), column
    return pd.Series(dtype="Int64"), ""


def _direction_series(frame: pd.DataFrame) -> pd.Series:
    for column in ("predicted_direction", "direction", "signal"):
        if column in frame.columns:
            return pd.to_numeric(frame[column], errors="coerce").fillna(0.0).map(lambda value: 1.0 if value > 0 else (-1.0 if value < 0 else 0.0))
    if "selected_signal" in frame.columns:
        text = frame["selected_signal"].astype(str).str.lower()
        return text.map(lambda value: 1.0 if "long" in value or value in {"1", "buy"} else (-1.0 if "short" in value or value in {"-1", "sell"} else 0.0))
    return pd.Series(np.ones(len(frame)), index=frame.index)


def _return_series(frame: pd.DataFrame) -> pd.Series:
    for column in ("realized_return", "net_return", "label_return", "future_return", "return"):
        if column in frame.columns:
            return pd.to_numeric(frame[column], errors="coerce").fillna(0.0)
    return pd.Series(np.zeros(len(frame)), index=frame.index)


def _cost_series(frame: pd.DataFrame) -> pd.Series:
    for column in ("cost_assumption", "transaction_cost", "cost"):
        if column in frame.columns:
            return pd.to_numeric(frame[column], errors="coerce").fillna(0.0).abs()
    return pd.Series(np.zeros(len(frame)), index=frame.index)


def _drawdown(values: pd.Series) -> float:
    if values.empty:
        return 0.0
    cumulative = values.cumsum()
    running_max = cumulative.cummax()
    drawdown = cumulative - running_max
    return float(drawdown.min()) if not drawdown.empty else 0.0


def build_year_performance_table(frame: pd.DataFrame) -> dict[str, Any]:
    if frame is None or frame.empty:
        return {
            "status": "missing",
            "time_column": "",
            "rows": [],
            "blocking_reasons": ["oof_trace_empty"],
        }

    years, time_column = infer_year_from_available_time_columns(frame)
    if not time_column:
        return {
            "status": "missing",
            "time_column": "",
            "rows": [],
            "blocking_reasons": ["year_time_column_missing"],
        }

    working = frame.copy()
    working["_year"] = years
    working = working.dropna(subset=["_year"])
    if working.empty:
        return {
            "status": "missing",
            "time_column": time_column,
            "rows": [],
            "blocking_reasons": ["year_time_column_unparseable"],
        }

    direction = _direction_series(working)
    realized = _return_series(working)
    cost = _cost_series(working)
    gross = direction * realized
    net = gross - (direction.abs() > 0).astype(float) * cost
    working["_gross_pnl"] = gross
    working["_net_pnl"] = net

    rows: list[dict[str, Any]] = []
    total_samples = int(len(working))
    total_abs_pnl = float(working["_net_pnl"].abs().sum())
    for year, group in working.groupby("_year", sort=True):
        year_int = int(year)
        sample_count = int(len(group))
        net_pnl = float(group["_net_pnl"].sum())
        gross_pnl = float(group["_gross_pnl"].sum())
        avg_return = float(group["_net_pnl"].mean()) if sample_count else 0.0
        median_return = float(group["_net_pnl"].median()) if sample_count else 0.0
        rows.append(
            {
                "year": year_int,
                "sample_count": sample_count,
                "sample_share": sample_count / max(total_samples, 1),
                "gross_pnl": gross_pnl,
                "net_pnl": net_pnl,
                "pnl_share": abs(net_pnl) / total_abs_pnl if total_abs_pnl > 0 else 0.0,
                "hit_rate": float((group["_net_pnl"] > 0).mean()) if sample_count else 0.0,
                "avg_return": avg_return,
                "median_return": median_return,
                "expectancy": avg_return,
                "max_drawdown": _drawdown(group["_net_pnl"]),
                "worst_period_return": float(group["_net_pnl"].min()) if sample_count else 0.0,
            }
        )

    return {
        "status": "available" if rows else "missing",
        "time_column": time_column,
        "rows": rows,
        "row_count": int(len(working)),
        "blocking_reasons": [] if rows else ["year_table_empty"],
    }


def compute_year_concentration(table: Mapping[str, Any], thresholds: Mapping[str, Any] | None = None) -> dict[str, Any]:
    thresholds = {**DEFAULT_THRESHOLDS, **dict(thresholds or {})}
    rows = [dict(row) for row in table.get("rows", []) if isinstance(row, Mapping)] if isinstance(table, Mapping) else []
    if not rows:
        reasons = _as_reason_list(table.get("blocking_reasons", []) if isinstance(table, Mapping) else ["year_table_missing"])
        return {
            "status": "missing",
            "passed": False,
            "time_column": table.get("time_column", "") if isinstance(table, Mapping) else "",
            "year_performance_table": [],
            "max_year_sample_share": None,
            "max_year_pnl_share": None,
            "positive_year_count": 0,
            "negative_year_count": 0,
            "total_year_count": 0,
            "min_required_years": _safe_int(thresholds.get("min_required_years"), 3),
            "concentration_thresholds": dict(thresholds),
            "blocking_reasons": reasons or ["year_evidence_missing"],
            "training_invoked": False,
            "active_updated": False,
            "customer_prediction_generated": False,
        }

    total_year_count = len(rows)
    max_sample_share = max(_safe_float(row.get("sample_share"), 0.0) for row in rows)
    max_pnl_share = max(_safe_float(row.get("pnl_share"), 0.0) for row in rows)
    positive_year_count = sum(1 for row in rows if _safe_float(row.get("net_pnl"), 0.0) > 0)
    negative_year_count = sum(1 for row in rows if _safe_float(row.get("net_pnl"), 0.0) < 0)
    total_net_pnl = sum(_safe_float(row.get("net_pnl"), 0.0) for row in rows)

    blocking: list[str] = []
    if total_year_count < _safe_int(thresholds.get("min_required_years"), 3):
        blocking.append("insufficient_year_count")
    if max_sample_share > _safe_float(thresholds.get("max_year_sample_share"), 0.5):
        blocking.append("year_sample_concentration_high")
    if max_pnl_share > _safe_float(thresholds.get("max_year_pnl_share"), 0.6):
        blocking.append("year_pnl_concentration_high")
    if positive_year_count < _safe_int(thresholds.get("min_positive_year_count"), 2):
        blocking.append("positive_year_count_too_low")
    if total_net_pnl <= 0:
        blocking.append("non_positive_total_net_pnl")

    status = "pass" if not blocking else "fail"
    return {
        "status": status,
        "passed": status == "pass",
        "time_column": table.get("time_column", "") if isinstance(table, Mapping) else "",
        "year_performance_table": rows,
        "max_year_sample_share": max_sample_share,
        "max_year_pnl_share": max_pnl_share,
        "positive_year_count": positive_year_count,
        "negative_year_count": negative_year_count,
        "total_year_count": total_year_count,
        "min_required_years": _safe_int(thresholds.get("min_required_years"), 3),
        "concentration_thresholds": dict(thresholds),
        "total_net_pnl": total_net_pnl,
        "blocking_reasons": _as_reason_list(blocking),
        "training_invoked": False,
        "active_updated": False,
        "customer_prediction_generated": False,
    }


def validate_year_evidence(evidence: Mapping[str, Any]) -> bool:
    return bool(evidence.get("status") == "pass" and evidence.get("passed") is True)


def _oof_dir(candidate_version: str) -> Path:
    version = str(candidate_version).lower().lstrip("candidate_")
    return _output_dir() / "walk_forward" / version


def load_oof_trace_for_year_evidence(candidate_version: str) -> tuple[pd.DataFrame, list[str]]:
    base = _oof_dir(candidate_version)
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
        frame["_oof_trace_path"] = str(path)
        frame["_horizon"] = path.stem.replace("oof_trace_", "")
        frames.append(frame)
        loaded_paths.append(str(path))
    if not frames:
        return pd.DataFrame(), []
    return pd.concat(frames, ignore_index=True), loaded_paths


def _skipped_year_evidence(candidate_version: str, reasons: Iterable[Any]) -> dict[str, Any]:
    blocking = _as_reason_list(reasons)
    return {
        "status": "skipped",
        "passed": False,
        "candidate_version": str(candidate_version).lower().lstrip("candidate_"),
        "generated_at": _now(),
        "skipped_reason": ";".join(blocking) if blocking else "skipped",
        "time_column": "",
        "year_performance_table": [],
        "max_year_sample_share": None,
        "max_year_pnl_share": None,
        "positive_year_count": 0,
        "negative_year_count": 0,
        "total_year_count": 0,
        "min_required_years": DEFAULT_THRESHOLDS["min_required_years"],
        "concentration_thresholds": dict(DEFAULT_THRESHOLDS),
        "blocking_reasons": blocking or ["year_evidence_skipped"],
        "training_invoked": False,
        "active_updated": False,
        "customer_prediction_generated": False,
    }


def build_year_evidence_summary(
    candidate_version: str,
    *,
    skipped_reasons: Iterable[Any] | None = None,
) -> dict[str, Any]:
    version = str(candidate_version).lower().lstrip("candidate_")
    if skipped_reasons:
        return _skipped_year_evidence(version, skipped_reasons)

    frame, paths = load_oof_trace_for_year_evidence(version)
    table = build_year_performance_table(frame)
    evidence = compute_year_concentration(table)
    evidence.update(
        {
            "candidate_version": version,
            "generated_at": _now(),
            "oof_trace_paths": paths,
        }
    )
    if not paths and evidence["status"] == "missing":
        evidence["blocking_reasons"] = _as_reason_list([*evidence.get("blocking_reasons", []), "oof_trace_missing"])
    return sanitize_for_json(evidence)


def _candidate_v12_skip_reasons(report: Mapping[str, Any]) -> list[str]:
    reasons: list[str] = []
    if str(report.get("status") or "").lower() == "blocked":
        reasons.append("candidate_v12_blocked")
    if not bool(report.get("training_invoked")):
        reasons.append("training_not_invoked")
    _, paths = load_oof_trace_for_year_evidence("v12")
    if not paths:
        reasons.append("oof_trace_missing")
    reasons.extend(str(item) for item in report.get("blocking_reasons", []) if item)
    return _as_reason_list(reasons)


def attach_year_evidence_to_candidate_report(
    candidate_version: str,
    *,
    evidence: Mapping[str, Any] | None = None,
    skipped_reasons: Iterable[Any] | None = None,
) -> dict[str, Any]:
    version = str(candidate_version).lower().lstrip("candidate_")
    path = _candidate_report_path(version)
    report = _read_json(path)
    if not isinstance(report, Mapping):
        evidence_payload = dict(evidence or build_year_evidence_summary(version, skipped_reasons=skipped_reasons))
        return {
            "candidate_version": version,
            "report_path": str(path),
            "report_rewritten": False,
            "year_concentration_evidence": evidence_payload,
        }

    if evidence is None:
        reasons = list(skipped_reasons or [])
        if version == "v12":
            reasons.extend(_candidate_v12_skip_reasons(report))
        evidence_payload = build_year_evidence_summary(version, skipped_reasons=reasons if reasons else None)
    else:
        evidence_payload = dict(evidence)

    updated = dict(report)
    updated["year_concentration_evidence"] = sanitize_for_json(evidence_payload)
    passed = validate_year_evidence(evidence_payload)
    concentration_value = evidence_payload.get("max_year_pnl_share")

    if version == "v10":
        gates = dict(updated.get("v10_gate_checks") or {})
        gates["year_concentration"] = concentration_value
        gates["year_concentration_evidence_available"] = evidence_payload.get("status") in {"pass", "fail"}
        gates["year_concentration_pass"] = passed
        updated["v10_gate_checks"] = gates
    else:
        gates = dict(updated.get("gate_checks") or {})
        gates["year_concentration"] = concentration_value
        gates["year_concentration_evidence_present"] = evidence_payload.get("status") in {"pass", "fail"}
        gates["year_concentration_pass"] = passed
        if gates.get("gate_passed") and not passed:
            gates["gate_passed"] = False
        updated["gate_checks"] = gates

    if not passed:
        updated["manual_approval_recommended"] = False
        if "gate_passed" in updated:
            updated["gate_passed"] = False
    updated["active_updated"] = False
    updated["customer_prediction_generated"] = False

    written = _write_json(path, updated)
    return {
        "candidate_version": version,
        "report_path": str(path),
        "report_rewritten": True,
        "year_concentration_evidence": written.get("year_concentration_evidence"),
        "manual_approval_recommended": bool(written.get("manual_approval_recommended")),
        "training_invoked": False,
        "active_updated": False,
        "customer_prediction_generated": False,
    }


def get_candidate_report_with_year_evidence(candidate_version: str) -> dict[str, Any]:
    version = str(candidate_version).lower().lstrip("candidate_")
    path = _candidate_report_path(version)
    payload = _read_json(path)
    if not isinstance(payload, Mapping):
        return {
            "status": "missing",
            "candidate_version": version,
            "report_path": str(path),
            "year_concentration_evidence": build_year_evidence_summary(version),
            "manual_approval_recommended": False,
            "training_invoked": False,
            "active_updated": False,
            "customer_prediction_generated": False,
        }
    report = dict(payload)
    if "year_concentration_evidence" not in report:
        report["year_concentration_evidence"] = build_year_evidence_summary(version)
        if not validate_year_evidence(report["year_concentration_evidence"]):
            report["manual_approval_recommended"] = False
    return sanitize_for_json(report)


def get_candidate_v10_report() -> dict[str, Any]:
    return get_candidate_report_with_year_evidence("v10")


def get_candidate_v12_report_with_year_evidence() -> dict[str, Any]:
    payload = get_candidate_report_with_year_evidence("v12")
    evidence = payload.get("year_concentration_evidence")
    if isinstance(evidence, Mapping) and evidence.get("status") in {"skipped", "missing", "fail", "pass"}:
        return payload
    return attach_year_evidence_to_candidate_report("v12")


def refresh_year_concentration() -> dict[str, Any]:
    v10 = attach_year_evidence_to_candidate_report("v10")
    v12 = attach_year_evidence_to_candidate_report("v12")
    result = {
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
    return _write_json(_summary_path(), result)


def get_year_concentration_report() -> dict[str, Any]:
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
