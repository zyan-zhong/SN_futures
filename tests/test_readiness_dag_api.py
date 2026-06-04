from __future__ import annotations

import json
import unittest
from unittest.mock import patch

import sys

sys.path.insert(0, "src")

from sn_futures.api.terminal_api import TERMINAL_API_DOCS, handle_terminal_api


class ReadinessDagApiTest(unittest.TestCase):
    def test_docs_expose_readiness_dag_endpoints(self) -> None:
        paths = {entry["path"] for entry in TERMINAL_API_DOCS["endpoints"]}

        self.assertIn("/api/terminal/research/readiness-dag", paths)
        self.assertIn("/api/terminal/research/refresh-readiness-dag", paths)
        self.assertIn("/api/terminal/research/run-safe-readiness-checks", paths)

    def test_get_readiness_dag_reads_report_without_training(self) -> None:
        with patch(
            "sn_futures.api.terminal_api.get_readiness_dag_report",
            return_value={"status": "blocked", "training_invoked": False, "active_updated": False},
            create=True,
        ):
            status, payload = handle_terminal_api("/api/terminal/research/readiness-dag", method="GET")

        self.assertEqual(status, 200)
        self.assertFalse(payload["training_invoked"])
        self.assertFalse(payload["active_updated"])

    def test_refresh_readiness_dag_writes_report_only(self) -> None:
        with patch(
            "sn_futures.api.terminal_api.write_readiness_dag_report",
            return_value={"status": "blocked", "training_invoked": False, "customer_prediction_generated": False},
            create=True,
        ):
            status, payload = handle_terminal_api(
                "/api/terminal/research/refresh-readiness-dag",
                method="POST",
                body=json.dumps({}),
            )

        self.assertEqual(status, 200)
        self.assertFalse(payload["training_invoked"])
        self.assertFalse(payload["customer_prediction_generated"])

    def test_run_safe_checks_uses_dag_safe_runner(self) -> None:
        with patch(
            "sn_futures.api.terminal_api.run_readiness_checks_dry_run",
            return_value={"status": "blocked", "runnable_safe_checks": ["config_wizard"], "forbidden_actions": ["build_feature_store_v12"]},
            create=True,
        ):
            status, payload = handle_terminal_api(
                "/api/terminal/research/run-safe-readiness-checks",
                method="POST",
                body=json.dumps({}),
            )

        self.assertEqual(status, 200)
        self.assertIn("config_wizard", payload["runnable_safe_checks"])
        self.assertIn("build_feature_store_v12", payload["forbidden_actions"])


if __name__ == "__main__":
    unittest.main()
