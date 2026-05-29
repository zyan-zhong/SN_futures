from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_factor_page_displays_online_feature_readiness() -> None:
    content = (ROOT / "frontend" / "src" / "pages" / "FactorPage.tsx").read_text(encoding="utf-8")

    assert "自动在线因子准备度" in content
    assert "客户不需要上传 CSV/Excel" in content
    assert "公开在线源当前无法提供的字段，系统不会伪造数据" in content
    assert "getOnlineFeatureReadiness" in content


def test_terminal_client_exposes_online_feature_readiness_api() -> None:
    content = (ROOT / "frontend" / "src" / "api" / "terminal.ts").read_text(encoding="utf-8")

    assert "getOnlineFeatureReadiness" in content
    assert "/api/terminal/factors/online-readiness" in content


def test_frontend_does_not_require_customer_csv_excel_for_online_readiness() -> None:
    frontend = "\n".join(path.read_text(encoding="utf-8") for path in (ROOT / "frontend" / "src").rglob("*.tsx"))

    assert "客户必须提供 CSV" not in frontend
    assert "客户必须提供 Excel" not in frontend
    assert "fake prediction" not in frontend.lower()
    assert "baseline forecast" not in frontend.lower()
