from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_installed_smoke_requires_all_provider_keys_unconfigured_in_isolated_mode() -> None:
    script = (ROOT / "packaging" / "smoke_installed.ps1").read_text(encoding="utf-8")

    assert "$settingsStatus.alpha_vantage_configured -eq $false" in script
    assert "$settingsStatus.newsapi_configured -eq $false" in script
    assert "$settingsStatus.tushare_configured -eq $false" in script
    assert "$settingsStatus.local_api_provider_configured -eq $false" in script
    assert "Alpha Vantage is unconfigured in isolated smoke" in script
    assert "NewsAPI is unconfigured in isolated smoke" in script
    assert "Tushare is unconfigured in isolated smoke" in script
    assert "Local API Provider is unconfigured in isolated smoke" in script


def test_installed_smoke_clears_provider_key_environment_and_does_not_run_live_key_tests() -> None:
    script = (ROOT / "packaging" / "smoke_installed.ps1").read_text(encoding="utf-8")

    for name in (
        "SN_ALPHA_VANTAGE_KEY",
        "SN_NEWSAPI_KEY",
        "SN_TUSHARE_TOKEN",
        "SN_LOCAL_API_PROVIDER_TOKEN",
        "SN_MANAGED_PROXY_TOKEN",
        "SN_MANAGED_DATA_PROXY_TOKEN",
    ):
        assert name in script
    assert "/api/terminal/newsapi/test" not in script
    assert "Tushare configured/masked only; API permission or quota is not an install failure" not in script
