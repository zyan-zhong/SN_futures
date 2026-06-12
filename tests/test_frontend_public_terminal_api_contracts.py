from __future__ import annotations

import re
import sys
from pathlib import Path


sys.path.insert(0, "src")

from sn_futures.public_terminal.schema import build_public_terminal_openapi


PUBLIC_TERMINAL_DIR = Path("frontend/src/public_terminal")
FRONTEND_SRC_DIR = Path("frontend/src")


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _backend_endpoints() -> list[dict[str, object]]:
    endpoints = build_public_terminal_openapi().get("endpoints")
    assert isinstance(endpoints, list)
    return [endpoint for endpoint in endpoints if isinstance(endpoint, dict)]


def _manifest_entry_body(source: str, path: str) -> str:
    match = re.search(r"\{[^{}]*path:\s*\"" + re.escape(path) + r"\"[\s\S]*?\n\s*\}", source)
    assert match, path
    return match.group(0)


def test_public_terminal_endpoint_manifest_maps_clients_types_and_pages() -> None:
    manifest_path = PUBLIC_TERMINAL_DIR / "endpointManifest.ts"
    assert manifest_path.exists()
    source = _read(manifest_path)

    assert "publicTerminalEndpointManifest" in source
    for endpoint in _backend_endpoints():
        path = str(endpoint["path"])
        body = _manifest_entry_body(source, path)
        assert f'method: "{endpoint["method"]}"' in body
        assert f'clientFunction: "{endpoint["client_function"]}"' in body
        assert f'responseSchemaName: "{endpoint["response_schema_name"]}"' in body
        assert 'classification: "public"' in body
        assert f'sideEffectClassification: "{endpoint["side_effect_classification"]}"' in body
        assert "forbiddenSideEffects:" in body
        assert "usedBy:" in body


def test_public_terminal_api_client_has_all_manifested_functions_and_paths() -> None:
    source = _read(PUBLIC_TERMINAL_DIR / "api.ts")

    for endpoint in _backend_endpoints():
        path = str(endpoint["path"])
        assert f"export function {endpoint['client_function']}" in source
        if "{task_id}" in path:
            prefix, suffix = path.split("{task_id}")
            assert prefix in source
            assert suffix in source
        else:
            assert path in source
        assert str(endpoint["response_schema_name"]) in source

    assert "allow_remote: false" in source


def test_public_terminal_response_types_exist_and_do_not_allow_raw_secrets() -> None:
    source = _read(PUBLIC_TERMINAL_DIR / "types.ts")

    for endpoint in _backend_endpoints():
        response_type = str(endpoint["response_schema_name"])
        assert f"export interface {response_type}" in source or f"export type {response_type}" in source

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


def test_public_terminal_e2e_mocks_only_manifested_public_endpoints() -> None:
    known = {str(endpoint["path"]) for endpoint in _backend_endpoints()}
    dynamic_task = "/api/public-terminal/tasks/{task_id}"
    dynamic_task_cancel = "/api/public-terminal/tasks/{task_id}/cancel"
    violations: list[str] = []
    for path in Path("frontend/e2e").glob("*.spec.ts"):
        source = _read(path)
        for mocked_path in re.findall(r'path\s*={2,3}\s*"(/api/public-terminal/[^"]+)"', source):
            normalized = mocked_path
            if re.fullmatch(r"/api/public-terminal/tasks/[^/]+", mocked_path):
                normalized = dynamic_task
            elif re.fullmatch(r"/api/public-terminal/tasks/[^/]+/cancel", mocked_path):
                normalized = dynamic_task_cancel
            if normalized not in known:
                violations.append(f"{path}:{mocked_path}")

    assert violations == []


def test_public_terminal_e2e_mocks_preserve_error_and_blocking_shape_terms() -> None:
    public_e2e_sources = "\n".join(
        _read(path)
        for path in Path("frontend/e2e").glob("*.spec.ts")
        if "/api/public-terminal/" in _read(path)
    )

    assert "blocking_reasons" in public_e2e_sources
    assert "error_code" in public_e2e_sources or "reason" in public_e2e_sources
    for flag in ("training_invoked", "prediction_generated", "backtest_invoked"):
        assert flag in public_e2e_sources
