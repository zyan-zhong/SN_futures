from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, "src")

from sn_futures.services.online_lme_tin_service import refresh_online_lme_tin_data


class OnlineLmeTinServiceTest(unittest.TestCase):
    def test_lme_tin_probe_reports_paid_or_unavailable_without_faking_rows(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            result = refresh_online_lme_tin_data()
            data_path = Path(tmp) / "outputs" / "fundamentals" / "sn_lme_tin.json"
            payload = json.loads(data_path.read_text(encoding="utf-8"))

        self.assertEqual(result["status"], "paid_or_unavailable")
        self.assertFalse(result["success"])
        self.assertEqual(payload["rows"], [])
        self.assertIn("lme_tin_close", result["missing_fields"])
        self.assertNotIn("copper", str(payload).lower())
        self.assertNotIn("aluminum", str(payload).lower())


if __name__ == "__main__":
    unittest.main()
