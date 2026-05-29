from __future__ import annotations

import json
import warnings
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import numpy as np
import pandas as pd

from .runtime import get_user_data_dir


REQUIRED_COLUMNS = [
    "date",
    "open",
    "high",
    "low",
    "close",
    "volume",
    "open_interest",
    "spot_price",
    "shfe_inventory",
    "lme_inventory",
    "bonded_inventory",
    "warrant",
    "spot_premium",
    "usd_cny",
    "dollar_index",
    "us10y",
    "pmi_surprise",
    "commodity_index_return",
    "top20_net_long",
    "top20_long_share",
    "top20_short_share",
    "smelter_runrate",
    "tc_rc",
    "mine_import_tons",
    "refined_output_tons",
    "apparent_demand_tons",
    "import_profit_ratio",
    "pv_demand_yoy",
    "semi_demand_yoy",
    "myanmar_supply_yoy",
    "indonesia_supply_yoy",
    "drc_supply_yoy",
    "event_score",
    "event_flag",
    "sentiment_score",
    "myanmar_clearance_tons",
    "port_arrivals_tons",
    "downstream_orders_idx",
    "bonded_inventory_delta",
    "lme_overnight_return",
    "domestic_open_gap",
    "delivery_month_flag",
    "warrant_cancelled",
    "maintenance_days",
    "pv_installation_lead",
    "arb_fund_flow",
    "holiday_gap_flag",
]

CORE_REQUIRED_COLUMNS = [
    "date",
    "open",
    "high",
    "low",
    "close",
    "volume",
    "open_interest",
]
MIN_CONTRACT_HISTORY_ROWS = 252


def _cache_dir() -> Path:
    path = get_user_data_dir() / "cache" / "market_history"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _cache_path(name: str) -> Path:
    return _cache_dir() / name


def _symbol_key(symbol: str | None) -> str:
    text = str(symbol or "SN0").strip().upper()
    return text.replace("/", "_")


def _cache_fresh(path: Path, max_age_hours: int) -> bool:
    if not path.exists():
        return False
    age_seconds = pd.Timestamp.now().timestamp() - path.stat().st_mtime
    return age_seconds <= max_age_hours * 3600


def _load_cached_frame(path: Path) -> pd.DataFrame | None:
    if not path.exists():
        return None
    try:
        return pd.read_csv(path)
    except Exception:
        return None


def _safe_cache_frame(frame: pd.DataFrame, path: Path) -> None:
    try:
        frame.to_csv(path, index=False, encoding="utf-8-sig")
    except OSError:
        pass


def _try_import_akshare():
    try:
        import akshare as ak  # type: ignore

        return ak
    except Exception:
        return None


def _fetch_jsonp_payload(url: str, params: dict[str, str], timeout: int = 20) -> object:
    request = Request(
        f"{url}?{urlencode(params)}",
        headers={"Referer": "https://finance.sina.com.cn/", "User-Agent": "Mozilla/5.0"},
    )
    with urlopen(request, timeout=timeout) as response:
        text = response.read().decode("utf-8", errors="ignore")
    if "=(" in text and ");" in text:
        text = text.split("=(", 1)[1].rsplit(");", 1)[0]
    return json.loads(text)


def _fetch_real_daily_sn_sina(symbol: str = "SN0") -> pd.DataFrame:
    url = (
        "https://stock2.finance.sina.com.cn/futures/api/jsonp.php/"
        "var%20_V21052021_4_12=/InnerFuturesNewService.getDailyKLine"
    )
    payload = _fetch_jsonp_payload(url, {"symbol": symbol, "type": "2021_04_12"})
    daily = pd.DataFrame(payload)
    if daily.empty:
        raise RuntimeError(f"Sina daily history returned no rows for {symbol}.")
    daily.columns = ["date", "open", "high", "low", "close", "volume", "hold", "settle"]
    return daily


def _fetch_real_intraday_sn_sina(symbol: str = "SN0", period: str = "15") -> pd.DataFrame:
    url = "https://stock2.finance.sina.com.cn/futures/api/jsonp.php/=/InnerFuturesNewService.getFewMinLine"
    payload = _fetch_jsonp_payload(url, {"symbol": symbol, "type": period})
    intraday = pd.DataFrame(payload)
    if intraday.empty:
        raise RuntimeError(f"Sina intraday history returned no rows for {symbol}.")
    intraday.columns = ["datetime", "open", "high", "low", "close", "volume", "hold"]
    return intraday


