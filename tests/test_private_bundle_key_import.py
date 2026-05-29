from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, "src")

from sn_futures.private_bundle_keys import import_private_bundle_keys_if_needed
from sn_futures.services.api_key_resolver import resolve_secret
from sn_futures.services.settings_service import get_terminal_settings_status


FAKE_ALPHA = "FAKE_ALPHA_PRIVATE_123456"
FAKE_NEWS = "FAKE_NEWS_PRIVATE_abcdef"


def _write_seed(path: Path, *, alpha: str = FAKE_ALPHA, news: str = FAKE_NEWS) -> None:
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "source": "private_bundle",
                "created_at": "2026-05-29T00:00:00",
                "secrets": {
                    "SN_ALPHA_VANTAGE_KEY": alpha,
                    "SN_NEWSAPI_KEY": news,
                },
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


class PrivateBundleKeyImportTest(unittest.TestCase):
    def test_private_seed_imports_when_user_secrets_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            seed = Path(tmp) / "private_bundle_seed.json"
            _write_seed(seed)
            env = {
                "SN_DATA_DIR": tmp,
                "SN_PRIVATE_BUNDLE_SEED": str(seed),
                "SN_ALPHA_VANTAGE_KEY": "",
                "SN_NEWSAPI_KEY": "",
            }
            with patch.dict(os.environ, env, clear=False):
                os.environ.pop("SN_ALPHA_VANTAGE_KEY", None)
                os.environ.pop("SN_NEWSAPI_KEY", None)
                result = import_private_bundle_keys_if_needed()
                status = get_terminal_settings_status()
                alpha = resolve_secret("SN_ALPHA_VANTAGE_KEY")
                news = resolve_secret("SN_NEWSAPI_KEY")

        self.assertTrue(result["available"])
        self.assertEqual({item["name"] for item in result["imported"]}, {"SN_ALPHA_VANTAGE_KEY", "SN_NEWSAPI_KEY"})
        self.assertEqual(alpha["source"], "private_bundle")
        self.assertEqual(news["source"], "private_bundle")
        self.assertTrue(status["alpha_vantage_configured"])
        self.assertTrue(status["newsapi_configured"])
        dumped = json.dumps(status, ensure_ascii=False)
        self.assertNotIn(FAKE_ALPHA, dumped)
        self.assertNotIn(FAKE_NEWS, dumped)

    def test_private_seed_with_utf8_bom_is_readable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            seed = Path(tmp) / "private_bundle_seed.json"
            payload = json.dumps(
                {
                    "secrets": {
                        "SN_ALPHA_VANTAGE_KEY": FAKE_ALPHA,
                        "SN_NEWSAPI_KEY": FAKE_NEWS,
                    }
                },
                ensure_ascii=False,
            )
            seed.write_text("\ufeff" + payload, encoding="utf-8")
            with patch.dict(os.environ, {"SN_DATA_DIR": tmp, "SN_PRIVATE_BUNDLE_SEED": str(seed)}, clear=False):
                os.environ.pop("SN_ALPHA_VANTAGE_KEY", None)
                os.environ.pop("SN_NEWSAPI_KEY", None)
                result = import_private_bundle_keys_if_needed()

        self.assertTrue(result["available"])
        self.assertEqual({item["name"] for item in result["imported"]}, {"SN_ALPHA_VANTAGE_KEY", "SN_NEWSAPI_KEY"})

    def test_partial_user_secrets_only_import_missing_key(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            seed = Path(tmp) / "private_bundle_seed.json"
            _write_seed(seed)
            secrets = Path(tmp) / "config" / "secrets.json"
            secrets.parent.mkdir(parents=True)
            secrets.write_text(
                json.dumps(
                    {
                        "SN_ALPHA_VANTAGE_KEY": "USER_ALPHA_PRIVATE_999",
                        "_sources": {"SN_ALPHA_VANTAGE_KEY": "user_secrets"},
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            with patch.dict(os.environ, {"SN_DATA_DIR": tmp, "SN_PRIVATE_BUNDLE_SEED": str(seed)}, clear=False):
                os.environ.pop("SN_ALPHA_VANTAGE_KEY", None)
                os.environ.pop("SN_NEWSAPI_KEY", None)
                result = import_private_bundle_keys_if_needed()
                payload = json.loads(secrets.read_text(encoding="utf-8"))

        self.assertEqual([item["name"] for item in result["imported"]], ["SN_NEWSAPI_KEY"])
        self.assertEqual(payload["SN_ALPHA_VANTAGE_KEY"], "USER_ALPHA_PRIVATE_999")
        self.assertEqual(payload["SN_NEWSAPI_KEY"], FAKE_NEWS)
        self.assertEqual(payload["_sources"]["SN_ALPHA_VANTAGE_KEY"], "user_secrets")
        self.assertEqual(payload["_sources"]["SN_NEWSAPI_KEY"], "private_bundle")


if __name__ == "__main__":
    unittest.main()
