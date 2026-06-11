from __future__ import annotations

from pathlib import Path

from ..runtime import get_user_output_dir


def public_terminal_dir() -> Path:
    path = get_user_output_dir() / "public_terminal"
    path.mkdir(parents=True, exist_ok=True)
    return path


def provider_smoke_report_path() -> Path:
    return public_terminal_dir() / "provider_smoke_report.json"


def data_watermark_path() -> Path:
    return public_terminal_dir() / "data_watermark.json"
