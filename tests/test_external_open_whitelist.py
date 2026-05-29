from __future__ import annotations

import sys
import unittest

sys.path.insert(0, "src")

from sn_futures.event_url_resolver import is_external_open_allowed


class ExternalOpenWhitelistTest(unittest.TestCase):
    def test_public_financial_domains_are_allowed(self) -> None:
        self.assertTrue(is_external_open_allowed("https://www.shmet.com/article/1"))
        self.assertTrue(is_external_open_allowed("https://www.shfe.com.cn/news/1"))
        self.assertTrue(is_external_open_allowed("https://finance.sina.com.cn/futures/1"))
        self.assertTrue(is_external_open_allowed("https://not-trusted.example/news"))

    def test_local_private_and_javascript_urls_are_rejected(self) -> None:
        self.assertFalse(is_external_open_allowed("file:///C:/Windows/win.ini"))
        self.assertFalse(is_external_open_allowed("javascript:alert(1)"))
        self.assertFalse(is_external_open_allowed("http://127.0.0.1/admin"))
        self.assertFalse(is_external_open_allowed("http://localhost:8000/admin"))
        self.assertFalse(is_external_open_allowed("http://10.0.0.1/admin"))


if __name__ == "__main__":
    unittest.main()
