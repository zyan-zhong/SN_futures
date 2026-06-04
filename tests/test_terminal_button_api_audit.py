from __future__ import annotations

from pathlib import Path


AUDIT_PATH = Path("docs/TERMINAL_BUTTON_API_AUDIT.md")

REQUIRED_COLUMNS = [
    "页面",
    "按钮名",
    "API",
    "方法",
    "重任务",
    "task queue",
    "loading state",
    "disabled 防重复点击",
    "成功/失败状态",
    "E2E 覆盖",
]

REQUIRED_PAGES = [
    "总览",
    "行情",
    "数据",
    "研究",
    "报告",
    "设置",
    "行情监控",
    "新闻与事件",
    "因子研究",
    "训练数据",
    "模型研究",
    "回测验证",
    "预测观察",
    "Artifact Center",
    "设置与诊断",
]


def _audit_rows() -> list[dict[str, str]]:
    assert AUDIT_PATH.exists(), "button API audit document must exist"
    lines = [line.strip() for line in AUDIT_PATH.read_text(encoding="utf-8").splitlines()]
    table_lines = [line for line in lines if line.startswith("|") and line.endswith("|")]
    assert table_lines, "button API audit must contain a markdown table"

    header = [cell.strip() for cell in table_lines[0].strip("|").split("|")]
    assert header == REQUIRED_COLUMNS

    rows: list[dict[str, str]] = []
    for line in table_lines[2:]:
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        if len(cells) == len(header):
            rows.append(dict(zip(header, cells, strict=True)))
    return rows


def test_terminal_button_api_audit_lists_all_terminal_surfaces() -> None:
    text = AUDIT_PATH.read_text(encoding="utf-8")
    rows = _audit_rows()

    for page in REQUIRED_PAGES:
        assert page in text

    assert len(rows) >= 45


def test_terminal_button_api_audit_has_no_dead_or_unknown_buttons() -> None:
    rows = _audit_rows()

    forbidden = {"", "TBD", "TODO", "unknown", "dead", "未接入"}
    for row in rows:
        for column in REQUIRED_COLUMNS:
            assert row[column] not in forbidden, f"{row['页面']} / {row['按钮名']} has incomplete {column}"
        assert row["成功/失败状态"] in {"yes", "navigation", "copy-only", "manual-danger"}
        assert row["E2E 覆盖"] in {"yes", "mocked", "static-contract", "manual-danger"}


def test_heavy_task_buttons_are_documented_as_task_queue_guarded() -> None:
    rows = _audit_rows()
    heavy_rows = [row for row in rows if row["重任务"] == "yes"]

    assert len(heavy_rows) >= 10
    for row in heavy_rows:
        assert row["task queue"] == "yes", f"{row['按钮名']} must use task queue"
        assert row["loading state"] == "yes", f"{row['按钮名']} must show loading"
        assert row["disabled 防重复点击"] == "yes", f"{row['按钮名']} must disable duplicate clicks"
