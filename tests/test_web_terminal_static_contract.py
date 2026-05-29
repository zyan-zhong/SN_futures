from __future__ import annotations

import re
import unittest
from pathlib import Path


class WebTerminalStaticContractTest(unittest.TestCase):
    def test_app_js_is_clean_utf8_and_has_no_probability_fallbacks(self) -> None:
        text = Path("ui_web/app.js").read_text(encoding="utf-8")
        mojibake_sentinels = ["鍒", "涓", "鏄", "�", "锛?", "€"]
        for sentinel in mojibake_sentinels:
            self.assertNotIn(sentinel, text)
        self.assertIn("missing_payload_error", text)
        self.assertNotIn("?? 0.5", text)
        self.assertNotIn("|| 0.5", text)
        self.assertNotIn("1 - up", text)
        self.assertNotIn("window.open(direct", text)

    def test_dom_ids_used_by_app_exist_in_index(self) -> None:
        app = Path("ui_web/app.js").read_text(encoding="utf-8")
        html = Path("ui_web/index.html").read_text(encoding="utf-8")
        used_ids = set(re.findall(r'\$\("([^"]+)"\)', app))
        declared_ids = set(re.findall(r'id="([^"]+)"', html))
        missing = sorted(used_ids - declared_ids)
        self.assertEqual([], missing)

    def test_web_terminal_does_not_require_external_chart_cdn(self) -> None:
        html = Path("ui_web/index.html").read_text(encoding="utf-8")
        app = Path("ui_web/app.js").read_text(encoding="utf-8")
        self.assertNotIn("cdn.jsdelivr", html)
        self.assertIn("renderSvgChart", app)
        self.assertIn("if (!window.echarts) return null", app)

    def test_v37_chinese_labels_and_task_panels_are_wired(self) -> None:
        html = Path("ui_web/index.html").read_text(encoding="utf-8")
        app = Path("ui_web/app.js").read_text(encoding="utf-8")
        self.assertIn("const LABELS", app)
        self.assertIn("候选未通过或尚未运行", app)
        self.assertIn("任务状态字段缺失", app)
        self.assertIn("技术明细", app)
        self.assertIn('id="taskStatusBox"', html)
        self.assertIn('id="chartDiagnostics"', html)
        self.assertIn('id="debugContent"', html)
        self.assertNotIn('id="apiStatus"', html)


if __name__ == "__main__":
    unittest.main()
