from __future__ import annotations

import json
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from ..runtime import get_user_output_dir
from ..utils.secret_sanitizer import sanitize_mapping, sanitize_text


SMOKE_ENDPOINTS = [
    "/api/terminal/docs",
    "/api/terminal/summary",
    "/api/terminal/snapshot-lite",
    "/api/terminal/data-watermark",
    "/api/terminal/data-consistency-report",
    "/api/terminal/data-status",
    "/api/terminal/system-health",
    "/api/terminal/system/process-status",
    "/api/terminal/market-analysis",
    "/api/terminal/charts/price-history",
    "/api/terminal/events/news",
    "/api/terminal/events/relevance-report",
    "/api/terminal/factors/coverage",
    "/api/terminal/feature-store/status",
    "/api/terminal/training-dataset/status",
    "/api/terminal/models/candidate-status",
    "/api/terminal/models/active-status",
    "/api/terminal/validation/report",
    "/api/terminal/research/artifacts",
    "/api/terminal/reports",
    "/api/terminal/settings/status",
    "/api/terminal/settings/key-diagnostics",
    "/api/terminal/tasks/recent",
]


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _output_path() -> Path:
    path = get_user_output_dir() / "diagnostics" / "all_api_smoke.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _contains_unmasked_secret_value(text: str) -> bool:
    value = str(text or "")
    secret_assignment = re.compile(
        r"(?i)(apikey|api_key|x-api-key|authorization|bearer|token|secret|password|SN_ALPHA_VANTAGE_KEY|SN_NEWSAPI_KEY|SN_TUSHARE_TOKEN)"
        r"\s*[:=]\s*(?!\*+|宸茶劚敂|已脱敏|masked|null|none|\"\"|'')[A-Za-z0-9._\-]{8,}"
    )
    return bool(secret_assignment.search(value))


def run_all_terminal_api_smoke() -> dict[str, Any]:
    from ..api.terminal_api import handle_terminal_api

    endpoints: list[dict[str, Any]] = []
    secret_leak = False
    for endpoint in SMOKE_ENDPOINTS:
        started = time.perf_counter()
        try:
            status_code, payload = handle_terminal_api(endpoint)
            safe_payload = sanitize_mapping(payload)
            json.dumps(safe_payload, ensure_ascii=False, allow_nan=False, default=str)
            serialized = json.dumps(safe_payload, ensure_ascii=False, default=str)
            secret_leak = secret_leak or _contains_unmasked_secret_value(serialized)
            item = {
                "endpoint": endpoint,
                "status_code": int(status_code),
                "duration_ms": round((time.perf_counter() - started) * 1000, 3),
                "json_safe": True,
                "payload_keys": sorted(safe_payload.keys())[:20] if isinstance(safe_payload, dict) else [],
            }
        except Exception as exc:
            item = {
                "endpoint": endpoint,
                "status_code": 500,
                "duration_ms": round((time.perf_counter() - started) * 1000, 3),
                "json_safe": False,
                "error": "internal_error",
                "message": sanitize_text(str(exc)),
            }
        endpoints.append(item)
    report = {
        "status": "success",
        "generated_at": _now(),
        "checked_count": len(endpoints),
        "failed_count": sum(1 for item in endpoints if int(item.get("status_code", 500)) >= 500),
        "secret_leak_detected": bool(secret_leak),
        "endpoints": endpoints,
        "output_path": str(_output_path()),
    }
    _output_path().write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report
