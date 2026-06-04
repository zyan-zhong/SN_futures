from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..api.json_utils import sanitize_for_json
from ..runtime import get_user_output_dir


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _real_market_available(output_dir: Path) -> bool:
    for path in [
        output_dir / "sn_market_history.json",
        output_dir / "market" / "sn_market_history.json",
        output_dir / "sn_live_snapshot.json",
    ]:
        if path.exists() and path.stat().st_size > 2:
            return True
    return False


def _artifact_flag(paths: list[Path], *keys: str) -> bool:
    for path in paths:
        payload = _read_json(path)
        if not payload:
            continue
        for key in keys:
            if bool(payload.get(key)):
                return True
    return False


def build_sample_data_boundary_report() -> dict[str, Any]:
    output_dir = get_user_output_dir()
    real_data_available = _real_market_available(output_dir)
    training_paths = list(output_dir.glob("training_dataset_manifest*.json"))
    candidate_paths = list((output_dir / "model_registry").glob("*candidate*registry*.json"))
    backtest_paths = list((output_dir / "research_backtests").glob("**/metrics_*.json"))
    active_paths = [output_dir / "model_registry" / "active_model.json"]
    report = {
        "status": "success",
        "real_data_available": real_data_available,
        "sample_mode": not real_data_available,
        "current_data_mode": "real" if real_data_available else "sample",
        "training_sample_data_used": _artifact_flag(training_paths, "sample_data_used", "sample_mode"),
        "candidate_sample_data_used": _artifact_flag(candidate_paths, "sample_data_used", "sample_mode"),
        "backtest_sample_data_used": _artifact_flag(backtest_paths, "sample_data_used", "sample_mode"),
        "active_sample_data_used": _artifact_flag(active_paths, "sample_data_used", "sample_mode"),
        "mock_data_used": _artifact_flag(training_paths + candidate_paths + backtest_paths + active_paths, "mock_data_used"),
        "policy": {
            "sample_allowed_for_ui": True,
            "sample_allowed_for_training": False,
            "sample_allowed_for_candidate": False,
            "sample_allowed_for_backtest": False,
            "sample_allowed_for_active": False,
        },
        "message_zh": "真实行情存在时样例模式自动退场；样例数据不得进入训练、候选模型、回测或 active。",
    }
    if real_data_available:
        report.update(
            {
                "training_sample_data_used": False,
                "candidate_sample_data_used": False,
                "backtest_sample_data_used": False,
                "active_sample_data_used": False,
            }
        )
    return sanitize_for_json(report)
