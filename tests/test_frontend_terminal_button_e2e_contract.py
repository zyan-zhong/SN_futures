from __future__ import annotations

from pathlib import Path


SPEC = Path("frontend/e2e/button-audit.spec.ts")


def test_button_audit_e2e_spec_exists_and_mocks_heavy_terminal_actions() -> None:
    assert SPEC.exists()
    text = SPEC.read_text(encoding="utf-8")

    for required in [
        "page.route(\"**/api/terminal/**\"",
        "request.method() === \"POST\"",
        "task_id",
        "safeButtonSelector",
        ".danger-button",
        ".error-boundary",
    ]:
        assert required in text


def test_button_audit_e2e_checks_layout_stability_after_clicks() -> None:
    text = SPEC.read_text(encoding="utf-8")

    assert "layoutBefore" in text
    assert "layoutAfter" in text
    assert "toBeLessThanOrEqual" in text


def test_button_audit_e2e_is_isolated_from_persistent_browser_state() -> None:
    text = SPEC.read_text(encoding="utf-8")

    assert "window.localStorage.clear()" in text
    assert "window.sessionStorage.clear()" in text
    assert "uiMode" in text
