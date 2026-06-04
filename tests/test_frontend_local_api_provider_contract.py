from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "frontend" / "src"


def _read(relative: str) -> str:
    return (SRC / relative).read_text(encoding="utf-8")


def test_local_api_provider_frontend_contract() -> None:
    api = _read("api/terminal.ts")
    types = _read("api/types.ts")
    onboarding = _read("pages/DataOnboardingPage.tsx")
    checklist = _read("components/setup/GuidedSetupChecklist.tsx")
    local_card = _read("components/setup/LocalApiProviderHandoffCard.tsx")

    assert "LocalApiProviderHubPayload" in types
    assert "ProviderCredentialsPayload" in types
    assert "ProviderSmokePayload" in types
    assert "getLocalApiProviderHub" in api
    assert "getProviderCredentials" in api
    assert "runProviderSmokeTest" in api
    assert "LocalApiProviderHandoffCard" in onboarding
    assert "LocalApiProviderHandoffCard" in checklist
    assert "local_api_provider" in local_card
    assert "local install / API provider mode" in local_card
    assert "configure_local_api_provider_credentials" in local_card
    assert "SN_TWELVEDATA_API_KEY" in local_card
    assert "<paste-key-only-in-your-local-shell>" in local_card
    assert "research_only" in local_card

    combined = "\n".join([onboarding, checklist, local_card])
    for forbidden in [
        "managed_proxy_server",
        "You need a managed proxy server",
        "type=\"password\"",
        "name=\"token\"",
        "name=\"key\"",
        "Save key",
        "save key",
        "Save token",
        "save token",
    ]:
        assert forbidden not in combined
