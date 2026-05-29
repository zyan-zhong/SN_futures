from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, "src")


class EventFeaturesUsedInModelTest(unittest.TestCase):
    def test_valid_tin_event_enters_feature_matrix(self) -> None:
        old_env = os.environ.get("SN_INSIGHT_DATA_DIR")
        with tempfile.TemporaryDirectory() as tmp:
            os.environ["SN_INSIGHT_DATA_DIR"] = tmp
            from sn_futures.event_features import build_event_evidence
            from sn_futures.news_store import upsert_articles

            upsert_articles(
                [
                    {
                        "title": "Myanmar tin ore supply disruption SHFE tin warrant decline",
                        "summary": "Tin ore supply disruption and warehouse warrant decline are supportive for SN futures.",
                        "source": {"name": "SHFE public"},
                        "provider": "shfe_public",
                        "url": "https://www.shfe.com.cn/news/sn-supply",
                        "publishedAt": "2026-05-15T10:00:00+08:00",
                        "available_at": "2026-05-15T10:01:00+08:00",
                    }
                ],
                fetch_batch_id="valid",
            )
            evidence = build_event_evidence(
                "tomorrow",
                prediction_time="2026-05-15T11:00:00+08:00",
                output_dir=Path(tmp) / "outputs",
            )
            self.assertGreater(evidence["recognized_event_count"], 0)
            self.assertGreater(evidence["used_in_model_event_count"], 0)
            self.assertGreater(evidence["event_feature_nonzero_count"], 0)
            self.assertTrue(evidence["event_feature_hash"])
        if old_env is None:
            os.environ.pop("SN_INSIGHT_DATA_DIR", None)
        else:
            os.environ["SN_INSIGHT_DATA_DIR"] = old_env


if __name__ == "__main__":
    unittest.main()
