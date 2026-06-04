from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _build_release_script() -> str:
    return (ROOT / "packaging" / "build_release.ps1").read_text(encoding="utf-8")


def test_private_bundle_build_supports_all_provider_keys_and_require_all_gate() -> None:
    script = _build_release_script()

    assert "[switch]$RequireAllPrivateProviderKeys" in script
    for name in (
        "SN_ALPHA_VANTAGE_KEY",
        "SN_NEWSAPI_KEY",
        "SN_TUSHARE_TOKEN",
        "SN_MANAGED_PROXY_TOKEN",
    ):
        assert name in script


def test_private_keys_file_is_read_even_when_alpha_and_news_come_from_env() -> None:
    script = _build_release_script()
    body = script.split("function Read-PrivateReleaseKeys", 1)[1].split("function New-PrivateBundleSeed", 1)[0]

    assert "$fileKeys" in body
    assert "$payload = Get-Content" in body
    assert body.index("$payload = Get-Content") < body.index("$alpha =")
    assert "SN_BUNDLE_TUSHARE_TOKEN" in body


def test_build_log_reports_tushare_masked_configured_without_raw_values() -> None:
    script = _build_release_script()

    assert "Tushare configured" in script
    assert "Mask-Key $keys.tushare" in script
    assert 'SN_TUSHARE_TOKEN"] = $keys.tushare' in script


def test_build_failure_preserves_provider_missing_reason() -> None:
    script = _build_release_script()

    assert "发行构建失败" in script
    assert "throw $failureMessage" in script
