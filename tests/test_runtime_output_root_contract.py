from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, "src")

from sn_futures import v2_api
from sn_futures.services.runtime_diagnostics_service import build_runtime_data_diagnostics


def _write_unified(path: Path, latest: float, marker: str, card_count: int = 1) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    cards = {f"h{idx}": {"p_up": 0.5, "p_down": 0.3, "p_neutral": 0.2} for idx in range(card_count)}
    path.write_text(
        json.dumps(
            {
                "cards": cards,
                "data_watermark": {
                    "source_mode": marker,
                    "live_quote": {"symbol": "SN0", "latest": latest, "quote_time": "2026-06-01T09:00:00+08:00"},
                    "latest_realtime": "2026-06-01T09:00:00+08:00",
                    "quality_score": 0.9,
                },
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


class RuntimeOutputRootContractTest(unittest.TestCase):
    def test_data_watermark_reads_runtime_root_not_higher_scoring_legacy_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            sandbox = Path(tmp)
            user_root = sandbox / "user-data"
            runtime_out = user_root / "outputs"
            repo_root = sandbox / "repo"
            legacy_out = repo_root / "outputs"
            _write_unified(runtime_out / "sn_unified_forecast.json", 111.0, "runtime_root", card_count=1)
            _write_unified(legacy_out / "sn_unified_forecast.json", 999.0, "legacy_repo_outputs", card_count=7)

            with patch.dict(os.environ, {"SN_DATA_DIR": str(user_root)}, clear=False), patch("sn_futures.runtime.get_bundle_root", return_value=repo_root):
                cwd = Path.cwd()
                try:
                    os.chdir(repo_root)
                    payload = v2_api.get_data_watermark()
                finally:
                    os.chdir(cwd)

        self.assertEqual(payload["latest_price"], 111.0)
        self.assertEqual(payload["source_mode"], "runtime_root")
        self.assertEqual(payload["runtime_root"], str(runtime_out))
        self.assertEqual(payload["source_path"], str(runtime_out / "sn_unified_forecast.json"))

    def test_missing_runtime_root_does_not_fallback_to_legacy_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            sandbox = Path(tmp)
            user_root = sandbox / "user-data"
            runtime_out = user_root / "outputs"
            repo_root = sandbox / "repo"
            legacy_out = repo_root / "outputs"
            legacy_out.mkdir(parents=True, exist_ok=True)
            (legacy_out / "sn_live_snapshot.json").write_text(
                json.dumps(
                    {
                        "generated_at": "2026-06-01T09:00:00+08:00",
                        "quotes": [{"symbol": "SN0", "latest": 999.0}],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            with patch.dict(os.environ, {"SN_DATA_DIR": str(user_root)}, clear=False), patch("sn_futures.runtime.get_bundle_root", return_value=repo_root):
                cwd = Path.cwd()
                try:
                    os.chdir(repo_root)
                    payload = v2_api.get_data_watermark()
                finally:
                    os.chdir(cwd)

        self.assertEqual(payload["runtime_root"], str(runtime_out))
        self.assertEqual(payload["source_path"], "")
        self.assertEqual(payload["source_mode"], "no_cached_snapshot")
        self.assertIsNone(payload["latest_price"])

    def test_runtime_diagnostics_reports_ignored_legacy_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            sandbox = Path(tmp)
            user_root = sandbox / "user-data"
            runtime_out = user_root / "outputs"
            repo_root = sandbox / "repo"
            legacy_out = repo_root / "outputs"
            legacy_out.mkdir(parents=True, exist_ok=True)
            (legacy_out / "sn_unified_forecast.json").write_text("{}", encoding="utf-8")

            with patch.dict(os.environ, {"SN_DATA_DIR": str(user_root)}, clear=False), patch("sn_futures.runtime.get_bundle_root", return_value=repo_root):
                cwd = Path.cwd()
                try:
                    os.chdir(repo_root)
                    payload = build_runtime_data_diagnostics()
                finally:
                    os.chdir(cwd)

        self.assertEqual(payload["current_runtime_root"], str(runtime_out))
        self.assertEqual(payload["runtime_root"], str(runtime_out))
        self.assertGreaterEqual(payload["found_legacy_artifacts_count"], 1)
        self.assertIn(str(legacy_out), [item["path"] for item in payload["ignored_legacy_dirs"]])
        self.assertIn("旧 outputs", payload["recommendation_zh"])

    def test_model_registry_defaults_to_runtime_root_outputs(self) -> None:
        captured: list[Path] = []

        class FakeRegistry:
            def __init__(self, path: Path) -> None:
                captured.append(path)

            def records(self) -> list[dict[str, object]]:
                return []

        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            from sn_futures.services import learning_status_service, model_health_service

            with (
                patch.object(model_health_service, "ModelRegistry", FakeRegistry),
                patch.object(learning_status_service, "ModelRegistry", FakeRegistry),
            ):
                model_health_service.build_api_model_health(cards={})
                learning_status_service.build_api_learning_status(scheduler_state={})

        expected = Path(tmp) / "outputs" / "model_governance_registry.json"
        self.assertEqual(captured, [expected, expected])

    def test_unwritable_user_data_dir_does_not_fallback_to_bundle_app_data(self) -> None:
        from sn_futures import runtime

        with tempfile.TemporaryDirectory() as tmp:
            user_root = Path(tmp) / "user-data"
            repo_root = Path(tmp) / "repo"
            with (
                patch.object(runtime, "get_user_data_root", return_value=user_root),
                patch.object(runtime, "get_bundle_root", return_value=repo_root),
                patch.object(Path, "write_text", side_effect=PermissionError("blocked")),
            ):
                with self.assertRaises(RuntimeError):
                    runtime.get_user_data_dir()

    def test_unwritable_runtime_outputs_does_not_fallback_to_bundle_app_data(self) -> None:
        from sn_futures import runtime

        with tempfile.TemporaryDirectory() as tmp:
            user_root = Path(tmp) / "user-data"
            user_root.mkdir(parents=True)
            repo_root = Path(tmp) / "repo"
            with (
                patch.object(runtime, "get_user_data_dir", return_value=user_root),
                patch.object(runtime, "get_bundle_root", return_value=repo_root),
                patch.object(Path, "write_text", side_effect=PermissionError("blocked")),
            ):
                with self.assertRaises(RuntimeError):
                    runtime.get_user_output_dir()


if __name__ == "__main__":
    unittest.main()
