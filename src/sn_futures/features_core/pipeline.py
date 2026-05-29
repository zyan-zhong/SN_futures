from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

import pandas as pd

from ..data_validators import build_validation_report
from ..labels.leakage_guard import infer_label_columns
from .basis import build_basis_factors
from .common import FactorBuildResult, FactorSpec
from .cross_market import build_cross_market_factors
from .event import build_event_factors
from .inventory import build_inventory_factors
from .mean_reversion import build_mean_reversion_factors
from .regime import build_regime_factors
from .technical import build_technical_factors
from .term_structure import build_term_structure_factors


FactorBuilder = Callable[[pd.DataFrame], tuple[pd.DataFrame, list[FactorSpec], dict[str, str]] | FactorBuildResult]


@dataclass
class FeaturePipelineResult:
    feature_df: pd.DataFrame
    feature_metadata: list[dict[str, object]]
    factor_groups: dict[str, list[str]]
    missing_feature_report: dict[str, str]
    data_quality_score: float
    warnings: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "feature_df": self.feature_df,
            "feature_metadata": self.feature_metadata,
            "factor_groups": self.factor_groups,
            "missing_feature_report": self.missing_feature_report,
            "data_quality_score": self.data_quality_score,
            "warnings": self.warnings,
        }


DEFAULT_BUILDERS: tuple[FactorBuilder, ...] = (
    build_technical_factors,
    build_mean_reversion_factors,
    build_term_structure_factors,
    build_basis_factors,
    build_inventory_factors,
    build_cross_market_factors,
    build_event_factors,
    build_regime_factors,
)


def _normalise_result(result: tuple[pd.DataFrame, list[FactorSpec], dict[str, str]] | FactorBuildResult) -> FactorBuildResult:
    if isinstance(result, FactorBuildResult):
        return result
    frame, metadata, missing = result
    return FactorBuildResult(frame=frame, metadata=metadata, missing=missing)


def build_feature_matrix(
    raw_frame: pd.DataFrame,
    *,
    builders: tuple[FactorBuilder, ...] = DEFAULT_BUILDERS,
    include_raw_ohlcv: bool = True,
) -> FeaturePipelineResult:
    if raw_frame is None or raw_frame.empty:
        return FeaturePipelineResult(pd.DataFrame(), [], {}, {"raw_frame": "输入行情数据为空"}, 0.0, ["输入行情数据为空"])

    raw = raw_frame.copy().sort_index()
    validation = build_validation_report(raw)
    pieces: list[pd.DataFrame] = []
    metadata: list[dict[str, object]] = []
    missing: dict[str, str] = {}
    warnings: list[str] = []
    factor_groups: dict[str, list[str]] = {}

    if include_raw_ohlcv:
        raw_cols = [col for col in ("open", "high", "low", "close", "volume", "open_interest") if col in raw.columns]
        pieces.append(raw[raw_cols].copy())
        factor_groups["raw_market"] = raw_cols

    for builder in builders:
        try:
            result = _normalise_result(builder(raw))
        except Exception as exc:
            name = getattr(builder, "__name__", "unknown_builder")
            warnings.append(f"{name} 构建失败：{exc}")
            continue
        if not result.frame.empty:
            pieces.append(result.frame)
        for spec in result.metadata:
            payload = spec.to_dict()
            metadata.append(payload)
            factor_groups.setdefault(str(payload["group"]), []).append(str(payload["feature_name"]))
        missing.update(result.missing)

    feature_df = pd.concat(pieces, axis=1)
    feature_df = feature_df.loc[:, ~feature_df.columns.duplicated()]
    label_columns = set(infer_label_columns(feature_df.columns))
    if label_columns:
        feature_df = feature_df.drop(columns=sorted(label_columns), errors="ignore")
        warnings.append("已从特征矩阵移除标签/未来收益字段，避免未来函数")

    return FeaturePipelineResult(
        feature_df=feature_df,
        feature_metadata=metadata,
        factor_groups={key: sorted(set(value)) for key, value in factor_groups.items()},
        missing_feature_report=missing,
        data_quality_score=float(validation.data_quality_score),
        warnings=warnings,
    )
