from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VERSION = "0.4.2-private-research-beta.2"


def test_private_release_042_version_is_consistent() -> None:
    build_script = (ROOT / "packaging" / "build_release.ps1").read_text(encoding="utf-8")

    assert VERSION == "0.4.2-private-research-beta.2"
    assert "[switch]$RequireAllPrivateProviderKeys" in build_script


def test_private_release_042_docs_capture_research_only_acceptance() -> None:
    notes = ROOT / "docs" / "PRIVATE_RELEASE_NOTES_0.4.2.md"
    report = ROOT / "docs" / "CUSTOMER_RELEASE_REPORT_0.4.2_PRIVATE.md"

    assert notes.exists()
    assert report.exists()

    combined = notes.read_text(encoding="utf-8") + "\n" + report.read_text(encoding="utf-8")
    for required in (
        VERSION,
        "Tushare",
        "private bundle",
        "fut_daily",
        "fut_settle",
        "fut_holding",
        "fut_wsr",
        "no_sn_rows",
        "Feature Store v7",
        "Candidate v7",
        "No active model",
        "No customer predictions",
        "secret scan",
        "diagnostics bundle",
    ):
        assert required in combined
