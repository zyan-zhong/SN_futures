from __future__ import annotations

import json
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from ..api.json_utils import sanitize_for_json
from ..runtime import get_user_output_dir


DIAGNOSTIC_ENDPOINTS = [
    "/api/terminal/summary",
    "/api/terminal/snapshot-lite",
    "/api/terminal/data-status",
    "/api/terminal/system-health",
    "/api/terminal/factors/coverage",
    "/api/terminal/feature-store/status",
    "/api/terminal/training-dataset/status",
    "/api/terminal/models/candidate-status",
    "/api/terminal/research/artifacts",
    "/api/terminal/reports",
]


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _budget(endpoint: str) -> int:
    if endpoint in {"/api/terminal/summary", "/api/terminal/system-health"}:
        return 300
    if endpoint == "/api/terminal/snapshot-lite":
        return 500
    if endpoint in {"/api/terminal/data-status", "/api/terminal/feature-store/status", "/api/terminal/training-dataset/status"}:
        return 1000
    return 1500


def _recommended_fix(endpoint: str, duration_ms: float, cache_hit: bool) -> str:
    if duration_ms <= _budget(endpoint):
        return "within_budget"
    if not cache_hit:
        return "add_or_tighten_cache"
    if endpoint in {"/api/terminal/factors/coverage", "/api/terminal/research/artifacts"}:
        return "precompute_or_move_to_task_api"
    return "split_payload_or_reduce_provider_calls"


def _slow_reason(endpoint: str, duration_ms: float, cache_hit: bool) -> str:
    if duration_ms <= _budget(endpoint):
        return ""
    if cache_hit:
        return "cached_but_payload_or_serialization_slow"
    if endpoint in {"/api/terminal/snapshot-lite", "/api/terminal/system-health"}:
        return "light_api_budget_exceeded"
    return "uncached_or_heavy_component"


def run_api_performance_diagnostics() -> dict[str, Any]:
    from ..api.terminal_api import handle_terminal_api

    rows: list[dict[str, Any]] = []
    for endpoint in DIAGNOSTIC_ENDPOINTS:
        started = time.perf_counter()
        status, payload = handle_terminal_api(endpoint)
        duration_ms = round((time.perf_counter() - started) * 1000, 3)
        cache_hit = bool(isinstance(payload, dict) and payload.get("cache_hit"))
        rows.append(
            {
                "endpoint": endpoint,
                "http_status": status,
                "duration_ms": duration_ms,
                "target_ms": _budget(endpoint),
                "cache_hit": cache_hit,
                "slow_reason": _slow_reason(endpoint, duration_ms, cache_hit),
                "blocking_components": [] if duration_ms <= _budget(endpoint) else ["payload_build", "json_serialization"],
                "recommended_fix": _recommended_fix(endpoint, duration_ms, cache_hit),
            }
        )

    report = sanitize_for_json(
        {
            "generated_at": _now(),
            "endpoints": rows,
            "latency_budgets": {
                "light_ms": 300,
                "medium_ms": 1000,
                "heavy_policy": "async_or_cached",
            },
            "message_zh": "API 性能诊断完成；重任务必须通过任务 API 或缓存状态返回。",
        }
    )
    out_dir = get_user_output_dir() / "performance"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "api_performance_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report
