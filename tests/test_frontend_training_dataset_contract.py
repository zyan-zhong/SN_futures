from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend" / "src"


class FrontendTrainingDatasetContractTest(unittest.TestCase):
    def test_terminal_client_exposes_training_dataset_api(self) -> None:
        source = (FRONTEND / "api" / "terminal.ts").read_text(encoding="utf-8")
        self.assertIn("buildTrainingDataset", source)
        self.assertIn("getTrainingDatasetStatus", source)
        self.assertIn("/api/terminal/training-dataset/build", source)
        self.assertIn("/api/terminal/training-dataset/status", source)

    def test_settings_page_contains_training_dataset_status(self) -> None:
        settings = (FRONTEND / "pages" / "SettingsPage.tsx").read_text(encoding="utf-8")
        panel = (FRONTEND / "components" / "model" / "TrainingDatasetStatusPanel.tsx").read_text(encoding="utf-8")
        self.assertIn("TrainingDatasetStatusPanel", settings)
        self.assertIn("训练数据集状态", settings)
        self.assertIn("不训练模型", panel)
        self.assertIn("不生成预测", panel)
        self.assertIn("不生成回测", panel)

    def test_frontend_training_dataset_panel_has_no_baseline(self) -> None:
        panel = (FRONTEND / "components" / "model" / "TrainingDatasetStatusPanel.tsx").read_text(encoding="utf-8").lower()
        self.assertNotIn("baseline forecast", panel)
        self.assertNotIn("baseline backtest", panel)

    def test_training_data_page_exposes_v10_regime_balance_status(self) -> None:
        page = (FRONTEND / "pages" / "TrainingDataPage.tsx").read_text(encoding="utf-8")
        types = (FRONTEND / "api" / "types.ts").read_text(encoding="utf-8")

        self.assertIn('"v10"', page)
        self.assertIn("regime_balanced_tushare_cost_positioning", page)
        self.assertIn("v10 regime balance", page)
        self.assertIn("horizon_regime_counts", types)
        self.assertIn("regime_sample_weights", types)


if __name__ == "__main__":
    unittest.main()
