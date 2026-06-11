from __future__ import annotations

import json
from typing import Any, Mapping

from ..api.json_utils import sanitize_for_json
from ..data_layer.watermark import WatermarkStore
from ..prediction_core.data_readiness import build_prediction_data_readiness
from ..prediction_core.readiness import build_public_prediction_core_readiness
from ..utils.secret_sanitizer import sanitize_mapping
from .provider_smoke_result_bridge_service import DOWNSTREAM_FLAGS, get_public_provider_smoke_report
from .runtime import data_watermark_path


def _safe(payload: Any) -> Any:
    return sanitize_for_json(sanitize_mapping(payload))


def _load_data_watermark() -> dict[str, Any]:
    data_layer_watermark = WatermarkStore().load()
    if data_layer_watermark.get("reason") != "missing_data_layer_watermark":
        return data_layer_watermark

    path = data_watermark_path()
    if not path.exists():
        return {
            "status": "blocked",
            "reason": "missing_daily_bars",
            "sample_data_used": False,
            "baseline_used": False,
            "customer_prediction_generated": False,
        }
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {"status": "blocked", "reason": "data_watermark_unreadable"}
    return dict(payload) if isinstance(payload, Mapping) else {"status": "blocked", "reason": "data_watermark_invalid"}


def build_public_terminal_readiness() -> dict[str, Any]:
    smoke_report = get_public_provider_smoke_report()
    passed = int(smoke_report.get("passed_count") or 0)
    smoke_passed = passed > 0
    blocking_reasons = [] if smoke_passed else list(smoke_report.get("blocking_reasons") or ["no_active_provider_smoke_pass"])
    prediction_readiness = build_prediction_data_readiness()
    prediction_core_readiness = build_public_prediction_core_readiness()
    return _safe(
        {
            "status": "ready" if smoke_passed else "blocked",
            "summary": "provider smoke passed" if smoke_passed else "provider smoke required",
            "next_action": "refresh_data_status" if smoke_passed else "run_provider_smoke",
            "provider_smoke_passed": smoke_passed,
            "ready_for_refresh": smoke_passed,
            "blocking_reasons": blocking_reasons,
            "data_watermark": _load_data_watermark(),
            "provider_status": {
                "status": smoke_report.get("status"),
                "passed_count": passed,
                "failed_count": int(smoke_report.get("failed_count") or 0),
                "passed_providers": list(smoke_report.get("passed_providers") or []),
                "source_statuses": list(smoke_report.get("source_statuses") or []),
                "report_path": smoke_report.get("report_path", ""),
            },
            "prediction_readiness": prediction_readiness,
            "prediction_core_readiness": prediction_core_readiness,
            **{flag: False for flag in DOWNSTREAM_FLAGS},
        }
    )
