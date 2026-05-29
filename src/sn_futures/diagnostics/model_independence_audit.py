from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping

from ..horizon_registry import HORIZON_ORDER


def stable_hash(value: Any) -> str:
    blob = json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:16]


def _unique(rows: list[Mapping[str, Any]], field: str) -> dict[str, Any]:
    values = [str(row.get(field, "")) for row in rows]
    duplicates = sorted({value for value in values if value and values.count(value) > 1})
    return {"field": field, "ok": not duplicates and len(values) == len(set(values)), "duplicates": duplicates}


def _forecast_values(card: Mapping[str, Any]) -> tuple[Any, ...]:
    return (
        round(float(card.get("price_center", 0) or 0), 6),
        round(float(card.get("range_low", 0) or 0), 6),
        round(float(card.get("range_high", 0) or 0), 6),
    )


def _direction_values(card: Mapping[str, Any]) -> tuple[Any, ...]:
    return (
        round(float(card.get("prob_up", 0.5) or 0.5), 6),
        round(float(card.get("prob_down", 0.5) or 0.5), 6),
        round(float(card.get("p_neutral", card.get("prob_neutral", 0)) or 0), 6),
    )


def audit_model_independence(
    *,
    registry_rows: list[dict[str, Any]],
    live_cards: Mapping[str, Any],
    chart_payloads: Mapping[str, Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Detect horizon mixing, stale cache reuse, and duplicated forecast output."""

    checks = []
    fields = ("artifact_path", "scaler_id", "feature_set_id", "prediction_cache_key", "forecast_index_hash")
    for field in fields:
        checks.append(_unique(registry_rows, field))

    registry_by_horizon = {str(row.get("horizon")): row for row in registry_rows}
    missing_registry = [key for key in HORIZON_ORDER if key not in registry_by_horizon]
    missing_cards = [key for key in HORIZON_ORDER if key not in live_cards]
    checks.append({"field": "required_horizons", "ok": not missing_registry and not missing_cards, "missing_registry": missing_registry, "missing_cards": missing_cards})

    value_hashes: dict[str, str] = {}
    direction_hashes: dict[str, str] = {}
    index_hashes: dict[str, str] = {}
    for key in HORIZON_ORDER:
        card = live_cards.get(key, {}) if isinstance(live_cards.get(key, {}), Mapping) else {}
        value_hashes[key] = stable_hash(_forecast_values(card))
        direction_hashes[key] = stable_hash(_direction_values(card))
        chart = (chart_payloads or {}).get(key, {}) if isinstance((chart_payloads or {}).get(key, {}), Mapping) else {}
        forecast_series = chart.get("forecast_series", []) if isinstance(chart.get("forecast_series", []), list) else []
        index_hashes[key] = stable_hash([row.get("date") for row in forecast_series])

    duplicated_forecasts = sorted({h for h in value_hashes.values() if list(value_hashes.values()).count(h) > 1})
    duplicated_directions = sorted({h for h in direction_hashes.values() if list(direction_hashes.values()).count(h) > 1})
    duplicated_indexes = sorted({h for h in index_hashes.values() if h and list(index_hashes.values()).count(h) > 1})
    checks.extend(
        [
            {"field": "forecast_values_hash", "ok": not duplicated_forecasts, "duplicates": duplicated_forecasts},
            {"field": "direction_prob_hash", "ok": not duplicated_directions, "duplicates": duplicated_directions},
            {"field": "chart_forecast_index_hash", "ok": not duplicated_indexes, "duplicates": duplicated_indexes},
        ]
    )

    rows = []
    for key in HORIZON_ORDER:
        row = dict(registry_by_horizon.get(key, {}))
        row.update(
            {
                "horizon": key,
                "prediction_id": (live_cards.get(key, {}) if isinstance(live_cards.get(key, {}), Mapping) else {}).get("prediction_id", ""),
                "forecast_values_hash": value_hashes.get(key, ""),
                "direction_prob_hash": direction_hashes.get(key, ""),
                "chart_forecast_index_hash": index_hashes.get(key, ""),
            }
        )
        rows.append(row)

    ok = all(bool(check.get("ok")) for check in checks)
    return {
        "ok": ok,
        "status": "passed" if ok else "failed",
        "severity": "normal" if ok else "red",
        "summary": "七周期模型、缓存、时间轴隔离通过" if ok else "模型隔离失败，当前预测需谨慎处理",
        "checks": checks,
        "rows": rows,
    }
