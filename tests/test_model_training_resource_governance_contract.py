from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


sys.path.insert(0, "src")

from sn_futures.api.terminal_api import handle_terminal_api
from sn_futures.model_governance.experiment import submit_training_job
from sn_futures.model_governance.promotion import evaluate_promotion_gate
from sn_futures.model_governance.registry import evaluate_active_model_safety, register_candidate_model
from sn_futures.resource_manager.gpu import GpuSnapshot
from sn_futures.resource_manager.memory import MemorySnapshot
from sn_futures.resource_manager.scheduler import InMemoryJobQueue, ResourceSnapshot


def _write_json(path: Path, payload: dict[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def _dataset_manifest(tmp_path: Path, **updates: Any) -> Path:
    payload: dict[str, Any] = {
        "schema_version": "training-dataset-manifest-v1",
        "status": "ready",
        "dataset_id": "dataset_real_contract",
        "content_hash": "dataset-hash-001",
        "feature_manifest_hash": "feature-hash-001",
        "label_manifest_hash": "label-hash-001",
        "data_watermark_hash": "watermark-hash-001",
        "row_count": 1200,
        "sample_data_used": False,
        "baseline_used": False,
        "fake_data_used": False,
        "allowed_for_training": True,
        "allowed_for_prediction": False,
    }
    payload.update(updates)
    return _write_json(tmp_path / "outputs" / "training_datasets" / "manifest.json", payload)


def _resources(
    *,
    gpu_available: bool = False,
    available_memory_gb: float = 24.0,
) -> ResourceSnapshot:
    return ResourceSnapshot(
        cpu_count=8,
        gpu=GpuSnapshot(available=gpu_available, device_count=1 if gpu_available else 0, name="fixture-gpu" if gpu_available else ""),
        memory=MemorySnapshot(total_gb=32.0, available_gb=available_memory_gb),
    )


def _training_request(tmp_path: Path, **updates: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "job_id": "train-dev-contract-001",
        "dev_mode": True,
        "requested_by": "contract-test",
        "dataset_manifest_path": str(_dataset_manifest(tmp_path)),
        "horizons": ["1d"],
        "requested_resources": {
            "requires_gpu": False,
            "allow_cpu_fallback": True,
            "memory_gb": 8,
        },
    }
    payload.update(updates)
    return payload


def _candidate_model(**updates: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "model_id": "candidate_governed_001",
        "status": "candidate",
        "horizon": "1d",
        "dataset_hash": "dataset-hash-001",
        "feature_manifest_hash": "feature-hash-001",
        "data_watermark_hash": "watermark-hash-001",
        "artifact_uri": "dev-only://candidate_governed_001",
        "sample_data_used": False,
        "baseline_used": False,
        "fake_data_used": False,
    }
    payload.update(updates)
    return payload


def test_training_job_requires_explicit_dev_mode(tmp_path: Path) -> None:
    queue = InMemoryJobQueue()
    request = _training_request(tmp_path, dev_mode=False)

    result = submit_training_job(request, resources=_resources(), queue=queue, output_dir=tmp_path / "outputs")

    assert result["status"] == "blocked"
    assert result["dev_only"] is True
    assert result["job_enqueued"] is False
    assert "dev_mode_required" in result["blocking_reasons"]
    assert result["real_training_invoked"] is False
    assert result["customer_prediction_generated"] is False
    assert queue.list_jobs() == []


def test_public_terminal_cannot_start_training() -> None:
    status, payload = handle_terminal_api(
        "/api/public-terminal/models/train",
        "POST",
        body={"dev_mode": True, "dataset_manifest_path": "anything"},
    )
    openapi_status, openapi = handle_terminal_api("/api/public-terminal/openapi.json", "GET")

    assert status == 404
    assert (payload.get("error_code") or payload.get("error")) in {"public_terminal_not_found", "not_found"}
    assert openapi_status == 200
    public_paths = [str(item.get("path", "")) for item in openapi.get("endpoints", []) if isinstance(item, dict)]
    assert all("train" not in path.lower() and "promotion" not in path.lower() for path in public_paths)


def test_gpu_unavailable_falls_back_to_cpu_when_allowed(tmp_path: Path) -> None:
    queue = InMemoryJobQueue()
    request = _training_request(
        tmp_path,
        requested_resources={
            "requires_gpu": True,
            "allow_cpu_fallback": True,
            "memory_gb": 8,
        },
    )

    result = submit_training_job(request, resources=_resources(gpu_available=False), queue=queue, output_dir=tmp_path / "outputs")

    assert result["status"] == "queued"
    assert result["resource_plan"]["device"] == "cpu"
    assert "gpu_unavailable_fallback_cpu" in result["resource_plan"]["warnings"]
    assert result["job_enqueued"] is True
    assert result["real_training_invoked"] is False
    assert len(queue.list_jobs()) == 1


def test_gpu_unavailable_blocks_when_gpu_is_required(tmp_path: Path) -> None:
    request = _training_request(
        tmp_path,
        requested_resources={
            "requires_gpu": True,
            "allow_cpu_fallback": False,
            "memory_gb": 8,
        },
    )

    result = submit_training_job(request, resources=_resources(gpu_available=False), output_dir=tmp_path / "outputs")

    assert result["status"] == "blocked"
    assert result["job_enqueued"] is False
    assert "gpu_unavailable" in result["blocking_reasons"]


def test_memory_limit_exceeded_blocks_training_job(tmp_path: Path) -> None:
    request = _training_request(
        tmp_path,
        requested_resources={
            "requires_gpu": False,
            "allow_cpu_fallback": True,
            "memory_gb": 20,
        },
    )

    result = submit_training_job(request, resources=_resources(available_memory_gb=12), output_dir=tmp_path / "outputs")

    assert result["status"] == "blocked"
    assert result["job_enqueued"] is False
    assert "memory_limit_exceeded" in result["blocking_reasons"]
    assert result["resource_plan"]["memory"]["allowed"] is False


def test_training_output_requires_dataset_manifest(tmp_path: Path) -> None:
    request = _training_request(tmp_path, dataset_manifest_path=str(tmp_path / "missing_manifest.json"))

    result = submit_training_job(request, resources=_resources(), output_dir=tmp_path / "outputs")

    assert result["status"] == "blocked"
    assert result["experiment_manifest"]["status"] == "blocked"
    assert "dataset_manifest_missing" in result["blocking_reasons"]
    assert result["model_artifact_written"] is False


def test_model_registry_requires_feature_hash_and_data_watermark(tmp_path: Path) -> None:
    dataset_manifest_path = _dataset_manifest(tmp_path)
    invalid = register_candidate_model(
        _candidate_model(feature_manifest_hash=""),
        dataset_manifest_path=dataset_manifest_path,
        output_dir=tmp_path / "outputs",
    )

    valid = register_candidate_model(
        _candidate_model(),
        dataset_manifest_path=dataset_manifest_path,
        output_dir=tmp_path / "outputs",
    )

    assert invalid["status"] == "blocked"
    assert "feature_manifest_hash_missing" in invalid["blocking_reasons"]
    assert invalid["active_updated"] is False
    assert valid["status"] == "registered"
    assert valid["candidate_registered"] is True
    assert valid["active_updated"] is False
    assert valid["registry_record"]["feature_manifest_hash"] == "feature-hash-001"
    assert valid["registry_record"]["data_watermark_hash"] == "watermark-hash-001"


def test_promotion_requires_walk_forward_calibration_and_backtest(tmp_path: Path) -> None:
    candidate = _candidate_model()
    missing = evaluate_promotion_gate(
        candidate,
        evidence={
            "walk_forward": {"status": "pass"},
            "calibration": {"status": "missing"},
            "backtest": {"status": "missing"},
        },
        output_dir=tmp_path / "outputs",
    )
    ready = evaluate_promotion_gate(
        candidate,
        evidence={
            "walk_forward": {"status": "pass", "fold_count": 5},
            "calibration": {"status": "pass", "ece": 0.03},
            "backtest": {"status": "pass", "cost_adjusted_expectancy": 0.01},
        },
        output_dir=tmp_path / "outputs",
    )

    assert missing["status"] == "blocked"
    assert "calibration_missing" in missing["blocking_reasons"]
    assert "backtest_missing" in missing["blocking_reasons"]
    assert missing["active_updated"] is False
    assert ready["status"] == "ready"
    assert ready["promotion_allowed"] is True
    assert ready["approval_required"] is True
    assert ready["active_updated"] is False
    assert ready["customer_prediction_generated"] is False


def test_no_sample_or_baseline_model_can_be_active(tmp_path: Path) -> None:
    unsafe_sample = evaluate_active_model_safety(
        {
            "model_id": "sample_active_model",
            "status": "active",
            "sample_data_used": True,
            "baseline_used": False,
        }
    )
    unsafe_baseline = register_candidate_model(
        _candidate_model(model_id="baseline_candidate", baseline_used=True),
        dataset_manifest_path=_dataset_manifest(tmp_path),
        output_dir=tmp_path / "outputs",
    )

    assert unsafe_sample["status"] == "blocked"
    assert unsafe_sample["active_allowed"] is False
    assert "sample_data_used" in unsafe_sample["blocking_reasons"]
    assert unsafe_baseline["status"] == "blocked"
    assert "baseline_used" in unsafe_baseline["blocking_reasons"]
    assert unsafe_baseline["active_updated"] is False
