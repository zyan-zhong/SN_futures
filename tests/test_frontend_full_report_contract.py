from __future__ import annotations

from pathlib import Path


def test_settings_page_exposes_txt_zip_and_copy_actions() -> None:
    page = Path("frontend/src/pages/SettingsPage.tsx").read_text(encoding="utf-8")
    api = Path("frontend/src/api/terminal.ts").read_text(encoding="utf-8")
    types = Path("frontend/src/api/types.ts").read_text(encoding="utf-8")

    assert "生成完整系统 TXT 报告" in page
    assert "下载 TXT" in page
    assert "下载诊断包" in page
    assert "复制摘要" in page
    assert "diagnostics_bundle_path" in page
    assert "getLatestFullSystemTxtReport" in api
    assert "generateFullSystemTxtReport" in api
    assert "FullSystemReportPayload" in types
    assert "secrets.json" not in page
    assert "private_bundle_seed" not in page
