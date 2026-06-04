from __future__ import annotations

import json
import unittest
from unittest.mock import patch

import sys

sys.path.insert(0, "src")

from sn_futures.api.terminal_api import TERMINAL_API_DOCS, handle_terminal_api


class ManagedProxySchemaMappingApiTest(unittest.TestCase):
    def test_docs_list_schema_mapping_endpoints(self) -> None:
        paths = {row["path"] for row in TERMINAL_API_DOCS["endpoints"]}

        self.assertIn("/api/terminal/managed-proxy/schema-mapping", paths)
        self.assertIn("/api/terminal/managed-proxy/refresh-schema-mapping", paths)

    def test_get_schema_mapping_returns_sanitized_payload(self) -> None:
        with patch(
            "sn_futures.api.terminal_api.get_schema_mapping_report",
            return_value={
                "status": "blocked",
                "mapped_fields": ["spot_price"],
                "unmapped_required_fields": ["source_timestamp"],
                "ambiguous_mappings": [],
                "schema_mapping_ready": False,
                "training_invoked": False,
                "active_updated": False,
                "customer_prediction_generated": False,
            },
            create=True,
        ):
            status, payload = handle_terminal_api("/api/terminal/managed-proxy/schema-mapping", method="GET")

        self.assertEqual(status, 200)
        self.assertEqual(payload["status"], "blocked")
        self.assertFalse(payload["schema_mapping_ready"])
        self.assertIn("source_timestamp", payload["unmapped_required_fields"])

    def test_refresh_schema_mapping_ignores_body_and_does_not_trigger_downstream_tasks(self) -> None:
        with patch(
            "sn_futures.api.terminal_api.refresh_schema_mapping_report",
            return_value={
                "status": "blocked",
                "mapped_fields": [],
                "unmapped_required_fields": ["source_timestamp"],
                "schema_mapping_ready": False,
                "training_invoked": False,
                "active_updated": False,
                "customer_prediction_generated": False,
            },
            create=True,
        ), patch("sn_futures.api.terminal_api.build_feature_store_v12") as build_v12, patch(
            "sn_futures.api.terminal_api.start_task"
        ) as start_task:
            status, payload = handle_terminal_api(
                "/api/terminal/managed-proxy/refresh-schema-mapping",
                method="POST",
                body=json.dumps({"token": "managed-secret-token", "Authorization": "Bearer managed-secret-token"}),
            )

        self.assertEqual(status, 200)
        self.assertEqual(payload["status"], "blocked")
        self.assertFalse(payload["training_invoked"])
        self.assertFalse(payload["active_updated"])
        self.assertFalse(payload["customer_prediction_generated"])
        build_v12.assert_not_called()
        start_task.assert_not_called()
        self.assertNotIn("managed-secret-token", json.dumps(payload, ensure_ascii=False))


if __name__ == "__main__":
    unittest.main()
