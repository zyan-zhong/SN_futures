from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

import pandas as pd

from ..api.json_utils import sanitize_for_json
from ..backtest_core import BacktestConfig, CostConfig, run_futures_backtest
from ..runtime import get_user_output_dir


SCHEMA_VERSION = 1
DEFAULT_INPUT_ID = "sn_main"


@dataclass(frozen=True)
class ResearchBacktestRunConfig:
    initial_equity: float = 1_000_000.0
    max_position: int = 1
    margin_rate: float = 0.14
    commission_per_contract: float = 3.0
    commission_rate: float = 0.0
    slippage_ticks: float = 1.0
    tick_size: float = 10.0
    contract_multiplier: float = 1.0


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _safe_name(value: str | None, default: str) -> str:
    text = Path(str(value or default).strip() or default).name
    return text or default


def _output_dir() -> Path:
    return get_user_output_dir()


def _input_dir(input_id: str | None) -> Path:
    return _output_dir() / "backtest_inputs" / _safe_name(input_id, DEFAULT_INPUT_ID)


def _run_dir(run_id: str | None) -> Path:
    return _output_dir() / "backtests" / _safe_name(run_id, f"bt_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}")


def _read_json(path: Path) -> Any:
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return None
    return None


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(sanitize_for_json(dict(payload)), ensure_ascii=False, indent=2), encoding="utf-8")


def _sha256_file(path: Path) -> str:
    if not path.exists() or not path.is_file():
        return ""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _manifest_flag(payload: Any, key: str) -> bool:
    if isinstance(payload, Mapping):
        return bool(payload.get(key))
    return False


def _cost_config(config: ResearchBacktestRunConfig) -> CostConfig:
    return CostConfig(
        commission_per_contract=float(config.commission_per_contract),
        commission_rate=float(config.commission_rate),
        slippage_ticks=float(config.slippage_ticks),
        tick_size=float(config.tick_size),
        contract_multiplier=float(config.contract_multiplier),
        margin_rate=float(config.margin_rate),
    )


def _engine_config(config: ResearchBacktestRunConfig) -> BacktestConfig:
    return BacktestConfig(
        initial_equity=float(config.initial_equity),
        max_position=int(config.max_position),
        cost=_cost_config(config),
    )


def _timestamp_index(frame: pd.DataFrame) -> pd.DataFrame:
    for column in ("trade_date", "datetime", "timestamp", "date", "time"):
        if column in frame.columns:
            parsed = pd.to_datetime(frame[column], errors="coerce")
            work = frame.loc[parsed.notna()].copy()
            work.index = pd.DatetimeIndex(parsed.loc[parsed.notna()])
            return work.sort_index()
    return pd.DataFrame()


def _read_bars(path: Path) -> pd.DataFrame:
    frame = pd.read_csv(path)
    work = _timestamp_index(frame)
    required = ("open", "high", "low", "close")
    if work.empty or any(column not in work.columns for column in required):
        return pd.DataFrame()
    for column in ("open", "high", "low", "close", "volume", "open_interest"):
        if column in work.columns:
            work[column] = pd.to_numeric(work[column], errors="coerce")
    return work.dropna(subset=list(required)).sort_index()


def _read_signals(path: Path) -> pd.DataFrame:
    frame = pd.read_csv(path)
    work = _timestamp_index(frame)
    if work.empty:
        return pd.DataFrame()
    if "signal" not in work.columns:
        return pd.DataFrame()
    for column in ("signal", "stop_loss", "take_profit", "trade_edge", "edge", "data_quality_score", "atr_14"):
        if column in work.columns:
            work[column] = pd.to_numeric(work[column], errors="coerce")
    return work.sort_index()


def _write_backtest_outputs(run_path: Path, result: Mapping[str, Any]) -> dict[str, str]:
    run_path.mkdir(parents=True, exist_ok=True)
    equity_path = run_path / "equity_curve.csv"
    trades_path = run_path / "trades.csv"
    metrics_path = run_path / "metrics.json"

    equity = result.get("equity_curve")
    if isinstance(equity, pd.Series):
        equity_frame = equity.to_frame(name="equity").rename_axis("trade_date").reset_index()
    else:
        equity_frame = pd.DataFrame(columns=["trade_date", "equity"])
    equity_frame.to_csv(equity_path, index=False, encoding="utf-8")

    trades = result.get("trades")
    trade_frame = trades if isinstance(trades, pd.DataFrame) else pd.DataFrame()
    trade_frame.to_csv(trades_path, index=False, encoding="utf-8")

    metrics = result.get("metrics")
    _write_json(metrics_path, metrics if isinstance(metrics, Mapping) else {})
    return {
        "equity_curve_path": str(equity_path),
        "trades_path": str(trades_path),
        "metrics_path": str(metrics_path),
    }


