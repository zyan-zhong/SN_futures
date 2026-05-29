from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping

from ..api.json_utils import sanitize_for_json
from ..runtime import get_user_output_dir
from .api_key_resolver import resolve_secret


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


def _status_from_file(path: Path, default_status: str = "unavailable") -> dict[str, Any]:
    payload = _read_json(path)
    if not isinstance(payload, Mapping):
        return {"status": default_status, "last_success_time": "", "row_count": 0, "message_zh": "尚未刷新。"}
    status = str(payload.get("status") or payload.get("freshness_label") or default_status)
    rows = payload.get("rows")
    row_count = int(payload.get("row_count") or (len(rows) if isinstance(rows, list) else 0))
    return {
        "status": status,
        "last_success_time": str(payload.get("last_success_time") or payload.get("generated_at") or ""),
        "last_attempt_time": str(payload.get("last_attempt_time") or ""),
        "cooldown_until": str(payload.get("cooldown_until") or ""),
        "from_cache": bool(payload.get("from_cache")),
        "row_count": row_count,
        "message_zh": str(payload.get("message_zh") or ""),
    }


def _entry(
    *,
    source_id: str,
    category: str,
    provider: str,
    enabled: bool,
    requires_key: bool,
    requires_paid_account: bool,
    priority: int,
    ttl_seconds: int,
    legal_note: str,
    fields_provided: list[str],
    status: str,
    last_success_time: str = "",
    last_attempt_time: str = "",
    cooldown_until: str = "",
    row_count: int = 0,
    from_cache: bool = False,
    next_actions_zh: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "source_id": source_id,
        "category": category,
        "provider": provider,
        "enabled": enabled,
        "requires_key": requires_key,
        "requires_paid_account": requires_paid_account,
        "client_upload_required": False,
        "priority": priority,
        "ttl_seconds": ttl_seconds,
        "legal_note": legal_note,
        "fields_provided": fields_provided,
        "status": status,
        "last_success_time": last_success_time,
        "last_attempt_time": last_attempt_time,
        "cooldown_until": cooldown_until,
        "row_count": row_count,
        "from_cache": from_cache,
        "next_actions_zh": next_actions_zh or [],
    }


