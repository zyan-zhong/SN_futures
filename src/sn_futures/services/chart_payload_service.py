from __future__ import annotations

import csv
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping

from ..api.json_utils import sanitize_for_json
from ..api.schemas import DISCLAIMER
from ..runtime import get_user_output_dir


SCHEMA_VERSION = 1


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _output_dir() -> Path:
    return get_user_output_dir()


def _read_json(path: Path) -> Any:
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return None
    return None


def _read_csv(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    try:
        if not path.exists():
            return rows
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            for row in csv.DictReader(handle):
                rows.append(dict(row))
    except Exception:
        return []
    return rows


def _to_float(value: Any) -> float | None:
    try:
        parsed = float(value)
    except Exception:
        return None
    if parsed != parsed or parsed in {float("inf"), float("-inf")}:
        return None
    return parsed


def _base_payload(
    *,
    chart_type: str,
    x_field: str,
    y_fields: list[str],
    units: dict[str, str],
    source_files: list[str],
    research_only: bool = False,
) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": _now(),
        "chart_type": chart_type,
        "x_field": x_field,
        "y_fields": y_fields,
        "units": units,
        "source_files": source_files,
        "research_only": research_only,
        "downsampled": False,
        "downsample_method": "",
        "points": [],
        "status": "empty",
        "missing_reason": "",
        "message_zh": "",
        "disclaimer": DISCLAIMER,
    }


def _downsample(points: list[dict[str, Any]], max_points: int) -> tuple[list[dict[str, Any]], bool]:
    if max_points <= 0 or len(points) <= max_points:
        return points, False
    if max_points == 1:
        return [points[-1]], True
    step = max(1, (len(points) - 1) // (max_points - 1))
    sampled = points[::step]
    if sampled[-1] != points[-1]:
        sampled.append(points[-1])
    return sampled[: max_points - 1] + [points[-1]], True


def _history_rows() -> tuple[list[Mapping[str, Any]], Path]:
    path = _output_dir() / "sn_market_history.json"
    payload = _read_json(path)
    if isinstance(payload, Mapping):
        rows = payload.get("history") or payload.get("points")
        if isinstance(rows, list):
            return [row for row in rows if isinstance(row, Mapping)], path
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, Mapping)], path
    return [], path


def _market_points(max_points: int) -> tuple[list[dict[str, Any]], bool, Path]:
    rows, path = _history_rows()
    points: list[dict[str, Any]] = []
    for row in rows:
        close = _to_float(row.get("close") or row.get("price") or row.get("latest"))
        if close is None or close <= 0:
            continue
        points.append(
            {
                "time": str(row.get("time") or row.get("date") or row.get("ts") or row.get("datetime") or ""),
                "open": _to_float(row.get("open")) if row.get("open") is not None else close,
                "high": _to_float(row.get("high")) if row.get("high") is not None else close,
                "low": _to_float(row.get("low")) if row.get("low") is not None else close,
                "close": close,
                "volume": _to_float(row.get("volume")),
                "open_interest": _to_float(row.get("open_interest")),
            }
        )
    return (*_downsample(points, max_points), path)


def _latest_point_date(points: list[dict[str, Any]]) -> str:
    dates = []
    for point in points:
        text = str(point.get("time") or "").strip()
        if not text:
            continue
        dates.append(text.split("T", 1)[0].split(" ", 1)[0])
    return max(dates) if dates else ""


def build_price_chart_payload(*, max_points: int = 800) -> dict[str, Any]:
    points, downsampled, path = _market_points(max_points)
    payload = _base_payload(
        chart_type="price",
        x_field="time",
        y_fields=["open", "high", "low", "close"],
        units={"price": "CNY/ton"},
        source_files=[path.name],
    )
    payload.update({"points": points, "downsampled": downsampled})
    latest_date = _latest_point_date(points)
    payload["latest_date"] = latest_date
    payload["data_freshness"] = {
        "latest_date": latest_date,
        "source_file": path.name,
        "row_count": len(points),
    }
    if downsampled:
        payload["downsample_method"] = "stride_keep_ends"
    if points:
        payload.update({"status": "success", "message_zh": "真实行情价格图表数据已读取。"})
    else:
        payload.update({"status": "empty", "missing_reason": "no_market_history_file", "message_zh": "暂无真实行情历史，图表不显示空白画布。"})
    return sanitize_for_json(payload)


def build_volume_chart_payload(*, max_points: int = 800) -> dict[str, Any]:
    points, downsampled, path = _market_points(max_points)
    volume_points = [
        {
            "time": point.get("time"),
            "volume": point.get("volume"),
            "open_interest": point.get("open_interest"),
        }
        for point in points
        if point.get("volume") is not None or point.get("open_interest") is not None
    ]
    payload = _base_payload(
        chart_type="volume",
        x_field="time",
        y_fields=["volume", "open_interest"],
        units={"volume": "contracts", "open_interest": "contracts"},
        source_files=[path.name],
    )
    payload.update({"points": volume_points, "downsampled": downsampled})
    if downsampled:
        payload["downsample_method"] = "stride_keep_ends"
    if volume_points:
        payload.update({"status": "success", "message_zh": "真实成交量/持仓量图表数据已读取。"})
    else:
        payload.update({"status": "empty", "missing_reason": "no_volume_or_open_interest", "message_zh": "暂无成交量或持仓量字段，未绘制空白图表。"})
    return sanitize_for_json(payload)


def _research_curve_path(kind: str, version: str, horizon: str) -> Path:
    safe_version = str(version or "v3").strip() or "v3"
    safe_horizon = str(horizon or "1d").strip() or "1d"
    return _output_dir() / "research_backtests" / safe_version / f"{kind}_{safe_horizon}.csv"


