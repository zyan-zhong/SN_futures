from __future__ import annotations

import sys
import unittest

sys.path.insert(0, "src")

from sn_futures.event_url_resolver import resolve_canonical_url


class ShmetCanonicalUrlResolutionTest(unittest.TestCase):
    def test_shmet_url_is_allowed_without_network(self) -> None:
        result = resolve_canonical_url("https://www.shmet.com/news/123", network=False)
        self.assertEqual(result.url_status, "ok")
        self.assertEqual(result.canonical_url, "https://www.shmet.com/news/123")

    def test_unsupported_scheme_is_rejected(self) -> None:
        result = resolve_canonical_url("javascript:alert(1)", network=False)
        self.assertEqual(result.url_status, "invalid")
        self.assertFalse(result.canonical_url)

    def test_public_unknown_domain_is_allowed_by_safe_url_policy(self) -> None:
        result = resolve_canonical_url("https://example.invalid/news", network=False)
        self.assertEqual(result.url_status, "ok")
        self.assertEqual(result.canonical_url, "https://example.invalid/news")


if __name__ == "__main__":
    unittest.main()
