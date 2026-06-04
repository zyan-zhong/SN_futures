from __future__ import annotations

import json
import os
import tempfile
import unittest
import sys

sys.path.insert(0, "src")

from sn_futures.services.managed_data_proxy_service import managed_proxy_status
from sn_futures.utils.secret_sanitizer import sanitize_mapping


class ManagedProxyNoSecretLeakageTest(unittest.TestCase):
    def test_status_and_sanitizer_do_not_leak_license_token(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            os.environ["SN_INSIGHT_DATA_DIR"] = tmp
            os.environ["SN_MANAGED_DATA_PROXY_TOKEN"] = "managed-proxy-secret-token"
            os.environ["SN_MANAGED_DATA_PROXY_URL"] = "https://managed.example"
            status = managed_proxy_status()
            sanitized = sanitize_mapping({"headers": {"X-SN-License-Token": "managed-proxy-secret-token"}})
            text = json.dumps({"status": status, "sanitized": sanitized}, ensure_ascii=False)
            self.assertNotIn("managed-proxy-secret-token", text)
            self.assertIn("token_masked", status)


if __name__ == "__main__":
    unittest.main()
