from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend"
SRC = FRONTEND / "src"


def _frontend_source_text() -> str:
    parts: list[str] = []
    for path in SRC.rglob("*"):
        if path.is_file() and path.suffix in {".ts", ".tsx", ".css"}:
            parts.append(path.read_text(encoding="utf-8"))
    parts.append((FRONTEND / "index.html").read_text(encoding="utf-8"))
    return "\n".join(parts)


def test_ui_contract_script_and_package_script_exist() -> None:
    script = FRONTEND / "scripts" / "check-ui-contract.mjs"
    package = json.loads((FRONTEND / "package.json").read_text(encoding="utf-8"))
    assert script.exists()
    assert package["scripts"]["check:ui"].endswith("scripts/check-ui-contract.mjs")
    script_text = script.read_text(encoding="utf-8")
    assert "UI 合同检查通过" in script_text
    assert "allowedLocalStorageKeys" in script_text


def test_frontend_source_does_not_include_forbidden_customer_terms() -> None:
    text = _frontend_source_text()
    for forbidden in [
        "保证盈利",
        "稳赚",
        "建议买入",
        "建议卖出",
        "必涨",
        "必跌",
        "sure profit",
        "guaranteed profit",
        "buy now",
        "sell now",
        "fake probability",
        "backend contract complete",
    ]:
        assert forbidden.lower() not in text.lower()


def test_frontend_source_has_required_customer_contract_words() -> None:
    text = _frontend_source_text()
    for required in [
        "不构成投资建议",
        "不承诺收益",
        "不接实盘交易",
        "暂无交易点位",
        "已降级为研究观察",
        "技术明细 / 开发调试信息",
    ]:
        assert required in text


def test_frontend_does_not_save_sensitive_keys_to_localstorage() -> None:
    text = _frontend_source_text()
    assert "SN_ALPHA_VANTAGE_KEY=" not in text
    assert "SN_NEWSAPI_KEY=" not in text
    assert "Authorization: Bearer" not in text
    assert "apiKey:" not in text
    assert "useLocalSetting(\"refreshInterval\"" in text
    assert "useLocalSetting(\"showDebug\"" in text
    settings_page = (SRC / "pages" / "SettingsPage.tsx").read_text(encoding="utf-8")
    assert "localStorage" not in settings_page
