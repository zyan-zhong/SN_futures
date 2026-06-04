from __future__ import annotations

from pathlib import Path


API_FILE = Path("frontend/src/api/terminal.ts")
PAGE_DIR = Path("frontend/src/pages")
COMPONENT_DIR = Path("frontend/src/components")


def _frontend_text() -> str:
    files = list(PAGE_DIR.glob("*.tsx")) + list(COMPONENT_DIR.rglob("*.tsx"))
    return "\n".join(path.read_text(encoding="utf-8") for path in files)


def test_main_button_handlers_map_to_terminal_api_helpers() -> None:
    terminal_api = API_FILE.read_text(encoding="utf-8")
    frontend = _frontend_text()

    required_helpers = [
        "refreshMarket",
        "refreshNews",
        "runRefreshTask",
        "testProvider",
        "exportDiagnosticsBundle",
        "buildTrainingDataset",
        "buildFeatureStore",
        "getFeatureStoreStatus",
        "getCandidateV6Readiness",
        "runResearchBacktest",
        "generateFullSystemTxtReport",
        "buildSystemRepairPlan",
        "saveSettingsSecrets",
        "getKeyDiagnostics",
    ]

    for helper in required_helpers:
        assert helper in terminal_api, f"{helper} must be exported by terminal API client"
        assert helper in frontend, f"{helper} must be used by a terminal button handler"


def test_reusable_button_audit_components_exist_and_are_importable() -> None:
    for component in [
        "ButtonWithTaskState.tsx",
        "CompactProviderCard.tsx",
        "CompactReasonList.tsx",
        "TechnicalDetailsDrawer.tsx",
        "PageActionBar.tsx",
    ]:
        assert Path("frontend/src/components/common", component).exists()


def test_heavy_terminal_buttons_have_loading_and_duplicate_click_guards() -> None:
    frontend = _frontend_text()

    guarded_handlers = [
        "handleRunResearchBacktest",
        "handleRefreshMarket",
        "handleBuildDataset",
        "handleRunExperiment",
        "handleRunLearningScheduler",
        "handleRunCandidateV3",
        "handleRunCandidateV4",
        "handleRunCandidateV6",
        "generateFullReport",
        "generateRepairPlan",
    ]
    for handler in guarded_handlers:
        assert handler in frontend

    for state_name in [
        "researchLoading",
        "isRefreshing",
        "building",
        "loading",
        "reportBusy",
        "repairPlanBusy",
        "running",
    ]:
        assert f"disabled={{{state_name}" in frontend or f"disabled={{Boolean({state_name})" in frontend


def test_failures_render_error_state_or_visible_status_message() -> None:
    frontend = _frontend_text()

    assert frontend.count("ErrorState") >= 8
    for failure_copy in ["setMessage(exc instanceof Error", "setError(err.message", "catch (error)"]:
        assert failure_copy in frontend
