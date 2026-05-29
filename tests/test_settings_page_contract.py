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


def test_settings_page_has_secure_key_experience() -> None:
    source = (FRONTEND / "src" / "pages" / "SettingsPage.tsx").read_text(encoding="utf-8")
    assert "Alpha Vantage 密钥" in source
    assert "NewsAPI 密钥" in source
    assert "显示" in source
    assert "隐藏" in source
    assert "密钥仅保存在本机用户目录" in source
    assert "清除本机密钥" in source
    assert "测试连接" in source
    assert "日志目录" in source
    assert "配置目录" not in source or "config_path" in source


def test_settings_page_does_not_persist_keys_to_local_storage() -> None:
    source = (FRONTEND / "src" / "pages" / "SettingsPage.tsx").read_text(encoding="utf-8")
    assert "SN_ALPHA_VANTAGE_KEY" in source
    assert "SN_NEWSAPI_KEY" in source
    assert "useLocalSetting(\"SN_ALPHA_VANTAGE_KEY" not in source
    assert "useLocalSetting(\"SN_NEWSAPI_KEY" not in source
    assert "localStorage" not in source
    assert "sn-terminal-api-base" not in source


def test_frontend_keeps_trade_and_secret_guardrails() -> None:
    text = _frontend_text()
    assert "保证盈利" not in text
    assert "建议买入" not in text
    assert "建议卖出" not in text
    assert "稳赚" not in text
    assert "SN_ALPHA_VANTAGE_KEY=" not in text
    assert "SN_NEWSAPI_KEY=" not in text

