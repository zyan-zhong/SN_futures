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


def _outputs(root: Path) -> Path:
    out = root / "outputs"
    out.mkdir(parents=True, exist_ok=True)
    return out


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = sorted({key for row in rows for key in row})
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    return path


def _write_json(path: Path, payload: dict[str, Any]) -> dict[str, Any]:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload


def _feature_rows(count: int = 80) -> list[dict[str, Any]]:
    return [
        {
            "trade_date": f"2026-01-{(idx % 28) + 1:02d}",
            "close": 200_000 + idx,
            "ma_5": 199_900 + idx,
            "rsi_14": 45 + idx % 10,
        }
        for idx in range(count)
    ]


def _dataset_rows(count: int = 60, *, horizon: str = "tomorrow") -> list[dict[str, Any]]:
    return [
        {
            "feature_time": f"2026-02-{(idx % 28) + 1:02d}",
            "label_available_at": f"2026-03-{(idx % 28) + 1:02d}",
            "horizon": horizon,
            "ma_5": 199_900 + idx,
            "rsi_14": 45 + idx % 10,
            "target_return": 0.001 if idx % 2 == 0 else -0.001,
            "direction_label": 1 if idx % 2 == 0 else -1,
        }
        for idx in range(count)
    ]


def _write_feature_store(root: Path, *, sample: bool = False, pit: bool = True, rows: int = 80) -> dict[str, str]:
    out = _outputs(root)
    feature_path = _write_csv(out / "feature_store" / "v3" / "feature_store.csv", _feature_rows(rows))
    manifest: dict[str, Any] = {
        "version": "v3",
        "status": "success",
        "row_count": rows,
        "feature_count": 2,
        "feature_store_path": str(feature_path),
        "usable_fields": ["ma_5", "rsi_14"],
        "leakage_check_pass": True,
        "sample_data_used": sample,
        "fake_data_used": False,
        "baseline_used": False,
        "data_source_hash": _sha256(feature_path),
    }
    if pit:
        manifest["point_in_time_join_rules"] = {"labels": "label-like columns excluded from usable_fields"}
    manifest_path = out / "feature_store" / "v3" / "feature_store_manifest.json"
    _write_json(manifest_path, manifest)
    return {
        "feature_store_manifest_hash": _sha256(manifest_path),
        "feature_store_data_hash": _sha256(feature_path),
    }


