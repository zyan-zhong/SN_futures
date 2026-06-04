from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend" / "src"


class FrontendTerminalWorkspaceNavigationContractTest(unittest.TestCase):
    def test_workspace_routes_and_sidebar_entries_exist(self) -> None:
        app = (FRONTEND / "App.tsx").read_text(encoding="utf-8")
        sidebar = (FRONTEND / "components" / "layout" / "SimpleSidebar.tsx").read_text(encoding="utf-8")

        for page_name in [
            "TerminalOverviewPage",
            "PredictionWorkspacePage",
            "DataOnboardingPage",
            "CandidateResearchPage",
            "ResearchArchivePage",
        ]:
            self.assertIn(page_name, app)

        for key in ["terminal-overview", "prediction-workspace", "data-onboarding", "candidate-research", "research-archive"]:
            self.assertIn(f'"{key}"', app)
            self.assertIn(f'"{key}"', sidebar)

    def test_terminal_overview_is_current_state_only(self) -> None:
        page = (FRONTEND / "pages" / "TerminalOverviewPage.tsx").read_text(encoding="utf-8")

        for phrase in [
            "Current State",
            "Prediction Workspace summary",
            "next_allowed_action",
            "Managed Proxy / v12 chain",
            "No-active / no-prediction confirmation",
            "Latest blocking reasons",
        ]:
            self.assertIn(phrase, page)

        for forbidden in ["runCandidate", "approveActiveModel", "refreshPredictions", "getPredictions"]:
            self.assertNotIn(forbidden, page)

    def test_prediction_workspace_page_is_blocked_read_only(self) -> None:
        page = (FRONTEND / "pages" / "PredictionWorkspacePage.tsx").read_text(encoding="utf-8")

        for phrase in [
            "Prediction Workspace",
            "prediction_status",
            "prediction_generation_allowed",
            "active_model_available",
            "customer_prediction_generated",
            "required gates",
            "blocking reasons",
            "next_allowed_action",
            "no active model confirmation",
            "no customer prediction confirmation",
        ]:
            self.assertIn(phrase, page)

        for forbidden in [
            "generate customer prediction",
            "live prediction",
            "customer visible output path",
            "refreshPredictions",
            "getPredictions",
            "postJson",
        ]:
            self.assertNotIn(forbidden, page.lower())

    def test_data_onboarding_prioritizes_managed_proxy_v12_chain_and_collapses_details(self) -> None:
        page = (FRONTEND / "pages" / "DataOnboardingPage.tsx").read_text(encoding="utf-8")

        for phrase in [
            "Operator Runbook",
            "Endpoint Smoke",
            "Sample Fixture Contract",
            "Quarantine Snapshot",
            "Quarantine Contract",
            "Backfill Planner",
            "Production Cache Gate",
            "v12 Input Contract",
            "v12 Build Plan",
            "v12 Controlled Build",
        ]:
            self.assertIn(phrase, page)

        self.assertIn("<details", page)
        self.assertNotIn("<details open", page)
        self.assertIn("Detailed data source cards", page)

    def test_candidate_research_and_archive_boundaries(self) -> None:
        candidate = (FRONTEND / "pages" / "CandidateResearchPage.tsx").read_text(encoding="utf-8")
        archive = (FRONTEND / "pages" / "ResearchArchivePage.tsx").read_text(encoding="utf-8")

        for phrase in ["Candidate v12 current blocked summary", "Candidate v10 research-only summary", "Cost/year/CPCV short summary", "no active / no prediction notice"]:
            self.assertIn(phrase, candidate)
        self.assertIn("research-archive", candidate)

        for phrase in ["Archived Candidates", "candidate_v3", "candidate_v4", "candidate_v6", "candidate_v7", "candidate_v8", "candidate_v9", "OOF trace historical panels"]:
            self.assertIn(phrase, archive)
        self.assertIn("<details", archive)
        self.assertNotIn("<details open", archive)
        self.assertNotIn("Run candidate_", archive)
        self.assertIn("Advanced research-only toggle", archive)

    def test_global_task_bar_uses_notification_center_not_persistent_failed_toast(self) -> None:
        task_bar = (FRONTEND / "components" / "task" / "GlobalTaskBar.tsx").read_text(encoding="utf-8")
        api = (FRONTEND / "api" / "terminal.ts").read_text(encoding="utf-8")

        self.assertIn("getTaskNotifications", api)
        self.assertIn("Task Notification Center", task_bar)
        self.assertIn("stale_failure_suppressed", task_bar)
        self.assertIn("research task", task_bar)
        self.assertNotIn("setTask(payload.tasks?.[0]", task_bar)


if __name__ == "__main__":
    unittest.main()
