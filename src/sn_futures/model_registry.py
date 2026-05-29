from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from .bootstrap.runtime_guard import BUILD_ID, model_registry_path
from .horizon_registry import HORIZON_ORDER, get_horizon_config


def _hash_key(*parts: object) -> str:
    text = "|".join(str(part) for part in parts)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def build_registry(output_dir: Path | None = None) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    base_dir = model_registry_path().parent
    for key in HORIZON_ORDER:
        cfg = get_horizon_config(key)
        version = f"{BUILD_ID}-{cfg.canonical_name}-active"
        feature_set_id = _hash_key(BUILD_ID, key, cfg.model_family, cfg.bar_interval, "features")
        scaler_id = _hash_key(BUILD_ID, key, cfg.model_family, cfg.bar_interval, "scaler")
        forecast_index_hash = _hash_key(BUILD_ID, key, cfg.forecast_steps, cfg.forecast_interval_minutes, cfg.forecast_trading_day_interval)
        cache_key = _hash_key(BUILD_ID, key, version, "prediction_cache")
        artifact_path = base_dir / key / version / "model.json"
        rows.append(
            {
                "build_id": BUILD_ID,
                "status": "active",
                "horizon": key,
                "display_name": cfg.display_name,
                "model_family": cfg.model_family,
                "model_version": version,
                "feature_set_id": feature_set_id,
                "scaler_id": scaler_id,
                "forecast_index_hash": forecast_index_hash,
                "prediction_cache_key": cache_key,
                "artifact_path": str(artifact_path),
                "calibration_model_path": str(artifact_path.with_name("calibration.json")),
                "backtest_id": _hash_key(BUILD_ID, key, "walk_forward"),
                "data_cutoff_timestamp": "",
                "train_start": cfg.lookback_window,
                "train_end": "latest_available_before_prediction",
                "metrics_hash": _hash_key(BUILD_ID, key, "metrics"),
            }
        )
    validate_registry(rows)
    path = model_registry_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"build_id": BUILD_ID, "models": rows}, ensure_ascii=False, indent=2), encoding="utf-8")
    return rows


def validate_registry(rows: list[dict[str, Any]]) -> None:
    fields = ("artifact_path", "scaler_id", "forecast_index_hash", "prediction_cache_key")
    for field in fields:
        values = [str(row.get(field, "")) for row in rows]
        if len(values) != len(set(values)):
            raise ValueError(f"模型注册表冲突：不同周期存在重复 {field}")
    horizons = [str(row.get("horizon", "")) for row in rows]
    missing = [key for key in HORIZON_ORDER if key not in horizons]
    if missing:
        raise ValueError(f"模型注册表缺少周期：{missing}")


def load_registry(output_dir: Path | None = None) -> list[dict[str, Any]]:
    path = model_registry_path()
    if path.exists():
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            rows = payload.get("models", [])
            if isinstance(rows, list):
                validate_registry(rows)
                return rows
        except Exception:
            pass
    return build_registry(output_dir)
