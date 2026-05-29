from __future__ import annotations

import json
import csv
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping

from ..api.json_utils import sanitize_for_json
from ..runtime import get_user_output_dir


def _output_dir() -> Path:
    return get_user_output_dir()


def _normalise_version(version: str | None) -> str:
    value = str(version or "v3").strip().lower()
    return value or "v3"


def _safe_run_id(value: str | None, candidate_version: str) -> str:
    if value:
        return Path(str(value)).name
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{candidate_version}_{stamp}"


def _read_json(path: Path) -> Any:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(sanitize_for_json(dict(payload)), ensure_ascii=False, indent=2), encoding="utf-8")


def _copy_if_exists(src: Path, dst: Path, copied: list[dict[str, str]]) -> None:
    if not src.exists():
        return
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    copied.append({"source": str(src), "target": str(dst)})


def _copy_glob(src_dir: Path, pattern: str, dst_dir: Path, copied: list[dict[str, str]]) -> None:
    if not src_dir.exists():
        return
    for src in sorted(src_dir.glob(pattern)):
        _copy_if_exists(src, dst_dir / src.name, copied)


def _registry_path(version: str) -> Path:
    if version == "v1":
        return _output_dir() / "model_registry" / "candidate_model_registry.json"
    return _output_dir() / "model_registry" / f"candidate_{version}_model_registry.json"


def archive_research_run(
    *,
    candidate_version: str = "v3",
    run_id: str | None = None,
    extra_payload: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    version = _normalise_version(candidate_version)
    safe_id = _safe_run_id(run_id, version)
    archive_dir = _output_dir() / "research_runs" / safe_id
    archive_dir.mkdir(parents=True, exist_ok=True)
    copied: list[dict[str, str]] = []
    out = _output_dir()

    _copy_if_exists(out / "feature_store" / version / "feature_store_manifest.json", archive_dir / "feature_store_manifest.json", copied)
    _copy_if_exists(out / f"training_dataset_manifest_{version}.json", archive_dir / "training_dataset_manifest.json", copied)
    if version == "v1":
        _copy_if_exists(out / "training_dataset_manifest.json", archive_dir / "training_dataset_manifest.json", copied)
    _copy_if_exists(_registry_path(version), archive_dir / "candidate_registry.json", copied)
    _copy_if_exists(out / "oof_integrity" / version / "oof_integrity_report.json", archive_dir / "high_confidence_report.json", copied)
    _copy_if_exists(out / "institutional_validation" / f"institutional_validation_report_{version}.json", archive_dir / "institutional_validation.json", copied)
    _copy_if_exists(out / "model_registry" / f"promotion_report_{version}.json", archive_dir / "promotion_dry_run.json", copied)
    _copy_if_exists(out / "research_backtests" / version / "research_backtest_report.md", archive_dir / "research_backtest_report.md", copied)
    _copy_if_exists(out / "model_research" / "strategy_optimization" / version / "optimization_report.json", archive_dir / "strategy_optimization_report.json", copied)
    _copy_if_exists(out / "model_research" / "strategy_optimization" / version / "all_trials.csv", archive_dir / "strategy_optimization_trials.csv", copied)
    _copy_glob(out / "research_backtests" / version, "equity_curve_*.csv", archive_dir, copied)
    _copy_glob(out / "research_backtests" / version, "drawdown_curve_*.csv", archive_dir, copied)
    _copy_glob(out / "research_backtests" / version, "trades_*.csv", archive_dir, copied)
    _copy_glob(out / "research_backtests" / version, "metrics_*.json", archive_dir, copied)
    _copy_glob(out / "walk_forward" / version, "oof_trace_*.summary.json", archive_dir / "oof_trace_summaries", copied)

    registry = _read_json(_registry_path(version))
    feature_importance = []
    calibration_report: dict[str, Any] = {"candidate_version": version, "horizons": {}}
    if isinstance(registry, Mapping):
        records = registry.get("records") if isinstance(registry.get("records"), list) else registry.get("candidates")
        if isinstance(records, list):
            for record in records:
                if not isinstance(record, Mapping):
                    continue
                feature_importance.append(
                    {
                        "model_id": record.get("model_id"),
                        "horizon": record.get("horizon"),
                        "feature_columns": record.get("feature_columns", []),
                    }
                )
    with (archive_dir / "feature_importance.csv").open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=["model_id", "horizon", "feature_columns"])
        writer.writeheader()
        for row in feature_importance:
            writer.writerow(
                {
                    "model_id": row.get("model_id", ""),
                    "horizon": row.get("horizon", ""),
                    "feature_columns": "|".join(str(item) for item in row.get("feature_columns", [])),
                }
            )
    _write_json(archive_dir / "calibration_report.json", calibration_report)

    secret_scan_path = out.parent / "logs" / "runtime_secret_scan.json"
    if secret_scan_path.exists():
        _copy_if_exists(secret_scan_path, archive_dir / "secret_scan_summary.json", copied)
    else:
        _write_json(
            archive_dir / "secret_scan_summary.json",
            {"status": "not_run_in_archive_step", "message_zh": "密钥扫描需由 scripts/scan_runtime_secrets.ps1 单独执行。"},
        )

    config = {
        "run_id": safe_id,
        "candidate_version": version,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "research_only": True,
        "active_updated": False,
        "customer_prediction_generated": False,
        "baseline_used": False,
        "sample_data_used": False,
        "extra": dict(extra_payload or {}),
    }
    _write_json(archive_dir / "config.json", config)
    index = {
        "status": "success",
        "run_id": safe_id,
        "candidate_version": version,
        "artifact_dir": str(archive_dir),
        "copied_files": copied,
        "active_updated": False,
        "customer_prediction_generated": False,
        "baseline_used": False,
        "sample_data_used": False,
    }
    _write_json(archive_dir / "artifact_index.json", index)
    return sanitize_for_json(index)


def get_research_artifacts(*, run_id: str | None = None, candidate_version: str | None = None) -> dict[str, Any]:
    base = _output_dir() / "research_runs"
    if run_id:
        archive_dir = base / Path(run_id).name
        index = _read_json(archive_dir / "artifact_index.json")
        if not isinstance(index, Mapping):
            return {"status": "not_found", "run_id": run_id, "artifacts": [], "message_zh": "未找到该研究归档。"}
        files = [str(path) for path in sorted(archive_dir.glob("*")) if path.is_file()]
        return sanitize_for_json({"status": "success", **dict(index), "artifacts": files})
    if not base.exists():
        return {"status": "empty", "runs": [], "count": 0}
    version_filter = _normalise_version(candidate_version) if candidate_version else ""
    runs = []
    for path in sorted(base.iterdir(), reverse=True):
        if not path.is_dir():
            continue
        index = _read_json(path / "artifact_index.json")
        if isinstance(index, Mapping):
            if version_filter and str(index.get("candidate_version") or "").lower() != version_filter:
                continue
            runs.append(dict(index))
        else:
            if version_filter and not path.name.lower().startswith(f"{version_filter}_"):
                continue
            runs.append({"run_id": path.name, "artifact_dir": str(path), "status": "unknown"})
    return sanitize_for_json({"status": "success", "runs": runs, "count": len(runs)})
