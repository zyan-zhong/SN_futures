from __future__ import annotations

import json
import pickle
import sys
import traceback
from pathlib import Path

from .pipeline import run_live_prediction_pipeline


def _load_existing_result(path_value: str | None) -> dict[str, object] | None:
    if not path_value:
        return None
    path = Path(path_value)
    if not path.exists():
        return None
    try:
        with path.open("rb") as handle:
            payload = pickle.load(handle)
    except Exception:
        return None
    return payload if isinstance(payload, dict) else None


def _slim_result(result: dict[str, object]) -> dict[str, object]:
    keep_keys = {
        "raw",
        "predictions",
        "metrics",
        "signals",
        "selected_features",
        "report_manifest",
        "live_snapshot",
        "live_predictions",
        "scenario_matrix",
        "position_risk",
        "optimization_summary",
        "bandit_summary",
        "direction_summary",
        "backtest_diagnostics",
        "prediction_history",
        "prediction_evaluation",
        "prediction_evaluation_summary",
        "calibration_profile",
        "model_memory",
        "v2_artifacts",
        "risk_config",
        "optimization_level",
        "hardware_profile",
    }
    return {key: value for key, value in result.items() if key in keep_keys}


def run_live_worker(payload_path: str, result_path: str) -> int:
    target = Path(result_path)
    try:
        payload = json.loads(Path(payload_path).read_text(encoding="utf-8-sig"))
        existing_result = _load_existing_result(payload.get("existing_result_path"))
        result = run_live_prediction_pipeline(
            csv_path=payload.get("csv_path") or None,
            preset_name=payload.get("preset_name") or None,
            risk_profile_name=payload.get("risk_profile_name") or None,
            refresh_scope=str(payload.get("refresh_scope", "all")),
            use_remote=bool(payload.get("use_remote", True)),
            symbols=list(payload.get("symbols") or ["nf_SN0"]),
            existing_result=existing_result,
            use_demo=bool(payload.get("use_demo", False)),
            optimization_level=str(payload.get("optimization_level", "full")),
        )
        with target.open("wb") as handle:
            pickle.dump({"ok": True, "result": _slim_result(result)}, handle, protocol=pickle.HIGHEST_PROTOCOL)
        return 0
    except Exception:
        with target.open("wb") as handle:
            pickle.dump({"ok": False, "error": traceback.format_exc()}, handle, protocol=pickle.HIGHEST_PROTOCOL)
        return 1


def run_live_worker_from_argv(argv: list[str] | None = None) -> int:
    argv = list(argv or sys.argv)
    if "--live-worker" not in argv:
        return 2
    idx = argv.index("--live-worker")
    if len(argv) <= idx + 2:
        raise SystemExit("Missing payload/result path for --live-worker")
    return run_live_worker(argv[idx + 1], argv[idx + 2])
