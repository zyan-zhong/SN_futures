from __future__ import annotations

from typing import Iterable

import numpy as np
import pandas as pd

from .light_ml import LinearRegressionLite, spearmanr_lite


TECHNICAL_FEATURES = [
    "ma_bias_5",
    "ma_bias_20",
    "ema_spread_5_20",
    "macd_hist_delta",
    "boll_pos_20",
    "adx_14",
    "breakout_20",
    "intraday_persistence",
    "rsi_14",
    "kdj_k",
    "cci_20",
    "wr_14",
    "roc_10",
    "mfi_14",
    "atr_14",
    "hv_20",
    "ewma_vol_20",
    "range_vol_pct",
    "trend_efficiency_20",
    "donchian_pos_55",
    "choppiness_14",
    "volatility_compression",
    "realized_skew_20",
    "realized_kurt_20",
    "close_to_vwap_20",
    "delivery_liquidity_stress",
    "holiday_gap_stress",
]

FLOW_FEATURES = [
    "volume_chg_5",
    "oi_chg_5",
    "price_volume_div",
    "price_oi_div",
    "obv_slope_10",
    "net_long_top20_chg",
    "concentration_gap",
    "warrant_chg_5",
    "basis_mom_5",
    "warrant_cancel_ratio",
    "arb_fund_flow_factor",
    "cross_market_gap_factor",
    "oi_volume_pressure",
    "volume_zscore_20",
    "amihud_20",
    "signed_volume_pressure",
]

FUNDAMENTAL_FEATURES = [
    "supply_gap",
    "inventory_to_consumption",
    "inventory_chg_20",
    "smelter_runrate_mom",
    "tc_rc_yoy",
    "mine_supply_shock",
    "import_surprise_z",
    "spot_premium_mom",
    "import_arb_ratio",
    "lme_shfe_inventory_gap",
    "pv_demand_surprise",
    "semi_demand_surprise",
    "delivery_basis_momentum",
    "tc_rc_delta_5",
    "smelter_maintenance_expectation",
    "downstream_order_accel",
    "customs_arrival_gap",
    "pv_install_lead_surprise",
    "bonded_delta_shock",
    "inventory_pressure_z",
]

MACRO_EVENT_FEATURES = [
    "dxy_ret_5",
    "usdcny_ret_5",
    "us10y_chg_5",
    "pmi_surprise_z",
    "commodity_beta_60",
    "event_sentiment",
    "event_half_life_score",
    "black_swan_alert",
    "liquidity_risk",
    "overnight_lme_domestic_gap",
    "event_vol_regime_shift",
    "policy_heat_score",
    "macro_pressure_score",
]

FEATURE_GROUPS = {
    "technical": TECHNICAL_FEATURES,
    "flow": FLOW_FEATURES,
    "fundamental": FUNDAMENTAL_FEATURES,
    "macro_event": MACRO_EVENT_FEATURES,
}


