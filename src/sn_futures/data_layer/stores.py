from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from ..api.json_utils import sanitize_for_json
from ..runtime import get_user_output_dir
from ..utils.secret_sanitizer import sanitize_mapping


DATA_LAYER_SCHEMA_VERSION = "data-layer-v1"
DATASET_SCHEMA_VERSION = "data-layer-dataset-v1"

DIRTY_FLAGS = {
    "sample",
    "sample_mode",
    "sample_data_used",
    "demo",
    "demo_data_used",
    "fake",
    "fake_data_used",
    "mock_data_used",
    "baseline",
    "baseline_used",
}

ALLOW_FLAGS = (
    "allowed_for_public",
    "allowed_for_feature_store",
    "allowed_for_training",
    "allowed_for_prediction",
    "allowed_for_backtest",
)


class DataLayerContractError(ValueError):
    pass


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def data_layer_root(output_dir: Path | None = None) -> Path:
    root = output_dir or get_user_output_dir()
    path = root / "data_layer"
    path.mkdir(parents=True, exist_ok=True)
    return path


def safe_payload(payload: Any) -> Any:
    return sanitize_for_json(sanitize_mapping(payload))


def content_hash(payload: Any) -> str:
    encoded = json.dumps(safe_payload(payload), ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def atomic_write_json(path: Path, payload: Mapping[str, Any] | list[Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    try:
        tmp.write_text(json.dumps(safe_payload(payload), ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(path)
    finally:
        if tmp.exists():
            tmp.unlink(missing_ok=True)
    return path


def read_json(path: Path, default: Any = None) -> Any:
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default
    return default


def safe_part(value: str, default: str = "unknown") -> str:
    text = Path(str(value or default).strip() or default).name
    return text.replace(" ", "_").replace("/", "_").replace("\\", "_") or default


def _iter_mappings(value: Any):
    if isinstance(value, Mapping):
        yield value
        for item in value.values():
            yield from _iter_mappings(item)
    elif isinstance(value, list):
        for item in value:
            yield from _iter_mappings(item)


def _truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y", "sample", "demo", "fake"}
    return bool(value)


def _is_fixture(payload: Mapping[str, Any]) -> bool:
    return _truthy(payload.get("fixture")) or _truthy(payload.get("fixture_only"))


def validate_no_sample(payload: Any, *, allow_fixture: bool = False) -> None:
    dirty: set[str] = set()
    fixture_seen = False
    allowed_true: set[str] = set()
    for item in _iter_mappings(payload):
        if _is_fixture(item):
            fixture_seen = True
        for flag in DIRTY_FLAGS:
            if _truthy(item.get(flag)):
                dirty.add(flag)
        for flag in ALLOW_FLAGS:
            if _truthy(item.get(flag)):
                allowed_true.add(flag)
    if not dirty and not fixture_seen:
        return
    if allow_fixture and fixture_seen and not allowed_true:
        return
    reasons = sorted(dirty | allowed_true | ({"fixture"} if fixture_seen else set()))
    raise DataLayerContractError("no_sample_allowed:" + ",".join(reasons))


def normalize_manifest(
    *,
    provider_id: str,
    data_kind: str,
    rows: list[Mapping[str, Any]] | None = None,
    fetched_at: str = "",
    source_published_at: str = "",
    cache_status: str = "remote",
    stale_status: str = "fresh",
    extra: Mapping[str, Any] | None = None,
    allow_for_display: bool | None = None,
    allow_downstream: bool = False,
) -> dict[str, Any]:
    row_list = [dict(row) for row in rows or []]
    source_time = source_published_at or _source_published_at(row_list)
    row_count = len(row_list)
    display = row_count > 0 if allow_for_display is None else bool(allow_for_display)
    payload = {
        "schema_version": DATASET_SCHEMA_VERSION,
        "provider_id": str(provider_id or "unknown_provider"),
        "data_kind": str(data_kind or "unknown"),
        "row_count": row_count,
        "fetched_at": str(fetched_at or utc_now()),
        "source_published_at": str(source_time or ""),
        "source_timestamp": str(source_time or ""),
        "as_of": str(source_time or fetched_at or ""),
        "cache_status": str(cache_status or "remote"),
        "stale_status": str(stale_status or "fresh"),
        "content_hash": content_hash(row_list),
        "sample_data_used": False,
        "baseline_used": False,
        "fake_data_used": False,
        "demo_data_used": False,
        "mock_data_used": False,
        "allowed_for_display": display,
        "allowed_for_public": False,
        "allowed_for_feature_store": bool(allow_downstream),
        "allowed_for_training": bool(allow_downstream),
        "allowed_for_prediction": bool(allow_downstream),
        "allowed_for_backtest": bool(allow_downstream),
        "blocking_reasons": [],
    }
    if extra:
        payload.update(safe_payload(dict(extra)))
        payload["content_hash"] = str(payload.get("content_hash") or content_hash(row_list))
    validate_no_sample({"rows": row_list, "manifest": payload})
    return safe_payload(payload)


def _source_published_at(rows: list[Mapping[str, Any]]) -> str:
    values = [
        str(
            row.get("source_published_at")
            or row.get("published_at")
            or row.get("source_timestamp")
            or row.get("quote_time")
            or row.get("trade_date")
            or ""
        )
        for row in rows
    ]
    values = [value for value in values if value]
    return max(values) if values else ""


class JsonRowStore:
    store_name = "rows"

    def __init__(self, output_dir: Path | None = None) -> None:
        self.output_dir = output_dir

    @property
    def root(self) -> Path:
        return data_layer_root(self.output_dir) / self.store_name

    def path_for(self, provider_id: str, data_kind: str) -> Path:
        return self.root / safe_part(provider_id, "unknown_provider") / f"{safe_part(data_kind, 'unknown')}.json"

    def persist(
        self,
        *,
        provider_id: str,
        data_kind: str,
        rows: list[Mapping[str, Any]],
        fetched_at: str = "",
        source_published_at: str = "",
        cache_status: str = "remote",
        stale_status: str = "fresh",
        manifest: Mapping[str, Any] | None = None,
        allow_downstream: bool = False,
    ) -> dict[str, Any]:
        row_list = [dict(row) for row in rows]
        validate_no_sample(row_list)
        merged_manifest = normalize_manifest(
            provider_id=provider_id,
            data_kind=data_kind,
            rows=row_list,
            fetched_at=fetched_at,
            source_published_at=source_published_at,
            cache_status=cache_status,
            stale_status=stale_status,
            extra=manifest,
            allow_downstream=allow_downstream,
        )
        payload = {
            "schema_version": DATA_LAYER_SCHEMA_VERSION,
            "store": self.store_name,
            "provider_id": str(provider_id or "unknown_provider"),
            "data_kind": str(data_kind or "unknown"),
            "rows": safe_payload(row_list),
            "manifest": merged_manifest,
        }
        validate_no_sample(payload)
        atomic_write_json(self.path_for(provider_id, data_kind), payload)
        return safe_payload(payload)

    def load(self, provider_id: str, data_kind: str) -> dict[str, Any]:
        payload = read_json(self.path_for(provider_id, data_kind), {})
        return safe_payload(payload if isinstance(payload, Mapping) else {})

    def load_latest_by_kind(self, data_kind: str) -> dict[str, Any]:
        candidates: list[dict[str, Any]] = []
        pattern = f"{safe_part(data_kind, 'unknown')}.json"
        for path in self.root.glob(f"*/{pattern}"):
            payload = read_json(path, {})
            if isinstance(payload, Mapping):
                candidates.append(dict(payload))
        if not candidates:
            return {}
        return max(
            candidates,
            key=lambda payload: str(
                (payload.get("manifest") if isinstance(payload.get("manifest"), Mapping) else {}).get("source_published_at")
                or (payload.get("manifest") if isinstance(payload.get("manifest"), Mapping) else {}).get("fetched_at")
                or ""
            ),
        )


class RawStore(JsonRowStore):
    store_name = "raw"


class NormalizedStore(JsonRowStore):
    store_name = "normalized"
