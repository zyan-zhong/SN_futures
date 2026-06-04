from __future__ import annotations

import json
import os
import shutil
import sys
import unittest
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator
from unittest.mock import patch

sys.path.insert(0, "src")

from sn_futures.services.settings_service import reset_terminal_secrets, save_terminal_secrets


ROOT = Path(__file__).resolve().parents[1]


@contextmanager
def _temporary_data_dir() -> Iterator[Path]:
    base = ROOT / "app_data" / "test_tmp"
    base.mkdir(parents=True, exist_ok=True)
    path = base / f"private_bundle_reset_{uuid.uuid4().hex}"
    path.mkdir(parents=True, exist_ok=False)
    try:
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=True)


class PrivateBundleTushareResetRestoreTest(unittest.TestCase):
    def test_reset_restores_private_bundle_tushare_without_exposing_complete_token(self) -> None:
        with _temporary_data_dir() as tmp:
            root = tmp / "user"
            seed = tmp / "private_bundle_seed.json"
            private_token = "PRIVATE_TUSHARE_TOKEN_123456789"
            user_token = "USER_TUSHARE_TOKEN_123456789"
            seed.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "source": "private_bundle",
                        "secrets": {
                            "SN_ALPHA_VANTAGE_KEY": "PRIVATE_ALPHA_TOKEN_123456789",
                            "SN_NEWSAPI_KEY": "PRIVATE_NEWS_TOKEN_123456789",
                            "SN_TUSHARE_TOKEN": private_token,
                        },
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            with patch.dict(
                os.environ,
                {"SN_DATA_DIR": str(root), "SN_PRIVATE_BUNDLE_SEED": str(seed), "SN_TUSHARE_TOKEN": ""},
                clear=False,
            ):
                save_terminal_secrets({"SN_TUSHARE_TOKEN": user_token})
                reset = reset_terminal_secrets()

        self.assertTrue(reset["tushare_configured"])
        self.assertEqual(reset["tushare_source"], "private_bundle")
        self.assertIn("***", reset["tushare_masked"])
        rendered = json.dumps(reset, ensure_ascii=False)
        self.assertNotIn(private_token, rendered)
        self.assertNotIn(user_token, rendered)


if __name__ == "__main__":
    unittest.main()
