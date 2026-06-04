from __future__ import annotations

import os
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

import sys

sys.path.insert(0, "src")

from sn_futures.services.full_system_report_service import build_full_system_txt_report


class ReportNoSecretLeakageTest(unittest.TestCase):
    def test_txt_json_and_zip_never_include_complete_runtime_keys(self) -> None:
        secret = "sk-newsapi-complete-secret-123456"
        with tempfile.TemporaryDirectory() as tmp, patch.dict(
            os.environ,
            {"SN_DATA_DIR": tmp, "SN_NEWSAPI_KEY": secret, "SN_ALPHA_VANTAGE_KEY": "alpha-complete-secret-987"},
            clear=False,
        ):
            result = build_full_system_txt_report()
            txt = Path(result["latest_txt_path"]).read_text(encoding="utf-8", errors="replace")
            js = Path(result["json_path"]).read_text(encoding="utf-8", errors="replace")
            with zipfile.ZipFile(result["diagnostics_bundle_path"]) as zf:
                bundle_text = "\n".join(zf.read(name).decode("utf-8", errors="replace") for name in zf.namelist())

        for haystack in [txt, js, bundle_text]:
            self.assertNotIn(secret, haystack)
            self.assertNotIn("alpha-complete-secret-987", haystack)
            self.assertNotIn("SN_NEWSAPI_KEY=", haystack)
            self.assertNotIn("SN_ALPHA_VANTAGE_KEY=", haystack)


if __name__ == "__main__":
    unittest.main()
