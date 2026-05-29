from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, "src")

from sn_futures.services.news_relevance_diagnostics_service import build_news_relevance_diagnostics
from sn_futures.services.news_relevance_service import refresh_news_relevance


class EventFactorInputsQualityTest(unittest.TestCase):
    def test_event_factor_inputs_are_aggregated_from_used_in_model_only(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            events_dir = Path(tmp) / "outputs" / "events"
            events_dir.mkdir(parents=True, exist_ok=True)
            (events_dir / "news_events.json").write_text(
                json.dumps(
                    {
                        "events": [
                            {
                                "title": "LME tin inventory falls after Indonesia export suspension",
                                "description": "SHFE tin supply and warehouse stockpiles tighten.",
                                "published_at": "2026-05-20T02:00:00Z",
                                "query_group": "supply_asia",
                                "source": "Metals",
                            },
                            {
                                "title": "Macworld reviews an Apple audio DAC",
                                "description": "Consumer electronics review.",
                                "published_at": "2026-05-20T03:00:00Z",
                                "query_group": "demand",
                                "source": "Tech",
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
            diagnostics = build_news_relevance_diagnostics()

        self.assertEqual(result["used_in_model_count"], 1)
        self.assertEqual(factor_inputs["used_in_model_count"], 1)
        self.assertTrue(factor_inputs["inputs"])
        self.assertEqual(factor_inputs["inputs"][0]["used_in_model_count"], 1)
        self.assertGreater(factor_inputs["inputs"][0]["inventory_shock_score"], 0)
        self.assertEqual(len(factor_inputs["events"]), 1)
        self.assertEqual(report["rejected_count"], 1)
        self.assertEqual(diagnostics["used_in_model_count"], 1)
        self.assertEqual(diagnostics["excluded_count"], 1)
        self.assertTrue(diagnostics["articles"][0]["keyword_hits"])
        self.assertIn("supply_asia", diagnostics["query_groups"])

    def test_empty_model_events_write_clear_message_without_fake_scores(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            events_dir = Path(tmp) / "outputs" / "events"
            events_dir.mkdir(parents=True, exist_ok=True)
            (events_dir / "news_events.json").write_text(
                json.dumps(
                    {"events": [{"title": "PyPI package tin released", "description": "Python software package."}]},
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            refresh_news_relevance()
            factor_inputs = json.loads((events_dir / "event_factor_inputs.json").read_text(encoding="utf-8"))

        self.assertEqual(factor_inputs["used_in_model_count"], 0)
        self.assertEqual(factor_inputs["inputs"], [])
        self.assertIn("无通过相关性门槛", factor_inputs["message_zh"])


if __name__ == "__main__":
    unittest.main()
