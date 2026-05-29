from __future__ import annotations

import pandas as pd

from .light_ml import KMeansLite, StandardScalerLite

try:
    from hmmlearn.hmm import GaussianHMM
except ImportError:  # pragma: no cover
    GaussianHMM = None


REGIME_FEATURES = [
    "ret_5",
    "ema_spread_5_20",
    "adx_14",
    "hv_20",
    "atr_14",
    "volume_chg_5",
    "oi_chg_5",
    "net_long_top20_chg",
    "concentration_gap",
    "supply_gap",
    "inventory_to_consumption",
    "spot_premium_mom",
]

REGIME_ORDER = ("UPTREND", "DOWNTREND", "WIDE_RANGE", "NARROW_RANGE")
REGIME_CODE = {name: idx for idx, name in enumerate(REGIME_ORDER)}


def _state_mapping(train_frame: pd.DataFrame, labels) -> dict[int, str]:
    stats = []
    tmp = train_frame.assign(_label=labels)
    for label, group in tmp.groupby("_label"):
        stats.append((int(label), float(group["target_return_1d"].mean()), float(group["hv_20"].mean())))

    if len(stats) < 4:
        return {item[0]: REGIME_ORDER[idx] for idx, item in enumerate(stats)}

    sorted_by_return = sorted(stats, key=lambda item: item[1])
    down_label = sorted_by_return[0][0]
    up_label = sorted_by_return[-1][0]
    remain = [item for item in stats if item[0] not in {down_label, up_label}]
    remain = sorted(remain, key=lambda item: item[2])
    narrow_label = remain[0][0]
    wide_label = remain[-1][0]
    return {
        up_label: "UPTREND",
        down_label: "DOWNTREND",
        wide_label: "WIDE_RANGE",
        narrow_label: "NARROW_RANGE",
    }


def rolling_regime_detection(frame: pd.DataFrame, window: int = 126) -> pd.DataFrame:
    work = frame.copy()
    labels = pd.Series(index=work.index, dtype="object")
    confidence = pd.Series(index=work.index, dtype=float)
    cols = [col for col in REGIME_FEATURES if col in work.columns]
    extra_cols = list(dict.fromkeys(cols + ["target_return_1d", "hv_20"]))

    for end in range(window, len(work)):
        train = work.iloc[end - window : end][extra_cols].dropna()
        current = work.iloc[[end]][cols].dropna()
        if len(train) < max(40, window // 2) or current.empty:
            continue

        scaler = StandardScalerLite()
        x_train = scaler.fit_transform(train[cols])
        x_now = scaler.transform(current[cols])

        cluster = KMeansLite(n_clusters=4, n_init=20, random_state=42)
        init_labels = cluster.fit_predict(x_train)

        if GaussianHMM is not None:
            hmm = GaussianHMM(n_components=4, covariance_type="diag", n_iter=100, random_state=42)
            hmm.fit(x_train)
            train_labels = hmm.predict(x_train)
            current_label = int(hmm.predict(x_now)[0])
            regime_conf = float(hmm.predict_proba(x_now)[0].max() * 100)
        else:
            train_labels = init_labels
            current_label = int(cluster.predict(x_now)[0])
            regime_conf = float(100 / (1 + cluster.transform(x_now)[0].min()))

        mapping = _state_mapping(train, train_labels)
        labels.iloc[end] = mapping.get(current_label, "NARROW_RANGE")
        confidence.iloc[end] = regime_conf

    labels = labels.astype("string").ffill().fillna("NARROW_RANGE").astype(str)
    confidence = pd.to_numeric(confidence.ffill().fillna(55.0), errors="coerce").fillna(55.0)
    return pd.DataFrame(
        {
            "regime": labels,
            "regime_code": labels.map(REGIME_CODE).fillna(3).astype(int),
            "regime_confidence": confidence.clip(0, 100),
        },
        index=work.index,
    )
