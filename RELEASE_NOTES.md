# SNInsightTerminal V3.8 Release Notes

发布日期：2026-05-16

## 本轮定位

V3.8 是一次 UI 证据闭环、学习回测可视化、持仓情景和方向优先模型展示合同的增强版本。重点不是宣称固定胜率，而是让终端清楚回答：为什么给出这个方向、哪些事件和因子支持、模型最近表现如何、是否正在持续学习、用户持仓在不同周期下有哪些风险观察区。

## 已修复与增强

- 七周期预测卡片新增“决策说明”和中文小标签组，集中展示方向依据、核心事件、技术因子、模型晋级状态、路径守门、数据水位、事件入模数、回测口径和持续学习状态。
- 移除面向开发者的“后端预测合同完整/未使用前端假概率”类无关文案；技术合同信息仅保留在“技术明细/开发调试信息”折叠区。
- 新增“学习与回测”主面板，展示最近行情刷新、最近预测、最近验证、最近校准、最近候选训练、最近 walk-forward、下一次任务、active/candidate 状态和失败原因。
- 新增合规“持仓情景”面板，支持输入持仓方向、数量、均价、账户权益、最大可承受亏损和计划周期，输出观察区、风险区、周期共振、事件依据和不确定性提示。
- 后端 `/api/predictions/live` 为每张卡补充 `display_tags`、`decision_explanation`、`technical_tags`、`risk_notes`、`learning_status`、`backtest_summary`、`path_guard_summary`，前端默认只展示中文业务字段。
- `/api/models/health` 增加方向命中率、强信号命中率、MAE、RMSE、区间覆盖率、事件消融增益等七周期指标摘要。
- `/api/learning/status` 增加最近训练、最近 walk-forward、最近事件消融、下一次任务和失败原因等字段。
- `/api/backtest/diagnostics?horizon=...` 支持按周期返回 walk-forward 指标、baseline 对比、promotion gate 结论和失败原因。
- `/api/position/scenario` 输出合规持仓观察区，并保留“仅供投研参考，需独立决策”声明。

## 模型与治理边界

- 方向仍是第一目标：edge 判断、up/down 判断、概率校准、价格 return path 和路径守门按顺序执行。
- `train_candidate`、`walk_forward`、`event_ablation`、`promotion_check` 只允许生成候选、审计和报告。
- candidate 未通过方向优先指标、概率校准、事件消融、路径连续性和 promotion gate 时，不得替换 active。
- 如果真实 walk-forward 没有提升，系统必须显示 candidate failed 或 active retained，不得宣称模型准确率提升。
- GPU/深度模型只作为 challenger/research，不绕过 promotion gate。

## 合规边界

- 不接实盘交易接口。
- 不用 demo/random/static prediction 冒充真实预测。
- 不用旧缓存伪装新预测。
- 不承诺方向必然正确、固定胜率或收益。
- 所有预测、信号、回测、报告和持仓情景仅为沪锡期货量化投研参考，不构成投资建议。

## 验证命令

```powershell
$env:PYTHONPATH='src'
python -m unittest discover -s tests -p "test*.py" -v
pytest -q
python -m compileall -q src
```

## 构建

```powershell
.\packaging\build_windows_package.ps1 -BuildFlavor cpu -Version V3.8
```

正式发布目录只保留：

```text
release/SNInsightTerminal_Setup.exe
```
