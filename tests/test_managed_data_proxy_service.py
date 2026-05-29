from __future__ import annotations

import os
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, "src")

from sn_futures.services.managed_data_proxy_service import managed_proxy_status, refresh_managed_data_proxy


class ManagedDataProxyServiceTest(unittest.TestCase):
    def test_managed_proxy_default_disabled(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            os.environ.pop("SN_MANAGED_DATA_PROXY_ENABLED", None)
            os.environ.pop("SN_MANAGED_DATA_PROXY_TOKEN", None)
            status = managed_proxy_status()

        self.assertEqual(status["status"], "disabled")
        self.assertFalse(status["enabled"])
        self.assertFalse(status["client_upload_required"])

    def test_managed_proxy_enabled_without_token_is_token_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(
            os.environ,
            {"SN_DATA_DIR": tmp, "SN_MANAGED_DATA_PROXY_ENABLED": "1"},
            clear=False,
        ):
            os.environ.pop("SN_MANAGED_DATA_PROXY_TOKEN", None)
            result = refresh_managed_data_proxy()

        self.assertEqual(result["status"], "token_missing")
        self.assertFalse(result["success"])
        self.assertFalse(result["client_upload_required"])


if __name__ == "__main__":
    unittest.main()
