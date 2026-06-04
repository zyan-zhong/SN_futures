from __future__ import annotations

import re
from pathlib import Path


FRONTEND_DIR = Path("frontend/src")


def _tsx_text() -> str:
    return "\n".join(path.read_text(encoding="utf-8") for path in FRONTEND_DIR.rglob("*.tsx"))


def test_terminal_copy_keeps_csv_excel_message_single_sourced() -> None:
    text = _tsx_text()

    assert text.count("CSV/Excel") <= 3
    assert text.count("客户无需 CSV/Excel") <= 1
    assert text.count("客户不需要上传 CSV/Excel") <= 1
    assert text.count("客户不需要 CSV/Excel") <= 1


def test_page_and_card_descriptions_are_short_enough_for_terminal_ui() -> None:
    long_subtitles: list[str] = []
    for path in FRONTEND_DIR.rglob("*.tsx"):
        text = path.read_text(encoding="utf-8")
        for match in re.finditer(r"subtitle=\"([^\"]+)\"", text):
            subtitle = match.group(1).strip()
            if len(subtitle) > 170:
                long_subtitles.append(f"{path.name}: {subtitle[:90]}")

    assert long_subtitles == []


def test_terminal_does_not_render_raw_long_json_or_debug_payloads() -> None:
    text = _tsx_text()

    forbidden_visible_patterns = [
        "JSON.stringify(row.selected_params",
        "JSON.stringify(tushareSelectedParams",
        "JSON.stringify(result.bundle",
        "<pre>",
    ]
    for pattern in forbidden_visible_patterns:
        assert pattern not in text


def test_terminal_copy_never_exposes_placeholder_or_fake_prediction_terms() -> None:
    text = _tsx_text()

    for phrase in [">undefined<", ">null<", ">NaN<", "fake prediction", "baseline prediction"]:
        assert phrase not in text.lower()
