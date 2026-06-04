from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping

from ..api.json_utils import sanitize_for_json
from ..runtime import get_user_data_dir, get_user_output_dir


REQUIRED_GATES = [
    "decision_board_ready_for_manual_review",
    "manual_approval_recommended",
    "active_publish_allowed",
    "active_model_available",
    "shadow_output_contract_pass",
    "registry_safety_pass",
    "evidence_freshness_pass",
    "no_customer_predictions_artifact",
]


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _read_json(path: Path) -> Any:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _decision_board_path() -> Path:
    return get_user_output_dir() / "model_research" / "research_decision_board.json"


def _active_model_paths() -> list[Path]:
    root = get_user_data_dir()
    out = get_user_output_dir()
    return [
        out / "model_registry" / "active_model.json",
        out / "models" / "active_model.json",
        root / "registry" / "active_model.json",
    ]


def _customer_prediction_paths() -> list[Path]:
    root = get_user_data_dir()
    out = get_user_output_dir()
    return [
        out / "customer_predictions",
        out / "customer_predictions.json",
        root / "customer_predictions",
        root / "outputs" / "customer_predictions",
        root / "outputs" / "customer_predictions.json",
    ]


def _path_exists(paths: list[Path]) -> bool:
    return any(path.exists() for path in paths)


def _as_string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if str(item or "").strip()]


def build_prediction_workspace_status() -> dict[str, Any]:
    """Return a read-only prediction workspace gate summary.

    This service intentionally does not build reports, train models, refresh data,
    publish active models, or create customer prediction artifacts.
    """

    board_path = _decision_board_path()
    board_payload = _read_json(board_path)
    board = dict(board_payload) if isinstance(board_payload, Mapping) else {}

    active_path_exists = _path_exists(_active_model_paths())
    customer_prediction_path_exists = _path_exists(_customer_prediction_paths())
    board_status = str(board.get("status") or "missing")
    current_state = str(board.get("current_research_state") or "missing")
    next_action = str(board.get("next_allowed_action") or "configure_managed_proxy_endpoint_or_token")
    active_publish_allowed = bool(board.get("active_publish_allowed"))
    manual_approval_recommended = bool(board.get("manual_approval_recommended"))
    customer_prediction_generated = bool(board.get("customer_prediction_generated", False))
    active_updated = bool(board.get("active_updated", False))
    training_invoked = bool(board.get("training_invoked", False))

    blocking_reasons = _as_string_list(board.get("blocking_reasons"))
    if not board:
        blocking_reasons.append("decision_board_missing")
    if board_status not in {"ready_for_manual_review", "ready"}:
        blocking_reasons.append(f"decision_board_{board_status}")
    if not manual_approval_recommended:
        blocking_reasons.append("manual_approval_not_recommended")
    if not active_publish_allowed:
        blocking_reasons.append("active_publish_not_allowed")
    if active_path_exists:
        blocking_reasons.append("unexpected_active_model_artifact")
    if customer_prediction_path_exists:
        blocking_reasons.append("unexpected_customer_predictions_artifact")
    if customer_prediction_generated:
        blocking_reasons.append("customer_prediction_generated_flag_true")
    if active_updated:
        blocking_reasons.append("active_updated_flag_true")
    if training_invoked:
        blocking_reasons.append("training_invoked_flag_true")

    deduped_reasons = list(dict.fromkeys(blocking_reasons))
    violation = active_path_exists or customer_prediction_path_exists or active_updated or customer_prediction_generated
    active_model_available = active_path_exists and active_publish_allowed and not violation
    prediction_allowed = active_model_available and manual_approval_recommended and active_publish_allowed and not deduped_reasons
    status = "violation" if violation else ("ready" if prediction_allowed else "blocked")

    payload = {
        "status": status,
        "prediction_status": "ready" if prediction_allowed else "blocked",
        "generated_at": _now(),
        "workspace_version": "1.0",
        "decision_board_status": board_status,
        "decision_board_path": str(board_path),
        "current_research_state": current_state,
        "next_allowed_action": next_action,
        "required_gates": REQUIRED_GATES,
        "active_model_available": active_model_available,
        "active_model_path_exists": active_path_exists,
        "customer_predictions_path_exists": customer_prediction_path_exists,
        "manual_approval_recommended": manual_approval_recommended,
        "active_publish_allowed": active_publish_allowed,
        "prediction_generation_allowed": prediction_allowed,
        "customer_visible_output_allowed": False,
        "blocking_reasons": deduped_reasons,
        "warning_reasons": [] if deduped_reasons else ["prediction_workspace_requires_explicit_future_shadow_or_active_workflow"],
        "evidence_paths": dict(board.get("evidence_paths") or {}) if isinstance(board.get("evidence_paths"), Mapping) else {},
        "training_invoked": False,
        "active_updated": False,
        "customer_prediction_generated": False,
    }
    return sanitize_for_json(payload)
