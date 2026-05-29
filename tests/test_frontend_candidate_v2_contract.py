from __future__ import annotations

import unittest
from pathlib import Path


class FrontendCandidateV2ContractTest(unittest.TestCase):
    def test_model_governance_mentions_v2_research_only_contract(self) -> None:
        page = Path("frontend/src/pages/ModelGovernancePage.tsx").read_text(encoding="utf-8")
        self.assertIn("candidate_v1 vs candidate_v2", page)
        self.assertIn("不发布 active", page)
        self.assertIn("不生成客户预测", page)
        self.assertIn("不降低 promotion gate", page)
        self.assertIn("高置信 OOF 命中率不是客户预测", page)
        self.assertIn("dry_run=true 不写 active_model.json", page)

    def test_terminal_client_supports_v2_parameters(self) -> None:
        client = Path("frontend/src/api/terminal.ts").read_text(encoding="utf-8")
        self.assertIn("dataset_version", client)
        self.assertIn("candidate_version", client)
        self.assertIn("feature_set", client)
        self.assertIn("dry_run", client)
        self.assertIn("/api/terminal/models/oof-integrity-report", client)
        self.assertIn("/api/terminal/validation/report", client)


if __name__ == "__main__":
    unittest.main()
