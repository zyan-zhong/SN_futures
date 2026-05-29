# V3.1.0 Walk-forward 报告

本轮未运行完整七周期 walk-forward 重训。当前可验证部分来自现有单元测试与审计契约：

- 时间轴：7 个 horizon 的 future index 独立且晚于历史区。
- 路径：forecast path continuity guard 可修复极端第一跳，并避免死直线。
- 事件：available_at 约束防止未来函数。
- 七周期：预测数组、registry key、事件窗口哈希不应混用。

## 后续必须执行的真实训练任务

1. 按 h5m/h15m/h30m/h1h/h1d/h10d/h60d 分别构建 dataset。
2. 训练 price_only、event_only、price_plus_event、price_plus_event_plus_macro。
3. 每个 horizon 使用独立 scaler/calibrator。
4. 输出 directional_accuracy、strong_signal_accuracy、macro_f1、Brier、ECE、MAE、RMSE、interval_coverage。
5. 通过 promotion gate 后才允许替换 active。

## 合规说明

不使用随机切分，不使用未来新闻，不使用待兑现样本美化指标。