def rolling_zscore(series: pd.Series, window: int) -> pd.Series:
    mean = series.rolling(window, min_periods=max(5, window // 4)).mean()
    std = series.rolling(window, min_periods=max(5, window // 4)).std().replace(0, np.nan)
    return (series - mean) / std


def _true_range(df: pd.DataFrame) -> pd.Series:
    prev_close = df["close"].shift(1)
    pieces = pd.concat(
        [
            (df["high"] - df["low"]).abs(),
            (df["high"] - prev_close).abs(),
            (df["low"] - prev_close).abs(),
        ],
        axis=1,
    )
    return pieces.max(axis=1)


def _adx(df: pd.DataFrame, period: int = 14) -> pd.Series:
    up_move = df["high"].diff()
    down_move = -df["low"].diff()
    plus_dm = pd.Series(np.where((up_move > down_move) & (up_move > 0), up_move, 0.0), index=df.index)
    minus_dm = pd.Series(np.where((down_move > up_move) & (down_move > 0), down_move, 0.0), index=df.index)
    atr = _true_range(df).rolling(period, min_periods=period).mean()
    plus_di = 100 * plus_dm.rolling(period, min_periods=period).sum() / atr.replace(0, np.nan)
    minus_di = 100 * minus_dm.rolling(period, min_periods=period).sum() / atr.replace(0, np.nan)
    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan)
    return dx.rolling(period, min_periods=period).mean()


def _rsi(close: pd.Series, period: int = 14) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0).rolling(period, min_periods=period).mean()
    loss = -delta.clip(upper=0).rolling(period, min_periods=period).mean()
    rs = gain / loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def _stochastic_k(df: pd.DataFrame, period: int = 14) -> pd.Series:
    lowest = df["low"].rolling(period, min_periods=period).min()
    highest = df["high"].rolling(period, min_periods=period).max()
    return 100 * (df["close"] - lowest) / (highest - lowest).replace(0, np.nan)


def _cci(df: pd.DataFrame, period: int = 20) -> pd.Series:
    tp = (df["high"] + df["low"] + df["close"]) / 3
    ma = tp.rolling(period, min_periods=period).mean()
    md = (tp - ma).abs().rolling(period, min_periods=period).mean()
    return (tp - ma) / (0.015 * md).replace(0, np.nan)


def _mfi(df: pd.DataFrame, period: int = 14) -> pd.Series:
    tp = (df["high"] + df["low"] + df["close"]) / 3
    raw_flow = tp * df["volume"]
    direction = tp.diff()
    pos_flow = pd.Series(np.where(direction > 0, raw_flow, 0.0), index=df.index)
    neg_flow = pd.Series(np.where(direction < 0, raw_flow, 0.0), index=df.index)
    pos_sum = pos_flow.rolling(period, min_periods=period).sum()
    neg_sum = neg_flow.rolling(period, min_periods=period).sum()
    ratio = pos_sum / neg_sum.replace(0, np.nan)
    return 100 - (100 / (1 + ratio))


def build_factor_frame(df: pd.DataFrame) -> pd.DataFrame:
    work = df.copy()
    ret_1 = work["close"].pct_change()
    ret_5 = work["close"].pct_change(5)
    ret_10 = work["close"].pct_change(10)

    ema_5 = work["close"].ewm(span=5, adjust=False).mean()
    ema_12 = work["close"].ewm(span=12, adjust=False).mean()
    ema_26 = work["close"].ewm(span=26, adjust=False).mean()
    macd_hist = (ema_12 - ema_26) - (ema_12 - ema_26).ewm(span=9, adjust=False).mean()
    atr_14 = _true_range(work).rolling(14, min_periods=14).mean()

    mean_20 = work["close"].rolling(20, min_periods=20).mean()
    std_20 = work["close"].rolling(20, min_periods=20).std()
    upper = mean_20 + 2 * std_20
    lower = mean_20 - 2 * std_20

    obv = (np.sign(ret_1.fillna(0)) * work["volume"]).cumsum()
    total_inventory = work["shfe_inventory"] + work["lme_inventory"] + work["bonded_inventory"]
    consumption_20 = work["apparent_demand_tons"].rolling(20, min_periods=10).mean()
    prev_close = work["close"].shift(1)
    true_range = _true_range(work)
    typical_price = (work["high"] + work["low"] + work["close"]) / 3.0
    vwap_20 = (typical_price * work["volume"]).rolling(20, min_periods=8).sum() / work["volume"].rolling(20, min_periods=8).sum().replace(0, np.nan)
    donchian_high_55 = work["high"].rolling(55, min_periods=20).max()
    donchian_low_55 = work["low"].rolling(55, min_periods=20).min()
    donchian_range_55 = (donchian_high_55 - donchian_low_55).replace(0, np.nan)
    choppy_range_14 = (work["high"].rolling(14, min_periods=14).max() - work["low"].rolling(14, min_periods=14).min()).replace(0, np.nan)
    choppiness_14 = 100 * np.log10(true_range.rolling(14, min_periods=14).sum() / choppy_range_14) / np.log10(14)
    volume_ma_20 = work["volume"].rolling(20, min_periods=8).mean().replace(0, np.nan)
    trend_efficiency = work["close"].diff(20).abs() / work["close"].diff().abs().rolling(20, min_periods=10).sum().replace(0, np.nan)
    inventory_pressure = total_inventory / work["apparent_demand_tons"].replace(0, np.nan)
    oi_volume_pressure = work["open_interest"].pct_change(5) * np.sign(ret_5.fillna(0)) * np.log1p(
        work["volume"] / work["volume"].rolling(20, min_periods=5).mean().replace(0, np.nan)
    )
    policy_heat = work["event_flag"].rolling(5, min_periods=1).sum() * work["sentiment_score"].abs().rolling(5, min_periods=1).mean()
    dxy_ret_5 = work["dollar_index"].pct_change(5, fill_method=None)
    usdcny_ret_5 = work["usd_cny"].pct_change(5, fill_method=None)
    us10y_chg_5 = work["us10y"].diff(5)
    macro_pressure = (
        0.45 * rolling_zscore(dxy_ret_5, 60).fillna(0.0)
        - 0.30 * rolling_zscore(usdcny_ret_5, 60).fillna(0.0)
        + 0.25 * rolling_zscore(us10y_chg_5, 60).fillna(0.0)
    )

    feature_frame = work.assign(
        ret_1=ret_1,
        ret_5=ret_5,
        ma_bias_5=work["close"] / work["close"].rolling(5, min_periods=5).mean() - 1,
        ma_bias_20=work["close"] / mean_20 - 1,
        ema_spread_5_20=ema_5 / work["close"].ewm(span=20, adjust=False).mean() - 1,
        macd_hist_delta=macd_hist.diff(),
        boll_pos_20=(work["close"] - lower) / (upper - lower),
        adx_14=_adx(work, 14),
        breakout_20=(work["close"] - work["high"].rolling(20, min_periods=20).max()) / atr_14,
        intraday_persistence=(work["close"] - work["open"]) / (work["high"] - work["low"]).replace(0, np.nan),
        volume_chg_5=work["volume"].pct_change(5, fill_method=None),
        oi_chg_5=work["open_interest"].pct_change(5, fill_method=None),
        price_volume_div=rolling_zscore(ret_5, 20) - rolling_zscore(work["volume"].pct_change(fill_method=None), 20),
        price_oi_div=rolling_zscore(ret_5, 20) - rolling_zscore(work["open_interest"].pct_change(fill_method=None), 20),
        obv_slope_10=obv - obv.shift(10),
        net_long_top20_chg=work["top20_net_long"].pct_change(5, fill_method=None),
        concentration_gap=work["top20_long_share"] - work["top20_short_share"],
        warrant_chg_5=work["warrant"].pct_change(5),
        basis=work["spot_price"] - work["close"],
        basis_mom_5=(work["spot_price"] - work["close"]).diff(5),
        rsi_14=_rsi(work["close"], 14),
        kdj_k=_stochastic_k(work, 14),
        cci_20=_cci(work, 20),
        wr_14=(work["high"].rolling(14, min_periods=14).max() - work["close"])
        / (work["high"].rolling(14, min_periods=14).max() - work["low"].rolling(14, min_periods=14).min()).replace(0, np.nan),
        roc_10=ret_10,
        mfi_14=_mfi(work, 14),
        atr_14=atr_14,
        hv_20=ret_1.rolling(20, min_periods=20).std() * np.sqrt(252),
        ewma_vol_20=ret_1.pow(2).ewm(span=20, adjust=False).mean().pow(0.5) * np.sqrt(252),
        range_vol_pct=((work["high"] - work["low"]) / work["close"]).rolling(252, min_periods=40).rank(pct=True),
        trend_efficiency_20=trend_efficiency,
        donchian_pos_55=(work["close"] - donchian_low_55) / donchian_range_55,
        choppiness_14=choppiness_14,
        volatility_compression=ret_1.rolling(5, min_periods=5).std() / ret_1.rolling(20, min_periods=12).std().replace(0, np.nan),
        realized_skew_20=ret_1.rolling(20, min_periods=14).skew(),
        realized_kurt_20=ret_1.rolling(20, min_periods=14).kurt(),
        close_to_vwap_20=work["close"] / vwap_20 - 1.0,
        delivery_liquidity_stress=work["delivery_month_flag"] * rolling_zscore(work["volume"], 20).abs(),
        holiday_gap_stress=work["holiday_gap_flag"] * ((work["open"] - prev_close) / prev_close.replace(0, np.nan)).abs(),
        supply_gap=(work["mine_import_tons"] + work["refined_output_tons"] - work["apparent_demand_tons"])
        / work["apparent_demand_tons"],
        inventory_to_consumption=total_inventory / consumption_20.replace(0, np.nan),
        inventory_chg_20=total_inventory.pct_change(20, fill_method=None),
        smelter_runrate_mom=work["smelter_runrate"].pct_change(20, fill_method=None),
        tc_rc_yoy=work["tc_rc"].pct_change(252, fill_method=None),
        mine_supply_shock=0.4 * work["myanmar_supply_yoy"] + 0.35 * work["indonesia_supply_yoy"] + 0.25 * work["drc_supply_yoy"],
        import_surprise_z=rolling_zscore(work["mine_import_tons"], 252),
        spot_premium_mom=work["spot_premium"].diff(5),
        import_arb_ratio=work["import_profit_ratio"],
        lme_shfe_inventory_gap=rolling_zscore(work["lme_inventory"] - work["shfe_inventory"], 60),
        pv_demand_surprise=work["pv_demand_yoy"] - work["pv_demand_yoy"].rolling(252, min_periods=40).mean(),
        semi_demand_surprise=work["semi_demand_yoy"] - work["semi_demand_yoy"].rolling(252, min_periods=40).mean(),
        delivery_basis_momentum=work["delivery_month_flag"] * (work["spot_price"] - work["close"]).diff(2),
        warrant_cancel_ratio=work["warrant_cancelled"] / work["warrant"].replace(0, np.nan),
        arb_fund_flow_factor=rolling_zscore(work["arb_fund_flow"], 60),
        tc_rc_delta_5=work["tc_rc"].diff(5),
        smelter_maintenance_expectation=work["maintenance_days"].rolling(5, min_periods=3).mean(),
        downstream_order_accel=work["downstream_orders_idx"].pct_change(5, fill_method=None),
        customs_arrival_gap=(work["myanmar_clearance_tons"] - work["port_arrivals_tons"]) / work["port_arrivals_tons"].replace(0, np.nan),
        pv_install_lead_surprise=work["pv_installation_lead"] - work["pv_installation_lead"].rolling(63, min_periods=15).mean(),
        bonded_delta_shock=rolling_zscore(work["bonded_inventory_delta"], 60),
        inventory_pressure_z=rolling_zscore(inventory_pressure, 120),
        dxy_ret_5=dxy_ret_5,
        usdcny_ret_5=usdcny_ret_5,
        us10y_chg_5=us10y_chg_5,
        pmi_surprise_z=rolling_zscore(work["pmi_surprise"], 60),
        commodity_beta_60=ret_1.rolling(60, min_periods=30).cov(work["commodity_index_return"])
        / work["commodity_index_return"].rolling(60, min_periods=30).var().replace(0, np.nan),
        event_sentiment=work["sentiment_score"],
        event_half_life_score=work["event_score"].ewm(halflife=5, adjust=False).mean(),
        black_swan_alert=np.where(work["event_flag"] == 1, np.where(work["event_score"].abs() > 1.5, 3, 2), 0),
        liquidity_risk=((work["high"] - work["low"]) / work["close"]) / np.log1p(work["volume"]),
        overnight_lme_domestic_gap=work["lme_overnight_return"] - work["domestic_open_gap"],
        cross_market_gap_factor=rolling_zscore(work["lme_overnight_return"] - work["domestic_open_gap"], 40),
        oi_volume_pressure=oi_volume_pressure,
        volume_zscore_20=(work["volume"] / volume_ma_20 - 1.0),
        amihud_20=(ret_1.abs() / (work["volume"] * work["close"]).replace(0, np.nan)).rolling(20, min_periods=8).mean() * 1e9,
        signed_volume_pressure=np.sign(ret_1.fillna(0.0)) * np.log1p(work["volume"] / volume_ma_20),
        event_vol_regime_shift=rolling_zscore(ret_1.abs() * (1 + work["event_flag"]), 40),
        policy_heat_score=rolling_zscore(policy_heat, 60),
        macro_pressure_score=macro_pressure,
        target_return_1d=work["close"].pct_change().shift(-1),
        target_return_3d=work["close"].pct_change(3).shift(-3),
        target_return_5d=work["close"].pct_change(5).shift(-5),
        target_return_10d=work["close"].pct_change(10).shift(-10),
        target_return_20d=work["close"].pct_change(20).shift(-20),
        target_return_60d=work["close"].pct_change(60).shift(-60),
    )

    return feature_frame.replace([np.inf, -np.inf], np.nan)


def _monotonic_score(values: pd.Series, target: pd.Series) -> float:
    sample = pd.concat([values, target], axis=1).dropna()
    if len(sample) < 50:
        return np.nan
    sample.columns = ["factor", "target"]
    sample["bucket"] = pd.qcut(sample["factor"], 10, labels=False, duplicates="drop")
    grouped = sample.groupby("bucket", observed=False)["target"].mean().dropna()
    if len(grouped) < 4:
        return np.nan
    ranked = pd.Series(range(len(grouped)), index=grouped.index)
    return float(spearmanr_lite(grouped, ranked).correlation)


def calculate_vif(frame: pd.DataFrame, columns: Iterable[str]) -> pd.Series:
    cols = [col for col in columns if col in frame.columns]
    data = frame[cols].dropna()
    if len(data) < 50 or len(cols) < 2:
        return pd.Series(index=cols, dtype=float)

    scores = {}
    for col in cols:
        x = data.drop(columns=[col])
        y = data[col]
        if x.empty:
            scores[col] = np.nan
            continue
        model = LinearRegressionLite().fit(x, y)
        r2 = model.score(x, y)
        scores[col] = np.inf if r2 >= 0.999 else 1.0 / max(1e-6, 1 - r2)
    return pd.Series(scores)


def factor_diagnostics(frame: pd.DataFrame, target_col: str = "target_return_1d") -> pd.DataFrame:
    candidates = [col for group in FEATURE_GROUPS.values() for col in group if col in frame.columns]
    vif = calculate_vif(frame, candidates)
    rows = []

    for col in candidates:
        sample = frame[[col, target_col]].dropna()
        if len(sample) < 60:
            continue
        if sample[col].nunique() < 2 or sample[target_col].nunique() < 2:
            continue
        overall = spearmanr_lite(sample[col], sample[target_col], nan_policy="omit")

        ic_list = []
        for _, monthly in sample.groupby(pd.Grouper(freq="ME")):
            if len(monthly) < 8:
                continue
            if monthly[col].nunique() < 2 or monthly[target_col].nunique() < 2:
                continue
            ic = spearmanr_lite(monthly[col], monthly[target_col], nan_policy="omit").correlation
            ic_list.append(ic)

        ic_series = pd.Series(ic_list, dtype=float)
        ic_value = float(ic_series.mean()) if not ic_series.empty else float(overall.correlation)
        icir = float(ic_value / ic_series.std(ddof=1)) if len(ic_series) > 1 and ic_series.std(ddof=1) not in (0, np.nan) else np.nan
        rows.append(
            {
                "factor": col,
                "group": next(group for group, cols in FEATURE_GROUPS.items() if col in cols),
                "ic": ic_value,
                "icir": icir,
                "p_value": float(overall.pvalue),
                "monotonicity": _monotonic_score(frame[col], frame[target_col]),
                "vif": float(vif.get(col, np.nan)),
            }
        )

    result = pd.DataFrame(rows)
    if result.empty:
        return result
    result["abs_ic"] = result["ic"].abs()
    return result.sort_values(["abs_ic", "icir"], ascending=[False, False]).reset_index(drop=True)


def select_feature_subset(
    diagnostics: pd.DataFrame,
    ic_threshold: float = 0.06,
    icir_threshold: float = 0.60,
    p_value_threshold: float = 0.05,
    max_vif: float = 5.0,
    min_features: int = 12,
    max_features: int = 20,
) -> list[str]:
    if diagnostics.empty:
        return []

    filtered = diagnostics.copy()
    filtered = filtered[filtered["abs_ic"] >= ic_threshold]
    filtered = filtered[(filtered["icir"].isna()) | (filtered["icir"] >= icir_threshold)]
    filtered = filtered[(filtered["p_value"].isna()) | (filtered["p_value"] < p_value_threshold)]
    filtered = filtered[(filtered["vif"].isna()) | (filtered["vif"] < max_vif)]
    if filtered.empty:
        filtered = diagnostics.copy()

    selected = []
    for group in ("technical", "flow", "fundamental", "macro_event"):
        selected.extend(filtered[filtered["group"] == group].head(4)["factor"].tolist())

    if len(selected) < min_features:
        selected.extend(filtered["factor"].tolist())

    deduped = []
    for factor in selected:
        if factor not in deduped:
            deduped.append(factor)
    if len(deduped) < min_features:
        for factor in diagnostics["factor"].tolist():
            if factor not in deduped:
                deduped.append(factor)
            if len(deduped) >= min_features:
                break
    return deduped[:max_features]
