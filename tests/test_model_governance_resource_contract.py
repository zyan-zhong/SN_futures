from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any


sys.path.insert(0, "src")

from sn_futures.api.terminal_api import handle_terminal_api
from sn_futures.model_governance.active_release import (
    ACTIVE_RELEASE_SCHEMA_VERSION,
    build_active_release_manifest,
    load_active_release_manifest,
    publish_active_release,
)
from sn_futures.model_governance.experiment import submit_training_job
from sn_futures.model_governance.promotion import evaluate_promotion_gate
from sn_futures.model_governance.registry import evaluate_active_model_safety, register_candidate_model
from sn_futures.prediction_core.readiness import build_public_prediction_core_readiness
from sn_futures.resource_manager.hardware import HardwareSnapshot, ResourceBudget, plan_training_resources
from sn_futures.resource_manager.scheduler import InMemoryJobQueue
from sn_futures.resource_manager.worker_pool import WorkerPoolSnapshot, worker_pool_gate


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_json(path: Path, payload: dict[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def _dataset_manifest(tmp_path: Path, *, sample: bool = False, allowed: bool = True) -> Path:
    data_path = _write_json(tmp_path / "dataset.json", {"rows": [1, 2, 3], "sample": sample})
    payload = {
        "schema_version": "training-dataset-manifest-v1",
        "status": "ready",
        "dataset_id": "dataset-v1",
        "content_hash": _sha256(data_path),
        "feature_manifest_hash": "feature-hash-v1",
        "data_watermark_hash": "watermark-hash-v1",
        "row_count": 120,
        "fixture": False,
        "sample_data_used": sample,
        "fake_data_used": False,
        "baseline_used": False,
        "allowed_for_training": allowed,
        "allowed_for_prediction": False,
        "allowed_for_backtest": False,
    }
    return _write_json(tmp_path / "training_dataset_manifest.json", payload)


def _candidate(**overrides: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "model_id": "candidate-sn-v1",
        "horizon": "tomorrow",
        "dataset_hash": "dataset-hash-placeholder",
        "feature_manifest_hash": "feature-hash-v1",
        "data_watermark_hash": "watermark-hash-v1",
        "artifact_uri": "model_artifacts/candidate-sn-v1.pkl",
        "sample_data_used": False,
        "baseline_used": False,
        "fake_data_used": False,
    }
    payload.update(overrides)
    return payload


def _ready_evidence() -> dict[str, Any]:
    return {
        "calibration": {"status": "pass", "artifact_uri": "calibration/candidate.json"},
        "walk_forward": {"status": "pass", "fold_count": 5, "artifact_uri": "walk_forward/candidate.json"},
        "backtest": {"status": "pass", "artifact_uri": "backtest/candidate.json"},
    }


def test_public_terminal_cannot_start_training() -> None:
    public_paths = ["/api/public-terminal/train", "/api/public-terminal/models/train-candidate"]

    for path in public_paths:
        status, payload = handle_terminal_api(path, "POST", {}, {"dev_mode": True})

        assert status == 404
        assert payload["error"] == "not_found"
        serialized = json.dumps(payload, ensure_ascii=False).lower()
        assert "training_invoked" not in serialized


def test_training_requires_explicit_dev_mode_and_dataset_manifest(tmp_path: Path) -> None:
    queue = InMemoryJobQueue()

    missing_dev = submit_training_job(
        {
            "job_id": "missing-dev",
            "dataset_manifest_path": str(_dataset_manifest(tmp_path)),
            "requested_resources": {"memory_gb": 2},
        },
        resources={"cpu_count": 8, "memory": {"total_gb": 32, "available_gb": 24}},
        queue=queue,
        output_dir=tmp_path / "outputs",
    )
    missing_manifest = submit_training_job(
        {
            "job_id": "missing-manifest",
            "dev_mode": True,
            "dataset_manifest_path": str(tmp_path / "missing.json"),
            "requested_resources": {"memory_gb": 2},
        },
        resources={"cpu_count": 8, "memory": {"total_gb": 32, "available_gb": 24}},
        queue=queue,
        output_dir=tmp_path / "outputs",
    )

    assert missing_dev["status"] == "blocked"
    assert "dev_mode_required" in missing_dev["blocking_reasons"]
    assert missing_manifest["status"] == "blocked"
    assert "dataset_manifest_missing" in missing_manifest["blocking_reasons"]
    assert missing_dev["training_invoked"] is False
    assert missing_manifest["real_training_invoked"] is False


def test_gpu_missing_falls_back_to_cpu_or_blocks() -> None:
    snapshot = HardwareSnapshot(cpu_count=8, gpu_available=False, gpu_count=0, ram_total_gb=32, ram_available_gb=24)

    fallback = plan_training_resources(
        ResourceBudget(requires_gpu=True, allow_cpu_fallback=True, memory_gb=8),
        hardware=snapshot,
    )
    blocked = plan_training_resources(
        ResourceBudget(requires_gpu=True, allow_cpu_fallback=False, memory_gb=8),
        hardware=snapshot,
    )

    assert fallback["status"] == "ready"
    assert fallback["device"] == "cpu"
    assert "gpu_unavailable_fallback_cpu" in fallback["warnings"]
    assert blocked["status"] == "blocked"
    assert "gpu_unavailable" in blocked["blocking_reasons"]


def test_memory_budget_exceeded_blocks_training_plan() -> None:
    snapshot = HardwareSnapshot(cpu_count=8, gpu_available=True, gpu_count=1, ram_total_gb=32, ram_available_gb=4)

    result = plan_training_resources(ResourceBudget(memory_gb=8), hardware=snapshot)

    assert result["status"] == "blocked"
    assert "memory_limit_exceeded" in result["blocking_reasons"]


def test_worker_pool_gate_blocks_when_busy() -> None:
    result = worker_pool_gate(WorkerPoolSnapshot(running_jobs=2, max_workers=2))

    assert result["status"] == "blocked"
    assert "resource_busy" in result["blocking_reasons"]


def test_experiment_manifest_and_registry_version_are_required(tmp_path: Path) -> None:
    manifest_path = _dataset_manifest(tmp_path)
    dataset_hash = json.loads(manifest_path.read_text(encoding="utf-8"))["content_hash"]

    job = submit_training_job(
        {
            "job_id": "contract-job",
            "dev_mode": True,
            "dataset_manifest_path": str(manifest_path),
            "requested_resources": {"memory_gb": 2},
        },
        resources={"cpu_count": 8, "memory": {"total_gb": 32, "available_gb": 24}},
        queue=InMemoryJobQueue(),
        output_dir=tmp_path / "outputs",
    )
    invalid_registry = register_candidate_model(
        _candidate(dataset_hash=""),
        dataset_manifest_path=manifest_path,
        output_dir=tmp_path / "outputs",
    )
    valid_registry = register_candidate_model(
        _candidate(dataset_hash=dataset_hash),
        dataset_manifest_path=manifest_path,
        output_dir=tmp_path / "outputs",
    )

    assert job["status"] == "queued"
    assert job["experiment_manifest"]["schema_version"] == "dev-model-training-experiment-v1"
    assert job["experiment_manifest"]["training_invoked"] is False
    assert invalid_registry["status"] == "blocked"
    assert "dataset_hash_missing" in invalid_registry["blocking_reasons"]
    assert valid_registry["schema_version"] == "dev-model-registry-v1"
    assert valid_registry["registry_record"]["status"] == "candidate"


def test_promotion_requires_calibration_walk_forward_and_backtest(tmp_path: Path) -> None:
    candidate = _candidate(dataset_hash="dataset-hash")

    blocked = evaluate_promotion_gate(
        candidate,
        evidence={"calibration": {"status": "pass"}},
        output_dir=tmp_path / "outputs",
    )
    ready = evaluate_promotion_gate(candidate, evidence=_ready_evidence(), output_dir=tmp_path / "outputs")

    assert blocked["status"] == "blocked"
    assert "walk_forward_missing" in blocked["blocking_reasons"]
    assert "backtest_missing" in blocked["blocking_reasons"]
    assert ready["status"] == "ready"
    assert ready["promotion_allowed"] is True
    assert ready["active_updated"] is False


def test_sample_or_baseline_model_cannot_be_active() -> None:
    sample = evaluate_active_model_safety(_candidate(sample_data_used=True))
    baseline = evaluate_active_model_safety(_candidate(baseline_used=True))

    assert sample["status"] == "blocked"
    assert "sample_data_used" in sample["blocking_reasons"]
    assert baseline["status"] == "blocked"
    assert "baseline_used" in baseline["blocking_reasons"]


def test_active_release_manifest_is_dev_only_and_public_readiness_reads_it(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("SN_DATA_DIR", str(tmp_path))
    manifest = build_active_release_manifest(
        _candidate(dataset_hash="dataset-hash"),
        evidence=_ready_evidence(),
        approval={"status": "approved", "approved_by": "dev-reviewer"},
    )
    published = publish_active_release(manifest, output_dir=tmp_path / "outputs")
    loaded = load_active_release_manifest(output_dir=tmp_path / "outputs")
    readiness = build_public_prediction_core_readiness(output_dir=tmp_path / "outputs", horizons=("tomorrow",))

    assert manifest["schema_version"] == ACTIVE_RELEASE_SCHEMA_VERSION
    assert manifest["training_invoked"] is False
    assert manifest["prediction_generated"] is False
    assert published["status"] == "active_released"
    assert published["active_updated"] is True
    assert loaded["schema_version"] == ACTIVE_RELEASE_SCHEMA_VERSION
    assert readiness["active_release"]["exists"] is True
    assert readiness["training_invoked"] is False
    assert readiness["prediction_generated"] is False
    assert "prediction_output_available" in readiness
