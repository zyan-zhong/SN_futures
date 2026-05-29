from __future__ import annotations

from pathlib import Path
from urllib.request import urlopen

from sn_futures.api.json_utils import safe_json_dumps
from sn_futures.api.terminal_api import handle_terminal_api

from test_terminal_static_hosting import running_server


ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend"
UI_WEB = ROOT / "ui_web"


def _read_user_facing_frontend() -> str:
    paths = list(FRONTEND.rglob("*.tsx")) + list(FRONTEND.rglob("*.ts")) + list(FRONTEND.rglob("*.html")) + list(FRONTEND.rglob("*.css"))
    paths += list(UI_WEB.rglob("*.html")) + list(UI_WEB.rglob("*.js")) + list(UI_WEB.rglob("*.css"))
    return "\n".join(path.read_text(encoding="utf-8", errors="ignore") for path in paths if path.is_file())


def test_all_terminal_get_endpoints_are_available_and_json_safe() -> None:
    endpoints = [
        "/api/terminal/docs",
        "/api/terminal/summary",
        "/api/terminal/snapshot",
        "/api/terminal/predictions",
        "/api/terminal/model-health",
        "/api/terminal/learning-status",
        "/api/terminal/backtest-diagnostics",
        "/api/terminal/reports",
        "/api/terminal/data-status",
        "/api/terminal/system-health",
    ]
    for endpoint in endpoints:
        status, payload = handle_terminal_api(endpoint, "GET", {}, None)
        assert status == 200, endpoint
        dumped = safe_json_dumps(payload)
        assert "NaN" not in dumped
        assert "Infinity" not in dumped
        assert "SN_ALPHA_VANTAGE_KEY=" not in dumped
        assert "SN_NEWSAPI_KEY=" not in dumped


def test_root_route_remains_legacy_default() -> None:
    with running_server() as base:
        with urlopen(f"{base}/", timeout=10) as response:
            root_body = response.read().decode("utf-8", errors="ignore")
        with urlopen(f"{base}/legacy", timeout=10) as response:
            legacy_body = response.read().decode("utf-8", errors="ignore")
    assert "<html" in root_body.lower()
    assert "<html" in legacy_body.lower()


def test_user_facing_ui_has_no_forbidden_promise_or_debug_copy() -> None:
    text = _read_user_facing_frontend().lower()
    forbidden = [
        "backend contract complete",
        "fake probability",
        "debug raw json",
        "guaranteed profit",
        "buy now",
        "sell now",
        "建议买入",
        "建议卖出",
        "保证盈利",
        "稳赚",
    ]
    for item in forbidden:
        assert item.lower() not in text


def test_frontend_business_pages_are_present() -> None:
    required = [
        "DashboardPage.tsx",
        "PredictionPage.tsx",
        "FactorPage.tsx",
        "EventPage.tsx",
        "BacktestPage.tsx",
        "ModelGovernancePage.tsx",
        "PositionPage.tsx",
        "ReportsPage.tsx",
        "DataStatusPage.tsx",
        "SettingsPage.tsx",
    ]
    for filename in required:
        assert (FRONTEND / "src" / "pages" / filename).exists()
