from __future__ import annotations

import pandas as pd


def dataframe_to_text(
    df: pd.DataFrame | None,
    *,
    index: bool = False,
    rows: int | None = None,
    columns: list[str] | None = None,
) -> str:
    if not isinstance(df, pd.DataFrame) or df.empty:
        return "数据暂缺。"

    show = df.copy()
    if columns is not None:
        safe_cols = [col for col in columns if col in show.columns]
        if not safe_cols:
            return "数据暂缺。"
        show = show[safe_cols]
    if rows is not None:
        show = show.tail(rows)

    show = show.fillna("数据暂缺")
    with pd.option_context(
        "display.max_columns",
        None,
        "display.width",
        240,
        "display.max_colwidth",
        80,
    ):
        return show.to_string(index=index)
