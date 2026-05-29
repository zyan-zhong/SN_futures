from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, "src")

from sn_futures.services import market_data_service as svc


def _attempt(success: bool = False) -> dict[str, object]:
    return {
        "provider_name": "mock",
        "chain": "mock",
        "attempted": True,
        "success": success,
        "from_cache": False,
        "stale": False,
        "started_at": "2026-05-21T10:00:00",
        "finished_at": "2026-05-21T10:00:01",
        "duration_seconds": 1,
        "error_type": "" if success else "mock",
        "error_message_zh": "" if success else "mock failed",
        "rows": 1 if success else 0,
        "latest_price": 250000 if success else None,
        "latest_time": "2026-05-21T10:00:00" if success else "",
        "symbol_used": "SN0",
    }


def _history(count: int = 80) -> list[dict[str, object]]:
    return [
        {
            "time": f"2026-01-{(idx % 28) + 1:02d}",
            "open": 240000 + idx,
            "high": 240100 + idx,
            "low": 239900 + idx,
            "close": 240000 + idx,
            "volume": 1000 + idx,
            "open_interest": 2000 + idx,
        }
        for idx in range(count)
    ]


def test_normalize_sn_contract_symbol() -> None:
    assert svc.normalize_sn_contract_symbol("SN") == "nf_SN0"
    assert svc.normalize_sn_contract_symbol("sn0") == "nf_SN0"
    assert svc.normalize_sn_contract_symbol("SHFE.sn2406") == "nf_SN2406"
    assert svc.normalize_sn_contract_symbol("nf_SN0") == "nf_SN0"


def test_refresh_runs_realtime_and_history_even_when_realtime_succeeds(monkeypatch, tmp_path: Path) -> None:
    calls: list[str] = []

    def realtime() -> dict[str, object]:
        calls.append("realtime")
        return {
            "success": True,
            "quote": {"latest_price": 250000, "quote_time": "2026-05-21T10:00:00", "active_contract": "SN0"},
            "attempts": [_attempt(True)],
            "message_zh": "ok",
        }

    def history() -> dict[str, object]:
        calls.append("history")
        return {"success": True, "history": _history(80), "attempts": [_attempt(True)], "source": "mock_history", "message_zh": "ok"}

    monkeypatch.setattr(svc, "_outputs_dir", lambda: tmp_path)
    monkeypatch.setattr(svc, "refresh_realtime_quote", realtime)
    monkeypatch.setattr(svc, "refresh_market_history", history)
    monkeypatch.setattr(svc, "refresh_shfe_public_aux", lambda: {"success": False, "attempts": [_attempt(False)], "message_zh": "aux"})

    result = svc.refresh_sn_market_data()

    assert calls == ["realtime", "history"]
    assert result["success"] is True
    assert result["final_status"] == "full_success"
    assert (tmp_path / "sn_market_history.json").exists()


def test_all_providers_fail_with_last_good_cache_returns_cache(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(svc, "_outputs_dir", lambda: tmp_path)
    svc._write_json(
        tmp_path / "last_good_realtime_quote.json",
        {"latest_price": 250000, "quote_time": "2026-05-21T10:00:00", "active_contract": "SN0", "generated_at": "2026-05-21T10:00:00"},
    )
    svc._write_json(
        tmp_path / "last_good_market_history.json",
        {"history": _history(80), "generated_at": "2026-05-21T10:00:00", "row_count": 80},
    )
    monkeypatch.setattr(svc, "refresh_realtime_quote", lambda: {"success": False, "quote": None, "attempts": [_attempt(False)], "message_zh": "fail"})
    monkeypatch.setattr(svc, "refresh_market_history", lambda: {"success": False, "history": [], "attempts": [_attempt(False)], "message_zh": "fail"})
    monkeypatch.setattr(svc, "refresh_shfe_public_aux", lambda: {"success": False, "attempts": [_attempt(False)], "message_zh": "aux"})

    result = svc.refresh_sn_market_data()

    assert result["success"] is True
    assert result["final_status"] == "cache_only"
    assert result["from_cache"] is True


def test_all_providers_fail_without_cache_returns_failed(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(svc, "_outputs_dir", lambda: tmp_path)
    monkeypatch.setattr(svc, "refresh_realtime_quote", lambda: {"success": False, "quote": None, "attempts": [_attempt(False)], "message_zh": "fail"})
    monkeypatch.setattr(svc, "refresh_market_history", lambda: {"success": False, "history": [], "attempts": [_attempt(False)], "message_zh": "fail"})
    monkeypatch.setattr(svc, "refresh_shfe_public_aux", lambda: {"success": False, "attempts": [_attempt(False)], "message_zh": "aux"})

    result = svc.refresh_sn_market_data()

    assert result["success"] is False
    assert result["final_status"] == "failed"
    assert "无可用" in result["message_zh"]

