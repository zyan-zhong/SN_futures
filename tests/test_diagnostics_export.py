from __future__ import annotations

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from sn_futures.api.terminal_api import TERMINAL_API_DOCS, handle_terminal_api


def test_diagnostics_export_does_not_contain_full_key(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("SN_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("SN_NEWSAPI_KEY", "TEST_NEWS_SECRET_1234567890")
    monkeypatch.setenv("SN_ALPHA_VANTAGE_KEY", "TEST_ALPHA_SECRET_1234567890")

    status, payload = handle_terminal_api("/api/terminal/diagnostics/export", "POST", body={})
    assert status == 200
    text = str(payload)
    assert "TEST_NEWS_SECRET_1234567890" not in text
    assert "TEST_ALPHA_SECRET_1234567890" not in text
    assert payload["success"] is True
    assert Path(payload["path"]).exists()


def test_terminal_docs_include_observability_api() -> None:
    paths = {item["path"] for item in TERMINAL_API_DOCS["endpoints"]}
    assert "/api/terminal/refresh/last-error" in paths
    assert "/api/terminal/providers/status-detail" in paths
    assert "/api/terminal/providers/test" in paths
    assert "/api/terminal/diagnostics/export" in paths


def test_frontend_has_copy_diagnostics_action() -> None:
    page = (Path(__file__).resolve().parents[1] / "frontend" / "src" / "pages" / "DataStatusPage.tsx").read_text(encoding="utf-8")
    assert "复制诊断信息" in page
    assert "查看最近错误" in page
    assert "测试数据源" in page