def _write_dataset(
    root: Path,
    *,
    horizon: str = "tomorrow",
    rows: int = 60,
    label_specs: bool = True,
    single_class: bool = False,
) -> dict[str, str]:
    out = _outputs(root)
    dataset_path = _write_csv(out / "training_datasets" / "v3" / f"train_{horizon}.csv", _dataset_rows(rows, horizon=horizon))
    label_spec = {
        "horizon": horizon,
        "target_return": "target_return",
        "direction_label": "direction_label",
        "label_available_at": "label_available_at",
        "required_future_bars": 1,
        "sample_end_exclusion": 1,
    }
    manifest: dict[str, Any] = {
        "dataset_version": "v3",
        "feature_store_version": "v3",
        "label_version": "label_v1_multi_horizon_pit",
        "status": "success",
        "horizons": [horizon],
        "label_specs": {horizon: label_spec} if label_specs else {},
        "feature_cols": ["ma_5", "rsi_14"],
        "label_cols": ["target_return", "direction_label", "label_available_at"],
        "leakage_check_pass": True,
        "sample_data_used": False,
        "fake_data_used": False,
        "baseline_used": False,
        "sample_count_by_horizon": {horizon: rows},
        "class_distribution": {horizon: {"1": rows, "-1": 0} if single_class else {"1": rows // 2, "-1": rows - rows // 2}},
        "data_source_hash": _sha256(out / "feature_store" / "v3" / "feature_store.csv"),
        "dataset_paths": {horizon: str(dataset_path)},
        "dataset_outputs": {horizon: {"path": str(dataset_path), "sample_count": rows, "format": "csv"}},
        "no_model_training": True,
        "customer_prediction_generated": False,
    }
    manifest_path = out / "training_dataset_manifest_v3.json"
    _write_json(manifest_path, manifest)
    return {
        "training_dataset_manifest_hash": _sha256(manifest_path),
        "dataset_hash": _sha256(dataset_path),
    }


def _write_watermark(root: Path, *, stale: bool = False) -> None:
    WatermarkStore(output_dir=_outputs(root)).merge_record(
        provider_id="contract_fixture",
        data_kind="daily_bar",
        row_count=80,
        fetched_at="2026-06-11T09:00:00+08:00",
        source_published_at="2026-06-10",
        cache_status="remote",
        stale_status="stale" if stale else "fresh",
        content_hash="daily-hash",
    )


def _write_active_release(
    root: Path,
    evidence: dict[str, str],
    *,
    horizon: str = "tomorrow",
    calibration: bool = True,
    walk_forward: bool = True,
) -> None:
    out = _outputs(root)
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
        model["calibration"] = {"status": "ready", "method": "isotonic", "ece": 0.03}
    if walk_forward:
        model["walk_forward"] = {"status": "pass", "fold_count": 5, "sample_count": 600}
    _write_json(
        out / "model_registry" / "active_model.json",
        {
            "status": "active_available",
            "release_mode": "manual_human_approval",
            "candidate_version": "v12",
            "active_models": [model],
            "live_trading_enabled": False,
            "customer_order_routing_enabled": False,
            "sample_data_used": False,
            "fake_data_used": False,
            "baseline_used": False,
        },
    )
    _write_json(
        out / "model_registry" / "active_release_audit.json",
        {
            "status": "active_released",
            "active_updated": True,
            "candidate_version": "v12",
            "approval_checklist": [{"name": "no mock/sample data", "passed": True}],
            "live_trading_enabled": False,
            "customer_order_routing_enabled": False,
        },
    )


def _prepare_ready(root: Path, *, horizon: str = "tomorrow") -> dict[str, str]:
    evidence = {**_write_feature_store(root), **_write_dataset(root, horizon=horizon)}
    _write_watermark(root)
    _write_active_release(root, evidence, horizon=horizon)
    return evidence


def _assert_no_prediction_values(payload: dict[str, Any]) -> None:
    serialized = json.dumps(payload, ensure_ascii=False).lower()
    leaked = sorted(key for key in FORBIDDEN_PREDICTION_OUTPUT_KEYS if key in serialized)
    assert leaked == []
    assert payload["training_invoked"] is False
    assert payload["prediction_generated"] is False
    assert payload["backtest_invoked"] is False


def test_no_feature_store_blocks_unified_prediction_readiness(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("SN_DATA_DIR", str(tmp_path))

    payload = build_public_prediction_core_readiness(horizons=("tomorrow",))

    assert payload["status"] == "blocked"
    assert payload["can_predict"] is False
    assert "feature_store_missing" in payload["blocking_reasons"]
    assert "feature_store" in payload["missing_data"]
    _assert_no_prediction_values(payload)


def test_no_point_in_time_feature_store_blocks(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("SN_DATA_DIR", str(tmp_path))
    _write_feature_store(tmp_path, pit=False)
    _write_dataset(tmp_path)
    _write_watermark(tmp_path)

    payload = build_public_prediction_core_readiness(horizons=("tomorrow",))

    assert payload["status"] == "blocked"
    assert "feature_store_pit_missing" in payload["blocking_reasons"]
    assert "point_in_time_feature_store" in payload["missing_data"]


def test_sample_feature_store_blocks(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("SN_DATA_DIR", str(tmp_path))
    _write_feature_store(tmp_path, sample=True)
    _write_dataset(tmp_path)
    _write_watermark(tmp_path)

    payload = build_public_prediction_core_readiness(horizons=("tomorrow",))

    assert payload["status"] == "blocked"
    assert "sample_feature_store" in payload["blocking_reasons"]
    assert payload["data_readiness"]["feature_store"]["sample_data_used"] is True


def test_missing_label_specs_block(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("SN_DATA_DIR", str(tmp_path))
    _write_feature_store(tmp_path)
    _write_dataset(tmp_path, label_specs=False)
    _write_watermark(tmp_path)

    payload = build_public_prediction_core_readiness(horizons=("tomorrow",))

    assert payload["status"] == "blocked"
    assert "tomorrow:label_spec_missing" in payload["blocking_reasons"]
    assert "labels" in payload["missing_data"]


def test_intraday_missing_blocks(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("SN_DATA_DIR", str(tmp_path))
    evidence = {**_write_feature_store(tmp_path), **_write_dataset(tmp_path, horizon="next_15m")}
    _write_watermark(tmp_path)
    _write_active_release(tmp_path, evidence, horizon="next_15m")

    payload = build_public_prediction_core_readiness(horizons=("next_15m",))

    assert payload["status"] == "blocked"
    assert "next_15m:intraday_bars_missing" in payload["blocking_reasons"]
    assert "intraday_bars" in payload["missing_data"]


def test_insufficient_rows_block(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("SN_DATA_DIR", str(tmp_path))
    _write_feature_store(tmp_path)
    _write_dataset(tmp_path, rows=12)
    _write_watermark(tmp_path)

    payload = build_public_prediction_core_readiness(horizons=("tomorrow",))

    assert payload["status"] == "blocked"
    assert any(reason.startswith("tomorrow:insufficient_rows") for reason in payload["blocking_reasons"])
    assert "tomorrow_rows" in payload["missing_data"]


def test_no_active_model_blocks_after_data_is_ready(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("SN_DATA_DIR", str(tmp_path))
    _write_feature_store(tmp_path)
    _write_dataset(tmp_path)
    _write_watermark(tmp_path)

    payload = build_public_prediction_core_readiness(horizons=("tomorrow",))

    assert payload["status"] == "blocked"
    assert "active_model_missing" in payload["blocking_reasons"]
    assert "active_model" in payload["missing_model_evidence"]


def test_no_calibration_blocks(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("SN_DATA_DIR", str(tmp_path))
    evidence = {**_write_feature_store(tmp_path), **_write_dataset(tmp_path)}
    _write_watermark(tmp_path)
    _write_active_release(tmp_path, evidence, calibration=False)

    payload = build_public_prediction_core_readiness(horizons=("tomorrow",))

    assert payload["status"] == "blocked"
    assert "tomorrow:calibration_missing" in payload["blocking_reasons"]
    assert "calibration" in payload["missing_model_evidence"]


def test_no_walk_forward_blocks(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("SN_DATA_DIR", str(tmp_path))
    evidence = {**_write_feature_store(tmp_path), **_write_dataset(tmp_path)}
    _write_watermark(tmp_path)
    _write_active_release(tmp_path, evidence, walk_forward=False)

    payload = build_public_prediction_core_readiness(horizons=("tomorrow",))

    assert payload["status"] == "blocked"
    assert "tomorrow:walk_forward_missing" in payload["blocking_reasons"]
    assert "walk_forward" in payload["missing_model_evidence"]


def test_valid_fixture_evidence_is_ready_without_prediction_output(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("SN_DATA_DIR", str(tmp_path))
    _prepare_ready(tmp_path)

    payload = build_public_prediction_core_readiness(horizons=("tomorrow",))

    assert payload["status"] == "ready_no_prediction_output"
    assert payload["can_predict"] is True
    assert payload["active_release_safe"] is True
    assert payload["missing_data"] == []
    assert payload["missing_model_evidence"] == []
    assert payload["prediction_output_available"] is False
    assert payload["prediction_output_suppressed"] is True
    _assert_no_prediction_values(payload)


def test_public_readiness_consumes_unified_readiness_and_has_no_prediction_values(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("SN_DATA_DIR", str(tmp_path))
    _prepare_ready(tmp_path)

    status, payload = handle_terminal_api("/api/public-terminal/readiness", "GET", {}, None)

    assert status == 200
    unified = payload["prediction_readiness"]
    assert unified["status"] == "ready_no_prediction_output"
    assert unified["can_predict"] is True
    assert unified["prediction_output_available"] is False
    assert payload["prediction_core_readiness"]["status"] == "ready_no_prediction_output"
    _assert_no_prediction_values(unified)
    serialized = json.dumps(payload, ensure_ascii=False).lower()
    leaked = sorted(key for key in FORBIDDEN_PREDICTION_OUTPUT_KEYS if key in serialized)
    assert leaked == []
