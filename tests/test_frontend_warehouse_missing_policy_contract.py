from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_factor_and_data_status_pages_show_warehouse_missing_policy() -> None:
    factor_page = (ROOT / "frontend" / "src" / "pages" / "FactorPage.tsx").read_text(encoding="utf-8")
    data_status_page = (ROOT / "frontend" / "src" / "pages" / "DataStatusPage.tsx").read_text(encoding="utf-8")
    types = (ROOT / "frontend" / "src" / "api" / "types.ts").read_text(encoding="utf-8")

    for expected in (
        "warehouse_missing_policy",
        "inventory_missing_flag",
        "warehouse_data_quality_score",
        "当前无真实沪锡仓单数据，系统未伪造字段；模型将使用缺失风险标记。",
    ):
        assert expected in factor_page
    for expected in (
        "tushare_warehouse",
        "no_sn_rows",
        "当前无真实沪锡仓单数据，系统未伪造字段；模型将使用缺失风险标记。",
    ):
        assert expected in data_status_page
    for expected in ("warehouse_missing_policy", "warehouse_policy_features"):
        assert expected in types
