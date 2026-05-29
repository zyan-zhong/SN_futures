from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, "src")

from sn_futures.services import refresh_service as svc


def test_history_under_sixty_does_not_call_prediction_service(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(svc, "_outputs_dir", lambda: tmp_path)
    svc._write_json(tmp_path / "market_provider_status.json", {"final_status": "quote_only_partial"})
    svc._write_json(tmp_path / "sn_market_history.json", {"history": [{"time": f"t{i}", "close": 1} for i in range(20)]})

    def fail_if_called(_out=None):  # pragma: no cover - must not be called
        raise AssertionError("prediction service should not be called when real history is insufficient")

    from sn_futures import v2_api

    monkeypatch.setattr(v2_api, "get_live_predictions", fail_if_called)
    monkeypatch.setattr(v2_api, "get_data_watermark", lambda _out=None: {})

    result = svc.refresh_predictions()

    assert result["status"] == "skipped"
    assert result["history_rows"] == 20
    assert "真实历史行情不足" in result["message_zh"]


def test_cache_only_does_not_generate_new_prediction(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(svc, "_outputs_dir", lambda: tmp_path)
    svc._write_json(tmp_path / "market_provider_status.json", {"final_status": "cache_only"})
    svc._write_json(tmp_path / "sn_market_history.json", {"history": [{"time": f"t{i}", "close": 1} for i in range(100)]})

    from sn_futures import v2_api

    monkeypatch.setattr(v2_api, "get_live_predictions", lambda _out=None: {"cards": {"h": {"sample": False}}})
    monkeypatch.setattr(v2_api, "get_data_watermark", lambda _out=None: {})

    result = svc.refresh_predictions()

    assert result["status"] == "skipped"
    assert result["market_final_status"] == "cache_only"
    assert "缓存行情" in result["message_zh"]


def test_refresh_service_does_not_call_baseline_forecast_or_backtest() -> None:
    text = Path("src/sn_futures/services/refresh_service.py").read_text(encoding="utf-8")

    assert "baseline_forecast_service" not in text
    assert "baseline_backtest_service" not in text

