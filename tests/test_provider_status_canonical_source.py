from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, "src")

from sn_futures.services.provider_status_canonical_service import build_canonical_provider_status


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


class ProviderStatusCanonicalSourceTest(unittest.TestCase):
    def test_newsapi_success_file_wins_over_stale_error_status(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            output = Path(tmp) / "outputs"
            _write_json(
                output / "events" / "provider_status.json",
                {
                    "providers": [{"provider": "newsapi", "success": False, "error_code": "rate_limited", "row_count": 0}],
                    "updated_at": "2026-05-31T10:00:00",
                },
            )
            _write_json(
                output / "events" / "news_provider_status.json",
                {
                    "providers": [
                        {
                            "provider": "newsapi",
                            "success": True,
                            "row_count": 16,
                            "last_success_time": "2026-05-31T18:53:44",
                            "message": "NewsAPI success",
                        }
                    ],
                    "updated_at": "2026-05-31T18:53:44",
                },
            )

            canonical = build_canonical_provider_status()

            newsapi = canonical["providers"]["newsapi"]
            self.assertEqual(newsapi["status"], "success")
            self.assertEqual(newsapi["row_count"], 16)
            self.assertEqual(newsapi["last_attempt_time"], "2026-05-31T18:53:44")
            self.assertEqual(newsapi["last_success_time"], "2026-05-31T18:53:44")
            self.assertTrue((output / "provider_status_canonical.json").exists())

    def test_alpha_using_cache_rate_limited_is_canonical(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            output = Path(tmp) / "outputs"
            _write_json(
                output / "fundamentals" / "fx_macro_provider_status.json",
                {
                    "source_name": "alpha_vantage",
                    "status": "using_cache_rate_limited",
                    "success": False,
                    "configured": True,
                    "from_cache": True,
                    "row_count": 5000,
                    "last_attempt_time": "2026-05-31T18:53:34",
                    "cooldown_until": "2026-05-31T20:03:35",
                },
            )

            canonical = build_canonical_provider_status()

            alpha = canonical["providers"]["alpha_vantage"]
            self.assertEqual(alpha["status"], "using_cache_rate_limited")
            self.assertTrue(alpha["configured"])
            self.assertTrue(alpha["from_cache"])
            self.assertEqual(alpha["row_count"], 5000)


if __name__ == "__main__":
    unittest.main()
