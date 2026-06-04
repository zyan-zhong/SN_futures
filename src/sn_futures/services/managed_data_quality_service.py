from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from ..api.json_utils import sanitize_for_json
from ..runtime import get_user_output_dir
from ..utils.secret_sanitizer import sanitize_text
from .managed_data_proxy_service import MANAGED_REQUIRED_RESEARCH_FIELDS


QUALITY_VERSION = "managed_data_quality_v1"
SCORECARD_FILENAME = "managed_data_quality_scorecard.json"
DEFAULT_MAX_NULL_RATE = 0.2
INVENTORY_FIELDS = ("shfe_inventory", "shfe_warehouse_receipt", "lme_inventory")
OPEN_INTEREST_FIELDS = ("near_open_interest", "far_open_interest")
PRICE_FIELDS = ("spot_price", "lme_tin_close", "near_contract_close", "far_contract_close")


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _scorecard_path() -> Path:
    path = get_user_output_dir() / "diagnostics" / SCORECARD_FILENAME
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _managed_data_path() -> Path:
    return get_user_output_dir() / "fundamentals" / "managed_fundamentals.json"


def _read_json(path: Path) -> Any:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return None


def _write_scorecard(payload: Mapping[str, Any]) -> dict[str, Any]:
    safe = sanitize_for_json(dict(payload))
    _scorecard_path().write_text(json.dumps(safe, ensure_ascii=False, indent=2), encoding="utf-8")
    return safe


def _rows_from_payload(payload: Any) -> list[dict[str, Any]]:
    rows = payload.get("rows") or payload.get("data") or payload.get("history") if isinstance(payload, Mapping) else payload
    if not isinstance(rows, list):
        return []
    return [dict(row) for row in rows if isinstance(row, Mapping)]


def _load_rows() -> list[dict[str, Any]]:
    return _rows_from_payload(_read_json(_managed_data_path()))


def _date_value(row: Mapping[str, Any]) -> str:
    return str(row.get("feature_date") or row.get("trading_date") or row.get("trade_date") or row.get("date") or "").strip()


