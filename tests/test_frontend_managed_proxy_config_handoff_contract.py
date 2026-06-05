from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "frontend" / "src"


def _read(relative: str) -> str:
    return (SRC / relative).read_text(encoding="utf-8")


def test_config_handoff_api_helpers_and_types_exist() -> None:
    api = _read("api/terminal.ts")
    types = _read("api/types.ts")

    assert "LocalApiProviderHubPayload" in types
    assert "getLocalApiProviderHub" in api
    assert "refreshLocalApiProviderHub" in api
    assert '"/api/terminal/local-api-provider/hub"' in api
    assert '"/api/terminal/local-api-provider/refresh-hub"' in api

    # Legacy managed-proxy helpers remain as backward-compatible diagnostics,
    # but Local API Provider Hub is the primary configuration path.
    assert "ManagedProxyConfigHandoffPayload" in types
    assert "getManagedProxyConfigHandoff" in api
    assert "refreshManagedProxyConfigHandoff" in api
    assert '"/api/terminal/managed-proxy/config-handoff"' in api
    assert '"/api/terminal/managed-proxy/refresh-config-handoff"' in api


def test_config_handoff_card_is_visible_and_safe() -> None:
    onboarding = _read("pages/DataOnboardingPage.tsx")
    checklist = _read("components/setup/GuidedSetupChecklist.tsx")
    handoff = _read("components/setup/LocalApiProviderHandoffCard.tsx")

    assert "LocalApiProviderHandoffCard" in onboarding
    assert "LocalApiProviderHandoffCard" in checklist
    assert "Local API Provider Hub" in handoff
    assert "provider_credentials_status" in handoff
    assert "key_configured" in handoff
    assert "key_masked" in handoff
    assert "copy_safe_setup_commands" in handoff
    assert "<paste-key-only-in-your-local-shell>" in handoff
    assert "Do not paste API keys into ChatGPT, Codex, commits, logs, issues, screenshots, or reports." in handoff
    assert "tabIndex={0}" in handoff
    assert "aria-label={`Copy local API provider placeholder command" in handoff

    combined = "\n".join([onboarding, checklist, handoff])
    for forbidden in [
        "type=\"password\"",
        "name=\"token\"",
        "Save token",
        "save token",
        "customer prediction",
        "Publish active",
    ]:
        assert forbidden not in combined
