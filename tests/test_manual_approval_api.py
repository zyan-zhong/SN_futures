from __future__ import annotations

import json
import unittest
from unittest.mock import patch

import sys

sys.path.insert(0, "src")

from sn_futures.api.terminal_api import TERMINAL_API_DOCS, handle_terminal_api  # noqa: E402


class ManualApprovalApiTest(unittest.TestCase):
    def test_docs_expose_manual_approval_endpoints(self) -> None:
        paths = {entry["path"] for entry in TERMINAL_API_DOCS["endpoints"]}

        self.assertIn("/api/terminal/governance/manual-approval", paths)
        self.assertIn("/api/terminal/governance/refresh-manual-approval", paths)
        self.assertIn("/api/terminal/governance/create-manual-approval-request", paths)
        self.assertIn("/api/terminal/governance/record-manual-approval-decision", paths)

    def test_get_manual_approval_reads_report_without_training(self) -> None:
        with patch(
            "sn_futures.api.terminal_api.build_manual_approval_status",
            return_value={
                "status": "blocked_by_gates",
                "training_invoked": False,
                "active_updated": False,
                "customer_prediction_generated": False,
            },
            create=True,
        ):
            status, payload = handle_terminal_api("/api/terminal/governance/manual-approval", method="GET")

        self.assertEqual(status, 200)
        self.assertFalse(payload["training_invoked"])
        self.assertFalse(payload["active_updated"])
        self.assertFalse(payload["customer_prediction_generated"])

    def test_create_manual_approval_request_does_not_allow_active_publish(self) -> None:
        with patch(
            "sn_futures.api.terminal_api.create_manual_approval_request",
            return_value={
                "status": "blocked_by_gates",
                "requested_action": "active_publish",
                "approval_request_allowed": False,
                "active_write_allowed": False,
                "customer_prediction_write_allowed": False,
                "training_invoked": False,
                "active_updated": False,
                "customer_prediction_generated": False,
            },
            create=True,
        ):
            status, payload = handle_terminal_api(
                "/api/terminal/governance/create-manual-approval-request",
                method="POST",
                body=json.dumps({"requested_action": "active_publish", "candidate_version": "v12"}),
            )

        self.assertEqual(status, 200)
        self.assertFalse(payload["approval_request_allowed"])
        self.assertFalse(payload["active_write_allowed"])
        self.assertFalse(payload["customer_prediction_write_allowed"])
        self.assertFalse(payload["training_invoked"])

    def test_record_manual_approval_decision_requires_report_only_side_effects(self) -> None:
        with patch(
            "sn_futures.api.terminal_api.record_manual_approval_decision",
            return_value={
                "status": "approved_for_shadow_only",
                "two_person_review_pass": True,
                "active_write_allowed": False,
                "customer_prediction_write_allowed": False,
                "training_invoked": False,
                "active_updated": False,
                "customer_prediction_generated": False,
            },
            create=True,
        ):
            status, payload = handle_terminal_api(
                "/api/terminal/governance/record-manual-approval-decision",
                method="POST",
                body=json.dumps(
                    {
                        "decision": "approve",
                        "reviewers": [
                            {"reviewer_id": "alice", "display_name": "Alice"},
                            {"reviewer_id": "bob", "display_name": "Bob"},
                        ],
                    }
                ),
            )

        self.assertEqual(status, 200)
        self.assertTrue(payload["two_person_review_pass"])
        self.assertFalse(payload["active_write_allowed"])
        self.assertFalse(payload["customer_prediction_write_allowed"])
        self.assertFalse(payload["active_updated"])
        self.assertFalse(payload["customer_prediction_generated"])


if __name__ == "__main__":
    unittest.main()
