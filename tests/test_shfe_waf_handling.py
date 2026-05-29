from __future__ import annotations

import os
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, "src")

from sn_futures.services.shfe_public_data_service import refresh_shfe_public_data
from sn_futures.services.terminal_service import build_terminal_data_status


class ShfeWafHandlingTest(unittest.TestCase):
    def test_blocked_by_waf_does_not_mark_main_market_failed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            result = refresh_shfe_public_data(ak_module=object(), direct_fetcher=lambda: "\u4eba\u673a\u9a8c\u8bc1 captcha")
            data_status = build_terminal_data_status()

        self.assertEqual(result["results"]["shfe_direct_probe"]["status"], "blocked_by_waf")
        self.assertIn(result["status"], {"failed", "partial_success", "success"})
        sources = data_status.get("sources", [])
        direct = next(source for source in sources if source.get("source_name") == "SHFE 官网直连")
        self.assertEqual(direct["freshness_label"], "blocked_by_waf")
        self.assertIn("不影响主行情", direct["message_zh"])


if __name__ == "__main__":
    unittest.main()
