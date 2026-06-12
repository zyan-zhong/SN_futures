from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Any


sys.path.insert(0, "src")

from sn_futures.api.terminal_api import handle_terminal_api


MATRIX_PATH = Path("docs/SYSTEM_ACCEPTANCE_MATRIX.md")
E2E_PATH = Path("frontend/e2e/system-acceptance.spec.ts")
PUBLIC_DIR = Path("frontend/src/public_terminal")

ALLOWED_STATES = {"usable", "blocked_with_reason", "dev_only", "unsupported_with_reason"}
REQUIRED_FEATURES = {
    "install_start",
    "no_key",
    "setup",
    "provider_smoke",
    "refresh",
    "market",
    "indicators",
    "news_events",
    "reports",
    "prediction_blocked",
    "diagnostics",
    "dev_mode_hidden",
    "no_demo_fake",
    "no_raw_secrets",
    "no_buy_sell_advice",
    "resources_model_governance_dev_only",
    "realtime_prediction_dry_run",
}
FORBIDDEN_AMBIGUOUS_TERMS = {
    "tbd",
    "todo",
    "unknown",
    "unclear",
    "maybe",
    "ambiguous",
}
PUBLIC_SAFETY_FORBIDDEN = {
    "sample prediction",
    "fake prediction",
    "demo forecast",
    "baseline card",
    "raw_secret",
    "raw_key",
    "raw_token",
    "authorization",
    "api_key",
    "apikey",
}


def _parse_markdown_table(path: Path) -> list[dict[str, str]]:
    assert path.exists(), f"missing acceptance matrix: {path}"
    rows: list[dict[str, str]] = []
    lines = path.read_text(encoding="utf-8").splitlines()
    table_lines = [line.strip() for line in lines if line.strip().startswith("|")]
    assert table_lines, "acceptance matrix must contain a markdown table"
    header = [cell.strip() for cell in table_lines[0].strip("|").split("|")]
    assert {"feature_id", "state", "public_or_dev", "user_visible_reason", "evidence", "tests"}.issubset(header)
    for line in table_lines[2:]:
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        if len(cells) != len(header):
            continue
        rows.append(dict(zip(header, cells)))
    return rows


def test_system_acceptance_matrix_covers_every_required_feature_without_ambiguity() -> None:
    source = MATRIX_PATH.read_text(encoding="utf-8")
    assert "Full System Acceptance Matrix v2" in source
    rows = _parse_markdown_table(MATRIX_PATH)
    by_feature = {row["feature_id"]: row for row in rows}

    missing = sorted(REQUIRED_FEATURES - set(by_feature))
    assert missing == []

    for feature_id in REQUIRED_FEATURES:
        row = by_feature[feature_id]
        assert row["state"] in ALLOWED_STATES, row
        assert row["public_or_dev"] in {"public", "dev-only", "installer", "safety"}, row
        assert row["user_visible_reason"] and row["user_visible_reason"] != "-", row
        assert row["evidence"] and row["evidence"] != "-", row
        assert row["tests"] and row["tests"] != "-", row
        text = " ".join(row.values()).lower()
        leaked = sorted(term for term in FORBIDDEN_AMBIGUOUS_TERMS if re.search(rf"\b{re.escape(term)}\b", text))
        assert leaked == [], row


def test_public_terminal_openapi_acceptance_endpoints_are_all_non_ambiguous() -> None:
    status, payload = handle_terminal_api("/api/public-terminal/openapi.json", "GET", {}, None)
    assert status == 200
    endpoints = payload.get("endpoints")
    assert isinstance(endpoints, list)

    by_path = {str(item.get("path")): item for item in endpoints if isinstance(item, dict)}
    for path in [
        "/api/public-terminal/readiness",
        "/api/public-terminal/prediction-status",
        "/api/public-terminal/settings/status",
        "/api/public-terminal/settings/save",
        "/api/public-terminal/provider-smoke",
        "/api/public-terminal/refresh-data-status",
        "/api/public-terminal/market",
        "/api/public-terminal/events",
        "/api/public-terminal/report",
    ]:
        assert path in by_path
        endpoint = by_path[path]
        assert endpoint["classification"] == "public"
        assert endpoint["summary"]
        assert endpoint["side_effects"]["training"] is False
        assert endpoint["side_effects"]["prediction"] is False
        assert endpoint["side_effects"]["backtest"] is False
        assert endpoint["side_effects"]["feature_store"] is False
        assert endpoint["side_effects"]["real_api_default"] is False
        assert endpoint["used_by"], path


def test_public_terminal_runtime_payloads_are_blocked_or_usable_with_reason() -> None:
    payloads: list[tuple[str, dict[str, Any]]] = []
    for path in [
        "/api/public-terminal/readiness",
        "/api/public-terminal/prediction-status",
        "/api/public-terminal/market",
        "/api/public-terminal/events",
        "/api/public-terminal/report",
    ]:
        status, payload = handle_terminal_api(path, "GET", {}, None)
        assert status == 200, path
        assert isinstance(payload, dict), path
        payloads.append((path, payload))

    for path, payload in payloads:
        serialized = str(payload).lower()
        assert "customer_prediction_generated': true" not in serialized
        assert "prediction_generated': true" not in serialized
        for forbidden in PUBLIC_SAFETY_FORBIDDEN:
            assert forbidden not in serialized, (path, forbidden)
        status_text = str(payload.get("status") or payload.get("prediction_status", {}).get("status") or "").lower()
        if path == "/api/public-terminal/prediction-status":
            dry_run_status = str(payload.get("prediction_status", {}).get("dry_run_status") or "").lower()
            assert dry_run_status in {"blocked", "skipped", "ready_to_predict", "resource_busy", "stale_data"}
            assert payload["prediction_status"]["dry_run"] is True
        if status_text in {"blocked", "failed", "stale", "skipped"}:
            assert "reason" in serialized or "blocking_reasons" in serialized, path


def test_frontend_acceptance_e2e_and_public_sources_are_safe() -> None:
    assert E2E_PATH.exists(), "missing system acceptance e2e"
    e2e_source = E2E_PATH.read_text(encoding="utf-8")
    for marker in REQUIRED_FEATURES:
        assert marker in e2e_source

    public_source = "\n".join(path.read_text(encoding="utf-8", errors="replace") for path in PUBLIC_DIR.rglob("*.tsx"))
    assert "Candidate Research" not in public_source
    assert "Governance Console" not in public_source
    assert "Feature Store" not in public_source
    assert "fetch(" not in public_source
    lowered = public_source.lower()
    for forbidden in ["sample prediction", "fake prediction", "demo forecast", "buy", "sell"]:
        assert forbidden not in lowered
