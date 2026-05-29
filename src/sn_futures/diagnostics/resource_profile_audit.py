from __future__ import annotations

from typing import Any, Mapping


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return default


def audit_resource_profile(profile: Mapping[str, Any] | None) -> dict[str, Any]:
    """Audit whether the runtime training profile matches available hardware."""

    profile = profile or {}
    cores = _safe_int(profile.get("cpu_logical_cores"), 0)
    memory = _safe_float(profile.get("memory_gb"), 0.0)
    cuda = bool(profile.get("torch_cuda_available") or profile.get("cuda_available"))
    gpu_name = str(profile.get("gpu_name") or "")
    actual_device = str(profile.get("actual_training_device") or profile.get("training_device") or "cpu")
    recommended = str(profile.get("recommended_profile") or profile.get("current_profile") or "balanced")
    current = str(profile.get("current_profile") or recommended)

    warnings: list[str] = []
    if cores < 4:
        warnings.append("CPU 核心较少，建议使用 fast 档位并降低后台训练频率。")
    if memory and memory < 8:
        warnings.append("可用内存偏低，长周期 walk-forward 和事件消融应延后到非交易时段。")
    if "gpu" in current and not cuda:
        warnings.append("当前选择 GPU 档位，但运行时未检测到 CUDA Torch，必须自动降级 CPU。")
    if cuda and "cuda" not in actual_device:
        warnings.append("CUDA 可用但当前训练设备不是 cuda:0；GPU 只应在后台候选训练中启用。")

    strategy = (
        "GPU-Standard：后台重训、候选模型评估和事件消融可使用 GPU；实时预测保持轻量。"
        if cuda and _safe_float(profile.get("gpu_memory_gb"), 0.0) >= 6.0
        else "CPU 模式：使用树模型和轻量校准，重训练限流，优先保证终端稳定。"
    )
    severity = "yellow" if warnings else "normal"
    return {
        "ok": not any("必须" in item for item in warnings),
        "status": "passed" if not warnings else "warning",
        "severity": severity,
        "summary": "资源画像审计完成；训练档位应随硬件自动调整，重任务不得阻塞 UI。",
        "cpu_logical_cores": cores,
        "memory_gb": memory,
        "gpu_name": gpu_name,
        "cuda_available": cuda,
        "recommended_profile": recommended,
        "current_profile": current,
        "actual_training_device": actual_device,
        "strategy": strategy,
        "warnings": warnings,
    }
