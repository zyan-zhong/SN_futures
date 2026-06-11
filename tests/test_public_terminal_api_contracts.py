from __future__ import annotations

import sys


sys.path.insert(0, "src")

from sn_futures.api.terminal_api import handle_terminal_api


EXPECTED_PUBLIC_ENDPOINTS = [
    ("GET", "/api/public-terminal/readiness", "PublicReadinessPayload", "read_only"),
    ("GET", "/api/public-terminal/settings/status", "PublicSettingsStatus", "read_only"),
    ("POST", "/api/public-terminal/settings/save", "PublicSettingsSavePayload", "writes_settings"),
    ("POST", "/api/public-terminal/settings/reset", "PublicSettingsSavePayload", "writes_settings"),
    ("POST", "/api/public-terminal/provider-smoke", "PublicSmokePayload", "diagnostic_only"),
    ("POST", "/api/public-terminal/provider-smoke-real", "PublicSmokePayload", "diagnostic_only"),
    ("POST", "/api/public-terminal/refresh-data-status", "PublicTaskPayload", "starts_task"),
    ("GET", "/api/public-terminal/tasks/{task_id}", "PublicTaskPayload", "read_only"),
    ("POST", "/api/public-terminal/tasks/{task_id}/cancel", "PublicTaskCancelPayload", "starts_task"),
    ("GET", "/api/public-terminal/market", "PublicMarketPayload", "read_only"),
    ("GET", "/api/public-terminal/events", "PublicEventsPayload", "read_only"),
    ("GET", "/api/public-terminal/report", "PublicReportPayload", "read_only"),
]


FORBIDDEN_FLAGS = {
    "training",
    "prediction",
    "backtest",
    "feature_store",
    "production_cache_write",
    "legacy_refresh_all",
}


def _docs_payload() -> dict:
    status, payload = handle_terminal_api("/api/terminal/docs", "GET", {}, None)
    assert status == 200
    return payload


def _public_docs_by_path() -> dict[tuple[str, str], dict]:
    docs = _docs_payload()
    endpoints = docs.get("endpoints")
    assert isinstance(endpoints, list)
    return {
        (str(item.get("method")), str(item.get("path"))): item
        for item in endpoints
        if isinstance(item, dict) and str(item.get("path", "")).startswith("/api/public-terminal/")
    }


def test_public_terminal_endpoints_are_documented_with_contract_metadata() -> None:
    by_path = _public_docs_by_path()

    missing = [(method, path) for method, path, _, _ in EXPECTED_PUBLIC_ENDPOINTS if (method, path) not in by_path]
    assert missing == []

    for method, path, response_schema_name, side_effect_classification in EXPECTED_PUBLIC_ENDPOINTS:
        item = by_path[(method, path)]
        assert item.get("summary"), path
        assert item.get("description"), path
        assert item.get("response_schema_name") == response_schema_name
        assert item.get("classification") == "public"
        assert item.get("side_effect_classification") == side_effect_classification

        forbidden = item.get("forbidden_side_effects")
        assert isinstance(forbidden, dict), path
        assert FORBIDDEN_FLAGS.issubset(forbidden), path
        assert all(forbidden[flag] is True for flag in FORBIDDEN_FLAGS), path


def test_public_terminal_response_schemas_are_listed_in_backend_docs() -> None:
    docs = _docs_payload()
    schemas = docs.get("response_schemas")
    assert isinstance(schemas, dict)

    expected_schema_names = {schema_name for _, _, schema_name, _ in EXPECTED_PUBLIC_ENDPOINTS}
    missing = sorted(expected_schema_names - set(schemas))
    assert missing == []

    for schema_name in expected_schema_names:
        schema = schemas[schema_name]
        assert isinstance(schema, dict)
        assert schema.get("type") == "object"
        assert schema.get("properties"), schema_name


def test_public_terminal_docs_keep_downstream_generation_forbidden() -> None:
    for item in _public_docs_by_path().values():
        forbidden = item["forbidden_side_effects"]
        assert forbidden["training"] is True
        assert forbidden["prediction"] is True
        assert forbidden["backtest"] is True
        assert forbidden["feature_store"] is True
        assert item.get("provider_only") is True or item["side_effect_classification"] != "diagnostic_only"
