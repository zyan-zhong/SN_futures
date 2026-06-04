from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import sys

sys.path.insert(0, "src")

from sn_futures.services.managed_proxy_config_handoff_service import (
    build_secure_config_handoff,
    detect_local_managed_proxy_config,
    validate_no_raw_secret_in_handoff,
)


class ManagedProxyConfigHandoffServiceTest(unittest.TestCase):
    def test_missing_endpoint_and_token_returns_safe_handoff(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {}, clear=True):
            root = Path(tmp)
            (root / "config").mkdir()
            (root / ".env.example").write_text("SN_MANAGED_PROXY_ENABLED=\nSN_MANAGED_PROXY_BASE_URL=\nSN_MANAGED_PROXY_TOKEN=\n", encoding="utf-8")
            (root / ".gitignore").write_text(".env\n.env.local\nconfig/managed_proxy.local.json\nconfig/managed_proxy.mapping.local.json\nsecrets/\n", encoding="utf-8")
            (root / "config" / "managed_proxy.example.json").write_text("{}", encoding="utf-8")
            (root / "config" / "managed_proxy.mapping.example.json").write_text("{}", encoding="utf-8")

            payload = build_secure_config_handoff(project_root=root, write=False)

        serialized = json.dumps(payload, ensure_ascii=False)
        self.assertEqual(payload["status"], "missing_config")
        self.assertEqual(payload["current_step"], "configure_managed_proxy_endpoint_token")
        self.assertFalse(payload["endpoint_configured"])
        self.assertIs(payload["token_configured"], False)
        self.assertIn("SN_MANAGED_PROXY_TOKEN", serialized)
        self.assertIn("<paste-token-only-in-your-local-shell>", serialized)
        self.assertNotIn("raw-secret-token", serialized)
        self.assertFalse(payload["training_invoked"])
        self.assertFalse(payload["active_updated"])
        self.assertFalse(payload["customer_prediction_generated"])

    def test_configured_token_is_masked_and_never_echoed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(
            os.environ,
            {
                "SN_MANAGED_PROXY_ENABLED": "true",
                "SN_MANAGED_PROXY_BASE_URL": "https://managed.example.test",
                "SN_MANAGED_PROXY_TOKEN": "raw-secret-token-123456",
            },
            clear=True,
        ):
            root = Path(tmp)
            (root / "config").mkdir()
            (root / ".env.example").write_text("SN_MANAGED_PROXY_ENABLED=\nSN_MANAGED_PROXY_BASE_URL=\nSN_MANAGED_PROXY_TOKEN=\n", encoding="utf-8")
            (root / ".gitignore").write_text(".env\n.env.local\nconfig/managed_proxy.local.json\nconfig/managed_proxy.mapping.local.json\nsecrets/\n", encoding="utf-8")
            (root / "config" / "managed_proxy.example.json").write_text("{}", encoding="utf-8")
            (root / "config" / "managed_proxy.mapping.example.json").write_text("{}", encoding="utf-8")

            detected = detect_local_managed_proxy_config(project_root=root)
            payload = build_secure_config_handoff(project_root=root, write=False)

        serialized = json.dumps(payload, ensure_ascii=False)
        self.assertTrue(detected["token_configured"])
        self.assertIs(payload["token_configured"], True)
        self.assertTrue(payload["token_masked"])
        self.assertNotEqual(payload["token_masked"], "***")
        self.assertNotIn("raw-secret-token-123456", serialized)
        self.assertEqual(validate_no_raw_secret_in_handoff(payload, extra_secrets=["raw-secret-token-123456"])["status"], "pass")

    def test_alias_conflict_and_gitignore_gap_are_reported_without_side_effects(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(
            os.environ,
            {
                "SN_MANAGED_PROXY_TOKEN": "canonical-token-value",
                "SN_MANAGED_DATA_PROXY_TOKEN": "legacy-token-value",
            },
            clear=True,
        ):
            root = Path(tmp)
            (root / "config").mkdir()
            (root / ".env.example").write_text("SN_MANAGED_PROXY_ENABLED=\nSN_MANAGED_PROXY_BASE_URL=\nSN_MANAGED_PROXY_TOKEN=\n", encoding="utf-8")
            (root / ".gitignore").write_text(".env\nsecrets/\n", encoding="utf-8")
            (root / "config" / "managed_proxy.example.json").write_text("{}", encoding="utf-8")
            (root / "config" / "managed_proxy.mapping.example.json").write_text("{}", encoding="utf-8")

            payload = build_secure_config_handoff(project_root=root, write=False)

        self.assertEqual(payload["env_alias_consistency"]["status"], "warning")
        self.assertIn("SN_MANAGED_PROXY_TOKEN/SN_MANAGED_DATA_PROXY_TOKEN", payload["env_alias_consistency"]["conflicts"])
        self.assertNotEqual(payload["gitignore_secret_coverage"]["status"], "pass")
        self.assertFalse(payload["feature_store_v12_allowed"])
        self.assertFalse(payload["training_invoked"])
        self.assertFalse(payload["active_updated"])
        self.assertFalse(payload["customer_prediction_generated"])


if __name__ == "__main__":
    unittest.main()
