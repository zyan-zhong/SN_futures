from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_inno_installer_deletes_legacy_private_bundle_files_before_copy() -> None:
    script = (ROOT / "packaging" / "SNInsightTerminal.iss").read_text(encoding="utf-8")

    assert "[InstallDelete]" in script
    for relative_path in (
        r"{app}\_internal\private\private_bundle_seed.json",
        r"{app}\_internal\private\private_release_keys.json",
        r"{app}\_internal\private\secrets.json",
        r"{app}\_internal\private\.env",
    ):
        assert f'Type: files; Name: "{relative_path}"' in script
    assert 'Type: dirifempty; Name: "{app}\\_internal\\private"' in script


def test_inno_cleanup_scope_never_targets_user_data_dirs() -> None:
    script = (ROOT / "packaging" / "SNInsightTerminal.iss").read_text(encoding="utf-8")
    install_delete = script.split("[InstallDelete]", 1)[1].split("[", 1)[0]

    assert "{app}\\_internal\\private" in install_delete
    assert "{localappdata}\\SNInsightTerminal" not in install_delete
    assert "%LOCALAPPDATA%\\SNInsightTerminal" not in install_delete
    assert "SN_DATA_DIR" not in install_delete
    assert "secrets.json" in install_delete
    assert "{app}\\config\\secrets.json" not in install_delete


def test_installed_smoke_can_seed_legacy_private_bundle_only_in_temp_install_root() -> None:
    script = (ROOT / "packaging" / "smoke_installed.ps1").read_text(encoding="utf-8")

    assert "[switch]$InjectLegacyPrivateSeed" in script
    assert "Assert-LegacySeedInjectionIsSafe" in script
    assert "Seed-LegacyPrivateBundle" in script
    assert "private_bundle_seed.json" in script
    assert "InjectLegacyPrivateSeed requires an explicit temporary InstalledRoot" in script
    assert "SNInsightTerminalInstall_" in script
    assert "Programs\\SNInsightTerminal" in script


def test_installed_smoke_asserts_legacy_private_seed_removed_after_install() -> None:
    script = (ROOT / "packaging" / "smoke_installed.ps1").read_text(encoding="utf-8")

    assert "Assert-LegacyPrivateBundleRemoved" in script
    assert "legacy private bundle seed is removed from install root" in script
    assert "legacy private directory is empty or absent after install" in script
    assert script.index("\n  Seed-LegacyPrivateBundle") < script.index("Starting silent install.")
    assert script.index("Starting silent install.") < script.index("\n    Assert-LegacyPrivateBundleRemoved")