def _date_range(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    values = sorted({_date_value(row)[:10] for row in rows if _date_value(row)})
    return {"date_start": values[0] if values else None, "date_end": values[-1] if values else None}


def _present(value: Any) -> bool:
    return value is not None and str(value).strip() != ""


def _number(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        parsed = float(value)
    except Exception:
        return None
    if parsed != parsed or parsed in {float("inf"), float("-inf")}:
        return None
    return parsed


def _unique(values: Iterable[Any]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = str(value or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        out.append(text)
    return out


def validate_required_field_null_rate(
    rows: Sequence[Mapping[str, Any]],
    *,
    required_fields: Sequence[str] = MANAGED_REQUIRED_RESEARCH_FIELDS,
    max_null_rate: float = DEFAULT_MAX_NULL_RATE,
) -> dict[str, Any]:
    row_count = len(rows)
    null_rate_by_field: dict[str, float] = {}
    blocking: list[str] = []
    if row_count == 0:
        return {"status": "fail", "row_count": 0, "null_rate_by_field": {}, "blocking_reasons": ["managed_rows_missing"]}
    for field in required_fields:
        null_count = sum(1 for row in rows if not _present(row.get(field)))
        rate = round(null_count / row_count, 4)
        null_rate_by_field[str(field)] = rate
        if rate > max_null_rate:
            blocking.append(f"null_rate_too_high:{field}")
    return {
        "status": "fail" if blocking else "pass",
        "row_count": row_count,
        "max_null_rate": max_null_rate,
        "null_rate_by_field": null_rate_by_field,
        "blocking_reasons": blocking,
    }


def detect_duplicate_keys(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    seen: set[tuple[str, str, str]] = set()
    duplicate_count = 0
    duplicate_keys: list[str] = []
    for row in rows:
        key = (_date_value(row), str(row.get("asof_date") or "").strip(), str(row.get("source_timestamp") or "").strip())
        if key in seen:
            duplicate_count += 1
            duplicate_keys.append("|".join(key))
        else:
            seen.add(key)
    return {
        "status": "fail" if duplicate_count else "pass",
        "duplicate_key_count": duplicate_count,
        "duplicate_keys": duplicate_keys[:10],
        "blocking_reasons": ["duplicate_timestamp_key"] if duplicate_count else [],
    }


def detect_negative_or_invalid_values(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    invalid_count = 0
    negative_inventory = 0
    impossible_open_interest = 0
    invalid_price = 0
    for row in rows:
        for field in INVENTORY_FIELDS:
            value = _number(row.get(field))
            if value is None and _present(row.get(field)):
                invalid_count += 1
            elif value is not None and value < 0:
                invalid_count += 1
                negative_inventory += 1
        for field in OPEN_INTEREST_FIELDS:
            value = _number(row.get(field))
            if value is None and _present(row.get(field)):
                invalid_count += 1
            elif value is not None and (value < 0 or value > 1_000_000_000):
                invalid_count += 1
                impossible_open_interest += 1
        for field in PRICE_FIELDS:
            value = _number(row.get(field))
            if value is None and _present(row.get(field)):
                invalid_count += 1
            elif value is not None and value <= 0:
                invalid_count += 1
                invalid_price += 1
    blocking: list[str] = []
    if negative_inventory:
        blocking.append("negative_inventory")
    if impossible_open_interest:
        blocking.append("impossible_open_interest")
    if invalid_price:
        blocking.append("invalid_price")
    if invalid_count and not blocking:
        blocking.append("invalid_numeric_value")
    return {
        "status": "fail" if blocking else "pass",
        "invalid_value_count": invalid_count,
        "negative_inventory_count": negative_inventory,
        "impossible_open_interest_count": impossible_open_interest,
        "invalid_price_count": invalid_price,
        "blocking_reasons": blocking,
    }


def _sorted_numeric_series(rows: Sequence[Mapping[str, Any]], field: str) -> list[tuple[str, float]]:
    values: list[tuple[str, float]] = []
    for row in rows:
        value = _number(row.get(field))
        if value is not None:
            values.append((_date_value(row), value))
    return sorted(values, key=lambda item: item[0])


def detect_basis_outliers(
    rows: Sequence[Mapping[str, Any]],
    *,
    max_absolute_basis: float = 50_000.0,
    max_jump_abs: float = 20_000.0,
) -> dict[str, Any]:
    series = _sorted_numeric_series(rows, "spot_futures_basis")
    outliers: list[dict[str, Any]] = []
    previous: tuple[str, float] | None = None
    for date_text, value in series:
        if abs(value) > max_absolute_basis:
            outliers.append({"date": date_text, "reason": "basis_absolute_outlier", "value": value})
        if previous is not None and abs(value - previous[1]) > max_jump_abs:
            outliers.append({"date": date_text, "reason": "basis_jump_outlier", "value": value, "previous_value": previous[1]})
        previous = (date_text, value)
    warning = bool(outliers)
    return {
        "status": "warning" if warning else "pass",
        "outlier_count": len(outliers),
        "outliers": outliers[:20],
        "blocking_reasons": [],
        "warning_reasons": ["basis_jump_outlier"] if warning else [],
    }


def detect_inventory_outliers(rows: Sequence[Mapping[str, Any]], *, max_inventory_jump_ratio: float = 5.0) -> dict[str, Any]:
    outliers: list[dict[str, Any]] = []
    for field in INVENTORY_FIELDS:
        series = _sorted_numeric_series(rows, field)
        previous: tuple[str, float] | None = None
        for date_text, value in series:
            if previous is not None and previous[1] > 0:
                ratio = abs(value - previous[1]) / previous[1]
                if ratio > max_inventory_jump_ratio:
                    outliers.append({"date": date_text, "field": field, "reason": "inventory_jump_outlier", "ratio": round(ratio, 4)})
            previous = (date_text, value)
    warning = bool(outliers)
    return {
        "status": "warning" if warning else "pass",
        "outlier_count": len(outliers),
        "outliers": outliers[:20],
        "blocking_reasons": [],
        "warning_reasons": ["inventory_jump_outlier"] if warning else [],
    }


def detect_contract_switch_anomalies(rows: Sequence[Mapping[str, Any]], *, max_consecutive_switches: int = 2) -> dict[str, Any]:
    max_run = 0
    current = 0
    invalid_flag = 0
    for row in sorted(rows, key=_date_value):
        value = _number(row.get("main_contract_switch_flag"))
        if value not in {0.0, 1.0}:
            invalid_flag += 1
            current = 0
            continue
        if value == 1:
            current += 1
            max_run = max(max_run, current)
        else:
            current = 0
    blocking = ["invalid_contract_switch_flag"] if invalid_flag else []
    warnings = ["contract_switch_consecutive_anomaly"] if max_run > max_consecutive_switches else []
    return {
        "status": "fail" if blocking else "warning" if warnings else "pass",
        "max_consecutive_switches": max_run,
        "invalid_flag_count": invalid_flag,
        "blocking_reasons": blocking,
        "warning_reasons": warnings,
    }


def compute_quality_gate(
    *,
    row_count: int,
    null_rate_result: Mapping[str, Any],
    duplicate_result: Mapping[str, Any],
    invalid_result: Mapping[str, Any],
    outlier_summary: Mapping[str, Any],
    contract_switch_summary: Mapping[str, Any],
) -> dict[str, Any]:
    blocking = _unique(
        [
            *(null_rate_result.get("blocking_reasons") or []),
            *(duplicate_result.get("blocking_reasons") or []),
            *(invalid_result.get("blocking_reasons") or []),
            *(outlier_summary.get("blocking_reasons") or []),
            *(contract_switch_summary.get("blocking_reasons") or []),
        ]
    )
    warnings = _unique(
        [
            *(outlier_summary.get("warning_reasons") or []),
            *(contract_switch_summary.get("warning_reasons") or []),
        ]
    )
    if row_count <= 0 and "managed_rows_missing" not in blocking:
        blocking.insert(0, "managed_rows_missing")
    penalty = len(blocking) * 0.2 + len(warnings) * 0.05
    quality_score = 0.0 if row_count <= 0 else round(max(0.0, min(1.0, 1.0 - penalty)), 4)
    status = "fail" if blocking else "warning" if warnings else "pass"
    return {
        "status": status,
        "quality_score": quality_score,
        "gate_passed": not blocking and row_count > 0,
        "blocking_reasons": blocking,
        "warning_reasons": warnings,
    }


def _outlier_summary(basis: Mapping[str, Any], inventory: Mapping[str, Any]) -> dict[str, Any]:
    blocking = _unique([*(basis.get("blocking_reasons") or []), *(inventory.get("blocking_reasons") or [])])
    warnings = _unique([*(basis.get("warning_reasons") or []), *(inventory.get("warning_reasons") or [])])
    return {
        "status": "fail" if blocking else "warning" if warnings else "pass",
        "basis": dict(basis),
        "inventory": dict(inventory),
        "outlier_count": int(basis.get("outlier_count") or 0) + int(inventory.get("outlier_count") or 0),
        "blocking_reasons": blocking,
        "warning_reasons": warnings,
    }


def build_managed_data_quality_scorecard(
    *,
    rows: Sequence[Mapping[str, Any]] | None = None,
    write: bool = True,
) -> dict[str, Any]:
    clean_rows = [dict(row) for row in (rows if rows is not None else _load_rows()) if isinstance(row, Mapping)]
    null_rate = validate_required_field_null_rate(clean_rows)
    duplicates = detect_duplicate_keys(clean_rows)
    invalid = detect_negative_or_invalid_values(clean_rows)
    basis = detect_basis_outliers(clean_rows)
    inventory = detect_inventory_outliers(clean_rows)
    outliers = _outlier_summary(basis, inventory)
    contract = detect_contract_switch_anomalies(clean_rows)
    gate = compute_quality_gate(
        row_count=len(clean_rows),
        null_rate_result=null_rate,
        duplicate_result=duplicates,
        invalid_result=invalid,
        outlier_summary=outliers,
        contract_switch_summary=contract,
    )
    status = "blocked" if not clean_rows else gate["status"]
    payload = {
        "status": status,
        "quality_version": QUALITY_VERSION,
        "generated_at": _now(),
        "row_count": len(clean_rows),
        "date_range": _date_range(clean_rows),
        "null_rate_by_field": null_rate.get("null_rate_by_field") or {},
        "duplicate_key_count": duplicates.get("duplicate_key_count", 0),
        "invalid_value_count": invalid.get("invalid_value_count", 0),
        "outlier_summary": outliers,
        "contract_switch_anomaly_summary": contract,
        "quality_score": gate["quality_score"],
        "gate_passed": bool(gate["gate_passed"]),
        "blocking_reasons": gate["blocking_reasons"],
        "warning_reasons": gate["warning_reasons"],
        "training_invoked": False,
        "active_updated": False,
        "customer_prediction_generated": False,
        "fake_data_used": False,
        "mock_data_used": False,
        "scorecard_path": str(_scorecard_path()),
        "message_zh": "managed data quality gate passed." if gate["gate_passed"] else "managed data quality gate blocked.",
    }
    safe = sanitize_for_json(payload)
    safe["message_zh"] = sanitize_text(safe.get("message_zh", ""))
    return _write_scorecard(safe) if write else safe


def get_latest_managed_data_quality_scorecard() -> dict[str, Any]:
    payload = _read_json(_scorecard_path())
    if isinstance(payload, Mapping):
        return sanitize_for_json(dict(payload))
    return build_managed_data_quality_scorecard(rows=[], write=False)