def build_equity_curve_payload(*, version: str = "v3", horizon: str = "1d", max_points: int = 1200) -> dict[str, Any]:
    path = _research_curve_path("equity_curve", version, horizon)
    rows = _read_csv(path)
    points = [
        {"ts": str(row.get("ts") or row.get("time") or row.get("date") or ""), "value": _to_float(row.get("value") or row.get("equity"))}
        for row in rows
    ]
    points = [point for point in points if point["ts"] and point["value"] is not None]
    points, downsampled = _downsample(points, max_points)
    payload = _base_payload(
        chart_type="equity_curve",
        x_field="ts",
        y_fields=["value"],
        units={"equity": "multiple"},
        source_files=[path.name],
        research_only=True,
    )
    payload.update({"points": points, "downsampled": downsampled})
    if downsampled:
        payload["downsample_method"] = "stride_keep_ends"
    if points:
        payload.update({"status": "success", "message_zh": "研究型 OOF 收益曲线已读取；不代表实盘表现。"})
    else:
        payload.update({"status": "empty", "missing_reason": "no_equity_curve_file", "message_zh": "暂无研究回测收益曲线，请先运行研究回测。"})
    return sanitize_for_json(payload)


def build_drawdown_curve_payload(*, version: str = "v3", horizon: str = "1d", max_points: int = 1200) -> dict[str, Any]:
    path = _research_curve_path("drawdown_curve", version, horizon)
    rows = _read_csv(path)
    points: list[dict[str, Any]] = []
    for row in rows:
        value = _to_float(row.get("value") or row.get("drawdown"))
        if value is None:
            continue
        points.append({"ts": str(row.get("ts") or row.get("time") or row.get("date") or ""), "value": min(0.0, value)})
    points = [point for point in points if point["ts"]]
    points, downsampled = _downsample(points, max_points)
    payload = _base_payload(
        chart_type="drawdown_curve",
        x_field="ts",
        y_fields=["value"],
        units={"drawdown": "percent"},
        source_files=[path.name],
        research_only=True,
    )
    payload.update({"points": points, "downsampled": downsampled})
    if downsampled:
        payload["downsample_method"] = "stride_keep_ends"
    if points:
        payload.update({"status": "success", "message_zh": "研究型 OOF 回撤曲线已读取；回撤值为 0 或负数。"})
    else:
        payload.update({"status": "empty", "missing_reason": "no_drawdown_curve_file", "message_zh": "暂无研究回测回撤曲线，请先运行研究回测。"})
    return sanitize_for_json(payload)


def build_factor_coverage_payload() -> dict[str, Any]:
    path = _output_dir() / "feature_coverage_report.json"
    payload = _read_json(path)
    groups = payload.get("groups", []) if isinstance(payload, Mapping) else []
    return sanitize_for_json(
        {
            **_base_payload(
                chart_type="factor_coverage",
                x_field="group",
                y_fields=["coverage_rate"],
                units={"coverage_rate": "ratio"},
                source_files=[path.name],
            ),
            "points": groups if isinstance(groups, list) else [],
            "status": "success" if groups else "empty",
            "missing_reason": "" if groups else "no_feature_coverage_report",
            "message_zh": "因子覆盖率图表数据已读取。" if groups else "暂无因子覆盖率报告。",
        }
    )


def build_high_confidence_payload(*, horizon: str = "1d", candidate_version: str = "v1") -> dict[str, Any]:
    path = _output_dir() / "oof_integrity_report.json"
    payload = _read_json(path)
    horizons = payload.get("horizons", {}) if isinstance(payload, Mapping) else {}
    item = horizons.get(horizon, {}) if isinstance(horizons, Mapping) else {}
    subsets = item.get("confidence_subset", {}) if isinstance(item, Mapping) else {}
    points = list(subsets.values()) if isinstance(subsets, Mapping) else []
    return sanitize_for_json(
        {
            **_base_payload(
                chart_type="high_confidence",
                x_field="coverage_bucket",
                y_fields=["direction_accuracy", "cost_adjusted_expectancy"],
                units={"direction_accuracy": "ratio", "cost_adjusted_expectancy": "return"},
                source_files=[path.name],
                research_only=True,
            ),
            "candidate_version": candidate_version,
            "horizon": horizon,
            "points": points,
            "status": "success" if points else "empty",
            "missing_reason": "" if points else "no_high_confidence_report",
            "message_zh": "高置信 OOF 分层图表已读取。" if points else "暂无高置信 OOF 分层报告。",
        }
    )


def build_data_source_status_payload() -> dict[str, Any]:
    paths = [
        _output_dir() / "market_provider_status.json",
        _output_dir() / "fundamentals" / "fx_macro_provider_status.json",
        _output_dir() / "events" / "news_provider_status.json",
    ]
    points = []
    for path in paths:
        payload = _read_json(path)
        if isinstance(payload, Mapping):
            points.append({"source_file": path.name, "status": payload.get("status") or payload.get("final_status") or "unknown"})
    return sanitize_for_json(
        {
            **_base_payload(
                chart_type="data_source_status",
                x_field="source_file",
                y_fields=["status"],
                units={"status": "category"},
                source_files=[path.name for path in paths],
            ),
            "points": points,
            "status": "success" if points else "empty",
            "missing_reason": "" if points else "no_provider_status_files",
            "message_zh": "数据源状态图表数据已读取。" if points else "暂无数据源状态文件。",
        }
    )
