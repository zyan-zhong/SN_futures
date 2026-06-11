from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest


sys.path.insert(0, "src")


ROOT = Path(__file__).resolve().parents[1]
FRONTEND_PUBLIC = ROOT / "frontend" / "src" / "public_terminal"
BACKEND_PUBLIC = ROOT / "src" / "sn_futures" / "public_terminal"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def test_public_payload_guard_blocks_sample_prediction_cards() -> None:
    from sn_futures.core.data_safety import assert_public_payload_real_or_blocked

    payload = {
        "status": "success",
        "cards": {
            "tomorrow": {
                "sample": True,
                "sample_mode": True,
                "direction_label": "buy",
                "price_center": 250000,
            }
        },
        "customer_prediction_generated": True,
    }

    guarded = assert_public_payload_real_or_blocked(payload)

    assert guarded["status"] == "blocked"
    assert guarded["error_code"] == "no_demo_public_firewall"
    assert guarded["cards"] == {}
    assert guarded["sample_data_used"] is False
    assert guarded["baseline_used"] is False
    assert guarded["customer_prediction_generated"] is False
    assert "buy" not in json.dumps(guarded, ensure_ascii=False).lower()


def test_public_terminal_api_exit_runs_no_demo_firewall(monkeypatch: pytest.MonkeyPatch) -> None:
    from sn_futures.api import terminal_api

    monkeypatch.setattr(
        terminal_api,
        "build_public_terminal_readiness",
        lambda: {
            "status": "ready",
            "summary": "ready",
            "cards": {"tomorrow": {"sample": True, "direction_label": "buy"}},
            "customer_prediction_generated": True,
        },
    )

    status, payload = terminal_api.handle_terminal_api("/api/public-terminal/readiness", "GET", {}, None)

    assert status == 200
    assert payload["status"] == "blocked"
    assert payload["error_code"] == "no_demo_public_firewall"
    assert payload["cards"] == {}
    assert payload["customer_prediction_generated"] is False


def test_public_market_and_report_payloads_block_sample_outputs() -> None:
    from sn_futures.core.data_safety import assert_public_payload_real_or_blocked

    market = assert_public_payload_real_or_blocked(
        {
            "market": {
                "status": "success",
                "chart": [{"date": "2026-06-01", "close": 250000, "sample": True}],
                "latest_quote": {"price": 250100},
            }
        }
    )
    report = assert_public_payload_real_or_blocked(
        {
            "report": {
                "status": "ready",
                "sample_report": True,
                "markdown": "# sample report",
                "export_allowed": True,
            }
        }
    )

    assert market["market"]["status"] == "blocked"
    assert market["market"]["chart"] == []
    assert market["market"]["latest_quote"] is None
    assert report["report"]["status"] == "blocked"
    assert report["report"]["export_allowed"] is False
    assert "markdown" not in report["report"]


def test_fake_fixture_manifest_is_never_allowed_for_research_use() -> None:
    from sn_futures.core.data_safety import (
        DataSafetyViolation,
        assert_manifest_allowed_for_pipeline,
        mark_fixture_manifest,
    )

    fixture = mark_fixture_manifest({"status": "accepted", "fake_data_used": True})

    assert fixture["fixture"] is True
    assert fixture["allowed_for_public"] is False
    assert fixture["allowed_for_training"] is False
    assert fixture["allowed_for_prediction"] is False
    assert fixture["allowed_for_backtest"] is False

    with pytest.raises(DataSafetyViolation) as exc:
        assert_manifest_allowed_for_pipeline(
            {
                "fixture": True,
                "fake_data_used": True,
                "allowed_for_training": True,
                "allowed_for_prediction": True,
                "allowed_for_backtest": True,
            },
            pipeline="training",
        )
    assert "fake_data_used" in exc.value.blocking_reasons
    assert "allowed_for_training" in exc.value.blocking_reasons


def test_sample_helpers_are_tests_legacy_or_explicit_fixture_mode_only() -> None:
    allowed_legacy_files = {
        "src/sn_futures/services/terminal_service.py",
    }
    violations: list[str] = []
    pattern = re.compile(r"\b(def\s+)?(build_demo_dataset|sample_predictions)\b")
    for base in [ROOT / "src" / "sn_futures", ROOT / "frontend" / "src"]:
        for path in base.rglob("*"):
            if path.suffix.lower() not in {".py", ".ts", ".tsx"}:
                continue
            rel = path.relative_to(ROOT).as_posix()
            if rel.startswith("tests/") or "/devtools/" in rel or "/legacy/" in rel or rel in allowed_legacy_files:
                continue
            source = _read(path)
            if pattern.search(source) and "EXPLICIT_FIXTURE_MODE_ONLY = True" not in source:
                violations.append(rel)

    assert violations == []


def test_public_terminal_sources_do_not_reference_demo_forecast_or_sample_artifacts() -> None:
    forbidden = [
        re.compile(r"sample\s+prediction", re.IGNORECASE),
        re.compile(r"demo\s+forecast", re.IGNORECASE),
        re.compile(r"baseline\s+card", re.IGNORECASE),
        re.compile(r"sample[_-]?history", re.IGNORECASE),
        re.compile(r"sample[_-]?report", re.IGNORECASE),
        re.compile(r"sample_price_history|sample_report_full|read_sample_report", re.IGNORECASE),
    ]
    violations: list[str] = []
    for base in [FRONTEND_PUBLIC, BACKEND_PUBLIC]:
        for path in base.rglob("*"):
            if path.suffix.lower() not in {".py", ".ts", ".tsx"}:
                continue
            source = _read(path)
            if any(pattern.search(source) for pattern in forbidden):
                violations.append(str(path.relative_to(ROOT)))

    assert violations == []


def test_public_market_and_report_pages_use_public_client_only() -> None:
    checked = [
        FRONTEND_PUBLIC / "PublicMarketPage.tsx",
        FRONTEND_PUBLIC / "PublicReportsPage.tsx",
    ]
    violations = []
    for path in checked:
        source = _read(path)
        if "fetch(" in source or "../api/client" in source:
            violations.append(path.name)
        if "sample_price_history" in source or "sample_report_full" in source or "read_sample_report" in source:
            violations.append(path.name)

    assert violations == []