def _fetch_eastmoney_json(params: dict[str, str]) -> dict:
    url = "https://datacenter-web.eastmoney.com/api/data/v1/get"
    request = Request(
        f"{url}?{urlencode(params)}",
        headers={"Referer": "https://data.eastmoney.com/", "User-Agent": "Mozilla/5.0"},
    )
    with urlopen(request, timeout=20) as response:
        return json.loads(response.read().decode("utf-8", errors="ignore"))


def _fetch_real_inventory_sn_eastmoney() -> pd.DataFrame:
    code_payload = _fetch_eastmoney_json(
        {
            "reportName": "RPT_FUTU_POSITIONCODE",
            "columns": "TRADE_MARKET_CODE,TRADE_CODE,TRADE_TYPE",
            "filter": '(IS_MAINCODE="1")',
            "pageNumber": "1",
            "pageSize": "500",
            "source": "WEB",
            "client": "WEB",
        }
    )
    code_frame = pd.DataFrame(code_payload.get("result", {}).get("data", []))
    if code_frame.empty:
        raise RuntimeError("Eastmoney inventory code table returned no rows.")
    match = code_frame[code_frame["TRADE_TYPE"].astype(str).isin(["锡", "sn", "SN"])]
    if match.empty:
        match = code_frame[code_frame["TRADE_TYPE"].astype(str).isin(["\u9521", "sn", "SN"])]
    product_id = str(match.iloc[0]["TRADE_CODE"]) if not match.empty else "SN"
    inventory_payload = _fetch_eastmoney_json(
        {
            "reportName": "RPT_FUTU_STOCKDATA",
            "columns": "SECURITY_CODE,TRADE_DATE,ON_WARRANT_NUM,ADDCHANGE",
            "filter": f'(SECURITY_CODE="{product_id}")(TRADE_DATE>=\'2020-10-28\')',
            "pageNumber": "1",
            "pageSize": "500",
            "sortTypes": "-1",
            "sortColumns": "TRADE_DATE",
            "source": "WEB",
            "client": "WEB",
        }
    )
    inventory = pd.DataFrame(inventory_payload.get("result", {}).get("data", []))
    if inventory.empty:
        raise RuntimeError("Eastmoney inventory table returned no rows.")
    inventory = inventory.rename(
        columns={
            "TRADE_DATE": "date",
            "ON_WARRANT_NUM": "shfe_inventory",
            "ADDCHANGE": "shfe_inventory_delta",
        }
    )
    return inventory[["date", "shfe_inventory", "shfe_inventory_delta"]].copy()


def _fetch_real_daily_sn(symbol: str = "SN0") -> pd.DataFrame:
    ak = _try_import_akshare()
    daily = ak.futures_zh_daily_sina(symbol=symbol) if ak is not None else _fetch_real_daily_sn_sina(symbol=symbol)
    daily = daily.rename(columns={"hold": "open_interest", "settle": "spot_price"})
    keep = ["date", "open", "high", "low", "close", "volume", "open_interest", "spot_price"]
    daily = daily[keep].copy()
    daily["date"] = pd.to_datetime(daily["date"])
    for col in keep[1:]:
        daily[col] = pd.to_numeric(daily[col], errors="coerce")
    return daily.sort_values("date").reset_index(drop=True)


def _fetch_real_intraday_sn(symbol: str = "SN0", period: str = "15") -> pd.DataFrame:
    ak = _try_import_akshare()
    intraday = ak.futures_zh_minute_sina(symbol=symbol, period=period) if ak is not None else _fetch_real_intraday_sn_sina(symbol=symbol, period=period)
    intraday = intraday.rename(columns={"datetime": "date", "hold": "open_interest"})
    intraday["date"] = pd.to_datetime(intraday["date"])
    for col in ("open", "high", "low", "close", "volume", "open_interest"):
        intraday[col] = pd.to_numeric(intraday[col], errors="coerce")
    return intraday.sort_values("date").reset_index(drop=True)


def _fetch_real_inventory_sn() -> pd.DataFrame:
    ak = _try_import_akshare()
    inventory = ak.futures_inventory_em(symbol="\u9521") if ak is not None else _fetch_real_inventory_sn_eastmoney()
    inventory = inventory.rename(columns={"日期": "date", "库存": "shfe_inventory", "增减": "shfe_inventory_delta"})
    inventory["date"] = pd.to_datetime(inventory["date"])
    inventory["shfe_inventory"] = pd.to_numeric(inventory["shfe_inventory"], errors="coerce")
    inventory["shfe_inventory_delta"] = pd.to_numeric(inventory["shfe_inventory_delta"], errors="coerce")
    return inventory.sort_values("date").reset_index(drop=True)


