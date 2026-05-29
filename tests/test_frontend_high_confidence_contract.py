from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend" / "src"


def test_frontend_exposes_high_confidence_oof_panel_and_apis():
    terminal = (FRONTEND / "api" / "terminal.ts").read_text(encoding="utf-8")
    panel = (FRONTEND / "components" / "model" / "HighConfidenceValidationPanel.tsx").read_text(encoding="utf-8")
    governance = (FRONTEND / "pages" / "ModelGovernancePage.tsx").read_text(encoding="utf-8")

    assert "/api/terminal/models/oof-integrity-report" in terminal
    assert "/api/terminal/models/high-confidence-report" in terminal
    assert "高置信子集验证" in panel
    assert "高置信 OOF 命中率不是客户预测" in panel
    assert "不代表未来收益" in panel
    assert "不构成投资建议" in panel
    assert "HighConfidenceValidationPanel" in governance


def test_high_confidence_panel_does_not_present_as_customer_prediction():
    panel = (FRONTEND / "components" / "model" / "HighConfidenceValidationPanel.tsx").read_text(encoding="utf-8").lower()
    forbidden = [
        "客户预测结果",
        "真实预测结论",
        "建议买入",
        "建议卖出",
        "保证盈利",
        "fake prediction",
        "baseline forecast",
    ]
    for token in forbidden:
        assert token.lower() not in panel
