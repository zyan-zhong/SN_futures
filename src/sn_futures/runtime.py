from __future__ import annotations

import sys
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
        probe = target / ".write_probe"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink(missing_ok=True)
        return target
    except Exception:
        fallback = get_bundle_root() / "app_data"
        fallback.mkdir(parents=True, exist_ok=True)
        return fallback


def get_user_output_dir() -> Path:
    target = get_user_data_dir() / "outputs"
    try:
        target.mkdir(parents=True, exist_ok=True)
        probe = target / ".write_probe"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink(missing_ok=True)
        return target
    except Exception:
        fallback = get_bundle_root() / "app_data" / "outputs"
        fallback.mkdir(parents=True, exist_ok=True)
        return fallback


def get_bundled_docs() -> dict[str, Path]:
    return {
        "Institutional Blueprint": resource_path("docs", "sn_institutional_blueprint.md"),
        "Terminal PRD": resource_path("docs", "sn_terminal_prd.md"),
        "Report Templates": resource_path("docs", "sn_report_templates.md"),
        "Iteration Upgrade Plan": resource_path("docs", "sn_iteration_upgrade_plan.md"),
        "Project README": resource_path("README.md"),
    }