def build_real_dataset(
    symbol: str = "SN0",
    max_age_hours: int = 8,
    force_refresh: bool = False,
) -> pd.DataFrame:
    symbol_key = _symbol_key(symbol)
    daily_cache = _cache_path(f"sn_real_daily_{symbol_key}.csv")
    intraday_cache = _cache_path(f"sn_real_intraday_15m_{symbol_key}.csv")
    inventory_cache = _cache_path("sn_real_inventory.csv")

    daily = None if force_refresh or not _cache_fresh(daily_cache, max_age_hours) else _load_cached_frame(daily_cache)
    intraday = None if force_refresh or not _cache_fresh(intraday_cache, 2) else _load_cached_frame(intraday_cache)
    inventory = None if force_refresh or not _cache_fresh(inventory_cache, 8) else _load_cached_frame(inventory_cache)

    if daily is None:
        daily = _fetch_real_daily_sn(symbol=symbol)
        _safe_cache_frame(daily, daily_cache)
    else:
        daily["date"] = pd.to_datetime(daily["date"])

    if intraday is None:
        intraday = _fetch_real_intraday_sn(symbol=symbol)
        _safe_cache_frame(intraday, intraday_cache)
    else:
        intraday["date"] = pd.to_datetime(intraday["date"])

    if inventory is None:
        try:
            inventory = _fetch_real_inventory_sn()
            _safe_cache_frame(inventory, inventory_cache)
        except Exception:
            inventory = pd.DataFrame(columns=["date", "shfe_inventory", "shfe_inventory_delta"])
    else:
        inventory["date"] = pd.to_datetime(inventory["date"])

    intraday_work = intraday.copy()
    intraday_work["session_date"] = intraday_work["date"].dt.normalize()
    intraday_daily = intraday_work.groupby("session_date", as_index=False).agg(
        intraday_close=("close", "last"),
        intraday_high=("high", "max"),
        intraday_low=("low", "min"),
        intraday_volume=("volume", "sum"),
        intraday_open_interest=("open_interest", "last"),
        intraday_realized_vol=("close", lambda s: pd.Series(s).pct_change().std(ddof=1)),
    )
    intraday_daily = intraday_daily.rename(columns={"session_date": "date"})

    frame = daily.merge(intraday_daily, on="date", how="left")
    if not inventory.empty:
        frame = frame.merge(inventory, on="date", how="left")

    frame["spot_price"] = frame["spot_price"].fillna(frame["close"])
    frame["spot_premium"] = frame["spot_price"] - frame["close"]
    frame["shfe_inventory"] = frame["shfe_inventory"].ffill()
    frame["shfe_inventory_delta"] = frame.get("shfe_inventory_delta", pd.Series(index=frame.index, dtype=float)).fillna(frame["shfe_inventory"].diff())
    frame["bonded_inventory"] = np.nan
    frame["lme_inventory"] = np.nan
    frame["warrant"] = frame["shfe_inventory"]
    frame["warrant_cancelled"] = (-frame["shfe_inventory_delta"]).clip(lower=0)
    frame["usd_cny"] = np.nan
    frame["dollar_index"] = np.nan
    frame["us10y"] = np.nan
    frame["pmi_surprise"] = np.nan
    frame["commodity_index_return"] = np.nan
    frame["top20_net_long"] = np.nan
    frame["top20_long_share"] = np.nan
    frame["top20_short_share"] = np.nan
    frame["smelter_runrate"] = np.nan
    frame["tc_rc"] = np.nan
    frame["mine_import_tons"] = np.nan
    frame["refined_output_tons"] = np.nan
    frame["apparent_demand_tons"] = np.nan
    frame["import_profit_ratio"] = np.nan
    frame["pv_demand_yoy"] = np.nan
    frame["semi_demand_yoy"] = np.nan
    frame["myanmar_supply_yoy"] = np.nan
    frame["indonesia_supply_yoy"] = np.nan
    frame["drc_supply_yoy"] = np.nan
    frame["event_score"] = 0.0
    frame["event_flag"] = 0
    frame["sentiment_score"] = 0.0
    frame["myanmar_clearance_tons"] = np.nan
    frame["port_arrivals_tons"] = np.nan
    frame["downstream_orders_idx"] = np.nan
    frame["bonded_inventory_delta"] = np.nan
    frame["lme_overnight_return"] = np.nan
    frame["domestic_open_gap"] = frame["open"] / frame["close"].shift(1) - 1.0
    frame["delivery_month_flag"] = frame["date"].dt.month.isin([1, 5, 9]).astype(int)
    frame["maintenance_days"] = np.nan
    frame["pv_installation_lead"] = np.nan
    frame["arb_fund_flow"] = np.nan
    frame["holiday_gap_flag"] = (frame["date"].diff().dt.days.fillna(1) > 3).astype(int)
    frame["data_source_mode"] = "real_partial"
    frame["data_quality_score"] = 0.72
    frame["history_symbol"] = symbol_key

    return frame


