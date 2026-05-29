# V3.1.0 Promotion Gate 报告

本轮为 Hotfix，不执行完整七周期重训，也不把任何 challenger 无条件晋级为 active。

## 结论

- Active model：保持现有 registry 中的 active 状态。
- Candidate model：本轮未发布新 candidate。
- Promotion result：未触发晋级。

## 原因

本轮主要修复：

- 原文链接被误拦截和 canonical URL 降级。
- 前端概率兜底导致 50% 假象。
- 中性率固定高基准导致长周期过度中性。
- 资源画像和中性率审计可见性。

这些修复改善 live prediction 的可信展示和方向闸门逻辑，但不等价于完成真实 walk-forward 重训。若后续训练生成 candidate，必须按方向优先指标、Brier/ECE、路径连续性、事件消融和七周期独立审计通过后才能晋级。

## 合规边界

不得把本轮 Hotfix 描述为“保证方向准确率提升”。实际提升必须以后续 walk-forward 和实盘兑现样本验证。
