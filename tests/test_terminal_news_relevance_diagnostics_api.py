from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, "src")

from sn_futures.api.terminal_api import TERMINAL_API_DOCS, handle_terminal_api
from sn_futures.services.news_relevance_service import refresh_news_relevance


class TerminalNewsRelevanceDiagnosticsApiTest(unittest.TestCase):
    def test_relevance_diagnostics_endpoint_returns_query_group_stats(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            events_dir = Path(tmp) / "outputs" / "events"
            events_dir.mkdir(parents=True, exist_ok=True)
            (events_dir / "news_events.json").write_text(
                json.dumps(
                    {
                        "events": [
                            {
                                "title": "SHFE tin inventory falls after Indonesia tin export quota delay",
                                "description": "LME tin traders monitor warehouse stockpiles.",
                                "query_group": "supply_asia",
                                "published_at": "2026-05-20T03:00:00Z",
                                "fetched_at": "2026-05-20T03:05:00Z",
                            }
                        ]
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            refresh_news_relevance()
            status, payload = handle_terminal_api("/api/terminal/events/relevance-diagnostics", "GET", {}, None)

        self.assertEqual(status, 200)
        self.assertEqual(payload["used_in_model_count"], 1)
        self.assertIn("supply_asia", payload["query_groups"])
        self.assertTrue(payload["articles"][0]["keyword_hits"])

    def test_docs_include_relevance_diagnostics_endpoint(self) -> None:
        paths = {row["path"] for row in TERMINAL_API_DOCS["endpoints"]}
        self.assertIn("/api/terminal/events/relevance-diagnostics", paths)


if __name__ == "__main__":
    unittest.main()
