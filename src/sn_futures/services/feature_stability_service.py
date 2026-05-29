from __future__ import annotations

from typing import Any, Iterable, Mapping

import numpy as np

from ..api.json_utils import sanitize_for_json


def _feature_rows(fold_importances: Iterable[Mapping[str, Any]]) -> dict[str, list[float]]:
    values: dict[str, list[float]] = {}
    for fold in fold_importances:
        items = fold.get("feature_importance") or fold.get("importances") or {}
        if isinstance(items, list):
            iterator = []
            for item in items:
                if isinstance(item, Mapping):
                    iterator.append((str(item.get("feature") or item.get("name") or ""), item.get("importance", 0.0)))
        elif isinstance(items, Mapping):
            iterator = [(str(key), value) for key, value in items.items()]
        else:
            iterator = []
        for name, raw_value in iterator:
            if not name:
                continue
            try:
                value = float(raw_value)
            except (TypeError, ValueError):
                value = 0.0
            if not np.isfinite(value):
                value = 0.0
            values.setdefault(name, []).append(abs(value))
    return values


def build_feature_stability_report(
    fold_importances: Iterable[Mapping[str, Any]],
    *,
    feature_cols: Iterable[str] | None = None,
    missing_rate_by_feature: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    fold_list = list(fold_importances)
    features = list(feature_cols or [])
    values = _feature_rows(fold_list)
    for feature in features:
        values.setdefault(str(feature), [])

    rows: list[dict[str, Any]] = []
    unstable: list[str] = []
    high_missing: list[str] = []
    for name, scores in values.items():
        arr = np.asarray(scores, dtype=float)
        fold_count = int(arr.size)
        mean = float(arr.mean()) if fold_count else 0.0
        std = float(arr.std()) if fold_count else 0.0
        cv = float(std / mean) if mean > 1e-12 else None
        presence_rate = float(fold_count / max(1, len(fold_list) or fold_count or 1))
        missing_rate = None
        if missing_rate_by_feature and name in missing_rate_by_feature:
            try:
                missing_rate = float(missing_rate_by_feature[name])
            except (TypeError, ValueError):
                missing_rate = None
        if (cv is not None and cv > 1.5) or presence_rate < 0.5:
            unstable.append(name)
        if missing_rate is not None and missing_rate > 0.3:
            high_missing.append(name)
        rows.append(
            {
                "feature": name,
                "fold_count": fold_count,
                "importance_mean": mean,
                "importance_std": std,
                "importance_cv": cv,
                "presence_rate": presence_rate,
                "missing_rate": missing_rate,
                "stable": name not in unstable and name not in high_missing,
            }
        )

    rows.sort(key=lambda item: (item.get("importance_mean") or 0.0), reverse=True)
    payload = {
        "feature_stability": rows,
        "unstable_feature_blacklist": sorted(set(unstable + high_missing)),
        "high_missing_feature_removal": sorted(set(high_missing)),
        "high_collinearity_removal": [],
        "regime_specific_feature_whitelist": {},
        "shap_status": "optional_not_required",
        "message_zh": "已完成 fold-wise 特征稳定性评估；SHAP 为可选研究模块，未强制进入发行包。",
    }
    return sanitize_for_json(payload)
