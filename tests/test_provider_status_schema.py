from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))


REQUIRED_STATUS_FIELDS = {
    "source_name",
    "enabled",
    "configured",
    "attempted",
    "success",
    "from_cache",
    "stale",
    "freshness_label",
    "last_attempt_time",
    "last_success_time",
    "ttl_seconds",
    "next_expected_update",
    "row_count",
    "error_code",
    "message_zh",
    "next_actions_zh",
}


def _load_status(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("SN_DATA_DIR", str(tmp_path))
    monkeypatch.delenv("SN_NEWSAPI_KEY", raising=False)
    from sn_futures.services.terminal_service import build_terminal_data_status

    return build_terminal_data_status()


def test_provider_status_schema_contains_required_fields(monkeypatch, tmp_path: Path) -> None:
    payload = _load_status(monkeypatch, tmp_path)
    sources = payload.get("sources", [])
    assert sources
    for source in sources:
        assert REQUIRED_STATUS_FIELDS.issubset(source.keys())


def test_newsapi_unconfigured_not_expired(monkeypatch, tmp_path: Path) -> None:
    payload = _load_status(monkeypatch, tmp_path)
    newsapi = next(source for source in payload["sources"] if source["source_name"] == "NewsAPI")
    assert newsapi["freshness_label"] == "未配置"
    assert newsapi["stale"] is False
    assert "去设置页配置" in "；".join(newsapi["next_actions_zh"])


def test_optional_policy_sources_are_disabled_not_expired(monkeypatch, tmp_path: Path) -> None:
    payload = _load_status(monkeypatch, tmp_path)
    akshare = next(source for source in payload["sources"] if source["source_name"] == "AKShare 新闻")
    miit = next(source for source in payload["sources"] if source["source_name"] == "工信部政策")
    assert akshare["freshness_label"] == "未启用"
    assert miit["freshness_label"] == "未启用"
    assert akshare["stale"] is False
    assert miit["stale"] is False


def test_miit_policy_recent_cache_is_not_expired(monkeypatch, tmp_path: Path) -> None:
    events_dir = tmp_path / "outputs" / "events"
    events_dir.mkdir(parents=True)
    (events_dir / "provider_status.json").write_text(
        json.dumps(
            {
                "providers": [
                    {
                        "name": "miit_policy",
                        "enabled": True,
                        "configured": True,
                        "attempted": True,
                        "success": True,
                        "from_cache": True,
                        "last_success_time": (datetime.now() - timedelta(days=6)).isoformat(),
                        "row_count": 3,
                        "message_zh": "使用工信部政策缓存。",
                    }
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    payload = _load_status(monkeypatch, tmp_path)
    miit = next(source for source in payload["sources"] if source["source_name"] == "工信部政策")
    assert miit["freshness_label"] == "正常"
    assert miit["row_count"] == 3


def test_shfe_public_cache_is_cache_not_failed(monkeypatch, tmp_path: Path) -> None:
    outputs = tmp_path / "outputs"
    outputs.mkdir(parents=True)
    (outputs / "market_provider_status.json").write_text(
        json.dumps(
            {
                "providers": [
                    {
                        "provider_name": "shfe_public",
                        "enabled": True,
                        "configured": True,
                        "attempted": True,
                        "success": True,
                        "from_cache": True,
                        "last_success_time": (datetime.now() - timedelta(hours=6)).isoformat(),
                        "row_count": 2,
                        "message_zh": "使用 SHFE 公共数据缓存。",
                    }
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    payload = _load_status(monkeypatch, tmp_path)
    shfe = next(source for source in payload["sources"] if source["source_name"] == "SHFE 公共数据")
    assert shfe["freshness_label"] in {"使用缓存", "正常"}
    assert shfe["message_zh"]
