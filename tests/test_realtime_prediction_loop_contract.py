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
from sn_futures.prediction_core.realtime_loop import load_realtime_loop_state, run_realtime_prediction_dry_run
from sn_futures.resource_manager.worker_pool import WorkerPoolSnapshot


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


def _prepare_ready_prediction_inputs(root: Path, *, stale: bool = False, active_release: bool = True) -> dict[str, str]:
    out = _outputs(root)
    feature_path = _write_csv(
        out / "feature_store" / "v3" / "feature_store.csv",
        [
            {
                "trade_date": f"2026-01-{(idx % 28) + 1:02d}",
                "close": 200_000 + idx,
                "ma_5": 199_900 + idx,
                "rsi_14": 45 + idx % 10,
            }
            for idx in range(80)
        ],
    )
    feature_manifest_path = out / "feature_store" / "v3" / "feature_store_manifest.json"
    _write_json(
        feature_manifest_path,
        {
            "version": "v3",
            "status": "success",
            "row_count": 80,
            "feature_count": 2,
            "feature_store_path": str(feature_path),
            "usable_fields": ["ma_5", "rsi_14"],
            "point_in_time_join_rules": {"labels": "label-like columns excluded from usable_fields"},
            "leakage_check_pass": True,
            "sample_data_used": False,
            "fake_data_used": False,
            "baseline_used": False,
            "data_source_hash": _sha256(feature_path),
        },
    )
    feature_manifest_hash = _sha256(feature_manifest_path)
    feature_data_hash = _sha256(feature_path)

    dataset_path = _write_csv(
        out / "training_datasets" / "v3" / "train_tomorrow.csv",
        [
            {
                "feature_time": f"2026-02-{(idx % 28) + 1:02d}",
                "label_available_at": f"2026-03-{(idx % 28) + 1:02d}",
                "horizon": "tomorrow",
                "ma_5": 199_900 + idx,
                "rsi_14": 45 + idx % 10,
                "target_return": 0.001 if idx % 2 == 0 else -0.001,
                "direction_label": 1 if idx % 2 == 0 else -1,
            }
            for idx in range(60)
        ],
    )
    _write_json(
        out / "training_dataset_manifest_v3.json",
        {
            "dataset_version": "v3",
            "feature_store_version": "v3",
            "label_version": "label_v1_multi_horizon_pit",
            "status": "success",
            "horizons": ["tomorrow"],
            "label_specs": {
                "tomorrow": {
                    "horizon": "tomorrow",
                    "target_return": "target_return",
                    "direction_label": "direction_label",
                    "label_available_at": "label_available_at",
                    "required_future_bars": 1,
                    "sample_end_exclusion": 1,
                }
            },
            "leakage_check_pass": True,
            "sample_data_used": False,
            "fake_data_used": False,
            "baseline_used": False,
            "sample_count_by_horizon": {"tomorrow": 60},
            "class_distribution": {"tomorrow": {"1": 30, "-1": 30}},
            "data_source_hash": feature_data_hash,
            "dataset_paths": {"tomorrow": str(dataset_path)},
            "dataset_outputs": {"tomorrow": {"path": str(dataset_path), "sample_count": 60, "format": "csv"}},
            "no_model_training": True,
            "customer_prediction_generated": False,
        },
    )
    WatermarkStore(output_dir=out).merge_record(
        provider_id="contract_fixture",
        data_kind="daily_bar",
        row_count=80,
        fetched_at="2026-06-11T09:00:00+08:00",
        source_published_at="2026-06-10",
        cache_status="remote",
        stale_status="stale" if stale else "fresh",
        content_hash="daily-hash",
    )
    evidence = {
        "feature_store_manifest_hash": feature_manifest_hash,
        "feature_store_data_hash": feature_data_hash,
        "dataset_hash": _sha256(dataset_path),
    }
    if active_release:
        _write_json(
            out / "model_registry" / "active_model.json",
            {
                "status": "active_available",
                "release_mode": "manual_human_approval",
                "candidate_version": "v12",
                "active_models": [
                    {
                        "model_id": "active-sn-v12",
                        "horizon": "tomorrow",
                        "status": "active",
                        "artifact_path": "model_artifacts/active-sn-v12.pkl",
                        "evidence": evidence,
                        "calibration": {"status": "ready", "method": "isotonic", "ece": 0.03},
                        "walk_forward": {"status": "pass", "fold_count": 5, "sample_count": 600},
                    }
                ],
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
    return evidence


def _assert_no_prediction_values(payload: dict[str, Any]) -> None:
    serialized = json.dumps(payload, ensure_ascii=False).lower()
    leaked = sorted(key for key in FORBIDDEN_PREDICTION_OUTPUT_KEYS if key in serialized)
    assert leaked == []
    assert payload["prediction_generated"] is False
    assert payload["customer_prediction_generated"] is False
    assert payload["training_invoked"] is False
    assert payload["backtest_invoked"] is False


def test_no_active_release_blocks_realtime_dry_run_without_prediction(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("SN_DATA_DIR", str(tmp_path))
    out = _outputs(tmp_path)
    _prepare_ready_prediction_inputs(tmp_path, active_release=False)

    payload = run_realtime_prediction_dry_run(output_dir=out, now="2026-06-11T09:30:00+08:00")

    assert payload["status"] == "blocked"
    assert payload["dry_run"] is True
    assert payload["can_predict"] is False
    assert "active_model_missing" in payload["blocking_reasons"]
    _assert_no_prediction_values(payload)


def test_stale_data_blocks_realtime_dry_run_without_prediction(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("SN_DATA_DIR", str(tmp_path))
    out = _outputs(tmp_path)
    _prepare_ready_prediction_inputs(tmp_path, stale=True)

    payload = run_realtime_prediction_dry_run(output_dir=out, now="2026-06-11T09:30:00+08:00")

    assert payload["status"] == "blocked"
    assert payload["can_predict"] is False
    assert "data_watermark_stale" in payload["blocking_reasons"]
    _assert_no_prediction_values(payload)


def test_resource_busy_skips_realtime_dry_run_without_prediction(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("SN_DATA_DIR", str(tmp_path))
    out = _outputs(tmp_path)
    _prepare_ready_prediction_inputs(tmp_path)

    payload = run_realtime_prediction_dry_run(
        output_dir=out,
        now="2026-06-11T09:30:00+08:00",
        worker_pool=WorkerPoolSnapshot(running_jobs=2, max_workers=1),
    )

    assert payload["status"] == "skipped"
    assert payload["reason"] == "resource_busy"
    assert "resource_busy" in payload["blocking_reasons"]
    _assert_no_prediction_values(payload)


def test_valid_fixture_ready_dry_run_reports_ready_to_predict_without_values(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("SN_DATA_DIR", str(tmp_path))
    out = _outputs(tmp_path)
    _prepare_ready_prediction_inputs(tmp_path)

    payload = run_realtime_prediction_dry_run(
        output_dir=out,
        now="2026-06-11T09:30:00+08:00",
        latest_quote={"symbol": "SN", "quote_time": "2026-06-11T09:29:00+08:00", "fixture": True},
    )

    assert payload["status"] == "ready_to_predict"
    assert payload["can_predict"] is True
    assert payload["active_release_safe"] is True
    assert payload["ready_to_generate_prediction"] is True
    assert payload["dry_run"] is True
    _assert_no_prediction_values(payload)


def test_sample_or_demo_quote_is_blocked_by_realtime_loop(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("SN_DATA_DIR", str(tmp_path))
    out = _outputs(tmp_path)
    _prepare_ready_prediction_inputs(tmp_path)

    payload = run_realtime_prediction_dry_run(
        output_dir=out,
        now="2026-06-11T09:30:00+08:00",
        latest_quote={"symbol": "SN", "quote_time": "2026-06-11T09:29:00+08:00", "sample": True, "demo": True},
    )

    assert payload["status"] == "blocked"
    assert "latest_quote_sample" in payload["blocking_reasons"]
    assert "latest_quote_demo" in payload["blocking_reasons"]
    _assert_no_prediction_values(payload)


def test_realtime_loop_state_persists_between_ticks(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("SN_DATA_DIR", str(tmp_path))
    out = _outputs(tmp_path)
    _prepare_ready_prediction_inputs(tmp_path)

    first = run_realtime_prediction_dry_run(output_dir=out, now="2026-06-11T09:30:00+08:00")
    state = load_realtime_loop_state(output_dir=out)

    assert first["state_path"] == state["state_path"]
    assert state["last_status"] == "ready_to_predict"
    assert state["attempt_count"] == 1
    assert state["last_checked_at"] == "2026-06-11T09:30:00+08:00"
    assert state["prediction_generated"] is False


def test_realtime_loop_rate_limit_backoff_skips_repeated_tick(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("SN_DATA_DIR", str(tmp_path))
    out = _outputs(tmp_path)
    _prepare_ready_prediction_inputs(tmp_path)

    first = run_realtime_prediction_dry_run(output_dir=out, now="2026-06-11T09:30:00+08:00", min_interval_seconds=60)
    second = run_realtime_prediction_dry_run(output_dir=out, now="2026-06-11T09:30:10+08:00", min_interval_seconds=60)

    assert first["status"] == "ready_to_predict"
    assert second["status"] == "skipped"
    assert second["reason"] == "rate_limited"
    assert "rate_limited" in second["blocking_reasons"]
    assert second["next_allowed_at"] == "2026-06-11T09:31:00+08:00"
    _assert_no_prediction_values(second)


def test_public_prediction_status_endpoint_is_read_only_and_has_no_prediction_values(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("SN_DATA_DIR", str(tmp_path))
    _prepare_ready_prediction_inputs(tmp_path)

    status, payload = handle_terminal_api("/api/public-terminal/prediction-status", "GET", {}, None)
    docs_status, docs = handle_terminal_api("/api/public-terminal/openapi.json", "GET", {}, None)

    assert status == 200
    prediction_status = payload["prediction_status"]
    assert prediction_status["status"] == "ready_to_predict"
    _assert_no_prediction_values(prediction_status)
    assert docs_status == 200
    endpoint = next(item for item in docs["endpoints"] if item["path"] == "/api/public-terminal/prediction-status")
    assert endpoint["method"] == "GET"
    assert endpoint["response_schema_name"] == "PublicPredictionStatusPayload"
    assert endpoint["side_effect_classification"] == "read_only"
    assert endpoint["side_effects"]["prediction"] is False


def test_frontend_prediction_status_panel_uses_public_client_and_never_names_prediction_values() -> None:
    api_source = Path("frontend/src/public_terminal/api.ts").read_text(encoding="utf-8")
    types_source = Path("frontend/src/public_terminal/types.ts").read_text(encoding="utf-8")
    manifest_source = Path("frontend/src/public_terminal/endpointManifest.ts").read_text(encoding="utf-8")
    panel_source = Path("frontend/src/public_terminal/components/PredictionStatusPanel.tsx").read_text(encoding="utf-8")
    terminal_source = Path("frontend/src/public_terminal/PublicTerminalPage.tsx").read_text(encoding="utf-8")

    assert "getPublicPredictionStatus" in api_source
    assert '"/api/public-terminal/prediction-status"' in api_source
    assert "PublicPredictionStatusPayload" in types_source
    assert 'path: "/api/public-terminal/prediction-status"' in manifest_source
    assert "PredictionStatusPanel" in panel_source
    assert "PredictionStatusPanel" in terminal_source
    assert "fetch(" not in panel_source
    serialized = "\n".join([api_source, types_source, manifest_source, panel_source])
    leaked = sorted(key for key in FORBIDDEN_PREDICTION_OUTPUT_KEYS if key in serialized)
    assert leaked == []
