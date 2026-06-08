from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_settings_page_contains_tushare_token_entry() -> None:
    content = (ROOT / "frontend" / "src" / "pages" / "SettingsPage.tsx").read_text(encoding="utf-8")

    assert "Tushare" in content
    assert "SN_TUSHARE_TOKEN" in content
    assert "期货基础数据" in content


def test_data_status_page_exposes_tushare_status() -> None:
    content = (ROOT / "frontend" / "src" / "pages" / "DataStatusPage.tsx").read_text(encoding="utf-8")

    assert "Tushare" in content
    assert "token_missing" in content
    assert "no_sn_rows" in content


def test_factor_page_mentions_tushare_coverage_fields() -> None:
    content = (ROOT / "frontend" / "src" / "pages" / "FactorPage.tsx").read_text(encoding="utf-8")

    assert "Tushare" in content
    assert "open_interest" in content
    assert "warehouse_receipt" in content
    assert "settlement" in content


def test_terminal_client_can_save_tushare_token() -> None:
    terminal = (ROOT / "frontend" / "src" / "api" / "terminal.ts").read_text(encoding="utf-8")
    settings = (ROOT / "frontend" / "src" / "api" / "settings.ts").read_text(encoding="utf-8")

    assert 'from "./settings"' in terminal
    assert "saveSettingsSecrets" in terminal
    assert "SN_TUSHARE_TOKEN" in settings