def build_demo_dataset(n_days: int = 420, seed: int = 42) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    end_date = pd.bdate_range(end=pd.Timestamp.now(tz="Asia/Hong_Kong").tz_localize(None).normalize(), periods=1)[0]
    dates = pd.bdate_range(end=end_date, periods=n_days)
    t = np.arange(n_days)

    supply_tightness = 0.8 * np.sin(t / 28) + rng.normal(0.0, 0.18, n_days)
    demand_pulse = 0.7 * np.cos(t / 36 + 0.4) + rng.normal(0.0, 0.16, n_days)
    macro_pressure = 0.6 * np.sin(t / 44 + 1.2) + rng.normal(0.0, 0.14, n_days)

    event_flag = (rng.random(n_days) < 0.035).astype(int)
    event_direction = rng.choice([1.8, -1.4], size=n_days, p=[0.75, 0.25])
    event_score = event_flag * (event_direction + rng.normal(0.0, 0.18, n_days))
    sentiment_score = np.clip(
        0.5 * event_score + 0.4 * demand_pulse - 0.3 * macro_pressure + rng.normal(0, 0.15, n_days),
        -3.0,
        3.0,
    )

    dollar_return = 0.0012 * macro_pressure + rng.normal(0.0, 0.0015, n_days)
    commodity_index_return = (
        0.0022 * demand_pulse - 0.0014 * macro_pressure + rng.normal(0.0, 0.004, n_days)
    )
    lme_return = (
        0.0028 * supply_tightness
        + 0.0022 * demand_pulse
        - 0.0015 * macro_pressure
        + 0.0038 * event_score
        + rng.normal(0.0, 0.006, n_days)
    )

    sn_return = (
        0.0026 * supply_tightness
        + 0.0024 * demand_pulse
        - 0.0019 * macro_pressure
        + 0.22 * lme_return
        + 0.0036 * event_score
        + rng.normal(0.0, 0.007, n_days)
    )

    close = 205000 * np.exp(np.cumsum(sn_return))
    open_ = np.r_[close[0] * (1 + rng.normal(0, 0.002)), close[:-1] * (1 + rng.normal(0, 0.002, n_days - 1))]
    spread = np.abs(rng.normal(0.009, 0.003, n_days))
    high = np.maximum(open_, close) * (1 + spread)
    low = np.minimum(open_, close) * (1 - spread)

    volume = (
        21000
        * (1 + 0.22 * np.abs(sn_return) * 100 + 0.08 * demand_pulse + 0.10 * event_flag)
        * (1 + rng.normal(0, 0.08, n_days))
    )
    volume = np.clip(volume, 5000, None)

    open_interest = (
        16500
        * (1 + 0.05 * np.cumsum(np.sign(sn_return)) / np.sqrt(np.arange(1, n_days + 1)) + 0.03 * demand_pulse)
        * (1 + rng.normal(0, 0.03, n_days))
    )
    open_interest = np.clip(open_interest, 7000, None)

    shfe_inventory = np.clip(
        5200 * (1 - 0.12 * supply_tightness - 0.09 * demand_pulse + 0.05 * macro_pressure)
        + rng.normal(0, 180, n_days),
        1200,
        None,
    )
    lme_inventory = np.clip(
        4300 * (1 - 0.10 * supply_tightness - 0.05 * demand_pulse + 0.06 * macro_pressure)
        + rng.normal(0, 160, n_days),
        800,
        None,
    )
    bonded_inventory = np.clip(
        900 * (1 - 0.08 * supply_tightness + 0.05 * macro_pressure) + rng.normal(0, 55, n_days),
        120,
        None,
    )

    spot_premium = 1600 * supply_tightness + 850 * demand_pulse + 420 * event_score + rng.normal(0, 140, n_days)
    spot_price = close + spot_premium
    warrant = np.clip(shfe_inventory * (0.68 + rng.normal(0, 0.03, n_days)), 500, None)

    usd_cny = 7.15 * np.exp(np.cumsum(dollar_return))
    dollar_index = 103 * np.exp(np.cumsum(dollar_return * 0.7))
    us10y = 4.0 + 0.18 * macro_pressure + rng.normal(0, 0.05, n_days)
    pmi_surprise = 0.25 * demand_pulse - 0.15 * macro_pressure + rng.normal(0, 0.18, n_days)

    top20_net_long = (
        1800
        + 420 * np.cumsum(np.sign(sn_return)) / np.sqrt(np.arange(1, n_days + 1))
        + 260 * demand_pulse
        + rng.normal(0, 120, n_days)
    )
    top20_long_share = np.clip(0.37 + 0.025 * demand_pulse + rng.normal(0, 0.01, n_days), 0.25, 0.60)
    top20_short_share = np.clip(
        0.34 - 0.015 * demand_pulse + 0.012 * macro_pressure + rng.normal(0, 0.01, n_days),
        0.22,
        0.58,
    )

    smelter_runrate = np.clip(0.79 - 0.03 * supply_tightness + 0.02 * demand_pulse + rng.normal(0, 0.01, n_days), 0.62, 0.93)
    tc_rc = np.clip(15500 - 3200 * supply_tightness + rng.normal(0, 420, n_days), 6000, None)
    mine_import_tons = np.clip(8800 - 1050 * supply_tightness + rng.normal(0, 260, n_days), 3500, None)
    refined_output_tons = np.clip(15700 * smelter_runrate + rng.normal(0, 140, n_days), 9500, None)
    apparent_demand_tons = np.clip(
        15000 * (1 + 0.05 * demand_pulse + 0.01 * sentiment_score) + rng.normal(0, 160, n_days),
        10500,
        None,
    )
    import_profit_ratio = 0.012 * supply_tightness - 0.008 * macro_pressure + rng.normal(0, 0.003, n_days)
    pv_demand_yoy = 0.18 + 0.06 * demand_pulse + rng.normal(0, 0.02, n_days)
    semi_demand_yoy = 0.11 + 0.05 * demand_pulse - 0.01 * macro_pressure + rng.normal(0, 0.018, n_days)
    myanmar_supply_yoy = -0.12 * supply_tightness + rng.normal(0, 0.025, n_days)
    indonesia_supply_yoy = -0.09 * supply_tightness + rng.normal(0, 0.02, n_days)
    drc_supply_yoy = -0.07 * supply_tightness + rng.normal(0, 0.02, n_days)
    myanmar_clearance_tons = np.clip(3600 - 420 * supply_tightness + rng.normal(0, 110, n_days), 1500, None)
    port_arrivals_tons = np.clip(4200 - 360 * supply_tightness + rng.normal(0, 130, n_days), 1800, None)
    downstream_orders_idx = np.clip(100 * (1 + 0.08 * demand_pulse + 0.02 * sentiment_score) + rng.normal(0, 2.5, n_days), 70, None)
    bonded_inventory_delta = np.r_[0.0, np.diff(bonded_inventory)]
    lme_overnight_return = lme_return + rng.normal(0.0, 0.0015, n_days)
    domestic_open_gap = (open_ - np.r_[open_[0], close[:-1]]) / np.r_[open_[0], close[:-1]]
    delivery_month_flag = (dates.month % 3 == 0).astype(int)
    warrant_cancelled = np.clip(warrant * (0.08 + 0.04 * supply_tightness + rng.normal(0, 0.01, n_days)), 20, None)
    maintenance_days = np.clip(3 + 7 * np.maximum(supply_tightness, 0) + rng.normal(0, 1.1, n_days), 0, None)
    pv_installation_lead = np.clip(100 * (1 + 0.05 * demand_pulse) + rng.normal(0, 1.8, n_days), 80, None)
    arb_fund_flow = 60 * supply_tightness - 40 * macro_pressure + 25 * lme_return * 100 + rng.normal(0, 8, n_days)
    holiday_gap_flag = ((dates.dayofweek == 0) | (dates.dayofweek == 4)).astype(int)

    return pd.DataFrame(
        {
            "date": dates,
            "open": open_,
            "high": high,
            "low": low,
            "close": close,
            "volume": volume,
            "open_interest": open_interest,
            "spot_price": spot_price,
            "shfe_inventory": shfe_inventory,
            "lme_inventory": lme_inventory,
            "bonded_inventory": bonded_inventory,
            "warrant": warrant,
            "spot_premium": spot_premium,
            "usd_cny": usd_cny,
            "dollar_index": dollar_index,
            "us10y": us10y,
            "pmi_surprise": pmi_surprise,
            "commodity_index_return": commodity_index_return,
            "top20_net_long": top20_net_long,
            "top20_long_share": top20_long_share,
            "top20_short_share": top20_short_share,
            "smelter_runrate": smelter_runrate,
            "tc_rc": tc_rc,
            "mine_import_tons": mine_import_tons,
            "refined_output_tons": refined_output_tons,
            "apparent_demand_tons": apparent_demand_tons,
            "import_profit_ratio": import_profit_ratio,
            "pv_demand_yoy": pv_demand_yoy,
            "semi_demand_yoy": semi_demand_yoy,
            "myanmar_supply_yoy": myanmar_supply_yoy,
            "indonesia_supply_yoy": indonesia_supply_yoy,
            "drc_supply_yoy": drc_supply_yoy,
            "event_score": event_score,
            "event_flag": event_flag,
            "sentiment_score": sentiment_score,
            "myanmar_clearance_tons": myanmar_clearance_tons,
            "port_arrivals_tons": port_arrivals_tons,
            "downstream_orders_idx": downstream_orders_idx,
            "bonded_inventory_delta": bonded_inventory_delta,
            "lme_overnight_return": lme_overnight_return,
            "domestic_open_gap": domestic_open_gap,
            "delivery_month_flag": delivery_month_flag,
            "warrant_cancelled": warrant_cancelled,
            "maintenance_days": maintenance_days,
            "pv_installation_lead": pv_installation_lead,
            "arb_fund_flow": arb_fund_flow,
            "holiday_gap_flag": holiday_gap_flag,
        }
    )


