from __future__ import annotations

import unittest

import sys

sys.path.insert(0, "src")

from sn_futures.services.governance_maturity_matrix_service import identify_hardening_gaps, score_governance_domain


class ManagedDataBackfillPlannerMaturityTest(unittest.TestCase):
    def test_blocked_backfill_plan_is_data_readiness_gap(self) -> None:
        scored = score_governance_domain(
            "Managed Data Backfill",
            {
                "name": "managed_data_backfill_plan",
                "status": "blocked",
                "blocking_reasons": ["endpoint_smoke_not_passed"],
                "payload": {"blocking_reasons": ["backfill_plan_missing_or_blocked"]},
            },
        )

        gaps = identify_hardening_gaps({"Managed Data Backfill": scored})

        self.assertIn("backfill_plan_missing_or_blocked", gaps["data_onboarding_blockers"])


if __name__ == "__main__":
    unittest.main()
