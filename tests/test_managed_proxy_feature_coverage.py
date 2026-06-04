from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
import sys

sys.path.insert(0, "src")

from sn_futures.services.feature_coverage_service import build_feature_coverage_report


def _write(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


class ManagedProxyFeatureCoverageTest(unittest.TestCase):
    def test_managed_fundamentals_raise_basis_inventory_lme_and_term_coverage(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            os.environ["SN_INSIGHT_DATA_DIR"] = tmp
            out = Path(tmp) / "outputs"
            history = []
            for i in range(80):
                day = f"2026-03-{(i % 28) + 1:02d}" if i < 28 else f"2026-04-{((i - 28) % 28) + 1:02d}" if i < 56 else f"2026-05-{((i - 56) % 24) + 1:02d}"
                history.append({"trade_date": day, "open": 250000 + i, "high": 251000 + i, "low": 249000 + i, "close": 250500 + i, "volume": 1000 + i})
            _write(out / "sn_market_history.json", {"history": history})
            managed_rows = [
                {
                    "trade_date": row["trade_date"],
                    "symbol": "SN",
                    "spot_price": 251000 + i,
                    "spot_futures_basis": 500 + i,
                    "shfe_inventory": 8000 + i,
                    "shfe_warehouse_receipt": 4000 + i,
                    "lme_tin_close": 33500 + i,
                    "lme_inventory": 4700 + i,
                    "near_contract_close": 250000 + i,
                    "far_contract_close": 249000 + i,
                    "near_open_interest": 42000 + i,
                    "far_open_interest": 36000 + i,
                    "main_contract_switch_flag": 0,
                }
                for i, row in enumerate(history)
            ]
            _write(out / "fundamentals" / "managed_fundamentals.json", {"rows": managed_rows})

            report = build_feature_coverage_report(output_dir=out)

            usable = set(report["usable_feature_cols"])
            self.assertIn("spot_futures_basis", usable)
            self.assertIn("shfe_inventory_delta_1w", usable)
            self.assertIn("lme_tin_return_1d", usable)
            self.assertIn("near_far_spread", usable)
            groups = {group["group"]: group for group in report["groups"]}
            self.assertGreater(groups["basis"]["coverage_rate"], 0)
            self.assertGreater(groups["inventory"]["coverage_rate"], 0)
            self.assertGreater(groups["cross_market"]["coverage_rate"], 0)
            self.assertGreater(groups["term_structure"]["coverage_rate"], 0)


if __name__ == "__main__":
    unittest.main()
