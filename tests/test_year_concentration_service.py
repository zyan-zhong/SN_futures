from __future__ import annotations

import unittest

import pandas as pd

import sys

sys.path.insert(0, "src")

from sn_futures.services.year_concentration_service import (
    build_year_performance_table,
    compute_year_concentration,
    infer_year_from_available_time_columns,
)


class YearConcentrationServiceTest(unittest.TestCase):
    def test_infers_year_from_supported_time_columns(self) -> None:
        for column in ("prediction_date", "trading_date", "label_end_time"):
            with self.subTest(column=column):
                frame = pd.DataFrame(
                    {
                        column: ["2022-01-05", "2023-02-06"],
                        "predicted_direction": [1, -1],
                        "realized_return": [0.02, -0.01],
                    }
                )

                years, source = infer_year_from_available_time_columns(frame)

                self.assertEqual(source, column)
                self.assertEqual(years.tolist(), [2022, 2023])

    def test_oof_without_time_fields_is_missing(self) -> None:
        table = build_year_performance_table(
            pd.DataFrame({"predicted_direction": [1], "realized_return": [0.01]})
        )
        summary = compute_year_concentration(table)

        self.assertEqual(summary["status"], "missing")
        self.assertIn("year_time_column_missing", summary["blocking_reasons"])

    def test_empty_oof_is_missing(self) -> None:
        table = build_year_performance_table(pd.DataFrame())
        summary = compute_year_concentration(table)

        self.assertEqual(summary["status"], "missing")
        self.assertIn("oof_trace_empty", summary["blocking_reasons"])

    def test_single_year_pnl_contribution_too_high_fails(self) -> None:
        frame = pd.DataFrame(
            {
                "prediction_date": ["2020-01-01", "2020-02-01", "2021-01-01", "2022-01-01"],
                "predicted_direction": [1, 1, 1, 1],
                "realized_return": [0.20, 0.20, 0.02, 0.02],
                "cost_assumption": [0.0, 0.0, 0.0, 0.0],
            }
        )

        summary = compute_year_concentration(build_year_performance_table(frame))

        self.assertEqual(summary["status"], "fail")
        self.assertGreater(summary["max_year_pnl_share"], 0.6)
        self.assertIn("year_pnl_concentration_high", summary["blocking_reasons"])

    def test_single_year_sample_share_too_high_fails(self) -> None:
        frame = pd.DataFrame(
            {
                "trading_date": ["2020-01-01"] * 6 + ["2021-01-01", "2022-01-01"],
                "predicted_direction": [1] * 8,
                "realized_return": [0.01] * 8,
            }
        )

        summary = compute_year_concentration(build_year_performance_table(frame))

        self.assertEqual(summary["status"], "fail")
        self.assertGreater(summary["max_year_sample_share"], 0.5)
        self.assertIn("year_sample_concentration_high", summary["blocking_reasons"])

    def test_balanced_multi_year_distribution_passes(self) -> None:
        frame = pd.DataFrame(
            {
                "label_end_time": [
                    "2020-01-01",
                    "2020-02-01",
                    "2021-01-01",
                    "2021-02-01",
                    "2022-01-01",
                    "2022-02-01",
                ],
                "predicted_direction": [1, 1, 1, 1, 1, 1],
                "realized_return": [0.03, -0.005, 0.02, 0.01, 0.02, 0.005],
                "cost_assumption": [0.0] * 6,
            }
        )

        summary = compute_year_concentration(build_year_performance_table(frame))

        self.assertEqual(summary["status"], "pass")
        self.assertLessEqual(summary["max_year_sample_share"], 0.5)
        self.assertLessEqual(summary["max_year_pnl_share"], 0.6)
        self.assertGreaterEqual(summary["positive_year_count"], 2)

    def test_non_positive_total_net_pnl_never_passes(self) -> None:
        frame = pd.DataFrame(
            {
                "prediction_date": ["2020-01-01", "2021-01-01", "2022-01-01"],
                "predicted_direction": [1, 1, 1],
                "realized_return": [-0.01, -0.01, 0.005],
            }
        )

        summary = compute_year_concentration(build_year_performance_table(frame))

        self.assertEqual(summary["status"], "fail")
        self.assertIn("non_positive_total_net_pnl", summary["blocking_reasons"])


if __name__ == "__main__":
    unittest.main()
