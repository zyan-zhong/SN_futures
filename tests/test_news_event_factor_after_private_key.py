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


class NewsEventFactorAfterPrivateKeyTest(unittest.TestCase):
    def test_used_in_model_false_news_is_not_written_to_event_factor_inputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            events_dir = Path(tmp) / "outputs" / "events"
            events_dir.mkdir(parents=True, exist_ok=True)
            (events_dir / "news_events.json").write_text(
                json.dumps(
                    {
                        "events": [
                            {
                                "title": "LME tin inventory falls after Indonesia export quota delay",
                                "description": "SHFE tin supply tightens.",
                            },
                            {
                                "title": "PyPI package tin released",
                                "description": "Software package news for Python developers.",
                            },
                        ]
                    }
                ),
                encoding="utf-8",
            )
            result = refresh_news_relevance()
            factor_inputs = json.loads((events_dir / "event_factor_inputs.json").read_text(encoding="utf-8"))

        self.assertEqual(result["used_in_model_count"], 1)
        self.assertEqual(len(factor_inputs["events"]), 1)
        self.assertTrue(all(row.get("used_in_model") is True for row in factor_inputs["events"]))
        self.assertNotIn("PyPI", json.dumps(factor_inputs, ensure_ascii=False))


if __name__ == "__main__":
    unittest.main()
