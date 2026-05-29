from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping, Sequence

import pandas as pd

from ..api.json_utils import sanitize_for_json
from ..runtime import get_user_output_dir
from .shfe_public_data_service import refresh_shfe_public_data
from .term_structure_data_service import refresh_term_structure_data


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _fundamentals_dir() -> Path:
    path = get_user_output_dir() / "fundamentals"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(sanitize_for_json(payload), ensure_ascii=False, indent=2), encoding="utf-8")


def _read_json(path: Path) -> Any:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _payload_rows(path: Path) -> list[Mapping[str, Any]]:
    payload = _read_json(path)
    if isinstance(payload, Mapping) and isinstance(payload.get("rows"), list):
        return [row for row in payload["rows"] if isinstance(row, Mapping)]
    return []


def _to_float(value: Any) -> float | None:
    try:
        number = float(value)
    except Exception:
        return None
    return number if pd.notna(number) else None


def _date(row: Mapping[str, Any]) -> str:
    return str(row.get("trade_date") or row.get("date") or row.get("日期") or row.get("time") or "")[:10]


def build_spot_basis_rows(
    spot_rows: Sequence[Mapping[str, Any]],
    futures_rows: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    spot_by_date: dict[str, Mapping[str, Any]] = {_date(row): row for row in spot_rows if _date(row)}
    futures_by_date: dict[str, Mapping[str, Any]] = {_date(row): row for row in futures_rows if _date(row)}
    rows: list[dict[str, Any]] = []
    for trade_date in sorted(set(spot_by_date) & set(futures_by_date)):
        spot = spot_by_date[trade_date]
        future = futures_by_date[trade_date]
        spot_price = _to_float(spot.get("spot_price") or spot.get("price") or spot.get("现货价格"))
        futures_close = _to_float(future.get("futures_close") or future.get("close") or future.get("收盘"))
        if spot_price is None or futures_close is None or spot_price <= 0 or futures_close <= 0:
            continue
        spot_premium = _to_float(spot.get("spot_premium") or spot.get("premium") or spot.get("升贴水")) or 0.0
        rows.append(
            {
                "trade_date": trade_date,
                "spot_price": spot_price,
                "futures_close": futures_close,
                "spot_premium": spot_premium,
                "spot_futures_basis": spot_price - futures_close,
            }
        )
    if not rows:
        return {"success": False, "rows": [], "message_zh": "缺少真实现货锡价格或期货收盘价，基差因子不可用。"}
    frame = pd.DataFrame(rows)
    basis = pd.to_numeric(frame["spot_futures_basis"], errors="coerce")
    frame["basis_zscore_60"] = (basis - basis.rolling(60).mean()) / basis.rolling(60).std()
    frame["basis_percentile_252"] = basis.rolling(252).rank(pct=True)
    frame["cash_tightness_score"] = frame["basis_zscore_60"].fillna(0.0)
    return {"success": True, "rows": frame.where(pd.notna(frame), None).to_dict(orient="records"), "message_zh": "现货/基差数据已标准化。"}


def build_inventory_rows(
    shfe_rows: Sequence[Mapping[str, Any]],
    lme_rows: Sequence[Mapping[str, Any]],
    warehouse_rows: Sequence[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    shfe_by_date = {_date(row): row for row in shfe_rows if _date(row)}
    lme_by_date = {_date(row): row for row in lme_rows if _date(row)}
    wh_by_date = {_date(row): row for row in (warehouse_rows or []) if _date(row)}
    dates = sorted(set(shfe_by_date) | set(lme_by_date) | set(wh_by_date))
    rows: list[dict[str, Any]] = []
    for trade_date in dates:
        shfe_inventory = _to_float((shfe_by_date.get(trade_date) or {}).get("shfe_inventory") or (shfe_by_date.get(trade_date) or {}).get("inventory"))
        lme_inventory = _to_float((lme_by_date.get(trade_date) or {}).get("lme_inventory") or (lme_by_date.get(trade_date) or {}).get("inventory"))
        receipt = _to_float((wh_by_date.get(trade_date) or {}).get("shfe_warehouse_receipt") or (wh_by_date.get(trade_date) or {}).get("warehouse_receipt"))
        if shfe_inventory is None and lme_inventory is None and receipt is None:
            continue
        rows.append(
            {
                "trade_date": trade_date,
                "shfe_inventory": shfe_inventory,
                "shfe_warehouse_receipt": receipt,
                "lme_inventory": lme_inventory,
                "bonded_inventory": None,
                "global_visible_inventory": (shfe_inventory or 0.0) + (lme_inventory or 0.0),
            }
        )
    if not rows:
        return {"success": False, "rows": [], "message_zh": "缺少真实 SHFE/LME 库存或仓单数据，库存因子不可用。"}
    frame = pd.DataFrame(rows)
    for col in ("shfe_inventory", "shfe_warehouse_receipt", "lme_inventory", "global_visible_inventory"):
        frame[col] = pd.to_numeric(frame[col], errors="coerce")
    frame["inventory_delta_1w"] = frame["global_visible_inventory"].diff(5)
    frame["inventory_delta_4w"] = frame["global_visible_inventory"].diff(20)
    frame["warehouse_receipt_delta_1w"] = frame["shfe_warehouse_receipt"].diff(5)
    frame["inventory_percentile_3y"] = frame["global_visible_inventory"].rolling(756).rank(pct=True)
    return {"success": True, "rows": frame.where(pd.notna(frame), None).to_dict(orient="records"), "message_zh": "库存/仓单数据已标准化。"}


def refresh_fundamental_data(force: bool = False) -> dict[str, Any]:
    out = _fundamentals_dir()
    term_result = refresh_term_structure_data(force=force)
    shfe_result = refresh_shfe_public_data(force=force)

    spot_path = out / "sn_spot_basis.json"
    inv_path = out / "sn_inventory.json"
    receipts_path = out / "sn_warehouse_receipts.json"
    status_path = out / "fundamental_status.json"

    if not spot_path.exists():
        spot_basis = build_spot_basis_rows([], [])
        _write_json(spot_path, {"generated_at": _now(), "sample": False, "rows": spot_basis["rows"], "message_zh": spot_basis["message_zh"]})
    if not inv_path.exists():
        inventory = build_inventory_rows([], [], [])
        _write_json(inv_path, {"generated_at": _now(), "sample": False, "rows": inventory["rows"], "message_zh": inventory["message_zh"]})
    if not receipts_path.exists():
        inventory = build_inventory_rows([], [], [])
        _write_json(receipts_path, {"generated_at": _now(), "sample": False, "rows": inventory["rows"], "message_zh": inventory["message_zh"]})

    spot_rows = _payload_rows(spot_path)
    inventory_rows = _payload_rows(inv_path)
    receipt_rows = _payload_rows(receipts_path)
    shfe_steps = shfe_result.get("results", {}) if isinstance(shfe_result, Mapping) else {}
    success_count = sum(1 for value in shfe_steps.values() if isinstance(value, Mapping) and value.get("success"))
    success = bool(spot_rows or inventory_rows or receipt_rows or success_count)
    status = {
        "source_name": "fundamentals",
        "enabled": True,
        "configured": True,
        "attempted": True,
        "success": success,
        "from_cache": False,
        "freshness_label": "正常" if success else "无锡数据",
        "last_attempt_time": _now(),
        "last_success_time": _now() if success else "",
        "row_count": len(spot_rows) + len(inventory_rows) + len(receipt_rows),
        "message_zh": "SHFE/AKShare 库存、仓单、基差和交易所日线辅助源已尝试；失败项会保留具体原因，不伪造字段。",
        "next_actions_zh": [
            "检查 AKShare 版本和网络。",
            "若 SHFE 官网直连被 WAF 阻断，优先使用 AKShare/缓存辅助源。",
            "无锡数据时不能用其它品种替代。",
        ],
        "term_structure_step": term_result,
        "shfe_public_step": shfe_result,
    }
    _write_json(status_path, status)
    return sanitize_for_json(
        {
            "status": "success" if success else "partial_success",
            "message_zh": status["message_zh"],
            "row_count": status["row_count"],
            "output_files": [str(spot_path), str(inv_path), str(receipts_path), str(status_path)]
            + list(shfe_result.get("output_files", []) if isinstance(shfe_result, Mapping) else []),
            "next_actions_zh": status["next_actions_zh"],
            "active_updated": False,
            "customer_prediction_generated": False,
            "baseline_used": False,
        }
    )
