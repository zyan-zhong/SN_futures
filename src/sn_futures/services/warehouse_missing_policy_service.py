from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping

from ..api.json_utils import sanitize_for_json
from ..runtime import get_user_output_dir


POLICY_FILE = "warehouse_missing_policy.json"
WAREHOUSE_OUTPUT_FILE = "sn_warehouse_receipts.json"


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _output_dir() -> Path:
    return get_user_output_dir()


def _fundamentals_dir(output_dir: Path | None = None) -> Path:
    path = (output_dir or _output_dir()) / "fundamentals"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _read_json(path: Path) -> Any:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(sanitize_for_json(payload), ensure_ascii=False, indent=2), encoding="utf-8")


def _rows(payload: Any) -> list[Mapping[str, Any]]:
    if isinstance(payload, Mapping):
        values = payload.get("rows") or payload.get("data") or payload.get("history") or []
    elif isinstance(payload, list):
        values = payload
    else:
        values = []
    return [row for row in values if isinstance(row, Mapping) and not row.get("sample") and not row.get("mock_data_used")]


def _safe_text(value: Any) -> str:
    return str(value or "").strip().upper()


def _is_sn_row(row: Mapping[str, Any]) -> bool:
    candidates = [
        row.get("symbol"),
        row.get("ts_code"),
        row.get("contract"),
        row.get("main_contract"),
        row.get("near_contract"),
        row.get("far_contract"),
        row.get("product"),
        row.get("品种"),
        row.get("商品"),
    ]
    text = " ".join(_safe_text(item) for item in candidates if item)
    if not text:
        return True
    tokens = text.replace(".", " ").replace("_", " ").replace("-", " ").split()
    return any(token == "SN" or token.startswith("SN") or "沪锡" in token or "锡" == token for token in tokens)


def _number(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        parsed = float(value)
    except Exception:
        return None
    return parsed if parsed == parsed else None


def _warehouse_value(row: Mapping[str, Any]) -> float | None:
    for key in (
        "warehouse_receipt",
        "shfe_warehouse_receipt",
        "receipt",
        "wsr",
        "vol",
        "value",
        "wh_receipt",
        "仓单",
        "注册仓单",
    ):
        if key in row:
            value = _number(row.get(key))
            if value is not None:
                return value
    return None


def _normalise_warehouse_rows(rows: list[Mapping[str, Any]], *, source: str) -> list[dict[str, Any]]:
    normalised: list[dict[str, Any]] = []
    for row in rows:
        if not _is_sn_row(row):
            continue
        trade_date = str(row.get("trade_date") or row.get("date") or "").strip()
        receipt = _warehouse_value(row)
        if not trade_date or receipt is None:
            continue
        normalised.append(
            {
                "trade_date": trade_date,
                "product": "SN",
                "warehouse": str(row.get("warehouse") or row.get("warehouse_name") or row.get("wh_name") or "").strip(),
                "warehouse_receipt": receipt,
                "shfe_warehouse_receipt": receipt,
                "source": source,
                "from_cache": bool(row.get("from_cache")),
                "quality_flag": "real",
            }
        )
    return sorted(normalised, key=lambda item: (item["trade_date"], item["warehouse"]))


def _tushare_warehouse_status(fundamentals: Path) -> dict[str, Any]:
    status = _read_json(fundamentals / "tushare_provider_status.json")
    if isinstance(status, Mapping):
        result = ((status.get("results") or {}).get("tushare_warehouse") if isinstance(status.get("results"), Mapping) else None) or {}
        if isinstance(result, Mapping):
            return dict(result)
    return {}


def _missing_reason(fundamentals: Path) -> str:
    tushare_status = _tushare_warehouse_status(fundamentals)
    status = str(tushare_status.get("status") or "").strip()
    if status == "no_sn_rows":
        return "tushare_fut_wsr_no_sn_rows"
    if status:
        return f"warehouse_source_unavailable:{status}"
    return "warehouse_source_missing"


def _real_warehouse_candidates(fundamentals: Path) -> tuple[str, list[dict[str, Any]]]:
    managed_rows = _normalise_warehouse_rows(_rows(_read_json(fundamentals / "managed_fundamentals.json")), source="managed_data_proxy")
    if managed_rows:
        return "managed_proxy", managed_rows

    tushare_rows = _normalise_warehouse_rows(_rows(_read_json(fundamentals / "sn_tushare_warehouse_receipt.json")), source="tushare")
    if tushare_rows:
        return "tushare_fut_wsr", tushare_rows

    shfe_rows = _normalise_warehouse_rows(_rows(_read_json(fundamentals / "sn_shfe_warehouse_receipts.json")), source="shfe_public")
    if shfe_rows:
        return "shfe_public", shfe_rows

    return "", []


def build_warehouse_missing_policy(*, output_dir: Path | None = None) -> dict[str, Any]:
    fundamentals = _fundamentals_dir(output_dir)
    policy_path = fundamentals / POLICY_FILE
    source, rows = _real_warehouse_candidates(fundamentals)
    if rows:
        warehouse_path = fundamentals / WAREHOUSE_OUTPUT_FILE
        _write_json(
            warehouse_path,
            {
                "schema_version": 1,
                "source": source,
                "generated_at": _now(),
                "sample_data_used": False,
                "mock_data_used": False,
                "baseline_used": False,
                "rows": rows,
            },
        )
        policy = {
            "generated_at": _now(),
            "warehouse_receipt_available": True,
            "source": source,
            "reason": "real_sn_warehouse_receipt_available",
            "row_count": len(rows),
            "warehouse_receipt_path": str(warehouse_path),
            "no_fake_data": True,
            "inventory_missing_flag": 0,
            "warehouse_data_quality_score": 1.0,
            "model_usage_policy": {
                "inventory_numeric_factor": "allowed_real_only",
                "risk_feature": "inventory_missing_flag",
                "no_trade_filter": "not_required",
                "weighting": "normal",
            },
            "message_zh": "已发现真实沪锡仓单数据；系统未伪造字段。",
        }
    else:
        policy = {
            "generated_at": _now(),
            "warehouse_receipt_available": False,
            "source": "missing_real_warehouse_receipt",
            "reason": _missing_reason(fundamentals),
            "row_count": 0,
            "warehouse_receipt_path": "",
            "no_fake_data": True,
            "inventory_missing_flag": 1,
            "warehouse_data_quality_score": 0.0,
            "model_usage_policy": {
                "inventory_numeric_factor": "excluded",
                "risk_feature": "inventory_missing_flag",
                "no_trade_filter": "allow_no_trade_or_downweight",
                "weighting": "downweight_inventory_dependent_models",
            },
            "message_zh": "当前无真实沪锡仓单数据，系统未伪造字段；模型将使用缺失风险标记。",
        }
    policy["policy_path"] = str(policy_path)
    policy["customer_prediction_generated"] = False
    policy["active_model_written"] = False
    _write_json(policy_path, policy)
    return sanitize_for_json(policy)
