from __future__ import annotations

from pathlib import Path


def test_vite_build_splits_react_echarts_and_vendor_chunks() -> None:
    config = Path("frontend/vite.config.ts").read_text(encoding="utf-8")

    assert "manualChunks" in config
    assert "echarts" in config
    assert "react-vendor" in config
    assert "vendor" in config
    assert "chunkSizeWarningLimit" in config
