from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend" / "src"


def test_frontend_exposes_institutional_validation_apis():
    terminal = (FRONTEND / "api" / "terminal.ts").read_text(encoding="utf-8")
    types = (FRONTEND / "api" / "types.ts").read_text(encoding="utf-8")

    assert "/api/terminal/validation/run-institutional-check" in terminal
    assert "/api/terminal/validation/report" in terminal
    assert "/api/terminal/validation/stress-tests" in terminal
    assert "InstitutionalValidationReport" in types
    assert "InstitutionalStressTests" in types


def test_backtest_page_shows_institutional_validation_without_active_shortcut():
    page = (FRONTEND / "pages" / "BacktestPage.tsx").read_text(encoding="utf-8")
    panel = (FRONTEND / "components" / "backtest" / "InstitutionalValidationPanel.tsx").read_text(encoding="utf-8")

    assert "机构级验证" in page
    assert "InstitutionalValidationPanel" in page
    assert "成本压力" in panel
    assert "Regime 压力" in panel
    assert "Deflated Sharpe Ratio" in panel
    assert "PBO" in panel
    assert "Reality Check" in panel
    assert "不可上线原因" in panel
    assert "不会发布 active" in panel
    assert "发布 active" not in panel.replace("不会发布 active", "")


def test_institutional_validation_ui_has_no_forbidden_customer_claims():
    text = (FRONTEND / "components" / "backtest" / "InstitutionalValidationPanel.tsx").read_text(encoding="utf-8").lower()
    forbidden = ["保证盈利", "稳赚", "建议买入", "建议卖出", "fake prediction", "baseline forecast", "baseline backtest"]
    for token in forbidden:
        assert token.lower() not in text
