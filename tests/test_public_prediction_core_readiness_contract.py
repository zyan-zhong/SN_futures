from __future__ import annotations

import csv
import hashlib
import json
import sys
from pathlib import Path
from typing import Any


sys.path.insert(0, "src")

from sn_futures.api.terminal_api import handle_terminal_api
from sn_futures.data_layer.watermark import WatermarkStore
from sn_futures.prediction_core.readiness import build_public_prediction_core_readiness


FORBIDDEN_PREDICTION_OUTPUT_KEYS = {
    "prediction_card",
    "prediction_value",
    "forecast_price",
    "forecast_range",
    "price_range",
    "prob_up",
    "prob_down",
    "predicted_direction",
    "direction_prediction",
    "target_price",
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _outputs(root: Path) -> Path:
    out = root / "outputs"
    out.mkdir(parents=True, exist_ok=True)
    return out


def _write_json(path: Path, payload: dict[str, Any]) -> dict[str, Any]:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = sorted({key for row in rows for key in row})
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    return path


def _prepare_prediction_data(root: Path, *, horizon: str = "tomorrow") -> dict[str, str]:
    out = _outputs(root)
    feature_path = _write_csv(
        out / "feature_store" / "v3" / "feature_store.csv",
        [
            {"trade_date": f"2026-01-{(idx % 28) + 1:02d}", "close": 200_000 + idx, "ma_5": 199_900 + idx, "rsi_14": 45 + idx % 10}
            for idx in range(80)
        ],
    )
    feature_manifest_path = out / "feature_store" / "v3" / "feature_store_manifest.json"
    feature_manifest_hash = _sha256(feature_manifest_path) if feature_manifest_path.exists() else ""
    feature_manifest = {
        "version": "v3",
        "status": "success",
        "row_count": 80,
        "feature_count": 2,
        "feature_store_path": str(feature_path),
        "manifest_path": str(feature_manifest_path),
        "usable_fields": ["ma_5", "rsi_14"],
        "point_in_time_join_rules": {"labels": "label-like columns excluded from usable_fields"},
        "leakage_check_pass": True,
        "sample_data_used": False,
        "fake_data_used": False,
        "baseline_used": False,
        "data_source_hash": _sha256(feature_path),
    }
    _write_json(feature_manifest_path, feature_manifest)
    feature_manifest_hash = _sha256(feature_manifest_path)

    dataset_path = _write_csv(
        out / "training_datasets" / "v3" / f"train_{horizon}.csv",
        [
            {
                "feature_time": f"2026-02-{(idx % 28) + 1:02d}",
                "label_available_at": f"2026-03-{(idx % 28) + 1:02d}",
                "horizon": horizon,
                "ma_5": 199_900 + idx,
                "rsi_14": 45 + idx % 10,
                "target_return": 0.001 if idx % 2 == 0 else -0.001,
                "direction_label": 1 if idx % 2 == 0 else -1,
            }
            for idx in range(60)
        ],
    )
    label_spec = {
        "horizon": horizon,
        "target_return": "target_return",
        "direction_label": "direction_label",
        "neutral_band": 0.001,
        "volatility_adjusted_label": "volatility_adjusted_label",
        "label_available_at": "label_available_at",
        "required_future_bars": 1 if horizon == "tomorrow" else 3,
        "sample_end_exclusion": 1 if horizon == "tomorrow" else 3,
    }
    _write_json(
        out / "training_dataset_manifest_v3.json",
        {
            "dataset_version": "v3",
            "feature_store_version": "v3",
            "label_version": "label_v1_multi_horizon_pit",
            "status": "success",
            "horizons": [horizon],
            "label_specs": {horizon: label_spec},
            "feature_cols": ["ma_5", "rsi_14"],
            "label_cols": ["target_return", "direction_label", "label_available_at"],
            "leakage_check_pass": True,
            "sample_data_used": False,
            "fake_data_used": False,
            "baseline_used": False,
            "sample_count_by_horizon": {horizon: 60},
            "class_distribution": {horizon: {"1": 30, "-1": 30}},
            "data_source_hash": _sha256(feature_path),
            "dataset_paths": {horizon: str(dataset_path)},
            "dataset_outputs": {horizon: {"path": str(dataset_path), "sample_count": 60, "format": "csv"}},
            "no_model_training": True,
            "customer_prediction_generated": False,
            "active_model_written": False,
        },
    )
    return {
        "feature_store_manifest_hash": feature_manifest_hash,
        "feature_store_data_hash": _sha256(feature_path),
        "dataset_hash": _sha256(dataset_path),
    }


def _write_watermark(root: Path, *, stale: bool = False) -> None:
    WatermarkStore().merge_record(
        provider_id="contract_fixture",
        data_kind="daily_bar",
        row_count=80,
        fetched_at="2026-06-11T09:00:00+08:00",
        source_published_at="2026-06-10",
        cache_status="remote",
        stale_status="stale" if stale else "fresh",
        content_hash="daily-hash",
    )


def _active_model_payload(evidence: dict[str, str], *, horizon: str = "tomorrow", calibration: bool = True, walk_forward: bool = True) -> dict[str, Any]:
    model: dict[str, Any] = {
        "model_id": "active-sn-v12",
        "horizon": horizon,
        "status": "active",
        "artifact_path": "model_artifacts/active-sn-v12.pkl",
        "feature_columns": ["ma_5", "rsi_14"],
        "label_columns": ["target_return", "direction_label"],
        "evidence": {
            "feature_store_manifest_hash": evidence["feature_store_manifest_hash"],
            "feature_store_data_hash": evidence["feature_store_data_hash"],
            "dataset_hash": evidence["dataset_hash"],
        },
    }
    if calibration:
        model["calibration"] = {"status": "ready", "method": "isotonic", "ece": 0.03, "brier_score": 0.19}
    if walk_forward:
        model["walk_forward"] = {"status": "pass", "fold_count": 5, "sample_count": 600, "oof_trace_hash": "oof-hash"}
    return {
        "status": "active_available",
        "release_mode": "manual_human_approval",
        "candidate_version": "v12",
        "active_models": [model],
        "live_trading_enabled": False,
        "customer_order_routing_enabled": False,
        "sample_data_used": False,
        "fake_data_used": False,
        "baseline_used": False,
    }


def _write_active_release(
    root: Path,
    evidence: dict[str, str],
    *,
    horizon: str = "tomorrow",
    calibration: bool = True,
    walk_forward: bool = True,
    audit: bool = True,
) -> None:
    out = _outputs(root)
    _write_json(out / "model_registry" / "active_model.json", _active_model_payload(evidence, horizon=horizon, calibration=calibration, walk_forward=walk_forward))
    if audit:
        _write_json(
            out / "model_registry" / "active_release_audit.json",
            {
                "status": "active_released",
                "active_updated": True,
                "candidate_version": "v12",
                "approval_checklist": [
                    {"name": "promotion dry-run pass", "passed": True},
                    {"name": "institutional validation pass", "passed": True},
                    {"name": "no mock/sample data", "passed": True},
                    {"name": "human approval phrase", "passed": True},
                ],
                "live_trading_enabled": False,
                "customer_order_routing_enabled": False,
            },
        )


def _assert_no_prediction_values(payload: dict[str, Any]) -> None:
    text = json.dumps(payload, ensure_ascii=False).lower()
    leaked = sorted(key for key in FORBIDDEN_PREDICTION_OUTPUT_KEYS if key in text)
    assert leaked == []
    assert payload["training_invoked"] is False
    assert payload["prediction_generated"] is False
    assert payload["backtest_invoked"] is False


def test_no_active_model_blocks_public_prediction_core(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("SN_DATA_DIR", str(tmp_path))
    _prepare_prediction_data(tmp_path)
    _write_watermark(tmp_path)

    payload = build_public_prediction_core_readiness(horizons=("tomorrow",))

    assert payload["status"] == "blocked"
    assert payload["can_predict"] is False
    assert "active_model_missing" in payload["blocking_reasons"]
    assert payload["active_release_safe"] is False
    _assert_no_prediction_values(payload)


def test_active_model_without_calibration_blocks_with_missing_evidence(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("SN_DATA_DIR", str(tmp_path))
    evidence = _prepare_prediction_data(tmp_path)
    _write_watermark(tmp_path)
    _write_active_release(tmp_path, evidence, calibration=False)

    payload = build_public_prediction_core_readiness(horizons=("tomorrow",))

    assert payload["status"] == "blocked"
    assert "tomorrow:calibration_missing" in payload["blocking_reasons"]
    assert "calibration" in payload["missing_evidence"]


def test_active_model_without_walk_forward_blocks(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("SN_DATA_DIR", str(tmp_path))
    evidence = _prepare_prediction_data(tmp_path)
    _write_watermark(tmp_path)
    _write_active_release(tmp_path, evidence, walk_forward=False)

    payload = build_public_prediction_core_readiness(horizons=("tomorrow",))

    assert payload["can_predict"] is False
    assert "tomorrow:walk_forward_missing" in payload["blocking_reasons"]
    assert "walk_forward" in payload["missing_evidence"]


def test_feature_manifest_hash_mismatch_blocks(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("SN_DATA_DIR", str(tmp_path))
    evidence = _prepare_prediction_data(tmp_path)
    _write_watermark(tmp_path)
    mismatched = {**evidence, "feature_store_manifest_hash": "stale-feature-manifest-hash"}
    _write_active_release(tmp_path, mismatched)

    payload = build_public_prediction_core_readiness(horizons=("tomorrow",))

    assert payload["status"] == "blocked"
    assert "tomorrow:feature_manifest_mismatch" in payload["blocking_reasons"]


def test_data_watermark_stale_blocks(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("SN_DATA_DIR", str(tmp_path))
    evidence = _prepare_prediction_data(tmp_path)
    _write_watermark(tmp_path, stale=True)
    _write_active_release(tmp_path, evidence)

    payload = build_public_prediction_core_readiness(horizons=("tomorrow",))

    assert payload["can_predict"] is False
    assert "data_watermark_stale" in payload["blocking_reasons"]
    assert payload["data_watermark"]["stale_status"] == "stale"


def test_intraday_horizon_blocks_without_intraday_bars(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("SN_DATA_DIR", str(tmp_path))
    evidence = _prepare_prediction_data(tmp_path, horizon="next_15m")
    _write_watermark(tmp_path)
    _write_active_release(tmp_path, evidence, horizon="next_15m")

    payload = build_public_prediction_core_readiness(horizons=("next_15m",))

    assert payload["can_predict"] is False
    assert "next_15m:intraday_bars_missing" in payload["blocking_reasons"]
    assert payload["data_readiness"]["horizons"]["next_15m"]["intraday_allowed"] is False


def test_valid_fixture_release_evidence_is_ready_without_generating_prediction(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("SN_DATA_DIR", str(tmp_path))
    evidence = _prepare_prediction_data(tmp_path)
    _write_watermark(tmp_path)
    _write_active_release(tmp_path, evidence)

    payload = build_public_prediction_core_readiness(horizons=("tomorrow",))

    assert payload["status"] == "ready"
    assert payload["can_predict"] is True
    assert payload["active_release_safe"] is True
    assert payload["missing_evidence"] == []
    assert payload["sample_data_used"] is False
    assert payload["fake_data_used"] is False
    _assert_no_prediction_values(payload)


def test_public_readiness_contains_prediction_core_status_but_no_prediction_values(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("SN_DATA_DIR", str(tmp_path))
    evidence = _prepare_prediction_data(tmp_path)
    _write_watermark(tmp_path)
    _write_active_release(tmp_path, evidence)

    status, payload = handle_terminal_api("/api/public-terminal/readiness", "GET", {}, None)

    assert status == 200
    core = payload["prediction_core_readiness"]
    assert core["can_predict"] is True
    assert core["status"] == "ready"
    _assert_no_prediction_values(core)
    serialized = json.dumps(payload, ensure_ascii=False).lower()
    leaked = sorted(key for key in FORBIDDEN_PREDICTION_OUTPUT_KEYS if key in serialized)
    assert leaked == []
