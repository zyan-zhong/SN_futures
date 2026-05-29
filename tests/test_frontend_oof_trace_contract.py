from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend" / "src"


def test_frontend_exposes_oof_trace_apis_and_panel():
    terminal = (FRONTEND / "api" / "terminal.ts").read_text(encoding="utf-8")
    panel = (FRONTEND / "components" / "model" / "OOFTracePanel.tsx").read_text(encoding="utf-8")
    governance = (FRONTEND / "pages" / "ModelGovernancePage.tsx").read_text(encoding="utf-8")

    assert "/api/terminal/models/oof-trace-summary" in terminal
    assert "/api/terminal/models/oof-trace-sample" in terminal
    assert "/api/terminal/research/oof-trace-summary" in terminal
    assert "OOF 样本外验证轨迹" in panel
    assert "不是客户预测" in panel
    assert "OOFTracePanel" in governance


def test_oof_trace_frontend_does_not_present_trace_as_prediction():
    panel = (FRONTEND / "components" / "model" / "OOFTracePanel.tsx").read_text(encoding="utf-8").lower()
    forbidden = ["客户预测结果", "真实预测结论", "建议买入", "建议卖出", "保证盈利", "fake prediction", "baseline forecast"]
    for token in forbidden:
        assert token.lower() not in panel
