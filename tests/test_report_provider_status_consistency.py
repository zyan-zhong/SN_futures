from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, "src")

from sn_futures.services.active_absence_diagnostics_service import build_active_absence_diagnostics
from sn_futures.services.full_system_report_service import build_full_system_txt_report
from sn_futures.services.terminal_service import build_terminal_data_status


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


class ReportProviderStatusConsistencyTest(unittest.TestCase):
    def test_full_system_report_and_active_absence_use_canonical_provider_status(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            output = Path(tmp) / "outputs"
            _write_json(
                output / "events" / "news_provider_status.json",
                {
                    "providers": [{"provider": "newsapi", "success": True, "row_count": 16, "last_success_time": "2026-05-31T18:53:44"}],
                    "updated_at": "2026-05-31T18:53:44",
                },
            )
            _write_json(
                output / "fundamentals" / "fx_macro_provider_status.json",
                {
                    "source_name": "alpha_vantage",
                    "status": "using_cache_rate_limited",
                    "configured": True,
                    "from_cache": True,
                    "row_count": 5000,
                    "last_attempt_time": "2026-05-31T18:53:34",
                },
            )

            full = build_full_system_txt_report()
            active = build_active_absence_diagnostics()
            data_status = build_terminal_data_status()
            full_json = json.loads(Path(full["json_path"]).read_text(encoding="utf-8"))

        full_providers = full_json["provider_status_canonical"]["providers"]
        active_providers = active["data_source_status"]
        data_sources = {row.get("provider_id"): row for row in data_status["sources"]}
        self.assertEqual(full_providers["newsapi"]["status"], "success")
        self.assertEqual(full_providers["newsapi"]["row_count"], 16)
        self.assertEqual(active_providers["newsapi"]["status"], "success")
        self.assertEqual(active_providers["newsapi"]["row_count"], 16)
        self.assertEqual(data_sources["newsapi"]["status_code"], "success")
        self.assertEqual(data_sources["newsapi"]["row_count"], 16)
        self.assertEqual(full_providers["alpha_vantage"]["status"], "using_cache_rate_limited")
        self.assertEqual(active_providers["alpha_vantage"]["status"], "using_cache_rate_limited")
        self.assertEqual(data_sources["alpha_vantage"]["status_code"], "using_cache_rate_limited")


if __name__ == "__main__":
    unittest.main()
