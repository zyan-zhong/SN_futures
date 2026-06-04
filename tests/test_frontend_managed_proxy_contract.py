from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class FrontendManagedProxyContractTest(unittest.TestCase):
    def test_settings_page_exposes_endpoint_token_and_test_connection(self) -> None:
        text = (ROOT / "frontend" / "src" / "pages" / "SettingsPage.tsx").read_text(encoding="utf-8")
        self.assertIn("托管数据服务", text)
        self.assertIn("license token", text)
        self.assertIn("endpoint", text.lower())
        self.assertIn("测试托管服务", text)

    def test_data_and_factor_pages_show_managed_proxy_status_and_coverage(self) -> None:
        data_status = (ROOT / "frontend" / "src" / "pages" / "DataStatusPage.tsx").read_text(encoding="utf-8")
        factor = (ROOT / "frontend" / "src" / "pages" / "FactorPage.tsx").read_text(encoding="utf-8")
        self.assertIn("managed proxy", data_status.lower())
        self.assertIn("using_cache", data_status)
        self.assertIn("managed 字段覆盖", factor)
        self.assertIn("spot_futures_basis", factor)
        self.assertIn("lme_tin_close", factor)


if __name__ == "__main__":
    unittest.main()
