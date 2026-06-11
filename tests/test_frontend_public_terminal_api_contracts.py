from __future__ import annotations

import re
from pathlib import Path


PUBLIC_TERMINAL_DIR = Path("frontend/src/public_terminal")
FRONTEND_SRC_DIR = Path("frontend/src")

EXPECTED_PUBLIC_ENDPOINTS = [
    {
        "method": "GET",
        "path": "/api/public-terminal/readiness",
        "client": "getPublicReadiness",
        "response_type": "PublicReadinessPayload",
    },
    {
        "method": "GET",
        "path": "/api/public-terminal/settings/status",
        "client": "getPublicSettingsStatus",
        "response_type": "PublicSettingsStatus",
    },
    {
        "method": "POST",
        "path": "/api/public-terminal/settings/save",
        "client": "savePublicSettings",
        "response_type": "PublicSettingsSavePayload",
    },
    {
        "method": "POST",
        "path": "/api/public-terminal/settings/reset",
        "client": "resetPublicSettings",
        "response_type": "PublicSettingsSavePayload",
    },
    {
        "method": "POST",
        "path": "/api/public-terminal/provider-smoke",
        "client": "runPublicProviderSmoke",
        "response_type": "PublicSmokePayload",
    },
    {
        "method": "POST",
        "path": "/api/public-terminal/provider-smoke-real",
        "client": "runPublicProviderSmokeReal",
        "response_type": "PublicSmokePayload",
    },
    {
        "method": "POST",
        "path": "/api/public-terminal/refresh-data-status",
        "client": "startPublicDataRefresh",
        "response_type": "PublicTaskPayload",
    },
    {
        "method": "GET",
        "path": "/api/public-terminal/tasks/{task_id}",
        "client": "getPublicTask",
        "response_type": "PublicTaskPayload",
    },
    {
        "method": "POST",
        "path": "/api/public-terminal/tasks/{task_id}/cancel",
        "client": "cancelPublicTask",
        "response_type": "PublicTaskCancelPayload",
    },
    {
        "method": "GET",
        "path": "/api/public-terminal/market",
        "client": "getPublicMarket",
        "response_type": "PublicMarketPayload",
    },
    {
        "method": "GET",
        "path": "/api/public-terminal/events",
        "client": "getPublicEvents",
        "response_type": "PublicEventsPayload",
    },
    {
        "method": "GET",
        "path": "/api/public-terminal/report",
        "client": "getPublicReport",
        "response_type": "PublicReportPayload",
    },
]


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _manifest_entry_body(source: str, path: str) -> str:
    match = re.search(r"\{[^{}]*path:\s*\"" + re.escape(path) + r"\"[\s\S]*?\n\s*\}", source)
    assert match, path
    return match.group(0)


def test_public_terminal_endpoint_manifest_maps_clients_types_and_pages() -> None:
    manifest_path = PUBLIC_TERMINAL_DIR / "endpointManifest.ts"
    assert manifest_path.exists()
    source = _read(manifest_path)

    assert "publicTerminalEndpointManifest" in source
    for endpoint in EXPECTED_PUBLIC_ENDPOINTS:
        body = _manifest_entry_body(source, endpoint["path"])
        assert f'method: "{endpoint["method"]}"' in body
        assert f'clientFunction: "{endpoint["client"]}"' in body
        assert f'responseSchemaName: "{endpoint["response_type"]}"' in body
        assert 'classification: "public"' in body
        assert "sideEffectClassification:" in body
        assert "forbiddenSideEffects:" in body
        assert "usedBy:" in body


def test_public_terminal_api_client_has_all_manifested_functions_and_paths() -> None:
    source = _read(PUBLIC_TERMINAL_DIR / "api.ts")

    for endpoint in EXPECTED_PUBLIC_ENDPOINTS:
        assert f"export function {endpoint['client']}" in source
        if "{task_id}" in endpoint["path"]:
            prefix, suffix = endpoint["path"].split("{task_id}")
            assert prefix in source
            assert suffix in source
        else:
            assert endpoint["path"] in source
        assert endpoint["response_type"] in source

    assert "allow_remote: false" in source


def test_public_terminal_response_types_exist_and_do_not_allow_raw_secrets() -> None:
    source = _read(PUBLIC_TERMINAL_DIR / "types.ts")

    for endpoint in EXPECTED_PUBLIC_ENDPOINTS:
        assert f"export interface {endpoint['response_type']}" in source or f"export type {endpoint['response_type']}" in source

    forbidden_response_fields = [
        "raw_secret",
        "raw_key",
        "raw_token",
        "authorization",
        "Authorization",
        "headers",
        "api_key",
        "apikey",
    ]
    for field in forbidden_response_fields:
        assert field not in source


def test_public_terminal_pages_do_not_directly_fetch_public_terminal_endpoints() -> None:
    violations: list[str] = []
    for path in PUBLIC_TERMINAL_DIR.glob("*.tsx"):
        source = _read(path)
        if re.search(r"fetch\(\s*[`'\"](/api/public-terminal|[^`'\"]*/api/public-terminal)", source):
            violations.append(str(path))

    assert violations == []


def test_api_error_handling_preserves_error_code_and_blocking_reason() -> None:
    source = _read(Path("frontend/src/api/client.ts"))

    assert "class ApiError" in source or "export class ApiError" in source
    assert "error_code" in source
    assert "blocking_reasons" in source
    assert "payload" in source
    assert "status" in source
    assert re.search(r"throw new ApiError\(", source)
