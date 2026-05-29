import unittest

from sn_futures.diagnostics.data_reality_audit import audit_data_reality
from sn_futures.diagnostics.model_independence_audit import audit_model_independence
from sn_futures.model_registry import build_registry


class TruthAuditContractTest(unittest.TestCase):
    def test_model_independence_detects_duplicate_scaler(self):
        rows = build_registry()
        rows[1] = dict(rows[1])
        rows[1]["scaler_id"] = rows[0]["scaler_id"]
        cards = {
            row["horizon"]: {
                "price_center": 420000 + idx * 100,
                "range_low": 419000 + idx * 100,
                "range_high": 421000 + idx * 100,
                "prob_up": 0.40 + idx * 0.02,
                "prob_down": 0.60 - idx * 0.02,
                "p_neutral": 0.1 + idx * 0.01,
            }
            for idx, row in enumerate(rows)
        }
        audit = audit_model_independence(registry_rows=rows, live_cards=cards)
        self.assertFalse(audit["ok"])
        self.assertIn("scaler_id", [check["field"] for check in audit["checks"] if not check["ok"]])

    def test_data_reality_detects_mock_source(self):
        audit = audit_data_reality(
            {
                "source_mode": "mock_static_source",
                "live_quote": {"latest": 420000, "quote_time": "2026-05-14 21:30:00"},
                "source_status": [{"name": "mock", "success": True}],
            },
            {"is_trading": True},
        )
        self.assertFalse(audit["ok"])
        self.assertIn("mock_or_static_data_suspected", audit["issues"])


if __name__ == "__main__":
    unittest.main()
