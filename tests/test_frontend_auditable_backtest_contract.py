from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _api_client_surface() -> str:
    api_dir = ROOT / "frontend" / "src" / "api"
    return "\n".join(
        (api_dir / name).read_text(encoding="utf-8")
        for name in ("terminal.ts", "backtest.ts")
    )


def _type_surface() -> str:
    api_dir = ROOT / "frontend" / "src" / "api"
    return "\n".join(
        path.read_text(encoding="utf-8")
        for path in (
            api_dir / "types.ts",
            api_dir / "types" / "backtest.ts",
        )
    )


def test_frontend_exposes_auditable_backtest_readonly_client() -> None:
    api = _api_client_surface()
    types = _type_surface()

    assert "getAuditableResearchBacktest" in api
    assert "/api/terminal/backtest/auditable" in api
    assert "AuditableBacktestPayload" in types
    assert "BacktestManifest" in types
    assert "error_code?: string" in types


def test_backtest_page_exposes_auditable_manifest_metrics_equity_and_trades() -> None:
    page = (ROOT / "frontend" / "src" / "pages" / "BacktestPage.tsx").read_text(encoding="utf-8")

    assert "getAuditableResearchBacktest" in page
    assert "BacktestManifest" in page
    assert "auditableBacktest" in page
    assert "equity" in page
    assert "trades" in page
    assert "blocking_reasons" in page
    assert "error_code" in page
    assert "chart_payload_input_used" in page
    assert "display_payload_input_used" in page
    assert "fake equity" not in page.lower()
