from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_color_tokens_separate_market_and_system_colors() -> None:
    text = (ROOT / "frontend" / "src" / "utils" / "colorTokens.ts").read_text(encoding="utf-8")
    assert "price_up" in text and "#f15f5f" in text
    assert "price_down" in text and "#49c6a7" in text
    assert "system_ok" in text and "#66d9ef" in text


def test_css_tone_good_does_not_use_market_up_red() -> None:
    css = (ROOT / "frontend" / "src" / "styles" / "globals.css").read_text(encoding="utf-8")
    tone_good_block = css.split(".tone-good", 1)[1].split("}", 1)[0]
    assert "241, 95, 95" not in tone_good_block
    assert "102, 217, 239" in tone_good_block


def test_data_source_status_panel_has_new_statuses() -> None:
    text = (ROOT / "frontend" / "src" / "components" / "data" / "DataSourceStatusPanel.tsx").read_text(encoding="utf-8")
    for expected in ["正常", "使用缓存", "未配置", "已过期", "请求失败", "非交易时段等待更新"]:
        assert expected in text

