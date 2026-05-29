from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, "src")


class HorizonEventWindowIsolationTest(unittest.TestCase):
    def test_horizon_event_feature_hashes_are_distinct(self) -> None:
        old_env = os.environ.get("SN_INSIGHT_DATA_DIR")
        with tempfile.TemporaryDirectory() as tmp:
            os.environ["SN_INSIGHT_DATA_DIR"] = tmp
            from sn_futures.event_features import build_event_evidence
            from sn_futures.news_store import upsert_articles

            upsert_articles(
                [
                    {
                        "title": "SHFE tin exchange notice and warehouse inventory decline",
                        "summary": "Official SHFE tin notice with inventory decline affects SN futures.",
                        "source": {"name": "SHFE public"},
                        "provider": "shfe_public",
                        "url": "https://www.shfe.com.cn/news/sn-notice",
                        "publishedAt": "2026-05-15T10:00:00+08:00",
                        "available_at": "2026-05-15T10:01:00+08:00",
                    }
                ],
                fetch_batch_id="window",
            )
            horizons = ["next_5m", "next_15m", "next_30m", "next_hour", "tomorrow", "one_to_two_weeks", "one_to_three_months"]
            hashes = [
                build_event_evidence(
                    horizon,
                    prediction_time="2026-05-15T11:00:00+08:00",
                    output_dir=Path(tmp) / "outputs",
                )["event_feature_hash"]
                for horizon in horizons
            ]
            self.assertEqual(len(hashes), len(set(hashes)))
        if old_env is None:
            os.environ.pop("SN_INSIGHT_DATA_DIR", None)
        else:
            os.environ["SN_INSIGHT_DATA_DIR"] = old_env


if __name__ == "__main__":
    unittest.main()
