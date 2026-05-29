from __future__ import annotations

import json
from pathlib import Path


def test_playwright_e2e_files_and_scripts_exist() -> None:
    package = json.loads(Path("frontend/package.json").read_text(encoding="utf-8"))
    assert "test:e2e" in package["scripts"]
    assert "test:e2e:headed" in package["scripts"]
    assert "@playwright/test" in package["devDependencies"]
    assert Path("frontend/playwright.config.ts").exists()
    assert Path("frontend/e2e/terminal.spec.ts").exists()


def test_e2e_captures_required_screenshots_and_safety_checks() -> None:
    spec = Path("frontend/e2e/terminal.spec.ts").read_text(encoding="utf-8")
    for name in ("dashboard", "predictions", "events", "reports", "settings"):
        assert f"{name}.png" in spec
    assert "undefined" in spec
    assert "NaN" in spec
    assert "forbiddenVisibleTerms" in spec
    assert "样例" in spec


def test_installed_smoke_can_run_browser_smoke() -> None:
    script = Path("packaging/smoke_installed.ps1").read_text(encoding="utf-8")
    assert "RunBrowserSmoke" in script
    assert "PLAYWRIGHT_BASE_URL" in script
    assert "SN_E2E_SKIP_WEBSERVER" in script
