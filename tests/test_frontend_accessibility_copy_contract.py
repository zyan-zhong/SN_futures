from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "frontend" / "src"


def _read(relative: str) -> str:
    return (SRC / relative).read_text(encoding="utf-8")


def test_workspace_guard_banner_has_accessible_live_status_and_raw_label_boundary() -> None:
    source = _read("components/common/WorkspaceGuardBanner.tsx")

    assert 'role="status"' in source
    assert 'aria-live="polite"' in source
    assert "Raw status" in source
    assert '<details aria-label="Raw status details"' in source
    assert "formatStatusLabel" in source
    assert "formatNextAction" in source
    assert "<small>{formatRawStatusLabel" not in source


def test_status_pill_exposes_text_label_and_not_color_only() -> None:
    source = _read("components/common/StatusPill.tsx")

    assert "aria-label" in source
    assert "data-tone" in source
    assert "formatStatusLabel" in source


def test_task_notification_center_has_keyboard_state_semantics() -> None:
    source = _read("components/task/GlobalTaskBar.tsx")

    assert "aria-expanded" in source
    assert "aria-controls" in source
    assert "aria-label" in source
    assert "Task Notification Center" in source
    assert "formatStatusLabel" in source


def test_refresh_buttons_explain_disabled_reason() -> None:
    source = _read("pages/GovernanceConsolePage.tsx")

    assert "getDisabledReason" in source
    assert "aria-describedby" in source
    assert "disabledReason" in source


def test_workspace_details_have_accessible_names() -> None:
    for relative in [
        "pages/DataOnboardingPage.tsx",
        "pages/ResearchArchivePage.tsx",
    ]:
        source = _read(relative)
        assert "<details" in source
        assert "aria-label" in source
        assert "<summary" in source


def test_no_forbidden_prediction_or_active_primary_cta_copy() -> None:
    combined = "\n".join(
        path.read_text(encoding="utf-8")
        for path in [
            SRC / "pages" / "PredictionWorkspacePage.tsx",
            SRC / "pages" / "CandidateResearchPage.tsx",
            SRC / "pages" / "ResearchArchivePage.tsx",
            SRC / "components" / "common" / "WorkspaceGuardBanner.tsx",
        ]
    ).lower()

    for forbidden in [
        ">generate customer prediction<",
        ">live prediction<",
        ">publish active<",
        ">active publish<",
        "active publish primary",
    ]:
        assert forbidden not in combined
