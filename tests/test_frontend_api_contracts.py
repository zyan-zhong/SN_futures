from __future__ import annotations

import json
import re
import sys
from pathlib import Path


sys.path.insert(0, "src")

from sn_futures.api.terminal_api import handle_terminal_api


TERMINAL_PATH_RE = re.compile(r'"(/api/terminal/[^"?`]+)')
TERMINAL_TEMPLATE_PREFIX_RE = re.compile(r"`(/api/terminal/[^`?${]+)")


def _terminal_docs_paths() -> set[str]:
    status, payload = handle_terminal_api("/api/terminal/docs", "GET", {}, None)
    assert status == 200
    return {
        str(item.get("path"))
        for item in payload.get("endpoints", [])
        if isinstance(item, dict) and str(item.get("path", "")).startswith("/api/terminal/")
    }


def _terminal_docs_payload() -> dict:
    status, payload = handle_terminal_api("/api/terminal/docs", "GET", {}, None)
    assert status == 200
    return payload


def _frontend_terminal_paths() -> tuple[set[str], set[str]]:
    api_dir = Path("frontend/src/api")
    client_files = [
        path
        for path in api_dir.glob("*.ts")
        if path.name not in {"client.ts", "terminalEndpointManifest.ts"}
    ]
    source = "\n".join(path.read_text(encoding="utf-8") for path in client_files)
    literal_paths = set(TERMINAL_PATH_RE.findall(source))
    template_prefixes = set(TERMINAL_TEMPLATE_PREFIX_RE.findall(source))
    return literal_paths, template_prefixes


def _manifest_paths(export_name: str) -> set[str]:
    manifest = Path("frontend/src/api/terminalEndpointManifest.ts").read_text(encoding="utf-8")
    match = re.search(rf"export const {export_name} = \[(.*?)\] as const;", manifest, flags=re.S)
    assert match, export_name
    return set(re.findall(r'"(/api/terminal/[^"]+)"', match.group(1)))


def test_frontend_package_scripts_do_not_hardcode_local_node_path() -> None:
    package = json.loads(Path("frontend/package.json").read_text(encoding="utf-8"))
    scripts = package.get("scripts", {})

    assert scripts
    for name, command in scripts.items():
        assert "C:\\Progra~1\\nodejs\\node.exe" not in command, name
        assert "C:\\Program Files\\nodejs\\node.exe" not in command, name


def test_frontend_terminal_calls_are_listed_in_backend_docs() -> None:
    docs_paths = _terminal_docs_paths()
    literal_paths, template_prefixes = _frontend_terminal_paths()
    exact_frontend_paths = {path for path in literal_paths | template_prefixes if not path.endswith("/")}

    missing = sorted(exact_frontend_paths - docs_paths)

    assert missing == []


def test_frontend_terminal_calls_are_supported_by_backend_dispatcher() -> None:
    backend = Path("src/sn_futures/api/terminal_api.py").read_text(encoding="utf-8")
    backend_paths = set(re.findall(r'"(/api/terminal/[^"?]+)"', backend))
    literal_paths, template_prefixes = _frontend_terminal_paths()
    exact_frontend_paths = {path for path in literal_paths | template_prefixes if not path.endswith("/")}

    missing = sorted(exact_frontend_paths - backend_paths)

    assert missing == []


def test_backend_docs_paths_have_frontend_client_or_explicit_manifest_status() -> None:
    docs_paths = _terminal_docs_paths()
    literal_paths, template_prefixes = _frontend_terminal_paths()
    frontend_exact_paths = {path for path in literal_paths | template_prefixes if not path.endswith("/")}
    shared_client_paths = _manifest_paths("terminalEndpointsCoveredBySharedClient")
    intentionally_unwrapped_paths = _manifest_paths("terminalEndpointsWithoutDedicatedClient")

    missing = sorted(docs_paths - frontend_exact_paths - shared_client_paths - intentionally_unwrapped_paths)

    assert missing == []


def test_terminal_docs_schema_and_manifest_are_stable() -> None:
    payload = _terminal_docs_payload()
    endpoints = payload.get("endpoints")
    assert payload.get("title")
    assert payload.get("version")
    assert isinstance(endpoints, list)
    assert len(endpoints) > 50

    seen: set[tuple[str, str]] = set()
    for item in endpoints:
        assert isinstance(item, dict)
        assert item.get("method") in {"GET", "POST"}
        path = str(item.get("path", ""))
        assert path.startswith("/api/terminal/") or path.startswith("/api/public-terminal/")
        assert item.get("description")
        key = (str(item["method"]), str(item["path"]))
        assert key not in seen, key
        seen.add(key)

    docs_paths = {path for _, path in seen}
    manifest_paths = _manifest_paths("terminalEndpointsCoveredBySharedClient") | _manifest_paths("terminalEndpointsWithoutDedicatedClient")
    assert sorted(manifest_paths - docs_paths) == []
