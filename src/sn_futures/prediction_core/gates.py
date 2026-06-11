from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

from ..api.json_utils import sanitize_for_json
from ..data_layer.watermark import WatermarkStore
from ..runtime import get_user_output_dir
from ..utils.secret_sanitizer import sanitize_mapping
from .contracts import DIRTY_FLAGS, FORBIDDEN_PREDICTION_OUTPUT_KEYS


def safe_payload(payload: Any) -> Any:
    return sanitize_for_json(sanitize_mapping(payload))


def output_dir(output_dir: Path | None = None) -> Path:
    return output_dir or get_user_output_dir()


def read_json(path: Path) -> dict[str, Any]:
    try:
        if path.exists():
            payload = json.loads(path.read_text(encoding="utf-8"))
            return dict(payload) if isinstance(payload, Mapping) else {}
    except Exception:
        return {}
    return {}


def hash_file(path: Path) -> str:
    if not path.exists() or not path.is_file():
        return ""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y", "sample", "fake", "demo", "baseline"}
    return bool(value)


def dirty_reasons(payload: Mapping[str, Any], prefix: str = "active_release") -> list[str]:
    reasons: set[str] = set()
    for key, value in payload.items():
        if key in DIRTY_FLAGS and truthy(value):
            if key.startswith("sample"):
                reasons.add(f"{prefix}_sample")
            elif key.startswith("fake"):
                reasons.add(f"{prefix}_fake")
            elif key.startswith("demo"):
                reasons.add(f"{prefix}_demo")
            elif key.startswith("baseline"):
                reasons.add(f"{prefix}_baseline")
            elif key.startswith("mock"):
                reasons.add(f"{prefix}_mock")
        if isinstance(value, Mapping):
            reasons.update(dirty_reasons(value, prefix))
        elif isinstance(value, list):
            for item in value:
                if isinstance(item, Mapping):
                    reasons.update(dirty_reasons(item, prefix))
    return sorted(reasons)


def assert_no_prediction_values(payload: Mapping[str, Any]) -> dict[str, Any]:
    text = json.dumps(safe_payload(dict(payload)), ensure_ascii=False).lower()
    leaked = sorted(key for key in FORBIDDEN_PREDICTION_OUTPUT_KEYS if key in text)
    if leaked:
        blocked = {
            "status": "blocked",
            "can_predict": False,
            "blocking_reasons": ["prediction_value_output_forbidden", *[f"forbidden_key:{key}" for key in leaked]],
        }
        return safe_payload(blocked)
    return dict(payload)


def data_watermark_gate(output_dir_arg: Path | None = None) -> dict[str, Any]:
    watermark = WatermarkStore(output_dir=output_dir_arg).load()
    reasons: list[str] = []
    if watermark.get("reason") == "missing_data_layer_watermark":
        reasons.append("data_watermark_missing")
    if str(watermark.get("status") or "").lower() in {"blocked", "missing"}:
        reasons.append("data_watermark_blocked")
    stale_status = str(watermark.get("stale_status") or "").lower()
    if stale_status == "stale":
        reasons.append("data_watermark_stale")
    if watermark.get("allowed_for_prediction") is False:
        records = watermark.get("records_by_kind")
        daily = records.get("daily_bar") if isinstance(records, Mapping) and isinstance(records.get("daily_bar"), Mapping) else {}
        if daily and daily.get("allowed_for_prediction") is False:
            reasons.append("data_watermark_prediction_not_allowed")

    return safe_payload(
        {
            "status": "ready" if not reasons else "blocked",
            "watermark": watermark,
            "stale_status": stale_status or watermark.get("status") or "unknown",
            "blocking_reasons": sorted(set(reasons)),
        }
    )
