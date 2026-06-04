from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import pandas as pd


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def regime_market_rows(days: int = 180) -> list[dict[str, Any]]:
    start = date(2025, 1, 1)
    rows: list[dict[str, Any]] = []
    close = 230000.0
    for i in range(days):
        if i < days // 3:
            close += 12.0 + (i % 3)
        elif i < (days * 2) // 3:
            close += 85.0 if i % 2 == 0 else -82.0
        else:
            close += 620.0 if i % 2 == 0 else -540.0
        rows.append(
            {
                "trade_date": (start + timedelta(days=i)).isoformat(),
                "open": round(close - 80.0, 2),
                "high": round(close + 180.0, 2),
                "low": round(close - 220.0, 2),
                "close": round(close, 2),
                "volume": 2600 + (i % 17) * 40,
                "open_interest": 42000 + i * 8,
            }
        )
    return rows


def seed_v7_inputs(output_dir: Path) -> None:
    market = regime_market_rows()
    write_json(output_dir / "sn_market_history.json", {"history": market})
    write_json(
        output_dir / "fundamentals" / "sn_tushare_daily.json",
        {
            "rows": [
                {
                    "trade_date": row["trade_date"],
                    "contract": "SN2606",
                    "open_interest": 52000 + i * 11,
                    "settlement": row["close"] + (i % 5) - 2,
                }
                for i, row in enumerate(market)
            ]
        },
    )
    write_json(
        output_dir / "fundamentals" / "sn_tushare_settlement.json",
        {
            "rows": [
                {
                    "trade_date": row["trade_date"],
                    "contract": "SN2606",
                    "settlement": row["close"] + 6,
                    "trading_fee_rate": 0.00014 + (i % 4) * 0.00001,
                    "trading_fee": 2.7 + (i % 3) * 0.1,
                    "long_margin_rate": 0.11 + (i % 5) * 0.001,
                    "short_margin_rate": 0.12 + (i % 5) * 0.001,
                    "offset_today_fee": 1.1 + (i % 2) * 0.2,
                }
                for i, row in enumerate(market)
            ]
        },
    )
    write_json(
        output_dir / "fundamentals" / "sn_tushare_holding.json",
        {
            "rows": [
                {
                    "trade_date": market[i]["trade_date"],
                    "contract": "SN2606",
                    "long_position": 1800 + i * 3,
                    "short_position": 1450 + i * 2,
                    "long_change": 6,
                    "short_change": -5,
                }
                for i in range(0, len(market), 12)
            ]
        },
    )


def read_dataset(path: str) -> pd.DataFrame:
    dataset_path = Path(path)
    if dataset_path.suffix.lower() == ".parquet":
        try:
            return pd.read_parquet(dataset_path)
        except Exception:
            pass
    return pd.read_csv(dataset_path)
