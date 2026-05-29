from __future__ import annotations

import unittest
from pathlib import Path


class NoFrontendFakeProbabilityTest(unittest.TestCase):
    def test_web_ui_does_not_default_probabilities_to_half(self) -> None:
        text = Path("ui_web/app.js").read_text(encoding="utf-8")
        self.assertNotIn("card.p_up ?? card.prob_up ?? 0.5", text)
        self.assertNotIn("card.p_down ?? card.prob_down ?? 0.5", text)
        self.assertNotIn("1 - up", text)
        self.assertNotIn("window.open(direct", text)
        self.assertIn("missing_payload_error", text)


if __name__ == "__main__":
    unittest.main()
