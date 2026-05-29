from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping, Sequence

import pandas as pd

from ..api.json_utils import sanitize_for_json
from ..runtime import get_user_output_dir


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _fundamentals_dir() -> Path:
    path = get_user_output_dir() / "fundamentals"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(sanitize_for_json(payload), ensure_ascii=False, indent=2), encoding="utf-8")


def _contract_sort_key(contract: str) -> tuple[int, str]:
    match = re.search(r"(\d{3,4})", contract or "")
    if not match:
        return (999999, contract)
    number = match.group(1)
    if len(number) == 3:
        number = f"2{number}"
    return (int(number), contract)


def _row_date(row: Mapping[str, Any]) -> str:
    return str(row.get("trade_date") or row.get("date") or row.get("日期") or row.get("time") or "")[:10]


def _row_contract(row: Mapping[str, Any]) -> str:
    return str(row.get("contract") or row.get("合约") or row.get("symbol") or row.get("品种") or "")


def _to_float(value: Any) -> float | None:
    try:
        number = float(value)
    except Exception:
        return None
    return number if pd.notna(number) else None


def normalize_contract_curve_rows(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Build real near/far term structure rows from multi-contract input.

    A single continuous contract such as SN0 is explicitly rejected because it
    cannot represent both near and far contracts.
    """

    grouped: dict[str, list[Mapping[str, Any]]] = {}
    for row in rows:
        date = _row_date(row)
        contract = _row_contract(row).upper()
        close = _to_float(row.get("close") or row.get("收盘") or row.get("收盘价") or row.get("price"))
        if not date or not contract or close is None or close <= 0:
            continue
        grouped.setdefault(date, []).append(row)

    curve_rows: list[dict[str, Any]] = []
    for trade_date, day_rows in sorted(grouped.items()):
        unique: dict[str, Mapping[str, Any]] = {}
        for row in day_rows:
            contract = _row_contract(row).upper()
            if contract:
                unique[contract] = row
        if len(unique) < 2:
            continue
        ordered = sorted(unique.items(), key=lambda item: _contract_sort_key(item[0]))
        near_contract, near_row = ordered[0]
        far_contract, far_row = ordered[-1]
        if near_contract == far_contract:
            continue
        near_close = _to_float(near_row.get("close") or near_row.get("收盘") or near_row.get("收盘价") or near_row.get("price"))
        far_close = _to_float(far_row.get("close") or far_row.get("收盘") or far_row.get("收盘价") or far_row.get("price"))
        if near_close is None or far_close is None or near_close <= 0 or far_close <= 0:
            continue
        near_oi = _to_float(near_row.get("open_interest") or near_row.get("持仓量"))
        far_oi = _to_float(far_row.get("open_interest") or far_row.get("持仓量"))
        main_contract = max(
            ordered,
            key=lambda item: _to_float(item[1].get("volume") or item[1].get("成交量")) or -1,
        )[0]
        curve_rows.append(
            {
                "trade_date": trade_date,
                "near_contract": near_contract,
                "far_contract": far_contract,
                "main_contract": main_contract,
                "near_contract_close": near_close,
                "far_contract_close": far_close,
                "near_open_interest": near_oi,
                "far_open_interest": far_oi,
                "near_volume": _to_float(near_row.get("volume") or near_row.get("成交量")),
                "far_volume": _to_float(far_row.get("volume") or far_row.get("成交量")),
                "main_contract_switch_flag": 0.0,
                "roll_yield_proxy": far_close / near_close - 1.0,
                "term_structure_slope": (near_close - far_close) / near_close,
            }
        )
    for idx in range(1, len(curve_rows)):
        curve_rows[idx]["main_contract_switch_flag"] = 1.0 if curve_rows[idx]["main_contract"] != curve_rows[idx - 1]["main_contract"] else 0.0

    if not curve_rows:
        return {
            "success": False,
            "status": "unavailable",
            "message_zh": "只能拿到主力连续或单合约数据，期限结构不可用；未用 SN0 冒充近远月。",
            "rows": [],
        }
    return {
        "success": True,
        "status": "success",
        "message_zh": "真实多合约期限结构已标准化。",
        "rows": curve_rows,
    }


def refresh_term_structure_data(force: bool = False) -> dict[str, Any]:
    _ = force
    out = _fundamentals_dir()
    curve_path = out / "sn_contract_curve.json"
    term_path = out / "sn_term_structure.json"
    status_path = out / "term_structure_status.json"

    # The current verified market chain provides SN0/main continuous history.
    # Until a reliable multi-contract source is configured, explicitly mark
    # term structure as unavailable instead of synthesising near/far contracts.
    result = normalize_contract_curve_rows([])
    payload = {
        "generated_at": _now(),
        "source": "real_multi_contract_provider",
        "sample": False,
        "rows": result["rows"],
        "message_zh": result["message_zh"],
    }
    status = {
        "source_name": "term_structure",
        "enabled": True,
        "configured": False,
        "attempted": True,
        "success": bool(result["success"]),
        "from_cache": False,
        "stale": False,
        "freshness_label": "未启用",
        "last_attempt_time": _now(),
        "last_success_time": "",
        "row_count": len(result["rows"]),
        "error_code": "multi_contract_unavailable",
        "message_zh": result["message_zh"],
        "next_actions_zh": ["接入真实 SHFE 多合约日线/持仓数据", "不要用 SN0 同时冒充 near/far"],
    }
    _write_json(curve_path, payload)
    _write_json(term_path, payload)
    _write_json(status_path, status)
    return sanitize_for_json(
        {
            "status": "skipped",
            "message_zh": result["message_zh"],
            "row_count": 0,
            "output_files": [str(curve_path), str(term_path), str(status_path)],
            "next_actions_zh": status["next_actions_zh"],
        }
    )

