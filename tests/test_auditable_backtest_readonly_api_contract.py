from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from sn_futures.api.terminal_api import handle_terminal_api  # noqa: E402
from sn_futures.services.research_backtest_engine_service import run_auditable_research_backtest  # noqa: E402


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _write_auditable_inputs(input_dir: Path) -> None:
    input_dir.mkdir(parents=True, exist_ok=True)
    (input_dir / "immutable_historical_bars.csv").write_text(
        "\n".join(
            [
                "trade_date,open,high,low,close,volume,open_interest,main_contract",
                "2026-01-01,100,102,99,101,1000,5000,sn2601",
                "2026-01-02,101,106,100,105,1100,5100,sn2601",
                "2026-01-03,105,108,103,104,900,5050,sn2601",
                "2026-01-04,104,109,102,108,1200,5200,sn2601",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    (input_dir / "signals.csv").write_text(
        "\n".join(
            [
                "trade_date,signal,trade_edge,data_quality_score",
                "2026-01-01,1,1,1",
                "2026-01-02,-1,1,1",
                "2026-01-03,1,1,1",
                "2026-01-04,0,1,1",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    _write_json(
        input_dir / "historical_bars_manifest.json",
        {
            "schema_version": 1,
            "provider": "contract_test_provider",
            "data_kind": "daily_bar",
            "sample_data_used": False,
            "baseline_used": False,
            "history_immutable": True,
            "allowed_for_backtest": True,
        },
    )
    _write_json(
        input_dir / "signal_manifest.json",
        {
            "schema_version": 1,
            "source": "contract_test_signal",
            "sample_data_used": False,
            "baseline_used": False,
            "lookahead_check_pass": True,
        },
    )
    _write_json(
        input_dir / "contract_metadata.json",
        {
            "schema_version": 1,
            "exchange": "SHFE",
            "symbol": "SN",
            "active_contract": "sn2601",
        },
    )
    _write_json(
        input_dir / "point_in_time_feature_manifest.json",
        {
            "version": "feature_store_contract",
            "leakage_check_pass": True,
            "sample_data_used": False,
            "baseline_used": False,
            "display_overlay_used": False,
            "live_quote_used_for_training": False,
        },
    )


def test_auditable_backtest_readonly_api_blocks_without_inputs(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("SN_DATA_DIR", str(tmp_path / "user_data"))

    status, payload = handle_terminal_api("/api/terminal/backtest/auditable", "GET", {}, None)

    assert status == 200
    assert payload["status"] == "blocked"
    assert payload["read_only"] is True
    assert payload["equity"] == []
    assert payload["trades"] == []
    assert payload["metrics"] == {}
    assert "historical_bars_missing" in payload["blocking_reasons"]
    assert "signal_manifest_missing" in payload["blocking_reasons"]
    assert payload["chart_payload_input_used"] is False
    assert payload["display_payload_input_used"] is False
    assert payload["sample_data_used"] is False
    assert payload["baseline_used"] is False
    assert payload["customer_prediction_generated"] is False
    assert not (tmp_path / "user_data" / "outputs" / "backtests").exists()


def test_auditable_backtest_readonly_api_blocks_without_immutable_bars(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("SN_DATA_DIR", str(tmp_path / "user_data"))
    input_dir = tmp_path / "user_data" / "outputs" / "backtest_inputs" / "sn_main"
    _write_auditable_inputs(input_dir)
    (input_dir / "immutable_historical_bars.csv").unlink()

    status, payload = handle_terminal_api("/api/terminal/backtest/auditable", "GET", {}, None)

    assert status == 200
    assert payload["status"] == "blocked"
    assert payload["equity"] == []
    assert payload["trades"] == []
    assert "historical_bars_missing" in payload["blocking_reasons"]
    assert payload["backtest_invoked"] is False
    assert payload["customer_prediction_generated"] is False


def test_auditable_backtest_readonly_api_blocks_without_signals(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("SN_DATA_DIR", str(tmp_path / "user_data"))
    input_dir = tmp_path / "user_data" / "outputs" / "backtest_inputs" / "sn_main"
    _write_auditable_inputs(input_dir)
    (input_dir / "signals.csv").unlink()

    status, payload = handle_terminal_api("/api/terminal/backtest/auditable", "GET", {}, None)

    assert status == 200
    assert payload["status"] == "blocked"
    assert payload["equity"] == []
    assert payload["trades"] == []
    assert "signals_missing" in payload["blocking_reasons"]
    assert payload["metrics"] == {}


def test_auditable_backtest_readonly_api_blocks_without_required_manifest(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("SN_DATA_DIR", str(tmp_path / "user_data"))
    input_dir = tmp_path / "user_data" / "outputs" / "backtest_inputs" / "sn_main"
    _write_auditable_inputs(input_dir)
    (input_dir / "historical_bars_manifest.json").unlink()

    status, payload = handle_terminal_api("/api/terminal/backtest/auditable", "GET", {}, None)

    assert status == 200
    assert payload["status"] == "blocked"
    assert payload["equity"] == []
    assert payload["trades"] == []
    assert "data_manifest_missing" in payload["blocking_reasons"]
    assert payload["manifest"] == {}


def test_auditable_backtest_readonly_api_blocks_sample_data(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("SN_DATA_DIR", str(tmp_path / "user_data"))
    input_dir = tmp_path / "user_data" / "outputs" / "backtest_inputs" / "sn_main"
    _write_auditable_inputs(input_dir)
    _write_json(
        input_dir / "historical_bars_manifest.json",
        {
            "schema_version": 1,
            "provider": "contract_test_provider",
            "data_kind": "daily_bar",
            "sample_data_used": True,
            "baseline_used": False,
            "history_immutable": True,
            "allowed_for_backtest": True,
        },
    )

    status, payload = handle_terminal_api("/api/terminal/backtest/auditable", "GET", {}, None)

    assert status == 200
    assert payload["status"] == "blocked"
    assert payload["sample_data_used"] is True
    assert payload["equity"] == []
    assert payload["trades"] == []
    assert "sample_data_used" in payload["blocking_reasons"]


def test_auditable_backtest_readonly_api_rejects_display_payload_input(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("SN_DATA_DIR", str(tmp_path / "user_data"))

    status, payload = handle_terminal_api(
        "/api/terminal/backtest/auditable",
        "GET",
        {"input_source": ["display_payload"]},
        None,
    )

    assert status == 400
    assert payload["status"] == "rejected"
    assert payload["error_code"] == "display_payload_not_allowed"
    assert payload["equity"] == []
    assert payload["trades"] == []
    assert payload["chart_payload_input_used"] is False
    assert payload["display_payload_input_used"] is False


def test_auditable_backtest_readonly_api_ignores_chart_payload(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("SN_DATA_DIR", str(tmp_path / "user_data"))
    chart_dir = tmp_path / "user_data" / "outputs" / "research_backtests" / "v5"
    chart_dir.mkdir(parents=True)
    (chart_dir / "equity_curve_1d.csv").write_text("ts,value\n2026-01-01,1.25\n", encoding="utf-8")

    status, payload = handle_terminal_api("/api/terminal/backtest/auditable", "GET", {}, None)

    assert status == 200
    assert payload["status"] == "blocked"
    assert payload["equity"] == []
    assert payload["trades"] == []
    assert payload["chart_payload_input_used"] is False
    assert payload["display_payload_input_used"] is False
    assert "auditable_backtest_result_missing" in payload["blocking_reasons"]


def test_auditable_backtest_readonly_api_reads_manifest_metrics_equity_and_trades(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("SN_DATA_DIR", str(tmp_path / "user_data"))
    input_dir = tmp_path / "user_data" / "outputs" / "backtest_inputs" / "sn_main"
    _write_auditable_inputs(input_dir)
    created = run_auditable_research_backtest(run_id="api-readable-run", input_id="sn_main")
    assert created["status"] == "success"

    status, payload = handle_terminal_api(
        "/api/terminal/backtest/auditable",
        "GET",
        {"run_id": ["api-readable-run"]},
        None,
    )

    assert status == 200
    assert payload["status"] == "success"
    assert payload["run_id"] == "api-readable-run"
    assert payload["read_only"] is True
    assert payload["manifest"]["run_id"] == "api-readable-run"
    assert payload["manifest"]["chart_payload_input_used"] is False
    assert payload["manifest"]["display_payload_input_used"] is False
    assert payload["manifest"]["data_manifest_hash"]
    assert payload["manifest"]["signal_manifest_hash"]
    assert payload["manifest"]["point_in_time_feature_manifest_hash"]
    assert payload["manifest"]["cost_model"]["commission_per_contract"] == 3.0
    assert payload["manifest"]["slippage_model"]["slippage_ticks"] == 1.0
    assert payload["manifest"]["margin_model"]["margin_rate"] == 0.14
    assert payload["metrics"]["trade_count"] > 0
    assert payload["equity"]
    assert payload["trades"]
    assert payload["blocking_reasons"] == []
    assert payload["sample_data_used"] is False
    assert payload["baseline_used"] is False
    assert payload["backtest_invoked"] is False
    assert payload["customer_prediction_generated"] is False
