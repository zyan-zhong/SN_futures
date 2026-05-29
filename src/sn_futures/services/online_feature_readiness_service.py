from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping

import pandas as pd

from ..api.json_utils import sanitize_for_json
from ..runtime import get_user_output_dir
from .feature_coverage_service import build_feature_coverage_report
from .online_data_source_registry import build_online_data_source_registry


FIELD_SOURCES: tuple[dict[str, Any], ...] = (
    {
        "field": "usd_cny",
        "category": "cross_market",
        "source": "alpha_vantage",
        "file": "sn_cross_market.json",
        "status_file": "fx_macro_provider_status.json",
    },
    {
        "field": "usd_cny_return",
        "category": "cross_market",
        "source": "alpha_vantage",
        "file": "sn_cross_market.json",
        "status_file": "fx_macro_provider_status.json",
    },
    {
        "field": "us10y",
        "category": "cross_market",
        "source": "alpha_vantage",
        "file": "sn_cross_market.json",
        "status_file": "fx_macro_provider_status.json",
    },
    {
        "field": "us10y_change",
        "category": "cross_market",
        "source": "alpha_vantage",
        "file": "sn_cross_market.json",
        "status_file": "fx_macro_provider_status.json",
    },
    {
        "field": "copper_global_proxy",
        "category": "cross_market",
        "source": "alpha_vantage",
        "file": "sn_cross_market.json",
        "status_file": "fx_macro_provider_status.json",
    },
    {
        "field": "copper_global_proxy_return",
        "category": "cross_market",
        "source": "alpha_vantage",
        "file": "sn_cross_market.json",
        "status_file": "fx_macro_provider_status.json",
    },
    {
        "field": "copper_proxy_return",
        "category": "cross_market",
        "source": "alpha_vantage",
        "file": "sn_cross_market.json",
        "status_file": "fx_macro_provider_status.json",
    },
    {
        "field": "lme_tin_close",
        "category": "lme",
        "source": "public_web",
        "file": "sn_lme_tin.json",
        "status_file": "lme_tin_provider_status.json",
    },
    {
        "field": "lme_tin_inventory",
        "category": "lme",
        "source": "public_web",
        "file": "sn_lme_tin.json",
        "status_file": "lme_tin_provider_status.json",
    },
    {
        "field": "spot_price",
        "category": "basis",
        "source": "akshare",
        "file": "sn_spot_basis.json",
        "status_file": "shfe_public_provider_status.json",
    },
    {
        "field": "spot_premium",
        "category": "basis",
        "source": "akshare",
        "file": "sn_spot_basis.json",
        "status_file": "shfe_public_provider_status.json",
    },
    {
        "field": "spot_futures_basis",
        "category": "basis",
        "source": "akshare",
        "file": "sn_spot_basis.json",
        "status_file": "shfe_public_provider_status.json",
    },
    {
        "field": "shfe_inventory",
        "category": "inventory",
        "source": "akshare",
        "file": "sn_shfe_inventory.json",
        "status_file": "shfe_public_provider_status.json",
    },
    {
        "field": "shfe_warehouse_receipt",
        "category": "warehouse_receipt",
        "source": "akshare",
        "file": "sn_shfe_warehouse_receipts.json",
        "status_file": "shfe_public_provider_status.json",
    },
    {
        "field": "open_interest",
        "category": "term_structure",
        "source": "akshare",
        "file": "sn_exchange_daily.json",
        "status_file": "shfe_public_provider_status.json",
    },
    {
        "field": "settlement",
        "category": "term_structure",
        "source": "akshare",
        "file": "sn_exchange_daily.json",
        "status_file": "shfe_public_provider_status.json",
    },
)


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _fundamentals_dir() -> Path:
    path = get_user_output_dir() / "fundamentals"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _read_json(path: Path) -> Any:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _rows(payload: Any) -> list[Mapping[str, Any]]:
    if isinstance(payload, Mapping):
        rows = payload.get("rows") or payload.get("data") or payload.get("history") or []
    elif isinstance(payload, list):
        rows = payload
    else:
        rows = []
    return [row for row in rows if isinstance(row, Mapping) and not row.get("sample")]


def _status_from_payload(payload: Any, default: str = "unavailable") -> str:
    if not isinstance(payload, Mapping):
        return default
    if payload.get("sample") or payload.get("sample_mode"):
        return "unavailable"
    return str(payload.get("status") or payload.get("freshness_label") or default)


def _status_for_field(field: str, payload: Any, status_payload: Any) -> str:
    if isinstance(status_payload, Mapping):
        status = _status_from_payload(status_payload)
        if status in {"key_missing", "rate_limited", "paid_or_unavailable", "disabled", "token_missing"}:
            return status
        if status == "success":
            return "unavailable"
        results = status_payload.get("results")
        if isinstance(results, Mapping):
            for item in results.values():
                if isinstance(item, Mapping):
                    fields = item.get("fields") or item.get("fields_provided") or []
                    if field in fields or field in str(item):
                        item_status = str(item.get("status") or "")
                        if item_status:
                            return item_status
    return _status_from_payload(payload)


