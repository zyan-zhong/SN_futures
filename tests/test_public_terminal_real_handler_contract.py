from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any, Mapping
from unittest.mock import patch


sys.path.insert(0, "src")

from sn_futures.api.terminal_api import handle_terminal_api


FORBIDDEN_TRUE_FLAGS = {
    "training_invoked",
    "prediction_generated",
    "backtest_invoked",
    "feature_store_written",
    "production_cache_written",
    "customer_prediction_generated",
}
ERROR_FIELDS = {"error_code", "message", "blocking_reasons", "details_sanitized"}


def _walk_mappings(value: Any):
    if isinstance(value, Mapping):
        yield value
        for item in value.values():
            yield from _walk_mappings(item)
    elif isinstance(value, list):
        for item in value:
            yield from _walk_mappings(item)


def _public_openapi() -> dict[str, Any]:
    status, payload = handle_terminal_api("/api/public-terminal/openapi.json", "GET", {}, None)
    assert status == 200
    assert isinstance(payload, dict)
    return payload


def _runtime_path(template: str) -> str:
    return template.replace("{task_id}", "contract-task")


def _fake_body(request_schema_name: str) -> dict[str, Any]:
    if request_schema_name == "PublicSettingsSaveRequest":
        return {
            "provider": "local_api_provider",
            "base_url": "http://127.0.0.1:9",
            "token": "PUBLIC_CONTRACT_TOKEN_123456",
        }
    if request_schema_name == "PublicProviderSmokeRequest":
        return {"provider": "alpha_vantage", "allow_remote": False}
    return {}


def _assert_no_forbidden_runtime_side_effects(payload: Mapping[str, Any]) -> None:
    offenders: list[str] = []
    for item in _walk_mappings(payload):
        for flag in FORBIDDEN_TRUE_FLAGS:
            if item.get(flag) is True:
                offenders.append(flag)
    assert offenders == []


def _assert_payload_matches_declared_schema(payload: Mapping[str, Any], response_schema: Mapping[str, Any]) -> None:
    if "status" in payload:
        return
    properties = response_schema.get("properties")
    assert isinstance(properties, Mapping)
    assert set(payload).intersection(properties), {
        "payload_keys": sorted(payload),
        "schema_properties": sorted(str(key) for key in properties),
    }


def test_every_public_terminal_manifest_endpoint_dispatches_through_real_handler() -> None:
    endpoints = _public_openapi()["endpoints"]
    assert isinstance(endpoints, list)

    with tempfile.TemporaryDirectory() as tmp, patch.dict(
        os.environ,
        {
            "SN_DATA_DIR": tmp,
            "SN_INSIGHT_DATA_DIR": tmp,
            "SN_DISABLE_AUTO_SCHEDULER": "1",
        },
        clear=False,
    ):
        for endpoint in endpoints:
            assert isinstance(endpoint, dict)
            method = str(endpoint["method"])
            path = _runtime_path(str(endpoint["path"]))
            body = _fake_body(str(endpoint.get("request_schema_name")))

            status, payload = handle_terminal_api(path, method, {}, body)

            assert status in {200, 202}, (method, path, status, payload)
            assert isinstance(payload, dict), (method, path, payload)
            assert payload.get("error") != "not_found", (method, path, payload)
            _assert_payload_matches_declared_schema(payload, endpoint["response_schema"])
            _assert_no_forbidden_runtime_side_effects(payload)

        assert not (Path(tmp) / "outputs" / "feature_store").exists()
        model_files = list((Path(tmp) / "models").rglob("*")) if (Path(tmp) / "models").exists() else []
        assert [path for path in model_files if path.is_file()] == []


def test_public_terminal_invalid_json_errors_keep_public_error_contract() -> None:
    with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp, "SN_INSIGHT_DATA_DIR": tmp}, clear=False):
        status, payload = handle_terminal_api(
            "/api/public-terminal/provider-smoke",
            "POST",
            {},
            "{not-json",
        )

    assert status == 400
    assert isinstance(payload, dict)
    assert ERROR_FIELDS.issubset(payload)
    assert payload["error_code"]
    assert payload["blocking_reasons"]
    assert isinstance(payload["details_sanitized"], dict)


def test_public_terminal_real_handler_never_exposes_raw_secret_values() -> None:
    secret = "PUBLIC_CONTRACT_TOKEN_123456"
    with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp, "SN_INSIGHT_DATA_DIR": tmp}, clear=False):
        status, payload = handle_terminal_api(
            "/api/public-terminal/settings/save",
            "POST",
            {},
            {"provider": "local_api_provider", "base_url": "http://127.0.0.1:9", "token": secret},
        )

    assert status in {200, 202}
    encoded = json.dumps(payload, ensure_ascii=False)
    assert secret not in encoded
    assert "raw_secret" not in encoded
