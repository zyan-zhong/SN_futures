from __future__ import annotations

import sys
import unittest

sys.path.insert(0, "src")

from sn_futures.event_url_resolver import is_external_open_allowed


class TrustedDomainSubdomainPolicyTest(unittest.TestCase):
    def test_public_subdomains_are_allowed(self) -> None:
        self.assertTrue(is_external_open_allowed("https://news.shmet.com/article/abc"))
        self.assertTrue(is_external_open_allowed("https://finance.sina.com.cn/futures/x"))
        self.assertTrue(is_external_open_allowed("https://www.miit.gov.cn/jgsj/yxj/wjfb/art/2026/art_x.html"))
        self.assertTrue(is_external_open_allowed("https://policy.mofcom.gov.cn/article/2026?id=1"))
        self.assertTrue(is_external_open_allowed("https://evilshfe.com.cn/article/1"))
        self.assertTrue(is_external_open_allowed("https://gov.cn.evil.example/article/1"))

    def test_private_or_local_hosts_are_rejected(self) -> None:
        self.assertFalse(is_external_open_allowed("http://192.168.1.8/article/1"))
        self.assertFalse(is_external_open_allowed("http://169.254.169.254/latest/meta-data"))


if __name__ == "__main__":
    unittest.main()