def _base_manifest(
    *,
    run_id: str,
    generated_at: str,
    input_dir: Path,
    data_manifest: Any,
    signal_manifest: Any,
    feature_manifest: Any,
    config: ResearchBacktestRunConfig,
    blocked_reasons: list[str],
) -> dict[str, Any]:
    data_manifest_path = input_dir / "historical_bars_manifest.json"
    signal_manifest_path = input_dir / "signal_manifest.json"
    contract_metadata_path = input_dir / "contract_metadata.json"
    feature_manifest_path = input_dir / "point_in_time_feature_manifest.json"
    trading_calendar_path = input_dir / "trading_calendar.json"
    sample_data_used = _manifest_flag(data_manifest, "sample_data_used") or _manifest_flag(signal_manifest, "sample_data_used")
    sample_data_used = sample_data_used or _manifest_flag(feature_manifest, "sample_data_used")
    baseline_used = _manifest_flag(data_manifest, "baseline_used") or _manifest_flag(signal_manifest, "baseline_used")
    baseline_used = baseline_used or _manifest_flag(feature_manifest, "baseline_used")
    lookahead_check_pass = bool(_manifest_flag(signal_manifest, "lookahead_check_pass"))
    cost = _cost_config(config)
    return {
        "schema_version": SCHEMA_VERSION,
        "run_id": run_id,
        "generated_at": generated_at,
        "input_dir": str(input_dir),
        "historical_bars_path": str(input_dir / "immutable_historical_bars.csv"),
        "signals_path": str(input_dir / "signals.csv"),
        "contract_metadata_path": str(contract_metadata_path),
        "point_in_time_feature_manifest_path": str(feature_manifest_path),
        "trading_calendar_path": str(trading_calendar_path) if trading_calendar_path.exists() else "",
        "data_manifest_hash": _sha256_file(data_manifest_path),
        "signal_manifest_hash": _sha256_file(signal_manifest_path),
        "contract_metadata_hash": _sha256_file(contract_metadata_path),
        "point_in_time_feature_manifest_hash": _sha256_file(feature_manifest_path),
        "trading_calendar_hash": _sha256_file(trading_calendar_path),
        "trading_calendar_source": "trading_calendar_json" if trading_calendar_path.exists() else "historical_bars_index",
        "cost_model": {
            "name": "fixed_commission_plus_slippage",
            "commission_per_contract": float(cost.commission_per_contract),
            "commission_rate": float(cost.commission_rate),
            "contract_multiplier": float(cost.contract_multiplier),
        },
        "slippage_model": {
            "name": "fixed_tick_slippage",
            "slippage_ticks": float(cost.slippage_ticks),
            "tick_size": float(cost.tick_size),
        },
        "margin_rate": float(cost.margin_rate),
        "margin_model": {
            "name": "fixed_initial_margin_rate",
            "margin_rate": float(cost.margin_rate),
        },
        "commission": float(cost.commission_per_contract),
        "sample_data_used": bool(sample_data_used),
        "baseline_used": bool(baseline_used),
        "lookahead_check_pass": bool(lookahead_check_pass),
        "pit_feature_leakage_check_pass": bool(_manifest_flag(feature_manifest, "leakage_check_pass")),
        "blocked_reasons": blocked_reasons,
        "chart_payload_input_used": False,
        "display_payload_input_used": False,
        "equity_curve_path": "",
        "trades_path": "",
        "metrics_path": "",
        "research_only": True,
        "disclaimer": "Research reference only; not investment advice.",
    }


