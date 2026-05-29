from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend"


def _frontend_text() -> str:
    parts: list[str] = []
    for path in FRONTEND.rglob("*"):
        if path.is_file() and path.suffix in {".ts", ".tsx", ".json", ".html", ".css"}:
            parts.append(path.read_text(encoding="utf-8"))
    return "\n".join(parts)


def test_frontend_project_files_exist() -> None:
    assert (FRONTEND / "package.json").exists()
    assert (FRONTEND / "src" / "App.tsx").exists()
    assert (FRONTEND / "src" / "api" / "terminal.ts").exists()


def test_frontend_does_not_store_api_keys_or_trade_promises() -> None:
    text = _frontend_text()
    assert "SN_ALPHA_VANTAGE_KEY=" not in text
    assert "SN_NEWSAPI_KEY=" not in text
    assert "保证盈利" not in text
    assert "建议买入" not in text
    assert "建议卖出" not in text


def test_frontend_uses_terminal_api_only() -> None:
    terminal_client = (FRONTEND / "src" / "api" / "terminal.ts").read_text(encoding="utf-8")
    assert "/api/terminal/" in terminal_client
    assert "/api/predictions/live" not in _frontend_text()


def test_frontend_contains_compliance_and_trade_point_guard_text() -> None:
    text = _frontend_text()
    assert "仅供沪锡期货量化投研参考" in text
    assert "不构成投资建议" in text
    assert "暂无交易点位" in text


def test_collapsible_debug_is_collapsed_by_default() -> None:
    source = (FRONTEND / "src" / "components" / "common" / "CollapsibleDebug.tsx").read_text(encoding="utf-8")
    assert "<details" in source
    assert " open" not in source
    assert "技术明细 / 开发调试信息" in source