def _field_readiness(entry: Mapping[str, Any], fundamentals: Path) -> dict[str, Any]:
    field = str(entry["field"])
    payload = _read_json(fundamentals / str(entry["file"]))
    status_payload = _read_json(fundamentals / str(entry["status_file"]))
    rows = _rows(payload)
    total = len(rows)
    non_null = 0
    latest_value: Any = None
    if total:
        frame = pd.DataFrame(rows)
        if field in frame.columns:
            series = frame[field].replace("", pd.NA)
            non_null = int(series.notna().sum())
            valid = series.dropna()
            latest_value = valid.iloc[-1] if not valid.empty else None

    if non_null:
        status = "available"
        message = "字段已由在线数据源提供。"
    else:
        status = _status_for_field(field, payload, status_payload)
        if status == "success":
            status = "unavailable"
        message = _message_for_status(field, status)

    return {
        "field": field,
        "category": entry["category"],
        "status": status,
        "source": entry["source"],
        "non_null_count": non_null,
        "row_count": total,
        "non_null_rate": round(non_null / total, 6) if total else 0.0,
        "latest_value": latest_value,
        "message_zh": message,
    }


def _apply_cross_market_alignment_status(
    field_rows: list[dict[str, Any]],
    alignment: Mapping[str, Any],
) -> list[dict[str, Any]]:
    field_diagnostics = alignment.get("field_diagnostics") if isinstance(alignment, Mapping) else {}
    blocking = alignment.get("blocking_reasons") if isinstance(alignment, Mapping) else []
    blocking_reason = str(blocking[0]) if isinstance(blocking, list) and blocking else ""
    for row in field_rows:
        if row.get("category") != "cross_market":
            continue
        field = str(row.get("field") or "")
        info = field_diagnostics.get(field) if isinstance(field_diagnostics, Mapping) else None
        if isinstance(info, Mapping):
            aligned_rate = float(info.get("non_null_rate") or 0.0)
            row["aligned_non_null_count"] = int(info.get("non_null_count") or 0)
            row["aligned_non_null_rate"] = round(aligned_rate, 6)
            row["usable_for_training"] = bool(aligned_rate >= 0.7)
            if aligned_rate > 0:
                row["status"] = "available"
                row["message_zh"] = (
                    "字段已与沪锡交易日对齐，满足训练覆盖率门槛。"
                    if aligned_rate >= 0.7
                    else "字段已有部分对齐数据，但暂未达到训练覆盖率门槛。"
                )
            else:
                row["status"] = blocking_reason or "insufficient_non_null_rate"
                row["message_zh"] = "字段原始文件存在，但与沪锡交易日对齐后的覆盖率不足。"
        elif blocking_reason:
            row["aligned_non_null_count"] = 0
            row["aligned_non_null_rate"] = 0.0
            row["status"] = blocking_reason
            row["message_zh"] = "cross-market 数据未能与沪锡行情历史有效对齐。"
    return field_rows


def _message_for_status(field: str, status: str) -> str:
    if status == "key_missing":
        return f"{field} 需要配置对应 API key 后才能自动获取。"
    if status == "paid_or_unavailable":
        return f"{field} 当前没有可靠免费结构化在线源；系统不会用其它品种或新闻价格替代。"
    if status == "disabled":
        return f"{field} 对应托管数据服务当前关闭。"
    if status == "token_missing":
        return f"{field} 需要托管数据服务 license token。"
    if status in {"no_tin_rows", "function_unavailable", "missing_required_columns"}:
        return f"{field} 公开在线源当前无法提供沪锡相关结构化字段。"
    return f"{field} 暂不可用；系统不会伪造该字段。"


