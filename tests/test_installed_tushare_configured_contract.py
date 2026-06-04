from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_installed_smoke_requires_tushare_configured_when_private_bundle_expected() -> None:
    script = (ROOT / "packaging" / "smoke_installed.ps1").read_text(encoding="utf-8")

    assert "$settingsStatus.tushare_configured" in script
    assert "$settingsStatus.tushare_masked" in script
    assert '([string]$settingsStatus.tushare_masked).Length -gt 0' in script
    assert '([string]$keyDiagnostics.tushare.masked).Length -gt 0' in script
    assert '([string]$afterReset.tushare_masked).Length -gt 0' in script
    assert "Tushare source is private_bundle/user_secrets/env" in script
    assert "reset restores or retains Tushare private default" in script


def test_installed_smoke_does_not_require_tushare_network_success() -> None:
    script = (ROOT / "packaging" / "smoke_installed.ps1").read_text(encoding="utf-8")

    assert "Tushare configured/masked only; API permission or quota is not an install failure" in script
