from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_data_status_page_contains_online_data_source_matrix() -> None:
    content = (ROOT / "frontend" / "src" / "pages" / "DataStatusPage.tsx").read_text(encoding="utf-8")

    assert "在线数据源矩阵" in content
    assert "是否需要客户上传文件" in content
    assert "否" in content
    assert "getOnlineDataSourcesStatus" in content


def test_settings_page_contains_managed_data_proxy_entry() -> None:
    content = (ROOT / "frontend" / "src" / "pages" / "SettingsPage.tsx").read_text(encoding="utf-8")

    assert "托管数据服务" in content
    assert "客户无需 CSV/Excel" in content
    assert "SN_LOCAL_API_PROVIDER_TOKEN" in content
    assert "SN_MANAGED_DATA_PROXY_TOKEN" not in content
    assert "license token" in content


def test_terminal_client_exposes_online_data_source_api() -> None:
    content = (ROOT / "frontend" / "src" / "api" / "terminal.ts").read_text(encoding="utf-8")

    assert "getOnlineDataSourcesStatus" in content
    assert "/api/terminal/online-data-sources/status" in content