def _coverage_group_map(coverage: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    groups = coverage.get("groups") if isinstance(coverage, Mapping) else []
    return {str(group.get("group")): group for group in groups if isinstance(group, Mapping)}


def _factor_group_readiness(field_rows: list[dict[str, Any]], coverage: Mapping[str, Any]) -> list[dict[str, Any]]:
    by_group = _coverage_group_map(coverage)
    field_by_category: dict[str, list[dict[str, Any]]] = {}
    for row in field_rows:
        field_by_category.setdefault(str(row["category"]), []).append(row)

    group_to_categories = {
        "term_structure": ["term_structure"],
        "basis": ["basis"],
        "inventory": ["inventory", "warehouse_receipt"],
        "cross_market": ["cross_market", "lme"],
        "event": ["news"],
        "raw_market": ["term_structure"],
        "technical": [],
        "mean_reversion": [],
        "regime": [],
    }
    result: list[dict[str, Any]] = []
    for group in (
        "raw_market",
        "technical",
        "mean_reversion",
        "term_structure",
        "basis",
        "inventory",
        "cross_market",
        "event",
        "regime",
    ):
        coverage_row = by_group.get(group, {})
        after = float(coverage_row.get("coverage_rate") or 0.0)
        related = [
            field
            for category in group_to_categories.get(group, [])
            for field in field_by_category.get(category, [])
        ]
        blocking = [str(field["field"]) for field in related if field.get("status") != "available"]
        any_available = any(field.get("status") == "available" for field in related)
        result.append(
            {
                "group": group,
                "coverage_rate_before": 0.0 if related and any_available else after,
                "coverage_rate_after": after,
                "usable_now": bool(after >= 0.7),
                "blocking_fields": blocking,
                "online_fields_available": [str(field["field"]) for field in related if field.get("status") == "available"],
            }
        )
    return result


def build_online_feature_readiness_report() -> dict[str, Any]:
    fundamentals = _fundamentals_dir()
    registry = build_online_data_source_registry()
    coverage = build_feature_coverage_report()
    alignment = coverage.get("cross_market_diagnostics") if isinstance(coverage, Mapping) else {}
    field_rows = _apply_cross_market_alignment_status(
        [_field_readiness(entry, fundamentals) for entry in FIELD_SOURCES],
        alignment if isinstance(alignment, Mapping) else {},
    )
    group_rows = _factor_group_readiness(field_rows, coverage)

    available_fields = [row["field"] for row in field_rows if row["status"] == "available"]
    unavailable_fields = [row["field"] for row in field_rows if row["status"] != "available"]
    coverage_usable = set(coverage.get("usable_feature_cols") or [])
    has_cross_market = any(field in coverage_usable for field in ("usd_cny_return", "us10y_change", "copper_global_proxy_return"))
    has_basis_inventory = all(field in available_fields for field in ("spot_futures_basis", "shfe_inventory"))
    can_train_ohlcv = bool((coverage.get("training_readiness") or {}).get("can_train_ohlcv_model"))

    next_actions = [
        "配置 Alpha Vantage key 可自动补齐 USD/CNY 与 US10Y。",
        "继续完善 AKShare fundamentals 探测，但公开源没有沪锡行时不伪造。",
        "如需完整 basis/inventory/LME 字段，建议启用发行方托管数据服务或正式数据供应商。",
        "客户不需要上传 CSV/Excel。",
    ]

    return sanitize_for_json(
        {
            "generated_at": _now(),
            "client_upload_required": False,
            "online_sources": registry.get("sources", []),
            "field_readiness": field_rows,
            "available_fields": available_fields,
            "unavailable_fields": unavailable_fields,
            "factor_group_readiness": group_rows,
            "cross_market_alignment_diagnostics": alignment,
            "research_readiness": {
                "can_train_ohlcv_technical_model": can_train_ohlcv,
                "can_train_online_cross_market_model": bool(can_train_ohlcv and has_cross_market),
                "can_train_basis_inventory_model": bool(can_train_ohlcv and has_basis_inventory),
                "can_train_full_institutional_model": bool((coverage.get("training_readiness") or {}).get("can_train_full_fundamental_model")),
                "reason_zh": _research_reason(can_train_ohlcv, has_cross_market, has_basis_inventory),
            },
            "research_priority": _research_priority(can_train_ohlcv, has_cross_market, has_basis_inventory),
            "next_actions_zh": next_actions,
            "message_zh": "在线因子准备度审计完成；本接口不训练模型、不生成预测、不发布 active。",
            "active_updated": False,
            "customer_prediction_generated": False,
            "baseline_used": False,
        }
    )


def _research_reason(can_train_ohlcv: bool, has_cross_market: bool, has_basis_inventory: bool) -> str:
    if not can_train_ohlcv:
        return "真实 OHLCV 历史仍不足，暂不建议进入模型研究。"
    if has_cross_market and not has_basis_inventory:
        return "可继续研究 OHLCV 技术/均值回归/regime 模型，并加入 USD/CNY、US10Y 等在线跨市场字段；basis/inventory/LME 仍需托管或正式数据源。"
    if has_basis_inventory:
        return "基础技术模型与部分基本面模型具备研究条件，但仍需通过 walk-forward 和 promotion gate。"
    return "当前可继续研究 OHLCV 技术/均值回归/regime 模型；完整机构级基本面模型暂不具备条件。"


def _research_priority(can_train_ohlcv: bool, has_cross_market: bool, has_basis_inventory: bool) -> dict[str, list[str]]:
    can_study = []
    should_not_study = []
    if can_train_ohlcv:
        can_study.extend(["OHLCV 技术/均值回归模型", "Regime-aware 模型", "News relevance event model，仅使用 used_in_model=true 新闻"])
    if has_cross_market:
        can_study.append("FX/US10Y cross-market 模型")
    if not has_basis_inventory:
        should_not_study.extend(["basis/inventory 模型", "完整库存/仓单压力模型"])
    should_not_study.extend(["LME tin spread 模型，如果 lme_tin_close 仍缺", "完整 term structure 模型，如果 near/far contract 仍缺"])
    return {
        "can_continue_research": can_study,
        "not_recommended_now": should_not_study,
        "recommended_next_steps": [
            "配置 Alpha Vantage key。",
            "继续完善 AKShare fundamentals 探测。",
            "启用 managed proxy 补齐 basis/inventory/LME。",
            "不要求客户 CSV/Excel。",
        ],
    }
