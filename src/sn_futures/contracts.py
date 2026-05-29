from __future__ import annotations

from dataclasses import asdict, dataclass

import pandas as pd


@dataclass(frozen=True)
class ContractCandidate:
    contract_code: str
    contract_month: str
    label: str
    sina_symbol: str

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


def _base_timestamp(base_time: pd.Timestamp | None = None) -> pd.Timestamp:
    if base_time is None:
        base_time = pd.Timestamp.now(tz="Asia/Hong_Kong")
    if base_time.tzinfo is None:
        return base_time.tz_localize("Asia/Hong_Kong")
    return base_time.tz_convert("Asia/Hong_Kong")


def rolling_sn_contracts(base_time: pd.Timestamp | None = None, count: int = 6) -> list[ContractCandidate]:
    base = _base_timestamp(base_time)
    # Use the next calendar month as the default trading target contract.
    start = base.tz_localize(None).normalize() + pd.DateOffset(months=1)
    candidates: list[ContractCandidate] = []
    for offset in range(count):
        month_ts = start + pd.DateOffset(months=offset)
        contract_month = month_ts.strftime("%y%m")
        contract_code = f"sn{contract_month}"
        candidates.append(
            ContractCandidate(
                contract_code=contract_code,
                contract_month=month_ts.strftime("%Y-%m"),
                label=f"SN {month_ts.strftime('%Y-%m')} ({contract_code})",
                sina_symbol=f"nf_SN{contract_month}",
            )
        )
    return candidates


def resolve_target_contract(base_time: pd.Timestamp | None = None) -> dict[str, object]:
    candidates = rolling_sn_contracts(base_time=base_time, count=6)
    target = candidates[0]
    return {
        "target_contract": target.contract_code,
        "target_contract_month": target.contract_month,
        "target_contract_label": target.label,
        "target_contract_symbol": target.sina_symbol,
        "continuous_symbol": "nf_SN0",
        "roll_rule": "calendar_next_month",
        "candidates": [candidate.to_dict() for candidate in candidates],
    }


def validate_contract_symbol(symbol: str) -> bool:
    """Validate SHFE tin futures contract symbols such as sn2606 or SN2606."""
    text = str(symbol or "").strip().lower()
    return bool(pd.Series([text]).str.match(r"^sn\d{4}$").iloc[0])


def get_contract_metadata(symbol: str | None = None, base_time: pd.Timestamp | None = None) -> dict[str, object]:
    """Return normalized metadata for a specific SN contract or the current target set."""
    meta = resolve_target_contract(base_time)
    if symbol and validate_contract_symbol(symbol):
        code = symbol.lower()
        month = f"20{code[2:4]}-{code[4:6]}"
        meta.update(
            {
                "target_contract": code,
                "target_contract_month": month,
                "target_contract_label": f"SN {month} ({code})",
                "target_contract_symbol": f"nf_SN{code[2:]}",
            }
        )
    return meta


def detect_main_contract(
    quotes: list[dict[str, object]] | pd.DataFrame | None = None,
    base_time: pd.Timestamp | None = None,
) -> dict[str, object]:
    """Select the most liquid SN contract by open interest, volume and near-month tie-breaker."""
    meta = resolve_target_contract(base_time)
    candidates = pd.DataFrame(meta.get("candidates", []))
    if quotes is None or candidates.empty:
        meta["selection_rule"] = "calendar_next_month_no_live_quotes"
        return meta
    quote_frame = pd.DataFrame(quotes)
    if quote_frame.empty or "symbol" not in quote_frame.columns:
        meta["selection_rule"] = "calendar_next_month_missing_quote_symbols"
        return meta
    merged = candidates.merge(quote_frame, left_on="sina_symbol", right_on="symbol", how="left")
    if merged.empty:
        meta["selection_rule"] = "calendar_next_month_no_candidate_match"
        return meta
    for col in ("latest", "volume", "open_interest"):
        if col not in merged.columns:
            merged[col] = 0.0
        merged[col] = pd.to_numeric(merged[col], errors="coerce").fillna(0.0)
    merged = merged[merged["latest"] > 0].copy()
    if merged.empty:
        meta["selection_rule"] = "calendar_next_month_no_valid_live_price"
        return meta

    def _norm(series: pd.Series) -> pd.Series:
        hi = float(series.max())
        lo = float(series.min())
        if hi <= lo:
            return pd.Series([0.5] * len(series), index=series.index)
        return (series - lo) / (hi - lo)

    merged["month_rank"] = range(len(merged))
    merged["liquidity_score"] = (
        0.60 * _norm(merged["open_interest"])
        + 0.30 * _norm(merged["volume"])
        + 0.10 * (1.0 - merged["month_rank"] / max(len(merged) - 1, 1))
    )
    best = merged.sort_values(["liquidity_score", "open_interest", "volume"], ascending=False).iloc[0]
    meta.update(
        {
            "active_contract": str(best.get("contract_code", meta["target_contract"])),
            "active_contract_symbol": str(best.get("sina_symbol", meta["target_contract_symbol"])),
            "active_contract_month": str(best.get("contract_month", meta["target_contract_month"])),
            "active_contract_label": str(best.get("label", meta["target_contract_label"])),
            "selection_rule": "liquidity_rank_open_interest_volume",
            "liquidity_table": merged[
                ["contract_code", "contract_month", "sina_symbol", "latest", "volume", "open_interest", "liquidity_score"]
            ]
            .sort_values("liquidity_score", ascending=False)
            .to_dict(orient="records"),
        }
    )
    return meta


def build_continuous_contract(frame: pd.DataFrame, price_col: str = "close") -> pd.DataFrame:
    """Build a conservative continuous series without inventing prices.

    If the caller already supplies a single continuous SN series, this function mainly
    normalizes sort order and keeps a roll marker column for downstream charts.
    """
    if frame is None or frame.empty:
        return pd.DataFrame()
    work = frame.copy()
    if "date" in work.columns:
        work["date"] = pd.to_datetime(work["date"], errors="coerce")
        work = work.dropna(subset=["date"]).sort_values("date")
    if "roll_flag" not in work.columns:
        work["roll_flag"] = False
    if price_col in work.columns:
        work[price_col] = pd.to_numeric(work[price_col], errors="coerce")
    return work.reset_index(drop=True)


def roll_adjustment(frame: pd.DataFrame, price_col: str = "close") -> pd.DataFrame:
    """Return a back-adjusted helper series while preserving raw prices."""
    work = build_continuous_contract(frame, price_col=price_col)
    if work.empty or price_col not in work.columns:
        return work
    work["raw_close"] = work[price_col]
    work["adjusted_close"] = work[price_col]
    if "roll_flag" in work.columns:
        roll_rows = work.index[work["roll_flag"].astype(bool)].tolist()
        adjustment = 0.0
        for idx in roll_rows:
            if idx <= 0:
                continue
            prev_price = float(work.loc[idx - 1, price_col])
            new_price = float(work.loc[idx, price_col])
            if pd.notna(prev_price) and pd.notna(new_price):
                adjustment += prev_price - new_price
            work.loc[idx:, "adjusted_close"] = pd.to_numeric(work.loc[idx:, price_col], errors="coerce") + adjustment
    return work
