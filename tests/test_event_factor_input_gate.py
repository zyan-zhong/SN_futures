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
from sn_futures.services.refresh_service import refresh_event_store


class EventFactorInputGateTest(unittest.TestCase):
    def test_event_factor_inputs_only_include_used_in_model_news(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            events_dir = Path(tmp) / "outputs" / "events"
            events_dir.mkdir(parents=True, exist_ok=True)
            (events_dir / "news_events.json").write_text(
                json.dumps(
                    {
                        "events": [
                            {
                                "title": "LME tin inventory falls after Indonesia export quota delay",
                                "description": "SHFE tin supply tightens",
                                "published_at": "2026-05-20T03:00:00Z",
                                "fetched_at": "2026-05-20T03:05:00Z",
                            },
                            {"title": "Macworld reviews a new Apple plugin", "description": "Software news"},
                        ]
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            relevance = refresh_news_relevance()
            refresh_event_store()
            factor_inputs = json.loads((events_dir / "event_factor_inputs.json").read_text(encoding="utf-8"))
            store = json.loads((events_dir / "event_store.json").read_text(encoding="utf-8"))

        self.assertEqual(relevance["used_in_model_count"], 1)
        self.assertEqual(len(factor_inputs["events"]), 1)
        self.assertTrue(all(row.get("used_in_model") is True for row in factor_inputs["events"]))
        self.assertNotIn("Macworld", json.dumps(store, ensure_ascii=False))


if __name__ == "__main__":
    unittest.main()
