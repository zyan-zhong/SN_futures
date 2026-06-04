from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "frontend" / "src"


def _read(relative: str) -> str:
    return (SRC / relative).read_text(encoding="utf-8")


def test_config_handoff_api_helpers_and_types_exist() -> None:
    api = _read("api/terminal.ts")
    types = _read("api/types.ts")

    assert "ManagedProxyConfigHandoffPayload" in types
    assert "getManagedProxyConfigHandoff" in api
    assert "refreshManagedProxyConfigHandoff" in api
    assert '"/api/terminal/managed-proxy/config-handoff"' in api
    assert '"/api/terminal/managed-proxy/refresh-config-handoff"' in api


def test_config_handoff_card_is_visible_and_safe() -> None:
    onboarding = _read("pages/DataOnboardingPage.tsx")
    checklist = _read("components/setup/GuidedSetupChecklist.tsx")
    handoff = _read("components/setup/ManagedProxyConfigHandoffCard.tsx")

    assert "ManagedProxyConfigHandoffCard" in onboarding
    assert "ManagedProxyConfigHandoffCard" in checklist
    assert "Secure Configuration Handoff" in handoff
    assert "endpoint_configured" in handoff
    assert "token_configured" in handoff
    assert "token_masked" in handoff
    assert "copy_safe_setup_commands" in handoff
    assert "<paste-token-only-in-your-local-shell>" in handoff
    assert "Do not paste token into ChatGPT, Codex, commits, logs, or screenshots." in handoff
    assert "tabIndex={0}" in handoff
    assert "aria-label={`Copy safe placeholder command" in handoff

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
