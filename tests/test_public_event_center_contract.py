from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


sys.path.insert(0, "src")

from sn_futures.api.terminal_api import handle_terminal_api
from sn_futures.data_layer.event_store import EventStore
from sn_futures.public_terminal.event_service import build_public_event_center
from sn_futures.public_terminal.report_service import build_public_report


def _persist_event(
    tmp_path: Path,
    *,
    title: str,
    provider_id: str,
    data_kind: str,
    fetched_at: str,
    source_published_at: str = "",
    category: str = "",
    region: str = "",
    language: str = "",
    summary: str = "",
) -> None:
    event: dict[str, Any] = {
        "title": title,
        "url": f"https://example.invalid/{provider_id}/{title.replace(' ', '-').lower()}",
        "summary": summary or title,
        "category": category,
        "region": region,
        "language": language,
    }
    if source_published_at:
        event["source_published_at"] = source_published_at
    EventStore(output_dir=tmp_path / "outputs").persist_event(
        provider_id=provider_id,
        data_kind=data_kind,
        event=event,
        fetched_at=fetched_at,
    )


def _event_by_title(payload: dict[str, Any], title: str) -> dict[str, Any]:
    for event in payload["event_center"]["events"]:
        if event["title"] == title:
            return event
    raise AssertionError(f"missing event: {title}\n{payload}")


def test_valid_events_are_classified_with_relevance_and_time_provenance(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("SN_DATA_DIR", str(tmp_path))
    _persist_event(
        tmp_path,
        title="China policy supports tin solder supply chain",
        provider_id="public_policy_rss",
        data_kind="policy_event",
        category="china_policy",
        region="CN",
        language="zh",
        source_published_at="2026-06-10T08:00:00+08:00",
        fetched_at="2026-06-11T09:00:00+08:00",
    )
    _persist_event(
        tmp_path,
        title="Global policy reviews Indonesia tin export quota",
        provider_id="newsapi",
        data_kind="news_event",
        category="global_policy",
        region="global",
        language="en",
        source_published_at="2026-06-10T10:00:00+08:00",
        fetched_at="2026-06-11T09:01:00+08:00",
    )
    _persist_event(
        tmp_path,
        title="SHFE tin warehouse warrants announcement",
        provider_id="shfe_public",
        data_kind="exchange_public",
        category="exchange_notice",
        region="CN",
        language="zh",
        source_published_at="2026-06-10T15:30:00+08:00",
        fetched_at="2026-06-11T09:02:00+08:00",
    )
    _persist_event(
        tmp_path,
        title="Tin smelter maintenance affects solder producers",
        provider_id="akshare_news",
        data_kind="news_event",
        category="supply_chain_event",
        region="global",
        language="en",
        source_published_at="2026-06-09T13:30:00+08:00",
        fetched_at="2026-06-11T09:03:00+08:00",
    )

    status, payload = handle_terminal_api("/api/public-terminal/events", "GET", {}, None)

    assert status == 200
    center = payload["event_center"]
    assert center["status"] == "ready"
    assert center["summary"]["total_count"] == 4
    assert center["summary"]["eligible_count"] == 4
    assert center["categories"]["china_policy"] == 1
    assert center["categories"]["global_policy"] == 1
    assert center["categories"]["exchange_notice"] == 1
    assert center["categories"]["supply_chain_event"] == 1

    event = _event_by_title(payload, "SHFE tin warehouse warrants announcement")
    assert event["source_published_at"] == "2026-06-10T15:30:00+08:00"
    assert event["fetched_at"] == "2026-06-11T09:02:00+08:00"
    assert event["source_published_at"] != event["fetched_at"]
    assert event["relevance_score"] >= 0.7
    assert event["relevance_to_shfe_sn"] is True
    assert event["used_in_model"] is True
    assert event["category"] == "exchange_notice"
    assert event["region"] == "CN"
    assert event["language"] == "zh"
    assert payload["training_invoked"] is False
    assert payload["prediction_generated"] is False
    json.dumps(payload, ensure_ascii=True, sort_keys=True)


def test_missing_source_published_at_is_visible_but_not_used_in_model(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("SN_DATA_DIR", str(tmp_path))
    _persist_event(
        tmp_path,
        title="China news mentions SHFE tin inventory without publish time",
        provider_id="newsapi",
        data_kind="news_event",
        category="china_news",
        region="CN",
        language="zh",
        fetched_at="2026-06-11T09:04:00+08:00",
    )

    payload = build_public_event_center()
    event = _event_by_title(payload, "China news mentions SHFE tin inventory without publish time")

    assert event["source_published_at"] == ""
    assert event["fetched_at"] == "2026-06-11T09:04:00+08:00"
    assert event["used_in_model"] is False
    assert event["eligible_for_event_factor"] is False
    assert "missing_source_published_at" in event["blocking_reasons"]
    assert payload["event_center"]["summary"]["eligible_count"] == 0


def test_unrelated_news_is_rejected_even_with_publish_time(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("SN_DATA_DIR", str(tmp_path))
    _persist_event(
        tmp_path,
        title="Coffee harvest outlook improves in Brazil",
        provider_id="newsapi",
        data_kind="news_event",
        category="global_news",
        region="global",
        language="en",
        source_published_at="2026-06-10T11:00:00+08:00",
        fetched_at="2026-06-11T09:05:00+08:00",
    )

    payload = build_public_event_center()
    event = _event_by_title(payload, "Coffee harvest outlook improves in Brazil")

    assert event["relevance_to_shfe_sn"] is False
    assert event["relevance_score"] < 0.35
    assert event["used_in_model"] is False
    assert "unrelated_to_shfe_sn" in event["blocking_reasons"]
    assert payload["event_center"]["summary"]["rejected_count"] == 1


def test_public_report_consumes_event_center_summary(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("SN_DATA_DIR", str(tmp_path))
    _persist_event(
        tmp_path,
        title="Global news: tin inventory falls at LME",
        provider_id="newsapi",
        data_kind="news_event",
        category="global_news",
        region="global",
        language="en",
        source_published_at="2026-06-10T11:30:00+08:00",
        fetched_at="2026-06-11T09:06:00+08:00",
    )
    _persist_event(
        tmp_path,
        title="Unrelated entertainment news",
        provider_id="newsapi",
        data_kind="news_event",
        category="global_news",
        region="global",
        language="en",
        source_published_at="2026-06-10T12:30:00+08:00",
        fetched_at="2026-06-11T09:07:00+08:00",
    )

    report = build_public_report()

    assert report["report"]["event_coverage"] == "ready"
    assert report["report"]["event_summary"]["eligible_count"] == 1
    assert report["report"]["event_summary"]["rejected_count"] == 1
    assert report["report"]["event_summary"]["categories"]["global_news"] == 2
