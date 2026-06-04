from __future__ import annotations

import sys
import unittest

import pandas as pd

sys.path.insert(0, "src")

from sn_futures.services.regime_neutral_strategy_service import build_regime_neutral_strategy_policy, select_regime_neutral_trades


class CandidateV9TradeQuotaTest(unittest.TestCase):
    def test_regime_year_and_fold_quotas_limit_selected_trades(self) -> None:
        frame = pd.DataFrame(
            [
                {
                    "predicted_direction": 1,
                    "confidence": 0.95 - idx * 0.005,
                    "trade_edge": 0.01,
                    "fold_id": "fold_1" if idx < 20 else f"fold_{idx}",
                    "label_start_time": "2020-01-05" if idx < 20 else f"202{idx % 5}-02-01",
                    "regime_label": "high_volatility" if idx < 30 else ("range" if idx < 45 else "low_volatility"),
                }
                for idx in range(60)
            ]
        )
        policy = build_regime_neutral_strategy_policy(
            v8_diagnostics={
                "regime_concentration_attribution": {
                    "dominant_regime": "high_volatility",
                    "dominant_contribution": 1.0,
                }
            },
            v8_report={},
        )

        selected = select_regime_neutral_trades(frame, policy)
        selected_frame = frame.loc[selected]
        total = max(int(selected.sum()), 1)

        self.assertGreater(int(selected.sum()), 0)
        self.assertLessEqual(selected_frame["regime_label"].value_counts().max() / total, 0.55)
        self.assertLessEqual(selected_frame["fold_id"].value_counts().max() / total, 0.35)
        self.assertLessEqual(pd.to_datetime(selected_frame["label_start_time"]).dt.year.value_counts().max() / total, 0.35)


if __name__ == "__main__":
    unittest.main()
