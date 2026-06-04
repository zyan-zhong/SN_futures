from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend" / "src"


def test_frontend_data_status_types_expose_canonical_times() -> None:
    types = (FRONTEND / "api" / "types.ts").read_text(encoding="utf-8")

    assert "provider_id?: string" in types
    assert "source_file?: string" in types
    assert "status_time?: string" in types
    assert "data_time?: string" in types
    assert "report_time?: string" in types


def test_data_status_panel_displays_canonical_source_times() -> None:
    panel = (FRONTEND / "components" / "data" / "DataSourceStatusPanel.tsx").read_text(encoding="utf-8")

    assert "status_time" in panel
    assert "data_time" in panel
    assert "report_time" in panel
    assert "source_file" in panel


def test_terminal_client_keeps_full_data_status_payload_for_consistency() -> None:
    api = (FRONTEND / "api" / "terminal.ts").read_text(encoding="utf-8")

    assert "getDataStatusPayload" in api
    assert "provider_status_canonical" in api
