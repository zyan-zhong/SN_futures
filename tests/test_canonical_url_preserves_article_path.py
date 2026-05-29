from __future__ import annotations

import sys
import unittest

sys.path.insert(0, "src")

from sn_futures.event_url_resolver import resolve_canonical_url


class CanonicalUrlPreservesArticlePathTest(unittest.TestCase):
    def test_preserves_article_path_and_query(self) -> None:
        url = "https://www.gov.cn/zhengce/2026-05/15/content_123456.htm?source=sn"
        result = resolve_canonical_url(url, network=False)
        self.assertEqual(result.url_status, "ok")
        self.assertEqual(result.canonical_url, url)
        self.assertIn("/zhengce/2026-05/15/content_123456.htm", result.canonical_url)
        self.assertIn("source=sn", result.canonical_url)


if __name__ == "__main__":
    unittest.main()
