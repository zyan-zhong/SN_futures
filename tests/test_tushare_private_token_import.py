from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, "src")

from sn_futures.services.api_key_resolver import resolve_secret


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


class TusharePrivateTokenImportTest(unittest.TestCase):
    def test_private_release_keys_file_can_supply_tushare_token_before_env(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            private_keys = Path(tmp) / "private_release_keys.json"
            _write_json(private_keys, {"SN_TUSHARE_TOKEN": "PRIVATE_TUSHARE_TOKEN_123456789"})
            with patch.dict(
                os.environ,
                {
                    "SN_DATA_DIR": str(Path(tmp) / "user"),
                    "SN_PRIVATE_RELEASE_KEYS": str(private_keys),
                    "SN_TUSHARE_TOKEN": "ENV_TUSHARE_TOKEN_123456789",
                },
                clear=False,
            ):
                resolved = resolve_secret("SN_TUSHARE_TOKEN")

        self.assertTrue(resolved["configured"])
        self.assertEqual(resolved["source"], "private_release_keys")
        self.assertEqual(resolved["value"], "PRIVATE_TUSHARE_TOKEN_123456789")
        self.assertIn("***", resolved["masked"])

    def test_user_secret_overrides_private_release_keys_and_env(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "user"
            private_keys = Path(tmp) / "private_release_keys.json"
            _write_json(private_keys, {"SN_TUSHARE_TOKEN": "PRIVATE_TUSHARE_TOKEN_123456789"})
            _write_json(root / "config" / "secrets.json", {"SN_TUSHARE_TOKEN": "USER_TUSHARE_TOKEN_123456789"})
            with patch.dict(
                os.environ,
                {
                    "SN_DATA_DIR": str(root),
                    "SN_PRIVATE_RELEASE_KEYS": str(private_keys),
                    "SN_TUSHARE_TOKEN": "ENV_TUSHARE_TOKEN_123456789",
                },
                clear=False,
            ):
                resolved = resolve_secret("SN_TUSHARE_TOKEN")

        self.assertEqual(resolved["source"], "user_secrets")
        self.assertEqual(resolved["value"], "USER_TUSHARE_TOKEN_123456789")

    def test_masked_or_placeholder_values_are_not_treated_as_configured_tokens(self) -> None:
        placeholders = ["***", "masked", "[masked]", "<本机真实 Tushare token>", "your_tushare_token_here"]
        for placeholder in placeholders:
            with self.subTest(placeholder=placeholder), tempfile.TemporaryDirectory() as tmp:
                private_keys = Path(tmp) / "private_release_keys.json"
                _write_json(private_keys, {"SN_TUSHARE_TOKEN": placeholder})
                with patch.dict(
                    os.environ,
                    {"SN_DATA_DIR": str(Path(tmp) / "user"), "SN_PRIVATE_RELEASE_KEYS": str(private_keys), "SN_TUSHARE_TOKEN": ""},
                    clear=False,
                ):
                    resolved = resolve_secret("SN_TUSHARE_TOKEN")

            self.assertFalse(resolved["configured"])
            self.assertEqual(resolved["source"], "none")


if __name__ == "__main__":
    unittest.main()
