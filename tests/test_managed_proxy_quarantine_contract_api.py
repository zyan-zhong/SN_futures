from __future__ import annotations

import json
import unittest
from unittest.mock import patch

import sys

sys.path.insert(0, "src")

from sn_futures.api.terminal_api import TERMINAL_API_DOCS, handle_terminal_api


class ManagedProxyQuarantineContractApiTest(unittest.TestCase):
    def test_docs_list_quarantine_contract_endpoints(self) -> None:
        paths = {row["path"] for row in TERMINAL_API_DOCS["endpoints"]}

        self.assertIn("/api/terminal/managed-proxy/quarantine-contract", paths)
        self.assertIn("/api/terminal/managed-proxy/run-quarantine-contract", paths)
        self.assertIn("/api/terminal/managed-proxy/promote-quarantine-to-research-cache", paths)

    def test_get_quarantine_contract_returns_latest_report(self) -> None:
        with patch(
            "sn_futures.api.terminal_api.get_latest_quarantine_contract_report",
            return_value={
                "status": "blocked",
                "research_cache_promotion_allowed": False,
                "research_cache_written": False,
                "feature_store_v12_allowed": False,
                "training_invoked": False,
                "active_updated": False,
                "customer_prediction_generated": False,
            },
            create=True,
        ):
            status, payload = handle_terminal_api("/api/terminal/managed-proxy/quarantine-contract", method="GET")

        self.assertEqual(status, 200)
        self.assertEqual(payload["status"], "blocked")
        self.assertFalse(payload["research_cache_promotion_allowed"])

    def test_post_quarantine_contract_rejects_custom_output_or_production_cache_and_never_runs_downstream(self) -> None:
        with patch("sn_futures.api.terminal_api.build_quarantine_contract_report", return_value={"status": "ready"}, create=True) as run_contract, patch(
            "sn_futures.api.terminal_api.promote_quarantine_to_research_cache", return_value={"status": "ready"}, create=True
        ) as promote, patch("sn_futures.api.terminal_api.build_feature_store_v12") as build_v12, patch(
            "sn_futures.api.terminal_api.build_training_dataset_v12"
        ) as build_td, patch("sn_futures.api.terminal_api.run_candidate_v12_research") as candidate:
            output_status, output_payload = handle_terminal_api(
                "/api/terminal/managed-proxy/promote-quarantine-to-research-cache",
                method="POST",
                body=json.dumps({"output_path": "outputs/fundamentals/managed_fundamentals.json"}),
            )
            production_status, production_payload = handle_terminal_api(
                "/api/terminal/managed-proxy/promote-quarantine-to-research-cache",
                method="POST",
                body=json.dumps({"production_cache": True, "build_v12": True}),
            )

        self.assertEqual(output_status, 400)
        self.assertIn("custom_output_path_forbidden", json.dumps(output_payload, ensure_ascii=False))
        self.assertEqual(production_status, 400)
        self.assertIn("production_cache_promotion_forbidden", json.dumps(production_payload, ensure_ascii=False))
        run_contract.assert_not_called()
        promote.assert_not_called()
        build_v12.assert_not_called()
        build_td.assert_not_called()
        candidate.assert_not_called()

    def test_post_quarantine_contract_and_promote_use_safe_fixed_paths(self) -> None:
        contract = {
            "status": "ready",
            "research_cache_promotion_allowed": True,
            "research_cache_written": False,
            "feature_store_v12_allowed": False,
            "training_invoked": False,
            "active_updated": False,
            "customer_prediction_generated": False,
        }
        promoted = {**contract, "research_cache_written": True, "research_cache_path": "outputs/managed_proxy_research_cache/cache.json"}
        with patch("sn_futures.api.terminal_api.build_quarantine_contract_report", return_value=contract, create=True) as run_contract, patch(
            "sn_futures.api.terminal_api.promote_quarantine_to_research_cache", return_value=promoted, create=True
        ) as promote:
            contract_status, contract_payload = handle_terminal_api("/api/terminal/managed-proxy/run-quarantine-contract", method="POST", body=json.dumps({}))
            promote_status, promote_payload = handle_terminal_api(
                "/api/terminal/managed-proxy/promote-quarantine-to-research-cache",
                method="POST",
                body=json.dumps({}),
            )

        self.assertEqual(contract_status, 200)
        self.assertEqual(promote_status, 200)
        self.assertFalse(contract_payload["feature_store_v12_allowed"])
        self.assertTrue(promote_payload["research_cache_written"])
        run_contract.assert_called_once()
        promote.assert_called_once()


if __name__ == "__main__":
    unittest.main()
