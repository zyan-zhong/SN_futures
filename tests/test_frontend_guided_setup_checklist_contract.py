from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "frontend" / "src"


def _read(relative: str) -> str:
    return (SRC / relative).read_text(encoding="utf-8")


def test_guided_setup_helpers_and_components_exist() -> None:
    helper = _read("utils/guidedSetup.ts")

    for name in [
        "deriveSetupChecklist",
        "deriveGuidedEmptyState",
        "deriveSafeConfigSteps",
        "deriveBlockedPredictionExplanation",
    ]:
        assert f"export function {name}" in helper

    for phrase in [
        "Configure Local API Provider credentials",
        "Review setup runbook",
        "Run Provider Smoke Test",
        "Schema Mapping / Sample Fixture Contract",
        "PIT Replay / PIT Audit",
        "Data Quality",
        "v12 input contract / controlled build plan",
    ]:
        assert phrase in helper

    for relative in [
        "components/setup/GuidedSetupChecklist.tsx",
        "components/setup/LocalApiProviderHandoffCard.tsx",
        "components/setup/PredictionBlockedEmptyState.tsx",
        "components/setup/NextActionStepper.tsx",
        "components/setup/SafeConfigInstructions.tsx",
    ]:
        assert (SRC / relative).exists(), relative


def test_guided_setup_copy_is_safe_and_user_facing() -> None:
    combined = "\n".join(
        _read(relative)
        for relative in [
            "utils/guidedSetup.ts",
            "components/setup/GuidedSetupChecklist.tsx",
            "components/setup/LocalApiProviderHandoffCard.tsx",
            "components/setup/PredictionBlockedEmptyState.tsx",
            "components/setup/NextActionStepper.tsx",
            "components/setup/SafeConfigInstructions.tsx",
        ]
    )

    for phrase in [
        "Prediction is blocked",
        "No active model exists.",
        "No customer prediction exists.",
        "Local API provider credentials are not configured.",
        "Feature Store v12 has not been built.",
        "No candidate has passed all gates.",
        "Do not paste API keys into ChatGPT",
        "Do not paste API keys into Codex",
        "Do not write API keys into commits",
        "logs",
        "View safe config instructions",
        "Refresh read-only status",
        "Run sample fixture contract",
    ]:
        assert phrase in combined

    for forbidden in [
        'type="password"',
        'name="token"',
        'name="api_key"',
        'name="key"',
        "managed_proxy_server",
        ">Generate customer prediction<",
        ">Publish active<",
        ">Run candidate<",
        ">Build Feature Store v12<",
    ]:
        assert forbidden not in combined


def test_setup_stepper_accessibility_and_disabled_reasons() -> None:
    checklist = _read("components/setup/GuidedSetupChecklist.tsx")
    stepper = _read("components/setup/NextActionStepper.tsx")
    prediction = _read("components/setup/PredictionBlockedEmptyState.tsx")

    assert 'aria-label="Setup Checklist"' in checklist
    assert "aria-current" in stepper
    assert "tabIndex={0}" in stepper
    assert "disabled-action-list" in prediction
    assert "Disabled reason" in prediction


def test_workspace_pages_render_guided_empty_states() -> None:
    expectations = {
        "pages/TerminalOverviewPage.tsx": ["GuidedSetupChecklist", "SafeConfigInstructions"],
        "pages/PredictionWorkspacePage.tsx": ["PredictionBlockedEmptyState", "GuidedSetupChecklist"],
        "pages/DataOnboardingPage.tsx": ["LocalApiProviderHandoffCard", "GuidedSetupChecklist"],
    }

    for relative, names in expectations.items():
        source = _read(relative)
        for name in names:
            assert name in source, f"{relative} should render {name}"


def test_guided_setup_sources_do_not_show_invalid_literals_or_forbidden_ctas() -> None:
    combined = "\n".join(
        _read(relative)
        for relative in [
            "utils/guidedSetup.ts",
            "components/setup/GuidedSetupChecklist.tsx",
            "components/setup/LocalApiProviderHandoffCard.tsx",
            "components/setup/PredictionBlockedEmptyState.tsx",
        ]
    )

    for forbidden in ['"undefined"', '"null"', '"NaN"', ">undefined<", ">null<", ">NaN<", "customer-visible output path", "active publish primary"]:
        assert forbidden not in combined


def test_guided_setup_uses_dynamic_status_endpoint_and_safe_action_wiring() -> None:
    checklist = _read("components/setup/GuidedSetupChecklist.tsx")
    stepper = _read("components/setup/NextActionStepper.tsx")
    api = _read("api/terminal.ts")
    types = _read("api/types.ts")

    assert "getSetupChecklistStatus" in checklist
    assert "runSetupChecklistSafeAction" in checklist
    assert '"/api/terminal/setup-checklist/status"' in api
    assert '"/api/terminal/setup-checklist/run-safe-action"' in api
    assert "SetupChecklistStatusPayload" in types
    assert "SetupChecklistStepPayload" in types
    assert "action_enabled" in checklist
    assert "action_disabled_reason" in checklist
    assert "aria-describedby" in checklist
    assert "setup_action_telemetry" in checklist
    assert "latest_action_status" in checklist
    assert "setup_action_history" in checklist
    assert "safe_action_id" in stepper
    assert "aria-current" in stepper


def test_setup_action_telemetry_surfaces_in_overview_prediction_and_task_center() -> None:
    overview = _read("pages/TerminalOverviewPage.tsx")
    prediction = _read("pages/PredictionWorkspacePage.tsx")
    task_bar = _read("components/task/GlobalTaskBar.tsx")
    types = _read("api/types.ts")

    assert "setup_action_telemetry" in overview
    assert "setup_action_telemetry" in prediction
    assert "setup_action_history" in task_bar
    assert "latest_action_status" in task_bar
    assert "SetupActionTelemetryPayload" in types
    assert "SetupActionRunPayload" in types


def test_guided_setup_safe_action_surface_excludes_forbidden_actions() -> None:
    combined = "\n".join(
        _read(relative)
        for relative in [
            "components/setup/GuidedSetupChecklist.tsx",
            "components/setup/NextActionStepper.tsx",
            "api/terminal.ts",
        ]
    )

    assert "run_sample_fixture_contract" in combined
    assert "refresh_operator_runbook" in combined
    assert "refresh_provider_credentials" in combined
    assert "run_provider_smoke" in combined
    for forbidden in [
        "build_feature_store_v12",
        "run_v12_controlled_build",
        "build_training_dataset_v12",
        "train_candidate",
        "run_candidate_v12",
        "promote_model",
        "write_active_model",
        "generate_customer_prediction",
        "write_token",
        "custom_output_path",
    ]:
        assert forbidden not in combined
