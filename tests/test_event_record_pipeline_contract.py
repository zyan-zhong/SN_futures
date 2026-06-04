from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, "src")

from sn_futures.event_features import build_event_evidence
from sn_futures.news_store import upsert_articles
from sn_futures.services.news_relevance_service import refresh_news_relevance, score_news_relevance


class EventRecordPipelineContractTest(unittest.TestCase):
    def test_policy_page_without_source_published_at_is_low_confidence_and_not_used(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            events_dir = Path(tmp) / "outputs" / "events"
            events_dir.mkdir(parents=True, exist_ok=True)
            (events_dir / "news_events.json").write_text(
                json.dumps(
                    {
                        "events": [
                            {
                                "title": "MIIT policy mentions semiconductor solder and SHFE tin supply chain",
                                "description": "Tin solder electronics demand and Shanghai tin futures policy update.",
                                "url": "https://www.miit.gov.cn/policy/sn-old-page",
                                "source": {"name": "MIIT"},
                                "provider": "miit_policy",
                                "region": "China",
                                "fetched_at": "2026-06-04T10:00:00+08:00",
                            }
                        ]
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            refresh_news_relevance()
            payload = json.loads((events_dir / "news_events.json").read_text(encoding="utf-8"))
            factor_inputs = json.loads((events_dir / "event_factor_inputs.json").read_text(encoding="utf-8"))

        event = payload["events"][0]
        self.assertFalse(event["used_in_model"])
        self.assertLess(event["event_time_confidence"], 0.5)
        self.assertIn("source_published_at", event["rejection_reason"])
        self.assertEqual(factor_inputs["used_in_model_count"], 0)

    def test_news_after_prediction_cutoff_is_not_point_in_time_visible(self) -> None:
        old_data_env = os.environ.get("SN_DATA_DIR")
        old_env = os.environ.get("SN_INSIGHT_DATA_DIR")
        with tempfile.TemporaryDirectory() as tmp:
            os.environ["SN_DATA_DIR"] = tmp
            os.environ["SN_INSIGHT_DATA_DIR"] = tmp
            upsert_articles(
                [
                    {
                        "title": "Indonesia tin export permit delay tightens SHFE tin supply",
                        "summary": "LME tin traders monitor supply disruption and Shanghai tin futures.",
                        "source": {"name": "Metals Daily"},
                        "provider": "newsapi",
                        "url": "https://example.com/future-published-tin-news",
                        "publishedAt": "2026-05-16T10:00:00+08:00",
                        "fetched_at": "2026-05-15T09:00:00+08:00",
                        "available_at": "2026-05-15T09:01:00+08:00",
                    }
                ],
                fetch_batch_id="future-published",
            )
            evidence = build_event_evidence(
                "tomorrow",
                prediction_time="2026-05-15T11:00:00+08:00",
                output_dir=Path(tmp) / "outputs",
            )
        if old_env is None:
            os.environ.pop("SN_INSIGHT_DATA_DIR", None)
        else:
            os.environ["SN_INSIGHT_DATA_DIR"] = old_env
        if old_data_env is None:
            os.environ.pop("SN_DATA_DIR", None)
        else:
            os.environ["SN_DATA_DIR"] = old_data_env

        self.assertEqual(evidence["used_in_model_event_count"], 0)
        self.assertEqual(evidence["rejected_reason_breakdown"].get("source_published_at_after_prediction_time"), 1)
        self.assertEqual(evidence["rejected_events"][0]["event_time_confidence"], 1.0)

    def test_unrelated_stock_ai_news_with_tin_accidental_match_is_rejected(self) -> None:
        result = score_news_relevance(
            {
                "title": "AI stock investing platform launches tin themed portfolio widget",
                "description": "The article is about stock analytics software and artificial intelligence tools.",
                "url": "https://example.com/ai-stock-widget",
                "source": {"name": "Tech Stocks"},
            }
        )

        self.assertFalse(result["used_in_model"])
        self.assertIn("exclusion_reason", result)
        self.assertLess(result["hard_evidence_score"], 0.30)

    def test_high_relevance_supply_news_is_accepted_and_event_factor_manifest_has_cutoff(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            events_dir = Path(tmp) / "outputs" / "events"
            events_dir.mkdir(parents=True, exist_ok=True)
            (events_dir / "news_events.json").write_text(
                json.dumps(
                    {
                        "events": [
                            {
                                "title": "SHFE tin warehouse warrants drop as Indonesia tin export permit delayed",
                                "description": "LME tin and Shanghai tin futures react to supply disruption and low inventory.",
                                "url": "https://www.lme.com/en/metals/non-ferrous/lme-tin/supply-update",
                                "source": {"name": "LME"},
                                "provider": "newsapi",
                                "region": "global",
                                "published_at": "2026-05-20T03:00:00Z",
                                "fetched_at": "2026-05-20T03:05:00Z",
                                "query_group": "exchange_inventory",
                            }
                        ]
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            result = refresh_news_relevance()
            factor_inputs = json.loads((events_dir / "event_factor_inputs.json").read_text(encoding="utf-8"))

        self.assertEqual(result["used_in_model_count"], 1)
        self.assertEqual(factor_inputs["used_in_model_count"], 1)
        self.assertIn("manifest", factor_inputs)
        self.assertIn("cutoff", factor_inputs)
        event = factor_inputs["events"][0]
        for key in (
            "event_id",
            "url_sanitized",
            "region",
            "category",
            "source_published_at",
            "fetched_at",
            "available_at",
            "event_time_confidence",
            "source_reliability_score",
            "content_hash",
        ):
            self.assertIn(key, event)
        self.assertTrue(event["used_in_model"])
        self.assertGreaterEqual(event["relevance_score"], 0.60)
        self.assertEqual(event["event_time_confidence"], 1.0)


if __name__ == "__main__":
    unittest.main()
