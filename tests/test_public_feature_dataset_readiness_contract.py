from __future__ import annotations

import csv
import hashlib
import json
import sys
from pathlib import Path
from typing import Any


sys.path.insert(0, "src")

from sn_futures.api.terminal_api import handle_terminal_api
from sn_futures.prediction_core.data_readiness import build_prediction_data_readiness
from sn_futures.services.intraday_bar_store_service import write_intraday_bars


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


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = sorted({key for row in rows for key in row})
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _feature_rows(count: int = 80) -> list[dict[str, Any]]:
    return [
        {
            "trade_date": f"2026-01-{(idx % 28) + 1:02d}",
            "close": 200_000 + idx,
            "volume": 1_000 + idx,
            "ma_5": 199_000 + idx,
            "rsi_14": 45 + (idx % 10),
        }
        for idx in range(count)
    ]


def _dataset_rows(count: int = 79, *, leaked_time: bool = False) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for idx in range(count):
        day = f"2026-02-{(idx % 28) + 1:02d}"
        rows.append(
            {
                "feature_time": "2026-03-10" if leaked_time and idx == 0 else day,
                "label_start_time": day,
                "label_end_time": f"2026-03-{(idx % 28) + 1:02d}",
                "label_available_at": "2026-03-01" if leaked_time and idx == 0 else f"2026-03-{(idx % 28) + 1:02d}",
                "horizon": "tomorrow",
                "ma_5": 199_000 + idx,
                "rsi_14": 45 + (idx % 10),
                "target_return": 0.001 if idx % 2 == 0 else -0.001,
                "direction_label": 1 if idx % 2 == 0 else -1,
            }
        )
    return rows


def _write_ready_feature_store(root: Path, *, sample: bool = False, missing_pit: bool = False, rows: int = 80) -> dict[str, Any]:
    out = _outputs(root)
    feature_dir = out / "feature_store" / "v3"
    csv_path = feature_dir / "feature_store.csv"
    _write_csv(csv_path, _feature_rows(rows))
    manifest = {
        "version": "v3",
        "status": "success",
        "row_count": rows,
        "feature_count": 2,
        "feature_store_path": str(csv_path),
        "manifest_path": str(feature_dir / "feature_store_manifest.json"),
        "usable_fields": ["ma_5", "rsi_14"],
        "leakage_check_pass": True,
        "sample_data_used": sample,
        "fake_data_used": False,
        "baseline_used": False,
        "customer_prediction_generated": False,
        "active_model_written": False,
        "data_source_hash": _sha256(csv_path),
    }
    if not missing_pit:
        manifest["point_in_time_join_rules"] = {
            "primary_market_history": "immutable daily bars indexed by trade_date",
            "labels": "forward returns and label-like columns are excluded from usable_fields",
        }
    _write_json(feature_dir / "feature_store_manifest.json", manifest)
    return manifest


