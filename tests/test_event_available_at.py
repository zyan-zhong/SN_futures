from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, "src")


class EventAvailableAtTest(unittest.TestCase):
    def test_future_available_event_is_rejected(self) -> None:
        old_env = os.environ.get("SN_INSIGHT_DATA_DIR")
        with tempfile.TemporaryDirectory() as tmp:
            os.environ["SN_INSIGHT_DATA_DIR"] = tmp
            from sn_futures.event_features import build_event_evidence
            from sn_futures.news_store import upsert_articles

            upsert_articles(
                [
                    {
                        "title": "Future tin policy should not leak into current prediction",
                        "summary": "A future SHFE tin policy item must be rejected by available_at guard.",
                        "source": {"name": "Test"},
                        "provider": "newsapi",
                        "url": "https://example.com/future-sn-policy",
                        "publishedAt": "2026-05-16T10:00:00+08:00",
                        "available_at": "2026-05-16T10:01:00+08:00",
                    }
                ],
                fetch_batch_id="future",
            )
            evidence = build_event_evidence(
                "tomorrow",
                prediction_time="2026-05-15T11:00:00+08:00",
                output_dir=Path(tmp) / "outputs",
            )
            self.assertEqual(evidence["used_in_model_event_count"], 0)
            self.assertEqual(evidence["rejected_reason_breakdown"].get("prediction_time_alignment_failed"), 1)
        if old_env is None:
            os.environ.pop("SN_INSIGHT_DATA_DIR", None)
        else:
            os.environ["SN_INSIGHT_DATA_DIR"] = old_env


if __name__ == "__main__":
    unittest.main()
