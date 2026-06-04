from __future__ import annotations

from pathlib import Path


AUDIT_PATH = Path("docs/TERMINAL_BUTTON_API_AUDIT.md")
FRONTEND_DIR = Path("frontend/src")


def _audit_table_rows() -> list[list[str]]:
    text = AUDIT_PATH.read_text(encoding="utf-8")
    table = [line.strip() for line in text.splitlines() if line.startswith("|") and line.endswith("|")]
    rows: list[list[str]] = []
    for line in table[2:]:
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        if len(cells) >= 10:
            rows.append(cells)
    return rows


def test_button_audit_includes_latest_research_and_operations_controls() -> None:
    text = AUDIT_PATH.read_text(encoding="utf-8")
    rows = _audit_table_rows()

    assert len(rows) >= 90
    for expected in (
        "runCandidateV7Research",
        "/api/terminal/research/run-candidate-v7",
        "candidate_v7",
        "warehouse_missing_policy",
        "inventory_missing_flag",
        "generateFullSystemTxtReport",
        "exportDiagnosticsBundle",
    ):
        assert expected in text


def test_button_audit_has_no_duplicate_page_button_api_rows() -> None:
    duplicates: list[str] = []
    seen: set[tuple[str, str, str]] = set()
    for row in _audit_table_rows():
        key = (row[0], row[1], row[2])
        if key in seen:
            duplicates.append(" / ".join(key))
        seen.add(key)

    assert duplicates == []


def test_frontend_has_no_duplicate_danger_or_shutdown_safe_actions() -> None:
    text = "\n".join(path.read_text(encoding="utf-8") for path in FRONTEND_DIR.rglob("*.tsx"))

    assert text.count("approveActiveModel") == 2  # import + single handler call
    assert text.count("shutdownBackend") <= 2  # import + single handler call
    assert "fake prediction" not in text.lower()
    assert "baseline prediction" not in text.lower()
