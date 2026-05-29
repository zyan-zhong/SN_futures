# 禁止 Baseline 预测/回测冒充真实结果

## 0.3.3-beta.1 no-baseline 验收

- refresh-all 不生成 baseline prediction。
- refresh-all 不生成 baseline backtest。
- 无 active model 时只显示“暂无可用 active 模型，未生成预测”等真实原因。
- 真实历史行情不足 60 条时不生成预测或回测。
- 前端 Playwright 验收确认不出现 `baseline`、`fake prediction`、`基线预测`、`基线回测` 等文案。

## 背景

用户明确要求：不要最低可运行 baseline，不要 baseline 预测，不要 baseline 回测，不要用样例或随机数据冒充真实结果。

## 当前策略

- refresh-all 不调用 `baseline_forecast_service`。
- refresh-all 不调用 `baseline_backtest_service`。
- 真实历史行情少于 60 条时，不生成预测。
- cache-only 时，不生成新的预测。
- sample mode 时，不生成真实预测。
- 无 active 模型或现有真实预测服务无结果时，只写空预测 payload 和中文原因。

## 前端展示

预测为空时，前端应显示：

> 暂无真实预测结果。原因可能是 active 模型不可用或真实历史行情不足。

回测为空时，前端应显示：

> 暂无真实回测结果。请先确保真实历史行情充足，并完成模型/策略验证。

## 回归测试

新增测试会检查：

- 历史行情不足时不会调用预测服务。
- cache-only 时不会生成新预测。
- 代码中没有 baseline forecast/backtest 服务调用。
- 前端不出现“基线预测”“baseline forecast”“baseline backtest”等文案。
