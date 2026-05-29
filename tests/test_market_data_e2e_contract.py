from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, "src")

from sn_futures.api.terminal_api import handle_terminal_api
from sn_futures.services import refresh_service


def _history(count: int) -> list[dict[str, object]]:
    return [{"time": f"2026-05-{(idx % 28) + 1:02d}", "close": 240000 + idx} for idx in range(count)]


def test_refresh_market_endpoint_returns_final_status_and_history_contract(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(refresh_service, "_outputs_dir", lambda: tmp_path)

    def fake_market(force: bool = False) -> dict[str, object]:
        refresh_service._write_json(
            tmp_path / "sn_market_history.json",
            {"points": _history(80), "history": _history(80), "row_count": 80, "message_zh": "历史行情可用。"},
        )
        refresh_service._write_json(
            tmp_path / "market_provider_status.json",
            {
                "final_status": "history_only_success",
                "realtime_attempts": [{"provider_name": "sina_realtime", "success": False, "symbol_used": "nf_SN0"}],
                "history_attempts": [{"provider_name": "akshare_futures_zh_daily_sina", "success": True, "rows": 80, "symbol_used": "SN0"}],
                "shfe_attempts": [{"provider_name": "shfe_public", "success": False, "status_code": "auxiliary_unavailable"}],
                "providers": [],
                "blocking_reasons": ["实时行情不可用。"],
                "next_actions_zh": ["查看 provider 诊断。"],
            },
        )
        return {
            "status": "success",
            "final_status": "history_only_success",
            "message_zh": "历史行情可用，实时价暂缺。",
            "output_files": [str(tmp_path / "sn_market_history.json")],
            "history_rows": 80,
            "provider_chain_status": [],
        }

    monkeypatch.setattr(refresh_service, "refresh_market_data", fake_market)

    status, payload = handle_terminal_api("/api/terminal/refresh/market", "POST", body=json.dumps({"force": True}))

    assert status == 200
    assert payload["steps"][0]["final_status"] == "history_only_success"
    assert payload["steps"][0]["history_rows"] == 80


def test_price_history_endpoint_reports_points_or_chinese_reason(monkeypatch, tmp_path: Path) -> None:
    from sn_futures.services import terminal_service

    monkeypatch.setattr(terminal_service, "_runtime_output_dir", lambda: tmp_path)
    monkeypatch.setattr(terminal_service, "_p31_read_json", lambda path: json.loads(path.read_text(encoding="utf-8")) if Path(path).exists() else None)
    (tmp_path / "sn_market_history.json").write_text(
        json.dumps({"points": _history(3), "history": _history(3), "row_count": 3}, ensure_ascii=False),
        encoding="utf-8",
    )

    status, payload = handle_terminal_api("/api/terminal/charts/price-history", "GET")

    assert status == 200
    assert "points" in payload
    assert payload["points"] or "message_zh" in payload


def test_provider_status_detail_contains_split_attempts(monkeypatch, tmp_path: Path) -> None:
    from sn_futures.services import provider_observability_service as obs

    outputs = tmp_path / "outputs"
    outputs.mkdir(parents=True)
    (outputs / "market_provider_status.json").write_text(
        json.dumps(
            {
                "final_status": "quote_only_partial",
                "realtime_attempts": [{"provider_name": "sina_realtime", "symbol_used": "nf_SN0"}],
                "history_attempts": [{"provider_name": "akshare_futures_main_sina", "symbol_used": "SN0"}],
                "shfe_attempts": [{"provider_name": "shfe_public"}],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(obs, "get_user_data_root", lambda: tmp_path)

    status, payload = handle_terminal_api("/api/terminal/providers/status-detail", "GET")

    assert status == 200
    market = payload["market_provider_status"]
    assert market["final_status"] == "quote_only_partial"
    assert market["realtime_attempts"]
    assert market["history_attempts"]
    assert market["shfe_attempts"]
