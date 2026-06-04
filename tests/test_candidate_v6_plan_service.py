from __future__ import annotations

import os
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, "src")

from sn_futures.services.active_absence_diagnostics_service import build_active_absence_diagnostics
from active_absence_fixture import write_blocked_candidate_fixture


class CandidateV6PlanServiceTest(unittest.TestCase):
    def test_candidate_v6_plan_contains_actionable_research_tracks_and_hard_gate_policy(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            write_blocked_candidate_fixture(tmp)
            plan = build_active_absence_diagnostics()["candidate_v6_plan"]

        self.assertEqual(plan["status"], "research_plan_only")
        self.assertFalse(plan["auto_publish_active"])
        self.assertFalse(plan["customer_prediction_generated"])
        self.assertIn("data_repair_priority", plan)
        self.assertIn("label_governance", plan)
        self.assertIn("model_family_plan", plan)
        self.assertIn("risk_controls", plan)
        self.assertIn("minimum_go_live_gates", plan)
        self.assertIn("needed_data_sources", plan)
        joined_gates = " ".join(plan["minimum_go_live_gates"])
        self.assertIn("PBO", joined_gates)
        self.assertIn("DSR", joined_gates)


if __name__ == "__main__":
    unittest.main()
