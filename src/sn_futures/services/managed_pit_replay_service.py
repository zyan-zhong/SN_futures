from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path
from typing import Any, Mapping, Sequence

from ..api.json_utils import sanitize_for_json
from ..runtime import get_user_output_dir


REPLAY_VERSION = "pit_replay_v1"
REPLAY_REPORT_FILENAME = "managed_pit_replay_report.json"
REQUIRED_TIMESTAMP_FIELDS = ("source_timestamp", "asof_date", "ingest_timestamp")


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _report_path() -> Path:
    path = get_user_output_dir() / "diagnostics" / REPLAY_REPORT_FILENAME
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _managed_data_path() -> Path:
    return get_user_output_dir() / "fundamentals" / "managed_fundamentals.json"


def _read_json(path: Path) -> Any:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _write_report(payload: Mapping[str, Any]) -> dict[str, Any]:
    safe = sanitize_for_json(dict(payload))
    path = _report_path()
    path.write_text(json.dumps(safe, ensure_ascii=False, indent=2), encoding="utf-8")
    return safe


def _rows_from_payload(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, Mapping):
        rows = payload.get("rows") or payload.get("data") or payload.get("history") or []
    else:
        rows = payload
    if not isinstance(rows, list):
        return []
    return [dict(row) for row in rows if isinstance(row, Mapping)]


