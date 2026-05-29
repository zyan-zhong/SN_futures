from __future__ import annotations

from pathlib import Path


def test_frontend_does_not_present_baseline_prediction_or_backtest() -> None:
    banned = ("基线预测", "基线回测", "baseline forecast", "baseline backtest")
    for path in Path("frontend/src").rglob("*"):
        if path.suffix.lower() not in {".ts", ".tsx", ".css"}:
            continue
        text = path.read_text(encoding="utf-8")
        lowered = text.lower()
        for word in banned:
            assert word.lower() not in lowered, f"{path} contains banned baseline wording: {word}"

