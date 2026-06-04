from __future__ import annotations

import json
import os
import urllib.parse
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Mapping

from ..api.json_utils import sanitize_for_json
from ..config import mask_secret
from ..runtime import get_user_output_dir
from ..user_data import secrets_path
from ..utils.secret_sanitizer import sanitize_mapping, sanitize_text
from .api_key_resolver import resolve_secret


MANAGED_SCHEMA_FIELDS = (
    "trade_date",
    "spot_price",
    "spot_premium",
    "spot_futures_basis",
    "shfe_inventory",
    "shfe_warehouse_receipt",
    "lme_tin_close",
    "lme_inventory",
    "near_contract",
    "far_contract",
    "near_contract_close",
    "far_contract_close",
    "near_open_interest",
    "far_open_interest",
    "main_contract",
    "main_contract_switch_flag",
)
MANAGED_RESEARCH_GROUPS = {
    "warehouse": ["shfe_warehouse_receipt"],
    "inventory": ["shfe_inventory"],
    "basis": ["spot_price", "spot_premium", "spot_futures_basis"],
    "lme": ["lme_tin_close", "lme_inventory"],
    "term_structure": [
        "near_contract",
        "far_contract",
        "near_contract_close",
        "far_contract_close",
        "near_open_interest",
        "far_open_interest",
        "main_contract",
        "main_contract_switch_flag",
    ],
}
MANAGED_REQUIRED_RESEARCH_FIELDS = tuple(
    dict.fromkeys(
        field
        for fields in MANAGED_RESEARCH_GROUPS.values()
        for field in fields
        if field not in {"near_contract", "far_contract", "main_contract"}
    )
)
NUMERIC_FIELDS = {
    "spot_price",
    "spot_premium",
    "spot_futures_basis",
    "shfe_inventory",
    "shfe_warehouse_receipt",
    "lme_tin_close",
    "lme_inventory",
    "near_contract_close",
    "far_contract_close",
    "near_open_interest",
    "far_open_interest",
    "main_contract_switch_flag",
}


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


def _read_user_config_value(name: str) -> str:
    if name in os.environ and os.environ.get(name):
        return str(os.environ.get(name) or "").strip()
    path = secrets_path()
    if not path.exists():
        return ""
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return ""
    value = payload.get(name) if isinstance(payload, dict) else ""
    return str(value or "").strip()


def _read_first_user_config_value(*names: str) -> str:
    for name in names:
        value = _read_user_config_value(name)
        if value:
            return value
    return ""


def _managed_endpoint() -> str:
    return _read_first_user_config_value(
        "SN_LOCAL_API_PROVIDER_BASE_URL",
        "SN_MANAGED_PROXY_BASE_URL",
        "SN_MANAGED_DATA_PROXY_URL",
    )


def _managed_token() -> dict[str, Any]:
    resolved = resolve_secret("SN_LOCAL_API_PROVIDER_TOKEN")
    value = str(resolved.get("value") or "").strip()
    return {
        "value": value,
        "source": str(resolved.get("source") or "none"),
        "masked": mask_secret(value) if value else "",
        "configured": bool(value),
        "deprecated": bool(resolved.get("deprecated")),
        "deprecated_warning": str(resolved.get("deprecated_warning") or ""),
    }


def _safe_symbol(value: Any) -> str:
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
    ]
    text = " ".join(_safe_symbol(item) for item in candidates if item)
    if not text:
        return True
    return any(part.startswith("SN") or part in {"沪锡", "锡"} for part in text.replace(".", " ").split())