def run_auditable_research_backtest(
    *,
    run_id: str | None = None,
    input_id: str = DEFAULT_INPUT_ID,
    config: ResearchBacktestRunConfig | Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    safe_run_id = _safe_name(run_id, f"bt_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}")
    run_path = _run_dir(safe_run_id)
    input_path = _input_dir(input_id)
    bars_path = input_path / "immutable_historical_bars.csv"
    data_manifest_path = input_path / "historical_bars_manifest.json"
    signals_path = input_path / "signals.csv"
    signal_manifest_path = input_path / "signal_manifest.json"
    contract_metadata_path = input_path / "contract_metadata.json"
    feature_manifest_path = input_path / "point_in_time_feature_manifest.json"
    run_config = ResearchBacktestRunConfig(**dict(config or {})) if isinstance(config, Mapping) else (config or ResearchBacktestRunConfig())

    data_manifest = _read_json(data_manifest_path)
    signal_manifest = _read_json(signal_manifest_path)
    feature_manifest = _read_json(feature_manifest_path)
    blocked_reasons: list[str] = []
    if not bars_path.exists():
        blocked_reasons.append("historical_bars_missing")
    if data_manifest is None:
        blocked_reasons.append("data_manifest_missing")
    if not signals_path.exists():
        blocked_reasons.append("signals_missing")
    if signal_manifest is None:
        blocked_reasons.append("signal_manifest_missing")
    if not contract_metadata_path.exists():
        blocked_reasons.append("contract_metadata_missing")
    if feature_manifest is None:
        blocked_reasons.append("point_in_time_feature_manifest_missing")
    if data_manifest is not None and not _manifest_flag(data_manifest, "history_immutable"):
        blocked_reasons.append("historical_bars_not_marked_immutable")
    if data_manifest is not None and data_manifest.get("allowed_for_backtest") is False:
        blocked_reasons.append("historical_bars_not_allowed_for_backtest")
    if _manifest_flag(data_manifest, "sample_data_used") or _manifest_flag(signal_manifest, "sample_data_used") or _manifest_flag(feature_manifest, "sample_data_used"):
        blocked_reasons.append("sample_data_used")
    if _manifest_flag(data_manifest, "baseline_used") or _manifest_flag(signal_manifest, "baseline_used") or _manifest_flag(feature_manifest, "baseline_used"):
        blocked_reasons.append("baseline_used")
    if signal_manifest is not None and not _manifest_flag(signal_manifest, "lookahead_check_pass"):
        blocked_reasons.append("lookahead_check_failed")
    if feature_manifest is not None and not _manifest_flag(feature_manifest, "leakage_check_pass"):
        blocked_reasons.append("point_in_time_leakage_check_failed")
    if _manifest_flag(feature_manifest, "display_overlay_used"):
        blocked_reasons.append("display_overlay_used_in_feature_manifest")
    if _manifest_flag(feature_manifest, "live_quote_used_for_training"):
        blocked_reasons.append("live_quote_used_for_training")

    bars = pd.DataFrame()
    signals = pd.DataFrame()
    if not blocked_reasons:
        try:
            bars = _read_bars(bars_path)
        except Exception:
            bars = pd.DataFrame()
        if bars.empty:
            blocked_reasons.append("historical_bars_malformed_or_empty")
        try:
            signals = _read_signals(signals_path)
        except Exception:
            signals = pd.DataFrame()
        if signals.empty:
            blocked_reasons.append("signals_malformed_or_empty")

    generated_at = _now()
    manifest = _base_manifest(
        run_id=safe_run_id,
        generated_at=generated_at,
        input_dir=input_path,
        data_manifest=data_manifest,
        signal_manifest=signal_manifest,
        feature_manifest=feature_manifest,
        config=run_config,
        blocked_reasons=blocked_reasons,
    )
    manifest_path = run_path / "backtest_manifest.json"
    if blocked_reasons:
        _write_json(manifest_path, manifest)
        return sanitize_for_json(
            {
                "status": "blocked",
                "run_id": safe_run_id,
                "generated_at": generated_at,
                "manifest": manifest,
                "manifest_path": str(manifest_path),
                "equity_curve_path": "",
                "trades_path": "",
                "metrics_path": "",
                "metrics": {},
                "engine_config": asdict(run_config),
                "message_zh": "回测已阻断：输入数据或可审计 manifest 不满足要求。",
            }
        )

    engine_result = run_futures_backtest(bars, signals, config=_engine_config(run_config))
    output_paths = _write_backtest_outputs(run_path, engine_result)
    manifest.update(output_paths)
    _write_json(manifest_path, manifest)
    metrics = engine_result.get("metrics") if isinstance(engine_result, Mapping) else {}
    return sanitize_for_json(
        {
            "status": "success",
            "run_id": safe_run_id,
            "generated_at": generated_at,
            "manifest": manifest,
            "manifest_path": str(manifest_path),
            **output_paths,
            "metrics": metrics if isinstance(metrics, Mapping) else {},
            "engine_config": asdict(run_config),
            "message_zh": "研究回测已基于不可变历史 bars 和可审计 signal manifest 生成；研究参考，不构成投资建议。",
        }
    )
