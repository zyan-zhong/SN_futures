from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PANEL = ROOT / "frontend" / "src" / "components" / "data" / "DataSourceStatusPanel.tsx"
TYPES = ROOT / "frontend" / "src" / "api" / "types.ts"


def test_frontend_knows_optional_failed_severity() -> None:
    panel = PANEL.read_text(encoding="utf-8")
    types = TYPES.read_text(encoding="utf-8")

    assert "optional_failed" in panel
    assert "\u53ef\u9009\u6e90\u5931\u8d25\uff0c\u4e0d\u5f71\u54cd\u4e3b\u884c\u60c5" in panel
    assert "severity" in types
    assert "optional_failed" in types


def test_frontend_does_not_render_optional_failed_as_fatal() -> None:
    panel = PANEL.read_text(encoding="utf-8")
    optional_branch = panel[panel.index("optional_failed") : panel.index("optional_failed") + 260]

    assert 'return "bad"' not in optional_branch
    assert 'return "warn"' in optional_branch or 'return "info"' in optional_branch
    assert "\u81f4\u547d" not in optional_branch
    assert "P0" not in optional_branch


def test_frontend_sanitizes_visible_local_paths() -> None:
    panel = PANEL.read_text(encoding="utf-8")

    assert "sanitizeVisiblePath" in panel
    assert "mini_racer.dll" in panel
    assert "C:\\\\Users" not in panel
