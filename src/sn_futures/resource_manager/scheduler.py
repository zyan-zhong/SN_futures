from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Mapping

from .gpu import GpuSnapshot, detect_gpu, normalise_gpu_snapshot
from .memory import MemorySnapshot, evaluate_memory_limit, normalise_memory_snapshot


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass(frozen=True)
class ResourceSnapshot:
    cpu_count: int = 1
    gpu: GpuSnapshot = field(default_factory=GpuSnapshot)
    memory: MemorySnapshot = field(default_factory=MemorySnapshot)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["gpu"] = self.gpu.to_dict()
        payload["memory"] = self.memory.to_dict()
        return payload


@dataclass(frozen=True)
class ResourceRequest:
    requires_gpu: bool = False
    allow_cpu_fallback: bool = True
    memory_gb: float = 1.0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def normalise_resource_snapshot(payload: Mapping[str, Any] | ResourceSnapshot | None = None) -> ResourceSnapshot:
    if isinstance(payload, ResourceSnapshot):
        return payload
    data = dict(payload or {})
    return ResourceSnapshot(
        cpu_count=int(data.get("cpu_count") or 1),
        gpu=normalise_gpu_snapshot(data.get("gpu") if isinstance(data.get("gpu"), Mapping) else None),
        memory=normalise_memory_snapshot(data.get("memory") if isinstance(data.get("memory"), Mapping) else None),
    )


def current_resource_snapshot() -> ResourceSnapshot:
    return ResourceSnapshot(cpu_count=1, gpu=detect_gpu(), memory=MemorySnapshot(total_gb=0.0, available_gb=0.0))


def normalise_resource_request(payload: Mapping[str, Any] | ResourceRequest | None = None) -> ResourceRequest:
    if isinstance(payload, ResourceRequest):
        return payload
    data = dict(payload or {})
    return ResourceRequest(
        requires_gpu=bool(data.get("requires_gpu")),
        allow_cpu_fallback=bool(data.get("allow_cpu_fallback", True)),
        memory_gb=float(data.get("memory_gb") or 1.0),
    )


def plan_resource_allocation(
    requested: Mapping[str, Any] | ResourceRequest | None,
    resources: ResourceSnapshot | Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    request = normalise_resource_request(requested)
    snapshot = normalise_resource_snapshot(resources) if resources is not None else current_resource_snapshot()
    blocking: list[str] = []
    warnings: list[str] = []

    device = "cpu"
    if request.requires_gpu:
        if snapshot.gpu.available:
            device = "gpu"
        elif request.allow_cpu_fallback:
            warnings.append("gpu_unavailable_fallback_cpu")
        else:
            blocking.append("gpu_unavailable")

    memory = evaluate_memory_limit(required_gb=request.memory_gb, snapshot=snapshot.memory)
    blocking.extend(str(reason) for reason in memory["blocking_reasons"])
    blocking = sorted(set(blocking))
    return {
        "status": "blocked" if blocking else "ready",
        "device": device,
        "requested": request.to_dict(),
        "snapshot": snapshot.to_dict(),
        "memory": memory,
        "warnings": warnings,
        "blocking_reasons": blocking,
    }


class InMemoryJobQueue:
    def __init__(self) -> None:
        self._jobs: list[dict[str, Any]] = []

    def enqueue(self, *, job_id: str, kind: str, manifest: Mapping[str, Any]) -> dict[str, Any]:
        job = {
            "job_id": str(job_id),
            "kind": str(kind),
            "status": "queued",
            "queued_at": utc_now(),
            "manifest": dict(manifest),
            "real_training_invoked": False,
            "customer_prediction_generated": False,
        }
        self._jobs.append(job)
        return dict(job)

    def list_jobs(self) -> list[dict[str, Any]]:
        return [dict(job) for job in self._jobs]
