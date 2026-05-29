from __future__ import annotations

import os
import sys
import tempfile
import unittest

sys.path.insert(0, "src")


class EventSchemaTest(unittest.TestCase):
    def test_structured_event_has_required_fields(self) -> None:
        old_env = os.environ.get("SN_INSIGHT_DATA_DIR")
        with tempfile.TemporaryDirectory() as tmp:
            os.environ["SN_INSIGHT_DATA_DIR"] = tmp
            from sn_futures.event_taxonomy import build_event_from_article

            event = build_event_from_article(
                {
                    "title": "Myanmar tin ore supply disruption supports SHFE tin",
                    "summary": "Tin ore shipment disruption and SHFE warrant decline are relevant to SN futures.",
                    "source": {"name": "SHFE public"},
                    "provider": "shfe_public",
                    "url": "https://www.shfe.com.cn/news/sn-event",
                    "publishedAt": "2026-05-15T09:00:00+08:00",
                    "available_at": "2026-05-15T09:02:00+08:00",
                },
                batch_id="schema",
            )
            self.assertIsNotNone(event)
            assert event is not None
            for key in (
                "event_id",
                "canonical_url",
                "available_at",
                "direction_bias",
                "impact_score",
                "direction_confidence",
                "final_event_weight",
                "symbol_tags",
            ):
                self.assertIn(key, event)
            self.assertTrue(event["canonical_url"].startswith("https://"))
            self.assertIn("SN", event["symbol_tags"])
        if old_env is None:
            os.environ.pop("SN_INSIGHT_DATA_DIR", None)
        else:
            os.environ["SN_INSIGHT_DATA_DIR"] = old_env


if __name__ == "__main__":
    unittest.main()

