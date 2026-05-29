from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend" / "src"


class FrontendFeatureCoverageContractTest(unittest.TestCase):
    def test_terminal_client_exposes_feature_coverage_api(self) -> None:
        source = (FRONTEND / "api" / "terminal.ts").read_text(encoding="utf-8")
        self.assertIn("getFeatureCoverage", source)
        self.assertIn("/api/terminal/factors/coverage", source)

    def test_factor_page_displays_real_feature_coverage(self) -> None:
        source = (FRONTEND / "pages" / "FactorPage.tsx").read_text(encoding="utf-8")
        self.assertIn("真实因子覆盖率", source)
        self.assertIn("可训练因子", source)
        self.assertIn("不训练模型、不生成预测、不生成回测", source)

    def test_factor_page_does_not_introduce_baseline(self) -> None:
        source = (FRONTEND / "pages" / "FactorPage.tsx").read_text(encoding="utf-8").lower()
        self.assertNotIn("baseline", source)
        self.assertNotIn("基线预测", source)


if __name__ == "__main__":
    unittest.main()
