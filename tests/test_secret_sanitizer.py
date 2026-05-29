from __future__ import annotations

import sys
import unittest

sys.path.insert(0, "src")

from sn_futures.utils.secret_sanitizer import contains_secret_like_value, sanitize_mapping, sanitize_text, sanitize_url


class SecretSanitizerTest(unittest.TestCase):
    def test_sanitize_text_and_url_masks_common_secret_forms(self) -> None:
        raw = "error apikey=NEWS_SECRET_1234567890 Authorization: Bearer TOKEN_SECRET_123456"
        cleaned = sanitize_text(raw)
        self.assertNotIn("NEWS_SECRET_1234567890", cleaned)
        self.assertNotIn("TOKEN_SECRET_123456", cleaned)
        self.assertIn("***", cleaned)

        url = sanitize_url("https://example.test/v2/everything?q=tin&apiKey=NEWS_SECRET_1234567890")
        self.assertNotIn("NEWS_SECRET_1234567890", url)
        self.assertIn("apiKey=%2A%2A%2A", url)

    def test_sanitize_mapping_masks_headers_and_nested_values(self) -> None:
        payload = {
            "headers": {"X-Api-Key": "NEWS_SECRET_1234567890"},
            "error": "SN_NEWSAPI_KEY=NEWS_SECRET_1234567890",
            "url": "https://example.test/?apikey=NEWS_SECRET_1234567890",
        }
        cleaned = sanitize_mapping(payload)
        text = str(cleaned)
        self.assertNotIn("NEWS_SECRET_1234567890", text)
        self.assertIn("***", text)

    def test_contains_secret_like_value(self) -> None:
        self.assertTrue(contains_secret_like_value("apiKey=NEWS_SECRET_1234567890"))
        self.assertTrue(contains_secret_like_value("Authorization: Bearer TOKEN_SECRET_123456"))
        self.assertFalse(contains_secret_like_value("NewsAPI status is key_missing"))


if __name__ == "__main__":
    unittest.main()
