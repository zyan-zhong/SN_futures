from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping

import pandas as pd

from ..api.json_utils import sanitize_for_json
from ..runtime import get_user_output_dir
from .feature_store_service import _feature_store_manifest_path, _write_store_frame
from .feature_store_v10_service import build_feature_store_v10
from .managed_data_proxy_service import (
    MANAGED_RESEARCH_GROUPS,
    MANAGED_REQUIRED_RESEARCH_FIELDS,
    managed_fundamentals_schema,
    managed_proxy_status,
    refresh_managed_data_proxy,
)


V11_FEATURE_SET = "managed_proxy_minimal_real_loop_v11"
V11_REQUIRED_FIELDS = tuple(MANAGED_REQUIRED_RESEARCH_FIELDS)


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _output_dir() -> Path:
    return get_user_output_dir()


def _read_json(path: Path) -> Any:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(sanitize_for_json(dict(payload)), ensure_ascii=False, indent=2), encoding="utf-8")


def _normalise_status_code(status: Mapping[str, Any]) -> str:
    return str(status.get("status") or "unknown")


def _blocking_reason_for_status(status_code: str) -> str:
    return {
        "disabled": "managed_proxy_disabled",
        "token_missing": "managed_proxy_token_missing",
        "endpoint_missing": "managed_proxy_endpoint_missing",
        "no_sn_rows": "managed_proxy_no_sn_rows",
        "network_failed": "managed_proxy_network_failed",
    }.get(status_code, "managed_proxy_not_ready")


def _available_managed_fields(manifest: Mapping[str, Any]) -> list[str]:
    fields = manifest.get("managed_fundamental_fields")
    if isinstance(fields, list):
        return sorted({str(item) for item in fields if str(item)})
    usable = set(str(item) for item in (manifest.get("usable_fields") or []) if str(item))
    return sorted(set(V11_REQUIRED_FIELDS).intersection(usable))


def _build_v11_readiness(v10_manifest: Mapping[str, Any], status: Mapping[str, Any]) -> dict[str, Any]:
    status_code = _normalise_status_code(status)
    available = set(_available_managed_fields(v10_manifest))
    missing = sorted(set(V11_REQUIRED_FIELDS) - available)
    group_ready: dict[str, bool] = {}
    for group, fields in MANAGED_RESEARCH_GROUPS.items():
        numeric_fields = [field for field in fields if field in set(V11_REQUIRED_FIELDS)]
        group_ready[group] = bool(numeric_fields and set(numeric_fields).issubset(available))

    provider_ready = status_code in {"success", "using_cache"} or bool(v10_manifest.get("managed_fundamentals_used"))
    ready = bool(provider_ready and not missing and all(group_ready.values()))
    blocking: list[str] = []
    if not provider_ready:
        blocking.append(_blocking_reason_for_status(status_code))
    if missing:
        blocking.append("managed_fundamental_fields_missing")
    if any(not value for value in group_ready.values()):
        blocking.append("managed_fundamental_groups_incomplete")

    return {
        "status": "ready" if ready else "blocked",
        "ready": ready,
        "provider_status": status_code,
        "available_fields": sorted(available),
        "missing_fields": missing,
        "group_ready": group_ready,
        "blocking_reasons": sorted(set(blocking)),
        "next_actions_zh": []
        if ready
        else [
            "配置真实 managed proxy endpoint/token 并刷新 spot、basis、inventory、warehouse、LME 与 near/far contract 字段。",
            "如果 fut_wsr 对沪锡继续 no_sn_rows，保持不伪造仓单，只使用真实 managed 字段或缺失风险标记。",
        ],
    }


def _copy_v10_store_to_v11(v10_manifest: Mapping[str, Any]) -> str:
    source = Path(str(v10_manifest.get("feature_store_path") or ""))
    if not source.exists():
        return ""
    frame = pd.read_csv(source)
    return _write_store_frame(frame, "v11")