def _write_training_manifest(
    root: Path,
    *,
    horizon: str = "tomorrow",
    rows: int = 79,
    leakage_check_pass: bool = True,
    single_class: bool = False,
    leaked_time: bool = False,
) -> dict[str, Any]:
    out = _outputs(root)
    dataset_dir = out / "training_datasets" / "v3"
    dataset_path = dataset_dir / f"train_{horizon}.csv"
    _write_csv(dataset_path, _dataset_rows(rows, leaked_time=leaked_time))
    class_distribution = {horizon: {"1": rows, "-1": 0} if single_class else {"1": rows // 2, "-1": rows - rows // 2}}
    manifest = {
        "dataset_version": "v3",
        "feature_store_version": "v3",
        "label_version": "label_v1_multi_horizon_pit",
        "status": "success",
        "horizons": [horizon],
        "label_specs": {
            horizon: {
                "horizon": horizon,
                "target_return": "target_return",
                "direction_label": "direction_label",
                "neutral_band": 0.001,
                "volatility_adjusted_label": "volatility_adjusted_label",
                "label_available_at": "label_available_at",
                "required_future_bars": 1 if horizon == "tomorrow" else 3,
                "sample_end_exclusion": 1 if horizon == "tomorrow" else 3,
            }
        },
        "feature_cols": ["ma_5", "rsi_14"],
        "label_cols": ["target_return", "direction_label", "label_available_at"],
        "leakage_check_pass": leakage_check_pass,
        "sample_data_used": False,
        "fake_data_used": False,
        "baseline_used": False,
        "sample_count_by_horizon": {horizon: rows},
        "class_distribution": class_distribution,
        "data_source_hash": _sha256(_outputs(root) / "feature_store" / "v3" / "feature_store.csv"),
        "dataset_paths": {horizon: str(dataset_path)},
        "dataset_outputs": {horizon: {"path": str(dataset_path), "sample_count": rows, "format": "csv"}},
        "blocked_reasons": [],
        "no_model_training": True,
        "customer_prediction_generated": False,
        "active_model_written": False,
    }
    _write_json(out / "training_dataset_manifest_v3.json", manifest)
    return manifest


def test_no_feature_store_blocks_prediction_data_readiness(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("SN_DATA_DIR", str(tmp_path))

    payload = build_prediction_data_readiness(horizons=("tomorrow",), dataset_version="v3", feature_store_version="v3")

    assert payload["status"] == "blocked"
    assert "feature_store_missing" in payload["blocking_reasons"]
    assert payload["training_invoked"] is False
    assert payload["prediction_generated"] is False


def test_sample_feature_store_is_blocked(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("SN_DATA_DIR", str(tmp_path))
    _write_ready_feature_store(tmp_path, sample=True)
    _write_training_manifest(tmp_path)

    payload = build_prediction_data_readiness(horizons=("tomorrow",), dataset_version="v3", feature_store_version="v3")

    assert payload["status"] == "blocked"
    assert "sample_feature_store" in payload["blocking_reasons"]
    assert payload["feature_store"]["sample_data_used"] is True


def test_missing_point_in_time_feature_store_blocks(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("SN_DATA_DIR", str(tmp_path))
    _write_ready_feature_store(tmp_path, missing_pit=True)
    _write_training_manifest(tmp_path)

    payload = build_prediction_data_readiness(horizons=("tomorrow",), dataset_version="v3", feature_store_version="v3")

    assert payload["status"] == "blocked"
    assert "feature_store_pit_missing" in payload["blocking_reasons"]
    assert payload["feature_store"]["point_in_time_ready"] is False


def test_future_label_timestamp_leakage_blocks(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("SN_DATA_DIR", str(tmp_path))
    _write_ready_feature_store(tmp_path)
    _write_training_manifest(tmp_path, leaked_time=True)

    payload = build_prediction_data_readiness(horizons=("tomorrow",), dataset_version="v3", feature_store_version="v3")

    assert payload["status"] == "blocked"
    assert "tomorrow:label_timestamp_leakage" in payload["blocking_reasons"]
    assert payload["horizons"]["tomorrow"]["leakage_check_pass"] is False


def test_daily_horizon_ready_when_bars_rows_classes_and_hashes_are_sufficient(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("SN_DATA_DIR", str(tmp_path))
    feature_manifest = _write_ready_feature_store(tmp_path, rows=80)
    dataset_manifest = _write_training_manifest(tmp_path, rows=79)

    payload = build_prediction_data_readiness(horizons=("tomorrow",), dataset_version="v3", feature_store_version="v3")

    assert payload["status"] == "ready"
    assert payload["ready_for_prediction"] is True
    assert payload["feature_store"]["row_count"] == 80
    assert payload["horizons"]["tomorrow"]["enough_rows"] is True
    assert payload["horizons"]["tomorrow"]["class_distribution"] == {"1": 39, "-1": 40}
    assert payload["manifest_hashes"]["feature_store_manifest_hash"]
    assert payload["manifest_hashes"]["training_dataset_manifest_hash"]
    assert payload["manifest_hashes"]["feature_store_data_hash"] == feature_manifest["data_source_hash"]
    assert payload["manifest_hashes"]["dataset_hashes"]["tomorrow"] == _sha256(Path(dataset_manifest["dataset_paths"]["tomorrow"]))


def test_intraday_horizon_blocks_without_intraday_bars(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("SN_DATA_DIR", str(tmp_path))
    _write_ready_feature_store(tmp_path)
    _write_training_manifest(tmp_path, horizon="next_15m", rows=60)

    payload = build_prediction_data_readiness(horizons=("next_15m",), dataset_version="v3", feature_store_version="v3")

    assert payload["status"] == "blocked"
    assert "next_15m:intraday_bars_missing" in payload["blocking_reasons"]
    assert payload["horizons"]["next_15m"]["requires_intraday_bars"] is True
    assert payload["horizons"]["next_15m"]["intraday_allowed"] is False


def test_intraday_horizon_allows_when_matching_intraday_bars_exist(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("SN_DATA_DIR", str(tmp_path))
    _write_ready_feature_store(tmp_path)
    _write_training_manifest(tmp_path, horizon="next_15m", rows=60)
    write_intraday_bars(
        [
            {
                "bar_start": "2026-06-01T09:00:00+08:00",
                "bar_end": "2026-06-01T09:15:00+08:00",
                "open": 200_000,
                "high": 201_000,
                "low": 199_500,
                "close": 200_500,
                "volume": 10,
            },
            {
                "bar_start": "2026-06-01T09:15:00+08:00",
                "bar_end": "2026-06-01T09:30:00+08:00",
                "open": 200_500,
                "high": 201_500,
                "low": 200_000,
                "close": 201_000,
                "volume": 12,
            },
        ],
        symbol="SN",
        interval="15m",
        provider="contract_test",
        fetched_at="2026-06-07T10:30:00+08:00",
    )

    payload = build_prediction_data_readiness(horizons=("next_15m",), dataset_version="v3", feature_store_version="v3")

    assert payload["status"] == "ready"
    assert payload["horizons"]["next_15m"]["intraday_allowed"] is True


def test_insufficient_rows_or_single_class_distribution_blocks(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("SN_DATA_DIR", str(tmp_path))
    _write_ready_feature_store(tmp_path)
    _write_training_manifest(tmp_path, rows=12, single_class=True)

    payload = build_prediction_data_readiness(horizons=("tomorrow",), dataset_version="v3", feature_store_version="v3")

    assert payload["status"] == "blocked"
    assert any(reason.startswith("tomorrow:insufficient_rows") for reason in payload["blocking_reasons"])
    assert "tomorrow:insufficient_class_distribution" in payload["blocking_reasons"]


def test_public_readiness_consumes_prediction_readiness_without_prediction_values(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("SN_DATA_DIR", str(tmp_path))
    _write_ready_feature_store(tmp_path)
    _write_training_manifest(tmp_path)

    status, payload = handle_terminal_api("/api/public-terminal/readiness", "GET", {}, None)

    assert status == 200
    assert payload["prediction_readiness"]["status"] == "ready"
    assert payload["prediction_readiness"]["ready_for_prediction"] is True
    assert payload["prediction_generated"] is False
    serialized = json.dumps(payload, ensure_ascii=False).lower()
    assert "prediction_value" not in serialized
    assert "forecast_price" not in serialized
