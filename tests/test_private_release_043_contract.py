from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VERSION = "0.4.3-private-research-beta.1"


def test_private_release_043_version_is_consistent() -> None:
    assert (ROOT / "VERSION").read_text(encoding="utf-8").strip() == VERSION
    package = json.loads((ROOT / "frontend" / "package.json").read_text(encoding="utf-8"))
    lock = json.loads((ROOT / "frontend" / "package-lock.json").read_text(encoding="utf-8"))
    build_script = (ROOT / "packaging" / "build_release.ps1").read_text(encoding="utf-8")
    installer_script = (ROOT / "packaging" / "SNInsightTerminal.iss").read_text(encoding="utf-8")

    assert package["version"] == VERSION
    assert lock["version"] == VERSION
    assert lock["packages"][""]["version"] == VERSION
    assert f'[string]$Version = "{VERSION}"' in build_script
    assert f'#define MyAppVersion "{VERSION}"' in installer_script


def test_private_release_043_docs_capture_research_only_acceptance() -> None:
    notes = ROOT / "docs" / "PRIVATE_RELEASE_NOTES_0.4.3.md"
    report = ROOT / "docs" / "CUSTOMER_RELEASE_REPORT_0.4.3_PRIVATE.md"

    assert notes.exists()
    assert report.exists()

    combined = notes.read_text(encoding="utf-8") + "\n" + report.read_text(encoding="utf-8")
    for required in (
        VERSION,
        "private research beta",
        "Alpha",
        "NewsAPI",
        "Tushare",
        "configured/masked",
        "Feature Store v7",
        "Feature Store v8",
        "Feature Store v9",
        "Candidate v8",
        "Candidate v9",
        "No active model",
        "No customer predictions",
        "full_system_report_latest.txt",
        "diagnostics_bundle.zip",
        "secret scan",
    ):
        assert required in combined
