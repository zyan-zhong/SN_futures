from __future__ import annotations

import os
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, "src")

from sn_futures.api.terminal_api import TERMINAL_API_DOCS, handle_terminal_api
from sn_futures.services.online_data_source_registry import build_online_data_source_registry


class OnlineDataSourceRegistryTest(unittest.TestCase):
    def test_registry_never_requires_customer_upload(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            payload = build_online_data_source_registry()

        self.assertFalse(payload["client_upload_required"])
        self.assertGreaterEqual(len(payload["sources"]), 6)
        for source in payload["sources"]:
            self.assertFalse(source["client_upload_required"], source["source_id"])

    def test_registry_contains_expected_online_layers(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            payload = build_online_data_source_registry()
        source_ids = {item["source_id"] for item in payload["sources"]}

        self.assertIn("akshare_exchange_daily", source_ids)
        self.assertIn("alphavantage_fx_macro", source_ids)
        self.assertIn("public_lme_tin_probe", source_ids)
        self.assertIn("managed_data_proxy", source_ids)

    def test_online_data_source_api_and_docs_are_available(self) -> None:
        endpoints = {item["path"] for item in TERMINAL_API_DOCS["endpoints"]}
        self.assertIn("/api/terminal/online-data-sources/status", endpoints)

        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            status, payload = handle_terminal_api("/api/terminal/online-data-sources/status", "GET", {}, None)

        self.assertEqual(status, 200)
        self.assertFalse(payload["client_upload_required"])
        self.assertIn("sources", payload)


if __name__ == "__main__":
    unittest.main()