def _parse_datetime(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    text = text.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(text).replace(tzinfo=None)
    except Exception:
        pass
    for fmt in ("%Y-%m-%d", "%Y%m%d"):
        try:
            sample = text[:10] if fmt == "%Y-%m-%d" else text[:8]
            return datetime.strptime(sample, fmt)
        except Exception:
            continue
    return None


def _parse_date(value: Any) -> date | None:
    parsed = _parse_datetime(value)
    return parsed.date() if parsed else None


def _cutoff_datetime(value: Any) -> datetime | None:
    parsed = _parse_datetime(value)
    if parsed:
        return parsed
    return None


def _row_id(row: Mapping[str, Any], index: int | None = None) -> str:
    for key in ("row_id", "id", "record_id", "provider_row_id"):
        value = str(row.get(key) or "").strip()
        if value:
            return value
    if index is not None:
        return f"row_{index}"
    return ""


def _revision_value(row: Mapping[str, Any]) -> tuple[int, str]:
    for key in ("provider_revision", "revision", "version", "record_version", "sequence"):
        value = row.get(key)
        try:
            return int(value), str(value)
        except (TypeError, ValueError):
            if str(value or "").strip():
                return 0, str(value)
    return 0, ""


def _sort_key(row: Mapping[str, Any]) -> tuple[datetime, datetime, tuple[int, str], str]:
    asof = _parse_datetime(row.get("asof_date")) or datetime.min
    source = _parse_datetime(row.get("source_timestamp")) or datetime.min
    return (asof, source, _revision_value(row), _row_id(row))


def _missing_timestamp_fields(rows: Sequence[Mapping[str, Any]]) -> list[str]:
    if not rows:
        return list(REQUIRED_TIMESTAMP_FIELDS)
    missing: set[str] = set()
    for row in rows:
        for field in REQUIRED_TIMESTAMP_FIELDS:
            if not str(row.get(field) or "").strip():
                missing.add(field)
    return sorted(missing)


def _row_is_future(row: Mapping[str, Any], cutoff: Any) -> bool:
    cutoff_dt = _cutoff_datetime(cutoff)
    source = _parse_datetime(row.get("source_timestamp"))
    asof = _parse_datetime(row.get("asof_date"))
    if cutoff_dt is None:
        return True
    return bool((source and source > cutoff_dt) or (asof and asof > cutoff_dt))


def select_asof_row_for_cutoff(rows: Sequence[Mapping[str, Any]], prediction_cutoff_date: Any) -> dict[str, Any]:
    cutoff_dt = _cutoff_datetime(prediction_cutoff_date)
    if cutoff_dt is None:
        return {}
    valid = [
        dict(row)
        for row in rows
        if all(str(row.get(field) or "").strip() for field in REQUIRED_TIMESTAMP_FIELDS)
        and not _row_is_future(row, prediction_cutoff_date)
    ]
    if not valid:
        return {}
    return dict(sorted(valid, key=_sort_key)[-1])


def detect_future_row_selected(selected_row: Mapping[str, Any] | None, prediction_cutoff_date: Any) -> bool:
    if not selected_row:
        return False
    return _row_is_future(selected_row, prediction_cutoff_date)


def detect_ingest_timestamp_misuse(selected_row: Mapping[str, Any] | None) -> bool:
    if not selected_row:
        return False
    return not str(selected_row.get("asof_date") or "").strip() and bool(str(selected_row.get("ingest_timestamp") or "").strip())


def build_pit_replay_cases(
    rows: Sequence[Mapping[str, Any]] | None = None,
    cutoffs: Sequence[Any] | None = None,
) -> list[dict[str, Any]]:
    clean_rows = [dict(row) for row in (rows or []) if isinstance(row, Mapping)]
    if cutoffs is None:
        values: set[str] = set()
        for row in clean_rows:
            for key in ("prediction_cutoff_date", "feature_date", "trading_date"):
                value = str(row.get(key) or "").strip()
                if value:
                    values.add(value[:10])
        cutoffs = sorted(values)
    return [
        {"case_id": f"cutoff_{idx + 1}", "prediction_cutoff_date": str(cutoff), "rows": clean_rows}
        for idx, cutoff in enumerate(cutoffs or [])
    ]


def _selected_summary(row: Mapping[str, Any], cutoff: Any) -> dict[str, Any]:
    return {
        "row_id": _row_id(row),
        "prediction_cutoff_date": str(cutoff),
        "asof_date": row.get("asof_date"),
        "source_timestamp": row.get("source_timestamp"),
        "ingest_timestamp": row.get("ingest_timestamp"),
    }


def _future_summaries(rows: Sequence[Mapping[str, Any]], cutoff: Any) -> list[dict[str, Any]]:
    summaries: list[dict[str, Any]] = []
    for index, row in enumerate(rows):
        if _row_is_future(row, cutoff):
            item = _selected_summary(row, cutoff)
            item["row_id"] = item["row_id"] or _row_id(row, index)
            summaries.append(item)
    return summaries


def _load_managed_rows() -> list[dict[str, Any]]:
    return _rows_from_payload(_read_json(_managed_data_path()))


def build_pit_replay_report(
    *,
    rows: Sequence[Mapping[str, Any]] | None = None,
    cutoffs: Sequence[Any] | None = None,
    write: bool = True,
) -> dict[str, Any]:
    clean_rows = [dict(row) for row in (rows if rows is not None else _load_managed_rows()) if isinstance(row, Mapping)]
    cases = build_pit_replay_cases(clean_rows, cutoffs)
    selected_rows: list[dict[str, Any]] = []
    rejected_future_rows: list[dict[str, Any]] = []
    case_results: list[dict[str, Any]] = []
    blocking: list[str] = []
    missing_ts = _missing_timestamp_fields(clean_rows)
    if not clean_rows:
        blocking.append("managed_rows_missing")
    for field in missing_ts:
        blocking.append(f"missing_{field}")
    if not cases:
        blocking.append("pit_replay_cases_missing")

    ingest_misuse = False
    deterministic_pass = True
    for case in cases:
        cutoff = case["prediction_cutoff_date"]
        case_rows = [dict(row) for row in case.get("rows") or [] if isinstance(row, Mapping)]
        selected = select_asof_row_for_cutoff(case_rows, cutoff)
        reverse_selected = select_asof_row_for_cutoff(list(reversed(case_rows)), cutoff)
        if selected and reverse_selected and _selected_summary(selected, cutoff) != _selected_summary(reverse_selected, cutoff):
            deterministic_pass = False
        future_rows = _future_summaries(case_rows, cutoff)
        rejected_future_rows.extend(future_rows)
        selected_future = detect_future_row_selected(selected, cutoff)
        ingest_misuse = ingest_misuse or detect_ingest_timestamp_misuse(selected)
        case_passed = bool(selected) and not selected_future and not missing_ts
        if selected:
            selected_rows.append(_selected_summary(selected, cutoff))
        case_results.append(
            {
                "case_id": case["case_id"],
                "prediction_cutoff_date": cutoff,
                "passed": case_passed,
                "selected_row_id": _row_id(selected) if selected else "",
                "future_row_selected": selected_future,
                "rejected_future_row_count": len(future_rows),
            }
        )
        if not selected:
            blocking.append("no_valid_asof_row_for_cutoff")
        if selected_future:
            blocking.append("future_row_selected")
        if future_rows and not selected:
            blocking.append("future_rows_after_cutoff")

    if ingest_misuse:
        blocking.append("ingest_timestamp_misuse")
    if not deterministic_pass:
        blocking.append("nondeterministic_tiebreak")

    cases_run = len(cases)
    cases_failed = sum(1 for case in case_results if not case.get("passed"))
    blocking = sorted(set(blocking))
    ready = bool(cases_run) and cases_failed == 0 and not blocking
    payload = {
        "status": "ready" if ready else "blocked",
        "replay_version": REPLAY_VERSION,
        "generated_at": _now(),
        "cases_run": cases_run,
        "cases_passed": max(cases_run - cases_failed, 0),
        "cases_failed": cases_failed,
        "case_results": case_results,
        "selected_rows": selected_rows,
        "rejected_future_rows": rejected_future_rows,
        "ingest_timestamp_misuse_detected": bool(ingest_misuse),
        "deterministic_tiebreak_status": "pass" if deterministic_pass else "fail",
        "blocking_reasons": blocking,
        "point_in_time_join_ready": ready,
        "training_invoked": False,
        "active_updated": False,
        "customer_prediction_generated": False,
        "report_path": str(_report_path()),
    }
    return _write_report(payload) if write else sanitize_for_json(payload)


def run_pit_replay_harness(
    *,
    rows: Sequence[Mapping[str, Any]] | None = None,
    cutoffs: Sequence[Any] | None = None,
) -> dict[str, Any]:
    return build_pit_replay_report(rows=rows, cutoffs=cutoffs, write=True)


def get_latest_pit_replay_report() -> dict[str, Any]:
    path = _report_path()
    if path.exists():
        payload = _read_json(path)
        if isinstance(payload, Mapping):
            return sanitize_for_json(dict(payload))
    return sanitize_for_json(
        {
            "status": "blocked",
            "replay_version": REPLAY_VERSION,
            "cases_run": 0,
            "cases_passed": 0,
            "cases_failed": 0,
            "selected_rows": [],
            "rejected_future_rows": [],
            "ingest_timestamp_misuse_detected": False,
            "deterministic_tiebreak_status": "not_run",
            "blocking_reasons": ["pit_replay_report_missing"],
            "point_in_time_join_ready": False,
            "training_invoked": False,
            "active_updated": False,
            "customer_prediction_generated": False,
            "report_path": str(path),
        }
    )


def load_latest_pit_replay_report() -> dict[str, Any]:
    path = _report_path()
    if not path.exists():
        return {}
    payload = _read_json(path)
    return sanitize_for_json(dict(payload)) if isinstance(payload, Mapping) else {}
