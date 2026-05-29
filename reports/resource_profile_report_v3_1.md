# V3.1.0 资源画像与训练调度说明

本轮实现目标：资源画像进入系统真实性审计，并明确区分“可展示硬件”和“实际训练调度策略”。

## 当前实现

- `resource_profile_audit.py` 会读取 CPU、内存、GPU、CUDA、Torch CUDA、训练设备等字段。
- 高性能 GPU 可用时，审计建议后台 challenger/retrain 使用 GPU；实时预测仍保持轻量模型，避免 UI 卡死。
- CPU-Lite 或 Torch CUDA 不可用时，系统明确降级为 CPU，并在 UI 显示原因。

## 调度边界

- 交易时段：行情、事件入库、轻量校准、推理优先。
- 非交易时段：允许 intraday challenger。
- 夜间/周末：允许 walk-forward、event ablation、promotion gate。
- GPU challenger 不得绕过 promotion gate 成为 active。

## 测试

- `tests/test_resource_profile.py` 覆盖 CUDA 可用和 CUDA 不可用两类路径。
