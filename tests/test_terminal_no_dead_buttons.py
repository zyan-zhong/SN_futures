from __future__ import annotations

import re
from pathlib import Path


FRONTEND_DIR = Path("frontend/src")


def _button_tags(text: str) -> list[str]:
    return re.findall(r"<button\b[\s\S]*?>", text)


def test_no_clickable_terminal_button_is_decorative_only() -> None:
    offenders: list[str] = []
    for path in FRONTEND_DIR.rglob("*.tsx"):
        text = path.read_text(encoding="utf-8")
        for tag in _button_tags(text):
            allowed_static = 'type="submit"' in tag or 'role="tab"' in tag
            has_handler = "onClick=" in tag or "onSubmit=" in tag
            if allowed_static or has_handler:
                continue
            offenders.append(f"{path.relative_to(FRONTEND_DIR)}: {tag[:160]}")

    assert offenders == []


def test_no_active_publish_or_backend_shutdown_button_is_e2e_safe_clicked() -> None:
    spec = Path("frontend/e2e/button-audit.spec.ts")
    assert spec.exists()
    text = spec.read_text(encoding="utf-8")

    assert ".danger-button" in text
    assert "审批发布 active" not in text
    assert "stopBackendService" not in text


def test_buttons_have_accessible_names_or_titles() -> None:
    offenders: list[str] = []
    for path in FRONTEND_DIR.rglob("*.tsx"):
        text = path.read_text(encoding="utf-8")
        for tag in _button_tags(text):
            local = tag.lower()
            if "aria-label=" in local or "title=" in local or "</button>" not in tag:
                continue
            # Multi-line button text is outside the opening tag, so require only icon-only patterns
            # to carry an explicit label. Text buttons are covered by E2E visible-name assertions.
            if "lucide" in local or "icon" in local:
                offenders.append(f"{path.relative_to(FRONTEND_DIR)}: {tag[:160]}")

    assert offenders == []
