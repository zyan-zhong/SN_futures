from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, "src")

from sn_futures.api.terminal_api import handle_terminal_api
from sn_futures.services import refresh_service


def test_predictions_endpoint_does_not_expose_baseline_wording() -> None:
    status, payload = handle_terminal_api("/api/terminal/predictions", "GET")

    assert status == 200
    text = json.dumps(payload, ensure_ascii=False).lower()
    assert "baseline forecast" not in text
    assert "baseline backtest" not in text
    assert "基线预测" not in text
    assert "基线回测" not in text


def test_backtest_endpoint_does_not_expose_baseline_backtest_wording() -> None:
    status, payload = handle_terminal_api("/api/terminal/backtest-diagnostics", "GET")

    assert status == 200
    text = json.dumps(payload, ensure_ascii=False).lower()
    assert "baseline backtest" not in text
    assert "基线回测" not in text
    assert "fake prediction" not in text


def test_refresh_predictions_with_no_active_result_writes_empty_cards(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(refresh_service, "_outputs_dir", lambda: tmp_path)
    refresh_service._write_json(tmp_path / "market_provider_status.json", {"final_status": "history_only_success"})
    refresh_service._write_json(tmp_path / "sn_market_history.json", {"history": [{"time": f"t{i}", "close": 1} for i in range(80)]})

    from sn_futures import v2_api

    monkeypatch.setattr(v2_api, "get_live_predictions", lambda _out=None: {"cards": {}})
    monkeypatch.setattr(v2_api, "get_data_watermark", lambda _out=None: {})

    result = refresh_service.refresh_predictions()
    payload = json.loads((tmp_path / "sn_unified_forecast.json").read_text(encoding="utf-8"))

    assert result["status"] == "skipped"
    assert payload["cards"] == {}
    assert "暂无可用 active 模型" in payload["message_zh"]

