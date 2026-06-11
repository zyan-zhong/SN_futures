from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from ..data_providers.base import ProviderResult
from .stores import (
    NormalizedStore,
    RawStore,
    atomic_write_json,
    content_hash,
    data_layer_root,
    read_json,
    safe_part,
    safe_payload,
    validate_no_sample,
)


PROVIDER_RESULT_STORE_SCHEMA_VERSION = "data-layer-provider-result-v1"


def _provider_dir(provider_id: str, output_dir: Path | None = None) -> Path:
    return data_layer_root(output_dir) / "provider_results" / safe_part(provider_id, "unknown_provider")


def _manifest_from_result(result: ProviderResult) -> dict[str, Any]:
    manifest = dict(result.manifest or {})
    manifest.setdefault("schema_version", PROVIDER_RESULT_STORE_SCHEMA_VERSION)
    manifest.setdefault("provider_id", result.provider_id)
    manifest.setdefault("data_kind", result.data_kind)
    manifest.setdefault("fetched_at", result.fetched_at)
    manifest.setdefault("source_published_at", result.source_timestamp or result.as_of)
    manifest.setdefault("source_timestamp", result.source_timestamp)
    manifest.setdefault("as_of", result.as_of)
    manifest.setdefault("row_count", len(result.rows))
    manifest.setdefault("normalized_row_count", len(result.normalized_rows))
    manifest.setdefault("cache_status", "cache" if result.from_cache else "remote")
    manifest.setdefault("stale_status", "stale" if result.stale else "fresh")
    manifest.setdefault("sample_data_used", False)
    manifest.setdefault("baseline_used", False)
    manifest.setdefault("fake_data_used", False)
    manifest.setdefault("demo_data_used", False)
    manifest.setdefault("mock_data_used", False)
    manifest.setdefault("allowed_for_display", bool(result.success and result.normalized_rows))
    manifest.setdefault("allowed_for_public", False)
    manifest.setdefault("allowed_for_feature_store", False)
    manifest.setdefault("allowed_for_training", False)
    manifest.setdefault("allowed_for_prediction", False)
    manifest.setdefault("allowed_for_backtest", False)
    manifest.setdefault("blocking_reasons", [] if result.success else [result.error_code or "provider_result_blocked"])
    manifest["content_hash"] = str(
        manifest.get("content_hash")
        or content_hash({"rows": result.rows, "normalized_rows": result.normalized_rows, "manifest": manifest})
    )
    return safe_payload(manifest)


def persist_provider_result(result: ProviderResult, output_dir: Path | None = None) -> dict[str, str]:
    manifest = _manifest_from_result(result)
    validate_no_sample({"rows": result.rows, "normalized_rows": result.normalized_rows, "manifest": manifest})
    raw_store = RawStore(output_dir=output_dir)
    normalized_store = NormalizedStore(output_dir=output_dir)
    raw_store.persist(
        provider_id=result.provider_id,
        data_kind=result.data_kind,
        rows=result.rows,
        fetched_at=result.fetched_at,
        source_published_at=str(manifest.get("source_published_at") or result.source_timestamp or ""),
        cache_status=str(manifest.get("cache_status") or ("cache" if result.from_cache else "remote")),
        stale_status=str(manifest.get("stale_status") or ("stale" if result.stale else "fresh")),
    )
    normalized_store.persist(
        provider_id=result.provider_id,
        data_kind=result.data_kind,
        rows=result.normalized_rows,
        fetched_at=result.fetched_at,
        source_published_at=str(manifest.get("source_published_at") or result.source_timestamp or ""),
        cache_status=str(manifest.get("cache_status") or ("cache" if result.from_cache else "remote")),
        stale_status=str(manifest.get("stale_status") or ("stale" if result.stale else "fresh")),
    )
    path = _provider_dir(result.provider_id, output_dir)
    result_payload = result.to_dict()
    result_payload["manifest"] = manifest
    result_payload["schema_version"] = PROVIDER_RESULT_STORE_SCHEMA_VERSION
    result_payload["raw_path"] = str(raw_store.path_for(result.provider_id, result.data_kind))
    result_payload["normalized_path"] = str(normalized_store.path_for(result.provider_id, result.data_kind))
    result_path = path / "latest_result.json"
    status_path = path / "latest_status.json"
    atomic_write_json(result_path, result_payload)
    status_payload = result.to_status().to_dict()
    status_payload["manifest"] = manifest
    status_payload["schema_version"] = PROVIDER_RESULT_STORE_SCHEMA_VERSION
    atomic_write_json(status_path, status_payload)
    return {
        "result_path": str(result_path),
        "status_path": str(status_path),
        "raw_path": str(raw_store.path_for(result.provider_id, result.data_kind)),
        "normalized_path": str(normalized_store.path_for(result.provider_id, result.data_kind)),
    }


def load_provider_result(provider_id: str, output_dir: Path | None = None) -> dict[str, Any]:
    payload = read_json(_provider_dir(provider_id, output_dir) / "latest_result.json", {})
    return safe_payload(payload if isinstance(payload, Mapping) else {})
