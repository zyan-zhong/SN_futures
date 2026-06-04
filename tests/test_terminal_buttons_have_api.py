from __future__ import annotations

import re
from pathlib import Path


PAGE_DIR = Path("frontend/src/pages")


def _button_opening_tags(text: str) -> list[str]:
    return re.findall(r"<button\b[\s\S]*?>", text)


def test_every_page_button_has_handler_or_accessible_static_role() -> None:
    offenders: list[str] = []
    for path in PAGE_DIR.glob("*.tsx"):
        text = path.read_text(encoding="utf-8")
        for tag in _button_opening_tags(text):
            if "onClick=" in tag or 'role="tab"' in tag:
                continue
            offenders.append(f"{path.name}: {tag[:120]}")
    assert offenders == []


def test_refresh_and_run_buttons_map_to_terminal_api_helpers() -> None:
    terminal_api = Path("frontend/src/api/terminal.ts").read_text(encoding="utf-8")
    required_helpers = [
        "refreshMarket",
        "refreshNews",
        "refreshAll",
        "buildTrainingDataset",
        "runResearchBacktest",
        "runModelExperiment",
        "testProvider",
        "saveSettingsSecrets",
    ]
    for helper in required_helpers:
        assert helper in terminal_api

    joined_pages = "\n".join(path.read_text(encoding="utf-8") for path in PAGE_DIR.glob("*.tsx"))
    for helper in required_helpers:
        assert helper in joined_pages or helper in {"refreshAll"}
