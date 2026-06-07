from __future__ import annotations

import re
import sys
from pathlib import Path


sys.path.insert(0, "src")

from sn_futures.api.terminal_api import handle_terminal_api


FRONTEND_API_DIR = Path("frontend/src/api")
DOMAIN_TYPE_MODULES = {
    "market": FRONTEND_API_DIR / "types" / "market.ts",
    "events": FRONTEND_API_DIR / "types" / "events.ts",
    "features": FRONTEND_API_DIR / "types" / "features.ts",
    "models": FRONTEND_API_DIR / "types" / "models.ts",
    "backtest": FRONTEND_API_DIR / "types" / "backtest.ts",
    "settings": FRONTEND_API_DIR / "types" / "settings.ts",
    "tasks": FRONTEND_API_DIR / "types" / "tasks.ts",
}


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _terminal_docs_paths() -> set[str]:
    status, payload = handle_terminal_api("/api/terminal/docs", "GET", {}, None)
    assert status == 200
    return {
        str(item.get("path"))
        for item in payload.get("endpoints", [])
        if isinstance(item, dict) and item.get("path")
    }


def _manifest_array_paths(source: str, export_name: str) -> set[str]:
    match = re.search(rf"export const {export_name} = \[(.*?)\] as const;", source, flags=re.S)
    assert match, export_name
    return set(re.findall(r'"(/api/terminal/[^"]+)"', match.group(1)))


def _manifest_domain_paths(source: str) -> tuple[dict[str, set[str]], set[str]]:
    match = re.search(r"export const terminalEndpointDomains = \{(.*?)\} as const;", source, flags=re.S)
    assert match, "terminalEndpointDomains"
    body = match.group(1)
    domains: dict[str, set[str]] = {}
    for domain, array_body in re.findall(r"(\w+):\s*\[(.*?)\]", body, flags=re.S):
        domains[domain] = set(re.findall(r'"(/api/terminal/[^"]+)"', array_body))
    all_paths = {path for paths in domains.values() for path in paths}
    return domains, all_paths


def _client_paths() -> set[str]:
    client_files = [
        path
        for path in FRONTEND_API_DIR.glob("*.ts")
        if path.name not in {"client.ts", "terminalEndpointManifest.ts"}
    ]
    source = "\n".join(_read(path) for path in client_files)
    literal_paths = set(re.findall(r'"(/api/terminal/[^"?`]+)', source))
    template_prefixes = set(re.findall(r"`(/api/terminal/[^`?${]+)", source))
    return {path for path in literal_paths | template_prefixes if not path.endswith("/")}


def test_frontend_api_types_are_split_by_terminal_domain() -> None:
    missing = [str(path) for path in DOMAIN_TYPE_MODULES.values() if not path.exists()]
    assert missing == []

    root_types = _read(FRONTEND_API_DIR / "types.ts")
    assert 'from "./types/backtest"' in root_types
    assert "export interface AuditableBacktestPayload" not in root_types
    assert "export interface BacktestManifest" not in root_types


def test_backtest_client_is_split_from_terminal_client() -> None:
    terminal = _read(FRONTEND_API_DIR / "terminal.ts")
    backtest = _read(FRONTEND_API_DIR / "backtest.ts")

    assert 'from "./backtest"' in terminal
    for function_name in (
        "getBacktestDiagnostics",
        "runResearchBacktest",
        "getAuditableResearchBacktest",
        "getResearchBacktestReport",
        "getResearchEquityCurve",
        "optimizeResearchStrategy",
    ):
        assert f"export function {function_name}" not in terminal
        assert f"export function {function_name}" in backtest


def test_backend_docs_and_frontend_domain_manifest_are_bidirectional() -> None:
    manifest = _read(FRONTEND_API_DIR / "terminalEndpointManifest.ts")
    domains, domain_paths = _manifest_domain_paths(manifest)
    expected_domains = {"market", "events", "features", "models", "backtest", "settings", "tasks"}
    assert set(domains) == expected_domains
    assert all(domains[domain] for domain in expected_domains)

    docs_paths = _terminal_docs_paths()
    client_paths = _client_paths()
    shared_paths = _manifest_array_paths(manifest, "terminalEndpointsCoveredBySharedClient")
    intentionally_unwrapped_paths = _manifest_array_paths(manifest, "terminalEndpointsWithoutDedicatedClient")

    assert sorted(domain_paths - docs_paths) == []
    assert sorted(client_paths - docs_paths) == []
    assert sorted(docs_paths - client_paths - domain_paths - shared_paths - intentionally_unwrapped_paths) == []
