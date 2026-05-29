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


class SettingsKeySourcePriorityTest(unittest.TestCase):
    def test_environment_key_can_be_read(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp, "SN_ALPHA_VANTAGE_KEY": "ENV_ALPHA_1234567890"}, clear=False):
            resolved = resolve_secret("SN_ALPHA_VANTAGE_KEY")

        self.assertTrue(resolved["configured"])
        self.assertEqual(resolved["source"], "env")

    def test_user_secrets_take_priority_over_env(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp, "SN_ALPHA_VANTAGE_KEY": "ENV_ALPHA_1234567890"}, clear=False):
            path = Path(tmp) / "config" / "secrets.json"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps({"SN_ALPHA_VANTAGE_KEY": "USER_ALPHA_1234567890"}), encoding="utf-8")
            resolved = resolve_secret("SN_ALPHA_VANTAGE_KEY")

        self.assertEqual(resolved["source"], "user_secrets")
        self.assertEqual(resolved["value"], "USER_ALPHA_1234567890")


if __name__ == "__main__":
    unittest.main()

