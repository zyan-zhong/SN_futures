from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_frontend_and_docs_do_not_make_csv_excel_a_customer_requirement() -> None:
    checked_files = [
        ROOT / "frontend" / "src" / "pages" / "DataStatusPage.tsx",
        ROOT / "frontend" / "src" / "pages" / "SettingsPage.tsx",
        ROOT / "docs" / "TIN_FUNDAMENTAL_DATA_SOURCES.md",
    ]
    combined = "\n".join(path.read_text(encoding="utf-8") for path in checked_files if path.exists())

    assert "客户无需 CSV/Excel" in combined or "客户不需要 CSV/Excel" in combined
    assert "必须上传 CSV" not in combined
    assert "必须上传 Excel" not in combined
    assert "客户必须提供 CSV" not in combined
    assert "客户必须提供 Excel" not in combined


def test_no_frontend_import_export_mentions_customer_file_upload_as_main_path() -> None:
    frontend = "\n".join(path.read_text(encoding="utf-8") for path in (ROOT / "frontend" / "src").rglob("*.tsx"))

    assert "本地 CSV 导入" not in frontend
    assert "本地 Excel 导入" not in frontend
    assert "上传库存文件" not in frontend