def _to_number(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        number = float(value)
    except Exception:
        return None
    if number != number:
        return None
    return number


def normalize_managed_fundamental_rows(rows: Any, *, from_cache: bool = False) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    if not isinstance(rows, list):
        return normalized
    for item in rows:
        if not isinstance(item, Mapping) or not _is_sn_row(item):
            continue
        trade_date = str(item.get("trade_date") or item.get("date") or "").strip()
        if not trade_date:
            continue
        row: dict[str, Any] = {
            "trade_date": trade_date,
            "symbol": str(item.get("symbol") or item.get("ts_code") or item.get("contract") or "SN").strip().upper(),
            "source": "managed_data_proxy",
            "from_cache": bool(from_cache),
            "quality_flag": "cached" if from_cache else "managed",
        }
        for field in MANAGED_SCHEMA_FIELDS:
            if field == "trade_date":
                continue
            value = item.get(field)
            if field in NUMERIC_FIELDS:
                row[field] = _to_number(value)
            else:
                row[field] = str(value or "").strip() if value is not None else ""
        normalized.append(row)
    return normalized


def managed_fundamentals_schema() -> dict[str, Any]:
    return {
        "provider_id": "managed_data_proxy",
        "schema_version": 2,
        "path": "/api/sn/fundamentals/history",
        "symbol": "SN",
        "fields": list(MANAGED_SCHEMA_FIELDS),
        "required_research_fields": list(MANAGED_REQUIRED_RESEARCH_FIELDS),
        "groups": {key: list(value) for key, value in MANAGED_RESEARCH_GROUPS.items()},
        "no_fake_data": True,
        "sample_data_allowed": False,
        "mock_data_allowed": False,
        "customer_prediction_generated": False,
        "active_model_written": False,
        "message_zh": "托管源 schema 可补齐沪锡仓单、库存、现货/基差和 LME 字段；没有真实数据时只记录缺失状态，不伪造字段。",
    }


class ManagedProxyHttpClient:
    def __init__(self, base_url: str, timeout_seconds: int = 20) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds

    def get_json(self, path: str, headers: dict[str, str]) -> dict[str, Any]:
        url = self.base_url + path
        request = urllib.request.Request(url, headers=headers, method="GET")
        with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
            raw = response.read().decode("utf-8")
        payload = json.loads(raw)
        return payload if isinstance(payload, dict) else {"status": "schema_mismatch", "payload": payload}


def _client(base_url: str, client: Any | None = None) -> Any:
    return client if client is not None else ManagedProxyHttpClient(base_url)


def _headers(token: str) -> dict[str, str]:
    return {"X-SN-License-Token": token, "Accept": "application/json"}


def managed_proxy_status() -> dict[str, Any]:
    token_info = _managed_token()
    base_url = _managed_endpoint()
    enabled = bool(
        token_info["configured"]
        or base_url
        or os.getenv("SN_LOCAL_API_PROVIDER_ENABLED", "").strip().lower() in {"1", "true", "yes", "on"}
        or os.getenv("SN_MANAGED_PROXY_ENABLED", "").strip().lower() in {"1", "true", "yes", "on"}
        or os.getenv("SN_MANAGED_DATA_PROXY_ENABLED", "").strip().lower() in {"1", "true", "yes", "on"}
    )
    status_file = _read_json(_fundamentals_dir() / "managed_proxy_status.json")
    status_code = str((status_file or {}).get("status") or "")
    if not enabled:
        status = "disabled"
        success = False
        message = "托管数据服务默认关闭；客户不需要 CSV/Excel。"
    elif not token_info["configured"]:
        status = "token_missing"
        success = False
        message = "托管数据服务已启用但缺少 license token。"
    elif not base_url:
        status = "endpoint_missing"
        success = False
        message = "托管数据服务缺少 endpoint。"
    else:
        status = status_code or "configured"
        success = status in {"success", "using_cache"}
        message = str((status_file or {}).get("message_zh") or "托管数据服务客户端已配置，可测试连接或刷新。")
    return {
        "source_name": "managed_data_proxy",
        "status": status,
        "success": success,
        "enabled": enabled,
        "configured": bool(token_info["configured"] and base_url),
        "token_masked": token_info["masked"],
        "source": token_info["source"],
        "base_url_configured": bool(base_url),
        "client_upload_required": False,
        "last_success_time": str((status_file or {}).get("last_success_time") or ""),
        "row_count": int((status_file or {}).get("row_count") or 0),
        "from_cache": bool((status_file or {}).get("from_cache") or False),
        "message_zh": message,
        "next_actions_zh": [
            "客户无需 CSV/Excel；私有发行包或 license token 可启用托管结构化基本面。",
            "托管服务仅补齐研究数据，不用于实盘交易。",
        ],
    }


def test_managed_proxy_connection(*, client: Any | None = None) -> dict[str, Any]:
    token_info = _managed_token()
    base_url = _managed_endpoint()
    if not token_info["configured"]:
        return {**managed_proxy_status(), "status": "token_missing", "success": False}
    if not base_url:
        return {**managed_proxy_status(), "status": "endpoint_missing", "success": False}
    try:
        payload = _client(base_url, client).get_json("/api/sn/status", _headers(str(token_info["value"])))
        status = str(payload.get("status") or "success")
        success = status in {"ok", "success", "available"}
        return sanitize_mapping(
            {
                **managed_proxy_status(),
                "status": "success" if success else status,
                "success": success,
                "configured": True,
                "request_params_sanitized": {"path": "/api/sn/status", "headers": {"X-SN-License-Token": "***"}},
                "message_zh": "托管数据服务连接成功。" if success else "托管数据服务返回非成功状态。",
                "last_validation_status": "success" if success else status,
            }
        )
    except Exception as exc:
        return sanitize_mapping(
            {
                **managed_proxy_status(),
                "status": "network_failed",
                "success": False,
                "error_message_zh": sanitize_text(str(exc)),
                "message_zh": "托管数据服务连接失败。",
            }
        )


test_managed_proxy_connection.__test__ = False


def _history_path() -> str:
    end = datetime.now().date()
    start = end - timedelta(days=3650)
    query = urllib.parse.urlencode({"symbol": "SN", "start": start.isoformat(), "end": end.isoformat()})
    return f"/api/sn/fundamentals/history?{query}"


def refresh_managed_data_proxy(force: bool = False, *, client: Any | None = None) -> dict[str, Any]:
    _ = force
    out = _fundamentals_dir()
    token_info = _managed_token()
    base_url = _managed_endpoint()
    status_path = out / "managed_proxy_status.json"
    data_path = out / "managed_fundamentals.json"
    last_good_path = out / "last_good_managed_fundamentals.json"
    if not token_info["configured"] or not base_url:
        status = managed_proxy_status()
        status["generated_at"] = _now()
        status["managed_schema"] = managed_fundamentals_schema()
        _write_json(status_path, status)
        return sanitize_for_json({"status": status["status"], "success": False, "output_files": [str(status_path)], **status})
    try:
        payload = _client(base_url, client).get_json(_history_path(), _headers(str(token_info["value"])))
        rows = normalize_managed_fundamental_rows(payload.get("rows") if isinstance(payload, Mapping) else [])
        if not rows:
            status = {
                **managed_proxy_status(),
                "status": "no_sn_rows",
                "success": False,
                "row_count": 0,
                "message_zh": "托管服务返回成功但没有 SN 结构化基本面行；系统未伪造数据。",
                "managed_schema": managed_fundamentals_schema(),
                "generated_at": _now(),
            }
            _write_json(status_path, status)
            return sanitize_for_json({"status": "no_sn_rows", "success": False, "output_files": [str(status_path)], **status})
        data = {
            "schema_version": 1,
            "source": "managed_data_proxy",
            "generated_at": _now(),
            "client_upload_required": False,
            "sample_data_used": False,
            "baseline_used": False,
            "rows": rows,
        }
        _write_json(data_path, data)
        _write_json(last_good_path, data)
        status = {
            **managed_proxy_status(),
            "status": "success",
            "success": True,
            "from_cache": False,
            "row_count": len(rows),
            "last_success_time": _now(),
            "message_zh": "托管结构化基本面刷新成功。",
            "fields": list(MANAGED_SCHEMA_FIELDS),
            "managed_schema": managed_fundamentals_schema(),
            "generated_at": _now(),
        }
        _write_json(status_path, status)
        return sanitize_for_json(
            {
                "status": "success",
                "success": True,
                "row_count": len(rows),
                "output_files": [str(data_path), str(last_good_path), str(status_path)],
                **status,
            }
        )
    except Exception as exc:
        cached = _read_json(last_good_path) or _read_json(data_path)
        has_cache = bool(isinstance(cached, Mapping) and cached.get("rows"))
        if has_cache:
            cached_rows = normalize_managed_fundamental_rows(cached.get("rows"), from_cache=True)
            cached_payload = {**dict(cached), "rows": cached_rows, "from_cache": True}
            _write_json(data_path, cached_payload)
            status_code = "using_cache"
            success = True
            row_count = len(cached_rows)
            message = "托管服务当前不可用，使用最近成功缓存；缓存不会冒充新数据。"
        else:
            status_code = "network_failed"
            success = False
            row_count = 0
            message = "托管服务请求失败，且没有可用缓存。"
        status = {
            **managed_proxy_status(),
            "status": status_code,
            "success": success,
            "from_cache": has_cache,
            "row_count": row_count,
            "error_message_zh": sanitize_text(str(exc)),
            "message_zh": message,
            "generated_at": _now(),
        }
        _write_json(status_path, status)
        return sanitize_mapping({"status": status_code, "success": success, "output_files": [str(status_path)], **status})
