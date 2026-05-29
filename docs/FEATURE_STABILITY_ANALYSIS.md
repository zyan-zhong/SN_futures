# 特征稳定性分析

## 目标

特征稳定性分析用于识别跨 fold 不稳定、缺失率高或可能带来过拟合风险的因子。

## 输出

`feature_stability_service.py` 输出：

- fold-wise importance mean。
- fold-wise importance std。
- importance coefficient of variation。
- feature presence rate。
- high missing feature removal。
- unstable feature blacklist。
- regime-specific feature whitelist。
- SHAP 状态。

## SHAP 说明

SHAP TreeExplainer 可用于树模型解释，但依赖较重。本阶段作为可选研究模块，不强制进入发行包。

## 使用方式

若特征在多个 fold 中重要性波动过大，或在多数 fold 中缺失，应进入 unstable feature blacklist。后续训练可以选择：

- 降低该特征权重。
- 移出默认特征集。
- 仅在特定 regime 下启用。
- 等待底层数据质量提升后再重新纳入。

## 边界

特征稳定性只影响研究建议，不自动降低 promotion gate，不自动发布 active model。
