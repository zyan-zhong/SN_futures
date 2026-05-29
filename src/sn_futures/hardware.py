from __future__ import annotations

import json
import os
import platform
import subprocess
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from .config import ProjectPaths


PROFILE_FILE_NAME = "sn_hardware_profile.json"


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        parsed = int(value)
    except Exception:
        return default
    return parsed if parsed >= 0 else default


def _memory_gb() -> float:
    try:
        import psutil  # type: ignore

        return round(float(psutil.virtual_memory().total) / 1024**3, 2)
    except Exception:
        return 0.0


def _torch_profile() -> dict[str, Any]:
    payload: dict[str, Any] = {
        "torch_available": False,
        "cuda_available": False,
        "torch_cuda_available": False,
        "cuda_device_count": 0,
        "gpu_name": "",
        "gpu_memory_gb": 0.0,
        "training_device": "cpu",
        "runtime_cuda_reason": "Torch not available in this runtime.",
    }
    try:
        import torch  # type: ignore

        payload["torch_available"] = True
        payload["cuda_available"] = bool(torch.cuda.is_available())
        payload["torch_cuda_available"] = bool(torch.cuda.is_available())
        payload["cuda_device_count"] = int(torch.cuda.device_count()) if payload["cuda_available"] else 0
        if payload["cuda_available"]:
            index = 0
            props = torch.cuda.get_device_properties(index)
            payload["gpu_name"] = str(props.name)
            payload["gpu_memory_gb"] = round(float(props.total_memory) / 1024**3, 2)
            payload["training_device"] = "cuda:0"
            payload["runtime_cuda_reason"] = "CUDA Torch is available; background training can use GPU."
        else:
            payload["runtime_cuda_reason"] = "Torch is installed, but torch.cuda.is_available() is false."
    except Exception:
        pass
    return payload


def _nvidia_smi_profile() -> dict[str, Any]:
    try:
        result = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=name,memory.total,driver_version",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            text=True,
            timeout=3,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except Exception:
        return {}
    if result.returncode != 0 or not result.stdout.strip():
        return {}
    first = result.stdout.strip().splitlines()[0]
    parts = [part.strip() for part in first.split(",")]
    if len(parts) < 2:
        return {}
    payload: dict[str, Any] = {
        "nvidia_driver_detected": True,
        "gpu_name": parts[0],
        "gpu_memory_gb": round(_safe_int(parts[1]) / 1024, 2),
    }
    if len(parts) >= 3:
        payload["nvidia_driver_version"] = parts[2]
    return payload


def detect_hardware_profile() -> dict[str, Any]:
    cpu_count = os.cpu_count() or 1
    memory_gb = _memory_gb()
    torch_payload = _torch_profile()
    smi_payload = _nvidia_smi_profile()
    nvidia_driver_detected = bool(smi_payload.get("nvidia_driver_detected"))
    if not torch_payload.get("gpu_name") and smi_payload:
        torch_payload["gpu_name"] = smi_payload.get("gpu_name", "")
        torch_payload["gpu_memory_gb"] = smi_payload.get("gpu_memory_gb", 0.0)
    if nvidia_driver_detected and not torch_payload.get("cuda_available"):
        torch_payload["runtime_cuda_reason"] = (
            "NVIDIA driver detected, but this runtime does not include CUDA-enabled Torch; "
            "training is safely downgraded to CPU."
        )

    cuda_available = bool(torch_payload.get("cuda_available"))
    gpu_memory = float(torch_payload.get("gpu_memory_gb", 0.0) or 0.0)

    if cuda_available and gpu_memory >= 6.0 and cpu_count >= 8 and memory_gb >= 16:
        recommended = "gpu_full"
        strategy = "启用 GPU 候选训练、较长训练窗口和更高 LSTM 轮次；全部在后台 worker 中运行。"
    elif cpu_count >= 8 and memory_gb >= 16:
        recommended = "full"
        strategy = "启用完整候选池和较长滚动窗口；深度模型自动降级为 CPU 轻量训练。"
    elif cpu_count >= 4 and memory_gb >= 8:
        recommended = "balanced"
        strategy = "使用平衡候选池，兼顾准确性与普通办公电脑稳定性。"
    else:
        recommended = "fast"
        strategy = "使用轻量候选池、低频重训和短超时，优先避免界面卡顿。"

    return {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "platform": platform.platform(),
        "processor": platform.processor() or platform.machine(),
        "cpu_logical_cores": int(cpu_count),
        "memory_gb": memory_gb,
        "nvidia_driver_detected": nvidia_driver_detected,
        "nvidia_driver_version": smi_payload.get("nvidia_driver_version", ""),
        **torch_payload,
        "recommended_profile": recommended,
        "current_profile": recommended,
        "last_gpu_task_used": bool(recommended == "gpu_full" and cuda_available),
        "actual_training_device": "cuda:0" if cuda_available and recommended == "gpu_full" else "cpu",
        "last_training_used_gpu": bool(recommended == "gpu_full" and cuda_available),
        "gpu_full_enabled": bool(recommended == "gpu_full" and cuda_available),
        "downgrade_reason": "" if cuda_available else str(torch_payload.get("runtime_cuda_reason", "")),
        "training_strategy": strategy,
        "worker_policy": "训练、回测、刷新均通过后台子进程执行；UI 只轮询任务状态。",
    }


def resolve_compute_profile(requested: str | None, profile: dict[str, Any] | None = None) -> str:
    profile = profile or detect_hardware_profile()
    requested = (requested or "auto").strip().lower()
    if requested in {"", "auto"}:
        return str(profile.get("recommended_profile", "balanced"))
    if requested == "gpu_full" and not profile.get("cuda_available"):
        return "full" if _safe_int(profile.get("cpu_logical_cores"), 1) >= 8 else "balanced"
    if requested not in {"fast", "balanced", "full", "gpu_full"}:
        return str(profile.get("recommended_profile", "balanced"))
    return requested


def hardware_profile_path(output_dir: Path | None = None) -> Path:
    return (output_dir or ProjectPaths().output_dir) / PROFILE_FILE_NAME


def save_hardware_profile(profile: dict[str, Any], output_dir: Path | None = None) -> None:
    path = hardware_profile_path(output_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(profile, ensure_ascii=False, indent=2, default=str), encoding="utf-8")


def load_hardware_profile(output_dir: Path | None = None, *, max_age_minutes: int = 60) -> dict[str, Any]:
    path = hardware_profile_path(output_dir)
    if path.exists():
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            created = datetime.fromisoformat(str(payload.get("created_at", "")))
            if datetime.now() - created <= timedelta(minutes=max_age_minutes):
                return payload if isinstance(payload, dict) else {}
        except Exception:
            pass
    profile = detect_hardware_profile()
    save_hardware_profile(profile, output_dir)
    return profile