def validate_columns(df: pd.DataFrame) -> None:
    missing = sorted(set(CORE_REQUIRED_COLUMNS) - set(df.columns))
    if missing:
        raise ValueError(f"Missing required columns: {missing}")


def preprocess_market_data(df: pd.DataFrame) -> pd.DataFrame:
    work = df.copy()
    for col in REQUIRED_COLUMNS:
        if col not in work.columns:
            work[col] = np.nan
    validate_columns(work)
    work["date"] = pd.to_datetime(work["date"])
    work = work.sort_values("date").drop_duplicates(subset=["date"]).set_index("date")

    numeric_cols = work.select_dtypes(include=["number"]).columns
    work[numeric_cols] = work[numeric_cols].ffill()

    event_mask = work["event_flag"].fillna(0).astype(int) == 1
    for col in numeric_cols:
        diff = work[col].diff()
        rolling_mean = diff.rolling(63, min_periods=20).mean()
        rolling_std = diff.rolling(63, min_periods=20).std().replace(0, np.nan)
        zscore = (diff - rolling_mean) / rolling_std
        suspected_error = (zscore.abs() > 3) & (~event_mask)
        work.loc[suspected_error, col] = np.nan
        work[col] = work[col].ffill()

    return work


def load_market_data(
    csv_path: str | Path | None = None,
    *,
    prefer_real: bool = True,
    allow_demo: bool = False,
    real_symbol: str | None = None,
) -> pd.DataFrame:
    if csv_path is None:
        if prefer_real:
            try:
                requested_symbol = _symbol_key(real_symbol or "SN0")
                frame = build_real_dataset(symbol=requested_symbol)
                if requested_symbol != "SN0" and len(frame) < MIN_CONTRACT_HISTORY_ROWS:
                    fallback = build_real_dataset(symbol="SN0")
                    fallback["requested_history_symbol"] = requested_symbol
                    fallback["history_symbol"] = "SN0"
                    fallback["data_source_mode"] = fallback["data_source_mode"].astype(str) + "+continuous_history_fallback"
                    frame = fallback
                else:
                    frame["requested_history_symbol"] = requested_symbol
                    frame["history_symbol"] = requested_symbol
                return preprocess_market_data(frame)
            except Exception as exc:
                if not allow_demo:
                    raise RuntimeError(f"Unable to load real SN history: {exc}") from exc
                warnings.warn(f"Falling back to demo dataset because real history failed: {exc}")
        return preprocess_market_data(build_demo_dataset())

    path = Path(csv_path)
    if not path.exists():
        raise FileNotFoundError(f"CSV file not found: {path}")

    data = pd.read_csv(path)
    return preprocess_market_data(data)
