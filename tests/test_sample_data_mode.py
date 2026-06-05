from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from sn_futures.api.terminal_api import handle_terminal_api


def test_sample_data_files_exist_and_are_marked() -> None:
    root = Path("sample_data")
    assert (root / "sample_market_history.json").exists()
    predictions = json.loads((root / "sample_predictions.json").read_text(encoding="utf-8"))
    news = json.loads((root / "sample_news_events.json").read_text(encoding="utf-8"))
    assert predictions["sample"] is True
    assert news["sample"] is True
    for card in predictions["predictions"]:
        assert card["signal"] == "观望"
        assert card["entry"] is None
        assert card["stop_loss"] is None
        assert card["take_profit"] is None
    assert all(item["title"].startswith("[样例]") for item in news["events"])


def test_sample_reports_are_clearly_disclaimed() -> None:
    daily = Path("sample_data/sample_reports/sample_daily_report.md").read_text(encoding="utf-8")
    event = Path("sample_data/sample_reports/sample_event_report.md").read_text(encoding="utf-8")
    assert "样例报告，不构成投资建议。" in daily
    assert "样例报告，不构成投资建议。" in event


def test_terminal_api_sample_mode_does_not_return_sample_predictions(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("SN_DATA_DIR", str(tmp_path))
    status, payload = handle_terminal_api("/api/terminal/snapshot", "GET", {}, None)
    assert status == 200
    assert payload["sample_mode"] is True
    assert "样例数据模式" in payload["sample_banner_zh"]
    assert payload["predictions"] == []
    predictions_text = json.dumps(payload["predictions"], ensure_ascii=False)
    assert '"sample": true' not in predictions_text
    assert '"sample_mode": true' not in predictions_text


def test_refresh_status_disables_sample_mode(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("SN_DATA_DIR", str(tmp_path))
    out = tmp_path / "outputs"
    out.mkdir(parents=True)
    (out / "refresh_status.json").write_text(json.dumps({"run_id": "test", "started_at": "now"}), encoding="utf-8")
    status, payload = handle_terminal_api("/api/terminal/snapshot", "GET", {}, None)
    assert status == 200
    assert payload.get("sample_mode") is not True


def test_sample_chart_news_report_endpoints(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("SN_DATA_DIR", str(tmp_path))
    for path in (
        "/api/terminal/charts/price-history",
        "/api/terminal/charts/forecast-path",
        "/api/terminal/events/news",
        "/api/terminal/reports/full",
    ):
        status, payload = handle_terminal_api(path, "GET", {"type": ["daily"]}, None)
        assert status == 200
        assert payload.get("sample_mode") is True
        assert "样例" in json.dumps(payload, ensure_ascii=False)
