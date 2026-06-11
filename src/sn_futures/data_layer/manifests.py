from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from .stores import (
    DataLayerContractError,
    atomic_write_json,
    content_hash,
    data_layer_root,
    read_json,
    safe_part,
    safe_payload,
    utc_now,
    validate_no_sample,
)


MANIFEST_SCHEMA_VERSION = "data-layer-manifest-v1"


class ManifestStore:
    def __init__(self, output_dir: Path | None = None) -> None:
        self.output_dir = output_dir

    @property
    def root(self) -> Path:
        return data_layer_root(self.output_dir) / "manifests"

    def path_for(self, name: str) -> Path:
        return self.root / f"{safe_part(name, 'manifest')}.json"

    def write_manifest(self, name: str, manifest: Mapping[str, Any], *, allow_fixture: bool = False) -> dict[str, Any]:
        payload = dict(manifest)
        payload.setdefault("schema_version", MANIFEST_SCHEMA_VERSION)
        payload.setdefault("fetched_at", utc_now())
        payload.setdefault("source_published_at", "")
        payload.setdefault("sample_data_used", False)
        payload.setdefault("baseline_used", False)
        payload.setdefault("fake_data_used", False)
        payload.setdefault("demo_data_used", False)
        payload.setdefault("mock_data_used", False)
        if allow_fixture and bool(payload.get("fixture") or payload.get("fixture_only")):
            payload["fixture"] = True
            payload["fixture_only"] = True
            payload["allowed_for_public"] = False
            payload["allowed_for_feature_store"] = False
            payload["allowed_for_training"] = False
            payload["allowed_for_prediction"] = False
            payload["allowed_for_backtest"] = False
        payload.setdefault("allowed_for_public", False)
        payload.setdefault("allowed_for_feature_store", False)
        payload.setdefault("allowed_for_training", False)
        payload.setdefault("allowed_for_prediction", False)
        payload.setdefault("allowed_for_backtest", False)
        basis = {key: value for key, value in payload.items() if key != "content_hash"}
        payload["content_hash"] = str(payload.get("content_hash") or content_hash(basis))
        validate_no_sample(payload, allow_fixture=allow_fixture)
        safe = safe_payload(payload)
        atomic_write_json(self.path_for(name), safe)
        return safe

    def load_manifest(self, name: str) -> dict[str, Any]:
        payload = read_json(self.path_for(name), {})
        return safe_payload(payload if isinstance(payload, Mapping) else {})


__all__ = ["DataLayerContractError", "ManifestStore", "content_hash"]
