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

from sn_futures.services.settings_service import get_key_diagnostics, get_terminal_settings_status


ROOT = Path(__file__).resolve().parents[1]


@contextmanager
def _temporary_data_dir() -> Iterator[Path]:
    base = ROOT / "app_data" / "test_tmp"
    base.mkdir(parents=True, exist_ok=True)
    path = base / f"private_bundle_import_{uuid.uuid4().hex}"
    path.mkdir(parents=True, exist_ok=False)
    try:
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=True)


def _write_seed(path: Path, token: str = "PRIVATE_TUSHARE_TOKEN_123456789") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "source": "private_bundle",
                "secrets": {
                    "SN_ALPHA_VANTAGE_KEY": "PRIVATE_ALPHA_TOKEN_123456789",
                    "SN_NEWSAPI_KEY": "PRIVATE_NEWS_TOKEN_123456789",
                    "SN_TUSHARE_TOKEN": token,
                },
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


class PrivateBundleTushareImportOnFirstRunTest(unittest.TestCase):
    def test_first_settings_status_imports_tushare_from_private_bundle_seed(self) -> None:
        with _temporary_data_dir() as tmp:
            root = tmp / "user"
            seed = tmp / "private" / "private_bundle_seed.json"
            token = "PRIVATE_TUSHARE_TOKEN_123456789"
            _write_seed(seed, token)
            with patch.dict(
                os.environ,
                {
                    "SN_DATA_DIR": str(root),
                    "SN_PRIVATE_BUNDLE_SEED": str(seed),
                    "SN_TUSHARE_TOKEN": "",
                    "SN_ALPHA_VANTAGE_KEY": "",
                    "SN_NEWSAPI_KEY": "",
                },
                clear=False,
            ):
                status = get_terminal_settings_status()
                diagnostics = get_key_diagnostics()

        self.assertTrue(status["tushare_configured"])
        self.assertEqual(status["tushare_source"], "private_bundle")
        self.assertIn("***", status["tushare_masked"])
        self.assertTrue(diagnostics["tushare"]["configured"])
        self.assertEqual(diagnostics["tushare"]["source"], "private_bundle")
        self.assertNotIn(token, json.dumps(status, ensure_ascii=False))
        self.assertNotIn(token, json.dumps(diagnostics, ensure_ascii=False))


if __name__ == "__main__":
    unittest.main()
