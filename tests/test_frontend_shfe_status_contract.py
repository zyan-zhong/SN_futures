from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_data_source_panel_explains_shfe_split_status() -> None:
    content = (ROOT / "frontend" / "src" / "components" / "data" / "DataSourceStatusPanel.tsx").read_text(encoding="utf-8")

    assert "blocked_by_waf" in content
    assert "SHFE 官网直连被人机验证阻断" in content
    assert "库存、仓单、现货基差、交易所日线和会员持仓会拆分展示" in content
    assert "SHFE public 不可用" in content


def test_factor_page_contains_shfe_factor_coverage_section() -> None:
    content = (ROOT / "frontend" / "src" / "pages" / "FactorPage.tsx").read_text(encoding="utf-8")

    assert "SHFE / 库存 / 仓单 / 基差覆盖率" in content
    assert "不伪造库存、仓单、基差或现货价格" in content
    assert "不会生成预测或 active 模型" in content
