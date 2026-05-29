from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, "src")

from sn_futures.services.news_relevance_service import refresh_news_relevance


class EventFactorInputFromHighQualityNewsTest(unittest.TestCase):
    def test_event_factor_inputs_only_from_high_quality_used_in_model_news(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            events_dir = Path(tmp) / "outputs" / "events"
            events_dir.mkdir(parents=True, exist_ok=True)
            (events_dir / "news_events.json").write_text(
                json.dumps(
                    {
                        "events": [
                            {
                                "title": "LME tin inventory falls as warehouse stocks tighten",
                                "description": "SHFE tin futures traders watch low tin stockpiles.",
                                "url": "https://www.lme.com/en/metals/non-ferrous/lme-tin/inventory-update",
                                "source": {"name": "LME"},
                                "published_at": "2026-05-20T03:00:00Z",
                                "query_group": "exchange_inventory",
                            },
                            {
                                "title": "Apple launches a tin-colored iPhone accessory",
                                "description": "Macworld consumer electronics article.",
                                "url": "https://www.macworld.com/article/apple-accessory",
                                "source": {"name": "Macworld"},
                                "published_at": "2026-05-20T04:00:00Z",
                                "query_group": "demand_electronics",
                            },
                        ]
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            result = refresh_news_relevance()
            factor_inputs = json.loads((events_dir / "event_factor_inputs.json").read_text(encoding="utf-8"))
            report = json.loads((events_dir / "news_relevance_report.json").read_text(encoding="utf-8"))

        self.assertEqual(result["used_in_model_count"], 1)
        self.assertEqual(factor_inputs["used_in_model_count"], 1)
        self.assertEqual(len(factor_inputs["events"]), 1)
        self.assertEqual(factor_inputs["inputs"][0]["used_in_model_count"], 1)
        self.assertGreater(factor_inputs["inputs"][0]["source_reliability_weighted_score"], 0)
        self.assertEqual(report["rejected_count"], 1)
        self.assertEqual(report["high_relevance_events"][0]["query_group"], "exchange_inventory")


if __name__ == "__main__":
    unittest.main()
