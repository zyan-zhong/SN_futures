from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, "src")


class FrontendPreconfiguredKeyContractTest(unittest.TestCase):
    def test_settings_page_explains_preconfigured_keys_without_local_storage(self) -> None:
        page = Path("frontend/src/pages/SettingsPage.tsx").read_text(encoding="utf-8")
        self.assertIn("发行方默认 key", page)
        self.assertIn("已预配置", page)
        self.assertIn("用户手动保存的 key 优先于发行方默认 key", page)
        self.assertIn("重置为发行方默认", page)
        self.assertIn("完整 key 不会返回到前端", page)
        self.assertNotIn("localStorage.setItem", page)
        self.assertNotIn("localStorage[", page)

    def test_frontend_types_include_source_labels(self) -> None:
        types = Path("frontend/src/api/types.ts").read_text(encoding="utf-8")
        self.assertIn("alpha_vantage_source_label_zh", types)
        self.assertIn("newsapi_source_label_zh", types)
        self.assertIn("ui_message_zh", types)


if __name__ == "__main__":
    unittest.main()
