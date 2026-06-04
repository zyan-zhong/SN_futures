from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend" / "src"


class FrontendWorkspaceGuardAuditContractTest(unittest.TestCase):
    def test_workspace_guard_helpers_exist_and_forbid_primary_prediction_actions(self) -> None:
        helper = (FRONTEND / "utils" / "workspaceGuards.ts").read_text(encoding="utf-8")

        for name in [
            "deriveWorkspaceCtaState",
            "deriveRouteAccessSummary",
            "deriveBlockedWorkspaceBanner",
            "assertNoForbiddenPrimaryActions",
            "groupSafeActionsByWorkspace",
        ]:
            self.assertIn(f"export function {name}", helper)

        for forbidden in [
            "generate customer prediction",
            "live prediction",
            "customer-visible output path",
            "active publish",
            "build Feature Store v12",
            "run candidate",
        ]:
            self.assertIn(forbidden, helper)

        self.assertIn("prediction_generation_allowed: false", helper)
        self.assertIn("active_publish_allowed: false", helper)

    def test_key_workspace_pages_use_unified_guard_banner(self) -> None:
        banner = (FRONTEND / "components" / "common" / "WorkspaceGuardBanner.tsx").read_text(encoding="utf-8")
        for label in [
            "current_state",
            "next_allowed_action",
            "prediction_generation_allowed",
            "active_publish_allowed",
            "no-active confirmation",
            "no-prediction confirmation",
        ]:
            self.assertIn(label, banner)

        for relative in [
            "pages/TerminalOverviewPage.tsx",
            "pages/PredictionWorkspacePage.tsx",
            "pages/DataOnboardingPage.tsx",
            "pages/CandidateResearchPage.tsx",
            "pages/ResearchArchivePage.tsx",
            "pages/GovernanceConsolePage.tsx",
        ]:
            page = (FRONTEND / relative).read_text(encoding="utf-8")
            self.assertIn("WorkspaceGuardBanner", page, relative)

    def test_prediction_workspace_has_no_forbidden_cta_or_customer_path(self) -> None:
        page = (FRONTEND / "pages" / "PredictionWorkspacePage.tsx").read_text(encoding="utf-8").lower()

        for required in ["blocked", "required gates", "blocking reasons", "next_allowed_action"]:
            self.assertIn(required, page)
        for forbidden in [
            "generate customer prediction",
            "live prediction",
            "customer-visible output path",
            "getpredictions",
            "refreshpredictions",
            "postjson",
        ]:
            self.assertNotIn(forbidden, page)

    def test_data_onboarding_and_archive_default_to_collapsed_no_run_buttons(self) -> None:
        data_page = (FRONTEND / "pages" / "DataOnboardingPage.tsx").read_text(encoding="utf-8")
        archive = (FRONTEND / "pages" / "ResearchArchivePage.tsx").read_text(encoding="utf-8")

        self.assertIn("Managed Proxy -> Production Cache -> v12 chain", data_page)
        self.assertIn("Detailed data source cards", data_page)
        self.assertIn("<details", data_page)
        self.assertNotIn("<details open", data_page)
        for forbidden in ["build Feature Store v12", "run candidate", "prediction button"]:
            self.assertNotIn(forbidden, data_page)

        self.assertIn("Archived Candidates", archive)
        self.assertIn("<details", archive)
        self.assertNotIn("<details open", archive)
        self.assertIn("research-only/no-active/no-prediction", archive)
        self.assertNotIn("Run candidate_", archive)

    def test_task_center_labels_stale_train_failure_as_research_task(self) -> None:
        task_bar = (FRONTEND / "components" / "task" / "GlobalTaskBar.tsx").read_text(encoding="utf-8")
        service = (ROOT / "src" / "sn_futures" / "services" / "task_notification_service.py").read_text(encoding="utf-8")

        self.assertIn("Task Notification Center", task_bar)
        self.assertIn("stale_failure_suppressed", task_bar)
        self.assertIn("latest failed research task", task_bar)
        self.assertIn("research task", service)
        self.assertIn("is_prediction_failure", service)


if __name__ == "__main__":
    unittest.main()
