from __future__ import annotations

import unittest

import sys

sys.path.insert(0, "src")

from sn_futures.services.governance_maturity_matrix_service import identify_hardening_gaps, score_governance_domain


class ManagedDataProductionCacheGateMaturityTest(unittest.TestCase):
    def test_blocked_production_cache_gate_is_data_readiness_gap(self) -> None:
        scored = score_governance_domain(
            "Production Managed Cache Gate",
            {
                "name": "managed_data_production_cache_gate",
                "status": "blocked",
                "blocking_reasons": ["manual_approval_missing_or_not_approved"],
                "payload": {"blocking_reasons": ["production_cache_gate_missing_or_blocked"]},
            },
        )

        gaps = identify_hardening_gaps({"Production Managed Cache Gate": scored})

        self.assertIn("production_cache_gate_missing_or_blocked", gaps["data_onboarding_blockers"])


if __name__ == "__main__":
    unittest.main()
