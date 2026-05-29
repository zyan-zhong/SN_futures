from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, "src")

from sn_futures.services.news_relevance_service import refresh_news_relevance, score_news_relevance


class NewsRelevanceServiceTest(unittest.TestCase):
    def test_macworld_and_pypi_news_are_low_relevance(self) -> None:
        macworld = score_news_relevance({"title": "Macworld reviews iPhone app plugin", "source": "Macworld"})
        pypi = score_news_relevance({"title": "PyPI package tin released for Python developers", "source": "PyPI"})
        self.assertLess(macworld["relevance_score"], 0.25)
        self.assertLess(pypi["relevance_score"], 0.25)
        self.assertFalse(macworld["used_in_model"])
        self.assertFalse(pypi["used_in_model"])

    def test_tin_supply_news_can_enter_event_factor(self) -> None:
        score = score_news_relevance(
            {
                "title": "Myanmar Wa State tin concentrate supply disruption hits LME tin",
                "description": "Tin smelters monitor SHFE tin inventory after export permit delay.",
            }
        )
        self.assertGreaterEqual(score["relevance_score"], 0.55)
        self.assertTrue(score["used_in_model"])
        self.assertEqual(score["category"], "supply")

    def test_refresh_writes_used_in_model_flags(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            events_dir = Path(tmp) / "outputs" / "events"
            events_dir.mkdir(parents=True, exist_ok=True)
            (events_dir / "news_events.json").write_text(
                json.dumps(
                    {
                        "events": [
                            {"title": "LME tin inventory falls as Indonesia export permit delayed", "published_at": "2026-01-01"},
                            {"title": "Macworld covers a new iPhone app", "published_at": "2026-01-01"},
                        ]
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            result = refresh_news_relevance()
            payload = json.loads((events_dir / "news_events.json").read_text(encoding="utf-8"))

        self.assertEqual(result["status"], "success")
        self.assertEqual(result["used_in_model_count"], 1)
        self.assertTrue(payload["events"][0]["used_in_model"])
        self.assertFalse(payload["events"][1]["used_in_model"])


if __name__ == "__main__":
    unittest.main()

