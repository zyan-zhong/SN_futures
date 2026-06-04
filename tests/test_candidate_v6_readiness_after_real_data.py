from __future__ import annotations

import os
import sys
import tempfile
import unittest
import json
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, "src")

from sn_futures.api.terminal_api import handle_terminal_api
from sn_futures.services.real_data_coverage_validation_service import build_candidate_v6_readiness


def _coverage(groups: dict[str, float]) -> dict[str, object]:
    return {
        "sample_count": 140,
        "groups": [
            {"group": group, "coverage_rate": value, "feature_count": 10, "available_feature_count": int(value * 10)}
            for group, value in groups.items()
        ],
        "usable_feature_cols": [],
    }


class CandidateV6ReadinessAfterRealDataTest(unittest.TestCase):
    def test_readiness_blocks_when_no_real_incremental_group_improves(self) -> None:
        readiness = build_candidate_v6_readiness(
            coverage_before=_coverage({"basis": 0.0, "inventory": 0.0}),
            coverage_after=_coverage({"basis": 0.0, "inventory": 0.0}),
            feature_store_v5={
                "status": "success",
                "usable_fields": ["spot_futures_basis"],
                "sample_data_used": False,
                "mock_data_used": False,
                "baseline_used": False,
                "no_lookahead_pass": True,
                "leakage_check_pass": True,
            },
        )

        self.assertEqual(readiness["status"], "blocked")
        self.assertIn("feature_coverage_delta_empty", readiness["blocked_reasons"])
        self.assertFalse(readiness["training_invoked"])
        self.assertFalse(readiness["customer_prediction_generated"])

    def test_readiness_ready_when_real_group_improves_without_sample_or_lookahead(self) -> None:
        readiness = build_candidate_v6_readiness(
            coverage_before=_coverage({"basis": 0.0, "inventory": 0.0}),
            coverage_after=_coverage({"basis": 0.5, "inventory": 0.0}),
            feature_store_v5={
                "status": "success",
                "usable_fields": ["spot_futures_basis", "basis_zscore_60"],
                "sample_data_used": False,
                "mock_data_used": False,
                "baseline_used": False,
                "no_lookahead_pass": True,
                "leakage_check_pass": True,
            },
        )

        self.assertEqual(readiness["status"], "ready")
        self.assertEqual(readiness["new_factor_groups"], ["basis"])
        self.assertIn("spot_futures_basis", readiness["new_fields"])
        self.assertTrue(readiness["no_lookahead_pass"])

    def test_terminal_api_exposes_candidate_v6_readiness_without_training(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            output = Path(tmp) / "outputs"
            readiness = build_candidate_v6_readiness(
                coverage_before=_coverage({"basis": 0.0}),
                coverage_after=_coverage({"basis": 0.5}),
                feature_store_v5={
                    "status": "success",
                    "usable_fields": ["spot_futures_basis"],
                    "sample_data_used": False,
                    "mock_data_used": False,
                    "baseline_used": False,
                    "no_lookahead_pass": True,
                    "leakage_check_pass": True,
                },
            )
            validation_path = output / "diagnostics" / "real_data_coverage_validation.json"
            validation_path.parent.mkdir(parents=True, exist_ok=True)
            validation_path.write_text(
                json.dumps(
                    {
                        "feature_coverage_before": _coverage({"basis": 0.0}),
                        "feature_coverage_after": _coverage({"basis": 0.5}),
                        "feature_store_v5": {
                            "status": "success",
                            "usable_fields": ["spot_futures_basis"],
                            "sample_data_used": False,
                            "mock_data_used": False,
                            "baseline_used": False,
                            "no_lookahead_pass": True,
                            "leakage_check_pass": True,
                        },
                    }
                ),
                encoding="utf-8",
            )

            status, payload = handle_terminal_api("/api/terminal/models/candidate-v6/readiness", method="GET")

            self.assertEqual(status, 200)
            self.assertEqual(payload["status"], readiness["status"])
            self.assertFalse(payload["training_invoked"])
            self.assertFalse(payload["active_updated"])
            self.assertFalse(payload["customer_prediction_generated"])
            self.assertFalse((output / "model_registry" / "active_model.json").exists())
            self.assertFalse((output / "sn_live_predictions.json").exists())

    def test_terminal_api_recomputes_readiness_instead_of_returning_stale_ready_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            output = Path(tmp) / "outputs"
            stale_path = output / "diagnostics" / "candidate_v6_readiness.json"
            stale_path.parent.mkdir(parents=True, exist_ok=True)
            stale_path.write_text(json.dumps({"status": "ready", "ready": True, "new_factor_groups": ["basis"]}), encoding="utf-8")

            status, payload = handle_terminal_api("/api/terminal/models/candidate-v6/readiness", method="GET")

            self.assertEqual(status, 200)
            self.assertEqual(payload["status"], "blocked")
            self.assertFalse(payload["ready"])
            self.assertIn("new_real_factor_group_missing", payload["blocked_reasons"])

    def test_frontend_factor_page_exposes_candidate_v6_readiness_contract(self) -> None:
        terminal_api = Path("frontend/src/api/terminal.ts").read_text(encoding="utf-8")
        types = Path("frontend/src/api/types.ts").read_text(encoding="utf-8")
        factor_page = Path("frontend/src/pages/FactorPage.tsx").read_text(encoding="utf-8")

        self.assertIn("getCandidateV6Readiness", terminal_api)
        self.assertIn("/api/terminal/models/candidate-v6/readiness", terminal_api)
        self.assertIn("CandidateV6ReadinessPayload", types)
        self.assertIn("candidate_v6 数据准入", factor_page)
        self.assertIn("本接口不训练 candidate_v6", factor_page)


if __name__ == "__main__":
    unittest.main()
