from __future__ import annotations

import sys
import uuid
from pathlib import Path

from .user_data import get_user_data_root


APP_NAME = "SN Insight Terminal"


def get_bundle_root() -> Path:
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS)  # type: ignore[attr-defined]
    return Path(__file__).resolve().parents[2]


def resource_path(*parts: str) -> Path:
    return get_bundle_root().joinpath(*parts)


def get_user_data_dir() -> Path:
    target = get_user_data_root()
    try:
        probe = target / f".write_probe_{uuid.uuid4().hex}"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink(missing_ok=True)
        return target
    except Exception as exc:
        raise RuntimeError(f"user data directory is not writable: {target}") from exc


def get_user_output_dir() -> Path:
    target = get_user_data_dir() / "outputs"
    try:
        target.mkdir(parents=True, exist_ok=True)
        probe = target / f".write_probe_{uuid.uuid4().hex}"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink(missing_ok=True)
        return target
    except Exception as exc:
        raise RuntimeError(f"runtime output directory is not writable: {target}") from exc


def legacy_output_dir_diagnostics(runtime_root: Path | None = None) -> dict[str, object]:
    runtime = runtime_root or get_user_output_dir()
    try:
        runtime_resolved = runtime.resolve()
    except Exception:
        runtime_resolved = runtime

    rows: list[dict[str, object]] = []
    seen: set[str] = set()
    for base in (get_bundle_root(), Path.cwd()):
        for candidate in (base / "outputs", base / "app_data" / "outputs"):
            try:
                resolved = candidate.resolve()
            except Exception:
                resolved = candidate
            key = str(resolved).lower()
            if key in seen or key == str(runtime_resolved).lower():
                continue
            seen.add(key)
            file_count = 0
            if resolved.exists():
                try:
                    file_count = sum(1 for item in resolved.rglob("*") if item.is_file())
                except Exception:
                    file_count = 0
            rows.append(
                {
                    "path": str(resolved),
                    "exists": resolved.exists(),
                    "artifact_count": file_count,
                    "ignored_for_business_reads": True,
                }
            )
    found = sum(int(row["artifact_count"]) for row in rows)
    return {
        "current_runtime_root": str(runtime_resolved),
        "runtime_root": str(runtime_resolved),
        "ignored_legacy_dirs": rows,
        "found_legacy_artifacts_count": found,
        "recommendation_zh": "业务读取只使用当前 runtime root；旧 outputs/app_data/outputs 仅做诊断，发现残留时请迁移或清理，不要作为预测/回测输入。",
    }


def get_bundled_docs() -> dict[str, Path]:
    return {
        "Institutional Blueprint": resource_path("docs", "sn_institutional_blueprint.md"),
        "Terminal PRD": resource_path("docs", "sn_terminal_prd.md"),
        "Report Templates": resource_path("docs", "sn_report_templates.md"),
        "Iteration Upgrade Plan": resource_path("docs", "sn_iteration_upgrade_plan.md"),
        "Project README": resource_path("README.md"),
    }