def build_online_data_source_registry() -> dict[str, Any]:
    fundamentals = _fundamentals_dir()
    shfe_status = _read_json(fundamentals / "shfe_public_provider_status.json")
    shfe_results = shfe_status.get("results") if isinstance(shfe_status, Mapping) and isinstance(shfe_status.get("results"), Mapping) else {}
    fx_status = _status_from_file(fundamentals / "fx_macro_provider_status.json")
    lme_status = _status_from_file(fundamentals / "lme_tin_provider_status.json", default_status="paid_or_unavailable")
    managed_enabled = os.getenv("SN_MANAGED_DATA_PROXY_ENABLED", "").strip().lower() in {"1", "true", "yes", "on"}
    alpha_key = resolve_secret("SN_ALPHA_VANTAGE_KEY")
    news_key = resolve_secret("SN_NEWSAPI_KEY")
    managed_token = str(resolve_secret("SN_MANAGED_DATA_PROXY_TOKEN").get("value") or "")

    def result_status(key: str, fallback: str) -> tuple[str, str]:
        item = shfe_results.get(key) if isinstance(shfe_results, Mapping) else None
        if isinstance(item, Mapping):
            return str(item.get("status") or fallback), str(item.get("last_success_time") or "")
        return fallback, ""

    inventory_status, inventory_success = result_status("shfe_inventory", "unavailable")
    receipt_status, receipt_success = result_status("shfe_warehouse_receipts", "unavailable")
    basis_status, basis_success = result_status("spot_basis", "unavailable")
    exchange_status, exchange_success = result_status("exchange_daily", "unavailable")

    entries = [
        _entry(
            source_id="akshare_futures_inventory_em",
            category="inventory",
            provider="akshare",
            enabled=True,
            requires_key=False,
            requires_paid_account=False,
            priority=1,
            ttl_seconds=36 * 3600,
            legal_note="公开 AKShare 辅助源；仅保留锡/SN 行，不用其它品种替代。",
            fields_provided=["shfe_inventory", "inventory_delta_1w", "inventory_delta_4w"],
            status=inventory_status,
            last_success_time=inventory_success,
            next_actions_zh=["点击刷新基础数据；如仍无锡行，等待 AKShare/交易所源更新。"],
        ),
        _entry(
            source_id="akshare_warehouse_receipt",
            category="warehouse_receipt",
            provider="akshare",
            enabled=True,
            requires_key=False,
            requires_paid_account=False,
            priority=1,
            ttl_seconds=36 * 3600,
            legal_note="公开 AKShare 仓单辅助源；无锡数据时不伪造。",
            fields_provided=["shfe_warehouse_receipt", "warehouse_receipt_delta_1w"],
            status=receipt_status,
            last_success_time=receipt_success,
            next_actions_zh=["点击刷新基础数据；检查当前 AKShare 版本是否支持锡仓单。"],
        ),
        _entry(
            source_id="akshare_spot_basis",
            category="spot_basis",
            provider="akshare",
            enabled=True,
            requires_key=False,
            requires_paid_account=False,
            priority=1,
            ttl_seconds=36 * 3600,
            legal_note="公开现货/基差辅助源；缺现货价格时 basis 因子保持不可用。",
            fields_provided=["spot_price", "spot_premium", "spot_futures_basis"],
            status=basis_status,
            last_success_time=basis_success,
            next_actions_zh=["点击刷新基础数据；如公开源无锡行，可使用托管数据服务补齐。"],
        ),
        _entry(
            source_id="akshare_exchange_daily",
            category="term_structure",
            provider="akshare",
            enabled=True,
            requires_key=False,
            requires_paid_account=False,
            priority=1,
            ttl_seconds=36 * 3600,
            legal_note="公开交易所日线/历史辅助源；不把 SN0 同时冒充 near/far。",
            fields_provided=["settlement", "volume", "open_interest"],
            status=exchange_status,
            last_success_time=exchange_success,
            next_actions_zh=["已可用于补齐交易所日线和持仓字段；期限结构仍需要真实多合约曲线。"],
        ),
        _entry(
            source_id="alphavantage_fx_macro",
            category="fx_macro",
            provider="alpha_vantage",
            enabled=True,
            requires_key=True,
            requires_paid_account=False,
            priority=2,
            ttl_seconds=24 * 3600,
            legal_note="Alpha Vantage 只用于 FX/Treasury/宏观代理，不用于沪锡主行情或库存基差。",
            fields_provided=["usd_cny", "usd_cny_return", "us10y", "us10y_change", "copper_global_proxy"],
            status=fx_status["status"] if alpha_key.get("configured") else "key_missing",
            last_success_time=str(fx_status.get("last_success_time") or ""),
            last_attempt_time=str(fx_status.get("last_attempt_time") or ""),
            cooldown_until=str(fx_status.get("cooldown_until") or ""),
            row_count=int(fx_status.get("row_count") or 0),
            from_cache=bool(fx_status.get("from_cache")),
            next_actions_zh=["在设置页配置 Alpha Vantage key；无需上传 CSV/Excel。"] if not alpha_key.get("configured") else ["点击刷新跨市场数据。"],
        ),
        _entry(
            source_id="newsapi_events",
            category="news",
            provider="newsapi",
            enabled=True,
            requires_key=True,
            requires_paid_account=False,
            priority=2,
            ttl_seconds=24 * 3600,
            legal_note="NewsAPI 只用于事件新闻；key 通过 X-Api-Key header 发送，不拼 URL。",
            fields_provided=["title", "description", "published_at", "relevance_score", "used_in_model"],
            status="configured" if news_key.get("configured") else "key_missing",
            last_success_time="",
            next_actions_zh=["在设置页配置 NewsAPI key；无需上传 CSV/Excel。"] if not news_key.get("configured") else ["点击刷新新闻并查看相关性报告。"],
        ),
        _entry(
            source_id="public_lme_tin_probe",
            category="lme",
            provider="public_web",
            enabled=True,
            requires_key=False,
            requires_paid_account=True,
            priority=3,
            ttl_seconds=24 * 3600,
            legal_note="无可靠免费结构化 LME tin 源时不使用铜/铝替代，也不从新闻价格入结构化因子。",
            fields_provided=["lme_tin_close", "lme_tin_inventory"],
            status=str(lme_status.get("status") or "paid_or_unavailable"),
            last_success_time=str(lme_status.get("last_success_time") or ""),
            next_actions_zh=["若需要完整 LME tin，可接入正式数据供应商或发行方托管数据服务。"],
        ),
        _entry(
            source_id="managed_data_proxy",
            category="spot_basis",
            provider="managed_proxy",
            enabled=managed_enabled,
            requires_key=True,
            requires_paid_account=True,
            priority=4,
            ttl_seconds=24 * 3600,
            legal_note="正式客户免配置推荐方案；第三方 API key 由发行方服务器维护，不能写入公开安装包。",
            fields_provided=["spot_price", "basis", "inventory", "warehouse_receipt", "lme_tin_close"],
            status="disabled" if not managed_enabled else "token_missing" if not managed_token else "unavailable",
            last_success_time="",
            next_actions_zh=["默认关闭；如发行方提供托管服务，在设置页启用并配置 license token。"],
        ),
    ]
    return sanitize_for_json(
        {
            "generated_at": _now(),
            "client_upload_required": False,
            "message_zh": "系统会自动尝试公开在线源和可选托管源；客户不需要 CSV/Excel。",
            "sources": entries,
        }
    )
