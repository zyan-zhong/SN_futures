from __future__ import annotations

import sys
import unittest

sys.path.insert(0, "src")

from sn_futures.event_url_resolver import resolve_canonical_url


class PolicyArticleUrlNotDowngradedToRootTest(unittest.TestCase):
    def test_policy_article_does_not_become_root_url(self) -> None:
        url = "https://www.ndrc.gov.cn/xxgk/zcfb/tz/202605/t20260515_999999.html"
        result = resolve_canonical_url(url, network=False)
        self.assertEqual(result.url_status, "ok")
        self.assertEqual(result.canonical_url, url)
        self.assertNotEqual(result.canonical_url, "https://www.ndrc.gov.cn/")


if __name__ == "__main__":
    unittest.main()
