from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from sn_futures.services.research_backtest_engine_service import run_auditable_research_backtest


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _write_real_bars(input_dir: Path, *, sample_data_used: bool = False) -> None:
    (input_dir / "immutable_historical_bars.csv").write_text(
        "\n".join(
            [
                "trade_date,open,high,low,close,volume,open_interest,main_contract",
                "2026-01-01,100,101,99,100,1000,5000,sn2601",
                "2026-01-02,100,116,99,115,1200,5100,sn2601",
                "2026-01-03,115,117,108,110,900,5050,sn2601",
                "2026-01-04,110,114,106,112,1100,5200,sn2601",
                "2026-01-05,112,116,110,115,1300,5300,sn2601",
                "2026-01-06,115,119,113,118,1250,5280,sn2601",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    _write_json(
        input_dir / "historical_bars_manifest.json",
        {
            "schema_version": 1,
            "provider": "unit_test_provider",
            "data_kind": "daily_bar",
            "sample_data_used": sample_data_used,
            "baseline_used": False,
            "history_immutable": True,
            "allowed_for_backtest": not sample_data_used,
        },
    )


def _write_real_signals(input_dir: Path, *, with_manifest: bool = True, sample_data_used: bool = False) -> None:
    (input_dir / "signals.csv").write_text(
        "\n".join(
            [
                "trade_date,signal,stop_loss,take_profit,trade_edge,data_quality_score",
                "2026-01-01,1,80,200,1,1",
                "2026-01-02,-1,200,80,1,1",
                "2026-01-03,1,80,200,1,1",
                "2026-01-04,1,80,200,1,1",
                "2026-01-05,0,80,200,1,1",
                "2026-01-06,0,80,200,1,1",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    if with_manifest:
        _write_json(
            input_dir / "signal_manifest.json",
            {
                "schema_version": 1,
                "source": "unit_test_signal",
                "sample_data_used": sample_data_used,
                "baseline_used": False,
                "lookahead_check_pass": True,
            },
        )


def _write_required_backtest_context(input_dir: Path) -> None:
    _write_json(
        input_dir / "contract_metadata.json",
        {
            "schema_version": 1,
            "exchange": "SHFE",
            "symbol": "SN",
            "active_contract": "sn2601",
            "contract_multiplier": 1.0,
            "margin_rate": 0.14,
            "commission_per_contract": 3.0,
        },
    )
    _write_json(
        input_dir / "point_in_time_feature_manifest.json",
        {
            "version": "feature_store_v3",
            "as_of_cutoff": "2026-01-06T15:00:00+08:00",
            "leakage_check_pass": True,
            "sample_data_used": False,
            "baseline_used": False,
            "display_overlay_used": False,
            "live_quote_used_for_training": False,
        },
    )


def test_missing_real_historical_bars_blocks_without_equity_curve(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("SN_DATA_DIR", str(tmp_path / "user_data"))
    outputs = tmp_path / "user_data" / "outputs"
    input_dir = outputs / "backtest_inputs" / "sn_main"
    input_dir.mkdir(parents=True)
    (input_dir / "signals.csv").write_text("trade_date,signal\n2026-01-01,1\n", encoding="utf-8")
    _write_json(
        input_dir / "signal_manifest.json",
        {
            "schema_version": 1,
            "source": "unit_test_signal",
            "sample_data_used": False,
            "baseline_used": False,
            "lookahead_check_pass": True,
        },
    )

    result = run_auditable_research_backtest(run_id="missing-bars", input_id="sn_main")

    assert result["status"] == "blocked"
    assert "historical_bars_missing" in result["manifest"]["blocked_reasons"]
    assert result["manifest"]["sample_data_used"] is False
    assert result["manifest"]["baseline_used"] is False
    assert result["equity_curve_path"] == ""
    assert not (outputs / "backtests" / "missing-bars" / "equity_curve.csv").exists()


def test_cost_and_slippage_change_auditable_backtest_result(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("SN_DATA_DIR", str(tmp_path / "user_data"))
    input_dir = tmp_path / "user_data" / "outputs" / "backtest_inputs" / "sn_main"
    input_dir.mkdir(parents=True)
    _write_real_bars(input_dir)
    _write_real_signals(input_dir)
    _write_required_backtest_context(input_dir)

    no_cost = run_auditable_research_backtest(
        run_id="no-cost",
        input_id="sn_main",
        config={"commission_per_contract": 0.0, "slippage_ticks": 0.0},
    )
    with_cost = run_auditable_research_backtest(
        run_id="with-cost",
        input_id="sn_main",
        config={"commission_per_contract": 25.0, "slippage_ticks": 2.0},
    )

    assert no_cost["status"] == "success"
    assert with_cost["status"] == "success"
    assert no_cost["manifest"]["blocked_reasons"] == []
    assert with_cost["manifest"]["blocked_reasons"] == []
    assert no_cost["manifest"]["sample_data_used"] is False
    assert no_cost["manifest"]["lookahead_check_pass"] is True
    assert no_cost["manifest"]["data_manifest_hash"]
    assert no_cost["manifest"]["signal_manifest_hash"]
    assert no_cost["manifest"]["display_payload_input_used"] is False
    assert Path(no_cost["equity_curve_path"]).exists()
    assert Path(no_cost["trades_path"]).exists()
    assert no_cost["metrics"]["trade_count"] > 0
    assert no_cost["metrics"]["net_profit_after_cost"] != with_cost["metrics"]["net_profit_after_cost"]
    assert no_cost["metrics"]["total_cost"] < with_cost["metrics"]["total_cost"]


def test_missing_signal_manifest_blocks_backtest(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("SN_DATA_DIR", str(tmp_path / "user_data"))
    input_dir = tmp_path / "user_data" / "outputs" / "backtest_inputs" / "sn_main"
    input_dir.mkdir(parents=True)
    _write_real_bars(input_dir)
    _write_real_signals(input_dir, with_manifest=False)
    _write_required_backtest_context(input_dir)

    result = run_auditable_research_backtest(run_id="missing-signal-manifest", input_id="sn_main")

    assert result["status"] == "blocked"
    assert "signal_manifest_missing" in result["manifest"]["blocked_reasons"]
    assert result["equity_curve_path"] == ""
    assert not (tmp_path / "user_data" / "outputs" / "backtests" / "missing-signal-manifest" / "equity_curve.csv").exists()


def test_sample_data_manifest_blocks_backtest(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("SN_DATA_DIR", str(tmp_path / "user_data"))
    input_dir = tmp_path / "user_data" / "outputs" / "backtest_inputs" / "sn_main"
    input_dir.mkdir(parents=True)
    _write_real_bars(input_dir, sample_data_used=True)
    _write_real_signals(input_dir)
    _write_required_backtest_context(input_dir)

    result = run_auditable_research_backtest(run_id="sample-blocked", input_id="sn_main")

    assert result["status"] == "blocked"
    assert result["manifest"]["sample_data_used"] is True
    assert "sample_data_used" in result["manifest"]["blocked_reasons"]
    assert result["equity_curve_path"] == ""


def test_terminal_chart_payload_is_ignored_as_backtest_input(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("SN_DATA_DIR", str(tmp_path / "user_data"))
    outputs = tmp_path / "user_data" / "outputs"
    chart_dir = outputs / "research_backtests" / "v3"
    chart_dir.mkdir(parents=True)
    (chart_dir / "equity_curve_1d.csv").write_text("ts,value\n2026-01-01,1.25\n", encoding="utf-8")

    input_dir = outputs / "backtest_inputs" / "sn_main"
    input_dir.mkdir(parents=True)
    _write_real_signals(input_dir)

    result = run_auditable_research_backtest(run_id="ignore-chart-payload", input_id="sn_main")

    assert result["status"] == "blocked"
    assert "historical_bars_missing" in result["manifest"]["blocked_reasons"]
    assert result["manifest"]["chart_payload_input_used"] is False
    assert result["manifest"]["display_payload_input_used"] is False
    assert result["equity_curve_path"] == ""
    assert not (outputs / "backtests" / "ignore-chart-payload" / "equity_curve.csv").exists()


def test_display_overlay_in_feature_manifest_blocks_backtest(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("SN_DATA_DIR", str(tmp_path / "user_data"))
    input_dir = tmp_path / "user_data" / "outputs" / "backtest_inputs" / "sn_main"
    input_dir.mkdir(parents=True)
    _write_real_bars(input_dir)
    _write_real_signals(input_dir)
    _write_required_backtest_context(input_dir)
    _write_json(
        input_dir / "point_in_time_feature_manifest.json",
        {
            "version": "feature_store_v3",
            "as_of_cutoff": "2026-01-06T15:00:00+08:00",
            "leakage_check_pass": True,
            "sample_data_used": False,
            "baseline_used": False,
            "display_overlay_used": True,
            "live_quote_used_for_training": False,
        },
    )

    result = run_auditable_research_backtest(run_id="overlay-feature-blocked", input_id="sn_main")

    assert result["status"] == "blocked"
    assert "display_overlay_used_in_feature_manifest" in result["manifest"]["blocked_reasons"]
    assert result["manifest"]["display_payload_input_used"] is False
    assert result["equity_curve_path"] == ""
