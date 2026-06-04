from __future__ import annotations

import unittest

import sys

sys.path.insert(0, "src")

from sn_futures.services.governance_access_control_service import (  # noqa: E402
    build_access_control_report,
    classify_api_action,
)


class GovernanceAccessControlShadowOutputTest(unittest.TestCase):
    def test_shadow_output_dry_run_is_safe_dry_run_and_real_output_is_not_allowed(self) -> None:
        dry_run = classify_api_action("POST", "/api/terminal/governance/build-shadow-output-dry-run")
        real_shadow = classify_api_action("POST", "/api/terminal/governance/build-shadow-output")

        self.assertEqual(dry_run["category"], "safe_dry_run")
        self.assertIn(real_shadow["category"], {"customer_prediction_write", "heavy_build"})

    def test_access_control_inventory_lists_shadow_output_contract(self) -> None:
        report = build_access_control_report(write=False, decision_board={"status": "blocked", "candidate_training_allowed": False})
        ids = {str(item.get("id")) for item in report["api_action_inventory"]}

        self.assertIn("read_shadow_output_contract", ids)
        self.assertIn("build_shadow_output_dry_run", ids)
        self.assertIn("build_shadow_output_dry_run", report["allowed_safe_actions"])


if __name__ == "__main__":
    unittest.main()
