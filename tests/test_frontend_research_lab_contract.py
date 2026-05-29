import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend"


def test_research_lab_frontend_contract_exists():
    page = FRONTEND / "src" / "pages" / "ResearchLabPage.tsx"
    terminal = FRONTEND / "src" / "api" / "terminal.ts"
    sidebar = FRONTEND / "src" / "components" / "layout" / "Sidebar.tsx"

    assert page.exists()
    assert "研究实验室" in page.read_text(encoding="utf-8")
    assert "候选模型不能替代 active" in page.read_text(encoding="utf-8")
    assert "高置信覆盖率" in page.read_text(encoding="utf-8")
    assert "成本后表现" in page.read_text(encoding="utf-8")
    assert "特征稳定性" in page.read_text(encoding="utf-8")
    assert "promotion gate" in page.read_text(encoding="utf-8")
    assert "runModelExperiment" in terminal.read_text(encoding="utf-8")
    assert "getThresholdOptimization" in terminal.read_text(encoding="utf-8")
    assert "research" in sidebar.read_text(encoding="utf-8")


def test_research_lab_package_has_no_customer_prediction_shortcut():
    page_text = (FRONTEND / "src" / "pages" / "ResearchLabPage.tsx").read_text(encoding="utf-8").lower()
    assert "baseline forecast" not in page_text
    assert "baseline backtest" not in page_text
    assert "fake prediction" not in page_text


def test_package_json_still_has_ui_contract_script():
    package = json.loads((FRONTEND / "package.json").read_text(encoding="utf-8"))
    assert package["scripts"]["check:ui"]
