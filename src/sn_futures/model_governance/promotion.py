from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from ..api.json_utils import sanitize_for_json
from ..data_layer.stores import atomic_write_json
from ..runtime import get_user_output_dir
from .registry import evaluate_active_model_safety


PROMOTION_SCHEMA_VERSION = "dev-model-promotion-gate-v1"


def _output_dir(output_dir: Path | None = None) -> Path:
    return output_dir or get_user_output_dir()


def _passed(evidence: Mapping[str, Any]) -> bool:
    status = str(evidence.get("status") or "").strip().lower()
    return status in {"pass", "passed", "ready", "success"}


def _evidence_blockers(evidence: Mapping[str, Any]) -> list[str]:
    required = ("walk_forward", "calibration", "backtest")
    reasons: list[str] = []
    for name in required:
        item = evidence.get(name)
        if not isinstance(item, Mapping) or not item:
            reasons.append(f"{name}_missing")
            continue
        if not _passed(item):
            reasons.append(f"{name}_missing")
    return sorted(set(reasons))


def _promotion_report_path(output_dir: Path, model_id: str) -> Path:
    safe_model_id = Path(str(model_id or "candidate_model")).name.replace(" ", "_")
    return output_dir / "model_governance" / "promotion" / f"{safe_model_id}_promotion_gate.json"


def evaluate_promotion_gate(
    candidate: Mapping[str, Any],
    *,
    evidence: Mapping[str, Any],
    output_dir: Path | None = None,
) -> dict[str, Any]:
    out = _output_dir(output_dir)
    candidate_payload = dict(candidate)
    active_safety = evaluate_active_model_safety(candidate_payload)
    blocking = sorted(
        set(
            [
                *[str(reason) for reason in active_safety.get("blocking_reasons") or [] if str(reason)],
                *_evidence_blockers(dict(evidence)),
            ]
        )
    )
    ready = not blocking
    report = sanitize_for_json(
        {
            "schema_version": PROMOTION_SCHEMA_VERSION,
            "status": "ready" if ready else "blocked",
            "candidate_model_id": str(candidate_payload.get("model_id") or ""),
            "promotion_allowed": ready,
            "approval_required": True,
            "no_customer_prediction_until_approved": True,
            "evidence": dict(evidence),
            "blocking_reasons": blocking,
            "active_updated": False,
            "customer_prediction_generated": False,
            "prediction_generated": False,
            "real_training_invoked": False,
            "backtest_invoked": False,
        }
    )
    atomic_write_json(_promotion_report_path(out, str(candidate_payload.get("model_id") or "")), report)
    return report
