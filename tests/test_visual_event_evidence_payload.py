from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, "src")


class VisualEventEvidencePayloadTest(unittest.TestCase):
    def test_payload_contains_used_and_rejected_events(self) -> None:
        old_data_env = os.environ.get("SN_DATA_DIR")
        old_env = os.environ.get("SN_INSIGHT_DATA_DIR")
        with tempfile.TemporaryDirectory() as tmp:
            os.environ["SN_DATA_DIR"] = tmp
            os.environ["SN_INSIGHT_DATA_DIR"] = tmp
            from sn_futures.event_pipeline import get_event_evidence
            from sn_futures.news_store import upsert_articles

            upsert_articles(
                [
                    {
                        "title": "Tin ore supply disruption supports SN",
                        "summary": "Tin ore supply disruption is bullish for SHFE tin.",
                        "source": {"name": "Industry public"},
                        "provider": "akshare_shmet",
                        "url": "https://example.com/sn-valid",
                        "publishedAt": "2026-05-15T10:00:00+08:00",
                        "available_at": "2026-05-15T10:01:00+08:00",
                    },
                    {
                        "title": "Tin event without URL should be filtered",
                        "summary": "Tin news has no canonical URL and should not be used formally.",
                        "source": {"name": "Bad source"},
                        "provider": "newsapi",
                        "url": "",
                        "publishedAt": "2026-05-15T10:00:00+08:00",
                        "available_at": "2026-05-15T10:01:00+08:00",
                    },
                ],
                fetch_batch_id="visual",
            )
            payload = get_event_evidence(
                "tomorrow",
                output_dir=Path(tmp) / "outputs",
                prediction_time="2026-05-15T11:00:00+08:00",
            )
            self.assertIn("recognized_events", payload)
            self.assertIn("used_events", payload)
            self.assertIn("rejected_events", payload)
            self.assertGreaterEqual(payload["used_in_model_event_count"], 1)
            self.assertTrue(payload["used_events"][0]["canonical_url"])
        if old_env is None:
            os.environ.pop("SN_INSIGHT_DATA_DIR", None)
        else:
            os.environ["SN_INSIGHT_DATA_DIR"] = old_env
        if old_data_env is None:
            os.environ.pop("SN_DATA_DIR", None)
        else:
            os.environ["SN_DATA_DIR"] = old_data_env


if __name__ == "__main__":
    unittest.main()
