from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any


sys.path.insert(0, "src")

from sn_futures.api.terminal_api import handle_terminal_api


PUBLIC_TERMINAL_DIR = Path("frontend/src/public_terminal")

EXPECTED_ENDPOINTS = [
    ("GET", "/api/public-terminal/openapi.json", "PublicTerminalOpenApiPayload", "read_only", ["PublicDiagnosticsPage"]),
    ("GET", "/api/public-terminal/readiness", "PublicReadinessPayload", "read_only", ["PublicTerminalPage", "PublicDataStatusPage", "PublicDiagnosticsPage"]),
    ("GET", "/api/public-terminal/settings/status", "PublicSettingsStatus", "read_only", ["PublicSetupPage"]),
    ("POST", "/api/public-terminal/settings/save", "PublicSettingsSavePayload", "writes_settings", ["PublicSetupPage"]),
    ("POST", "/api/public-terminal/settings/reset", "PublicSettingsSavePayload", "writes_settings", ["PublicSetupPage"]),
    ("POST", "/api/public-terminal/provider-smoke", "PublicSmokePayload", "diagnostic_only", ["PublicSetupPage"]),
    ("POST", "/api/public-terminal/provider-smoke-real", "PublicSmokePayload", "diagnostic_only", ["PublicSetupPage"]),
    ("POST", "/api/public-terminal/refresh-data-status", "PublicTaskPayload", "starts_task", ["PublicDataStatusPage"]),
    ("GET", "/api/public-terminal/tasks/{task_id}", "PublicTaskPayload", "read_only", ["PublicDataStatusPage"]),
    ("POST", "/api/public-terminal/tasks/{task_id}/cancel", "PublicTaskCancelPayload", "starts_task", ["PublicDataStatusPage"]),
    ("GET", "/api/public-terminal/market", "PublicMarketPayload", "read_only", ["PublicMarketPage"]),
    ("GET", "/api/public-terminal/events", "PublicEventsPayload", "read_only", ["PublicEventCenterPage", "PublicReportsPage"]),
    ("GET", "/api/public-terminal/report", "PublicReportPayload", "read_only", ["PublicReportsPage"]),
]

REQUIRED_ERROR_FIELDS = {"error_code", "message", "blocking_reasons", "details_sanitized"}
FORBIDDEN_RAW_SECRET_TERMS = {
    "raw_secret",
    "raw_key",
    "raw_token",
    "authorization",
    "api_key",
    "apikey",
    "headers",
}
PUBLIC_SIDE_EFFECT_FLAGS = {
    "training",
    "prediction",
    "backtest",
    "feature_store",
    "real_api_default",
}


def _openapi_payload() -> dict[str, Any]:
    status, payload = handle_terminal_api("/api/public-terminal/openapi.json", "GET", {}, None)
    assert status == 200
    assert isinstance(payload, dict)
    return payload


def _endpoints_by_key() -> dict[tuple[str, str], dict[str, Any]]:
    payload = _openapi_payload()
    endpoints = payload.get("endpoints")
    assert isinstance(endpoints, list)
    return {
        (str(endpoint.get("method")), str(endpoint.get("path"))): endpoint
        for endpoint in endpoints
        if isinstance(endpoint, dict)
    }


def _walk_strings(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        strings: list[str] = []
        for key, item in value.items():
            strings.extend(_walk_strings(key))
            strings.extend(_walk_strings(item))
        return strings
    if isinstance(value, list):
        strings = []
        for item in value:
            strings.extend(_walk_strings(item))
        return strings
    return []


def test_public_terminal_openapi_lists_every_endpoint_with_schema_contracts() -> None:
    endpoints = _endpoints_by_key()

    missing = [(method, path) for method, path, *_ in EXPECTED_ENDPOINTS if (method, path) not in endpoints]
    assert missing == []

    for method, path, response_schema_name, side_effect_classification, used_by in EXPECTED_ENDPOINTS:
        endpoint = endpoints[(method, path)]
        assert endpoint.get("summary"), path
        assert endpoint.get("request_schema_name"), path
        assert endpoint.get("request_schema"), path
        assert endpoint.get("response_schema_name") == response_schema_name
        assert endpoint.get("response_schema"), path
        assert endpoint.get("error_schema_name") == "PublicApiErrorPayload", path
        assert endpoint.get("error_schema"), path
        assert endpoint.get("side_effect_classification") == side_effect_classification
        assert endpoint.get("used_by") == used_by


def test_public_terminal_openapi_declares_no_public_training_prediction_or_real_api_default() -> None:
    for endpoint in _endpoints_by_key().values():
        side_effects = endpoint.get("side_effects")
        assert isinstance(side_effects, dict), endpoint
        for flag in PUBLIC_SIDE_EFFECT_FLAGS:
            assert side_effects.get(flag) is False, (endpoint.get("path"), flag)


def test_public_terminal_error_payload_contract_is_sanitized_and_consistent() -> None:
    payload = _openapi_payload()
    error_schema = payload.get("error_schema")
    assert isinstance(error_schema, dict)

    properties = error_schema.get("properties")
    assert isinstance(properties, dict)
    assert REQUIRED_ERROR_FIELDS.issubset(properties)
    assert set(error_schema.get("required", [])) == REQUIRED_ERROR_FIELDS

    for endpoint in _endpoints_by_key().values():
        endpoint_error = endpoint.get("error_schema")
        assert isinstance(endpoint_error, dict)
        endpoint_properties = endpoint_error.get("properties")
        assert isinstance(endpoint_properties, dict)
        assert REQUIRED_ERROR_FIELDS.issubset(endpoint_properties)


def test_public_terminal_schema_contract_never_names_raw_secret_fields() -> None:
    text = "\n".join(_walk_strings(_openapi_payload())).lower()
    leaked_terms = sorted(term for term in FORBIDDEN_RAW_SECRET_TERMS if term in text)
    assert leaked_terms == []


def test_public_terminal_frontend_manifest_client_types_and_pages_match_openapi() -> None:
    manifest = (PUBLIC_TERMINAL_DIR / "endpointManifest.ts").read_text(encoding="utf-8")
    api_client = (PUBLIC_TERMINAL_DIR / "api.ts").read_text(encoding="utf-8")
    types = (PUBLIC_TERMINAL_DIR / "types.ts").read_text(encoding="utf-8")

    for method, path, response_schema_name, side_effect_classification, used_by in EXPECTED_ENDPOINTS:
        assert path in manifest
        assert f'method: "{method}"' in manifest
        assert f'responseSchemaName: "{response_schema_name}"' in manifest
        assert f'sideEffectClassification: "{side_effect_classification}"' in manifest
        for page in used_by:
            assert page in manifest
        assert response_schema_name in api_client or path == "/api/public-terminal/openapi.json"
        assert f"export interface {response_schema_name}" in types or f"export type {response_schema_name}" in types

    assert "PublicApiErrorPayload" in types
    assert "details_sanitized" in types


def test_public_terminal_pages_do_not_directly_fetch_public_endpoints() -> None:
    violations: list[str] = []
    direct_public_endpoint = re.compile(r"fetch\(\s*[`'\"]([^`'\"]*)/api/public-terminal")
    direct_client_import = re.compile(r"from\s+[\"']\.\./api/client[\"']")

    for path in PUBLIC_TERMINAL_DIR.rglob("*.tsx"):
        source = path.read_text(encoding="utf-8")
        if direct_public_endpoint.search(source) or direct_client_import.search(source):
            violations.append(str(path))

    assert violations == []


def test_public_terminal_openapi_json_is_serializable() -> None:
    json.dumps(_openapi_payload(), ensure_ascii=True, sort_keys=True)
