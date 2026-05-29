from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, "src")


class CandidateV1V2ComparisonContractTest(unittest.TestCase):
    def test_frontend_and_api_expose_v1_v2_comparison(self) -> None:
        page = Path("frontend/src/pages/ModelGovernancePage.tsx").read_text(encoding="utf-8")
        api = Path("frontend/src/api/terminal.ts").read_text(encoding="utf-8")
        backend = Path("src/sn_futures/api/terminal_api.py").read_text(encoding="utf-8")

        self.assertIn("candidate_v1 vs candidate_v2", page)
        self.assertIn("usd_cny", page)
        self.assertIn("us10y", page)
        self.assertIn("copper_global_proxy", page)
        self.assertIn("event_shock_score", page)
        self.assertIn("dry_run=true 不写 active_model.json", page)
        self.assertIn("candidate_version", api)
        self.assertIn("dataset_version", api)
        self.assertIn("candidate_version", backend)
        self.assertIn("dry_run", backend)


if __name__ == "__main__":
    unittest.main()