def build_feature_store_v11() -> dict[str, Any]:
    v10_manifest = build_feature_store_v10()
    manifest_path = _feature_store_manifest_path("v11")
    status = managed_proxy_status()
    if not isinstance(v10_manifest, Mapping) or v10_manifest.get("status") != "success":
        readiness = _build_v11_readiness({}, status if isinstance(status, Mapping) else {})
        payload = {
            "version": "v11",
            "status": "failed",
            "generated_at": _now(),
            "row_count": 0,
            "feature_set": V11_FEATURE_SET,
            "feature_store_path": str(_output_dir() / "feature_store" / "v11" / "feature_store.csv"),
            "manifest_path": str(manifest_path),
            "managed_schema": managed_fundamentals_schema(),
            "managed_proxy_status": status,
            "feature_store_v11_readiness": readiness,
            "missing_managed_fields": readiness["missing_fields"],
            "no_fake_data": True,
            "sample_data_used": False,
            "mock_data_used": False,
            "baseline_used": False,
            "active_model_written": False,
            "customer_prediction_generated": False,
            "message_zh": "Feature Store v11 未构建：v10 基础特征仓不可用，未伪造 managed fundamentals。",
        }
        _write_json(manifest_path, payload)
        return sanitize_for_json(payload)

    store_path = _copy_v10_store_to_v11(v10_manifest)
    readiness = _build_v11_readiness(v10_manifest, status if isinstance(status, Mapping) else {})
    payload = dict(v10_manifest)
    payload.update(
        {
            "version": "v11",
            "status": "success",
            "generated_at": _now(),
            "feature_set": V11_FEATURE_SET,
            "feature_store_path": store_path or str(_output_dir() / "feature_store" / "v11" / "feature_store.csv"),
            "manifest_path": str(manifest_path),
            "managed_schema": managed_fundamentals_schema(),
            "managed_proxy_status": status,
            "feature_store_v11_readiness": readiness,
            "v11_readiness": readiness,
            "missing_managed_fields": readiness["missing_fields"],
            "managed_proxy_minimal_loop": {
                "status": readiness["status"],
                "required_fields": list(V11_REQUIRED_FIELDS),
                "available_fields": readiness["available_fields"],
                "missing_fields": readiness["missing_fields"],
                "group_ready": readiness["group_ready"],
                "no_fake_data": True,
            },
            "no_fake_data": True,
            "sample_data_used": bool(v10_manifest.get("sample_data_used")),
            "mock_data_used": bool(v10_manifest.get("mock_data_used")),
            "baseline_used": False,
            "active_model_written": False,
            "customer_prediction_generated": False,
            "message_zh": "Feature Store v11 已完成 managed proxy 最小真实闭环检查；缺字段只记录 blocked，不伪造数据。",
        }
    )
    _write_json(manifest_path, payload)
    return sanitize_for_json(payload)


def run_managed_proxy_v11_real_loop(*, force: bool = False, client: Any | None = None) -> dict[str, Any]:
    refresh = refresh_managed_data_proxy(force=force, client=client)
    feature_store = build_feature_store_v11()
    readiness = feature_store.get("feature_store_v11_readiness") if isinstance(feature_store, Mapping) else {}
    readiness = readiness if isinstance(readiness, Mapping) else {}
    status = feature_store.get("managed_proxy_status") if isinstance(feature_store, Mapping) else managed_proxy_status()
    payload = {
        "status": "success" if readiness.get("ready") else "blocked",
        "generated_at": _now(),
        "managed_proxy_status": status,
        "refresh_result": refresh,
        "feature_store_v11": feature_store,
        "v11_readiness": dict(readiness),
        "missing_fields": list(readiness.get("missing_fields") or []),
        "next_candidate_allowed": bool(readiness.get("ready")),
        "training_invoked": False,
        "active_updated": False,
        "customer_prediction_generated": False,
        "no_fake_data": True,
        "message_zh": "managed proxy v11 minimal real loop 已执行；本步骤不训练模型、不发布 active。",
    }
    return sanitize_for_json(payload)
