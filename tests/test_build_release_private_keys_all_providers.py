from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _build_release_script() -> str:
    return (ROOT / "packaging" / "build_release.ps1").read_text(encoding="utf-8")


def test_private_bundle_build_rejects_embedded_provider_keys() -> None:
    script = _build_release_script()

    assert "[switch]$RequireAllPrivateProviderKeys" in script
    assert "[switch]$PrivateBundleKeys" in script
    assert "[switch]$AllowEmbeddedProviderKeys" in script
    assert "PrivateBundleKeys 已禁用" in script
    assert "%LOCALAPPDATA%\\SNInsightTerminal\\config\\secrets.json" in script
    assert "Assert-NoEmbeddedPrivateBundle" in script


def test_private_keys_file_is_not_read_or_embedded_by_release_build() -> None:
    script = _build_release_script()

    assert "function Read-PrivateReleaseKeys" not in script
    assert "function New-PrivateBundleSeed" not in script
    assert "Get-Content -LiteralPath $resolved -Raw | ConvertFrom-Json" not in script
    assert "ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $PrivateBundleSeed" not in script


def test_build_log_reports_private_bundle_disabled_without_raw_values() -> None:
    script = _build_release_script()

    assert "发行包不得嵌入 provider key" in script
    assert "config\\secrets.json" in script
    assert "Mask-Key" not in script
    assert 'SN_TUSHARE_TOKEN"] = $keys.tushare' not in script


def test_build_failure_preserves_provider_missing_reason() -> None:
    script = _build_release_script()

    assert "发行构建失败" in script
    assert "throw $failureMessage" in script
