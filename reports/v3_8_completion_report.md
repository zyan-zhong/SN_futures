# SNInsightTerminal V3.8 Completion Report

生成时间：2026-05-16

## 本轮范围

V3.8 在 V3.7 基础上完成 UI 证据闭环、学习回测可视化、持仓情景面板、预测卡片中文决策说明和安装包重构验证。本轮不承诺固定预测准确率，不伪造胜率；active 模型晋级仍受 walk-forward、事件消融、概率校准、路径连续性和 promotion gate 约束。

## 已落地能力

- 七周期预测卡片新增中文展示合同：`display_tags`、`decision_explanation`、`technical_tags`、`risk_notes`、`learning_status`、`backtest_summary`、`path_guard_summary`。
- Web UI 新增“学习回测”页面，展示学习调度、模型健康、按周期回测诊断、walk-forward 与事件消融任务入口。
- Web UI 新增“持仓情景”页面，输出低风险试探区、加仓观察区、减仓观察区、止损失效区、仅观望区和合规声明。
- 后端 `/api/learning/status`、`/api/backtest/diagnostics?horizon=...`、`/api/position/scenario` 均完成接口 smoke。
- README 与 RELEASE_NOTES 升级到 V3.8，构建命令更新为 `-Version V3.8`。
- release 目录重新收敛为唯一正式安装包 `SNInsightTerminal_Setup.exe`。

## 验证结果

| 项目 | 结果 |
| --- | --- |
| `python -m unittest discover -s tests -p "test*.py" -v` | 54 tests OK |
| `pytest -q` | 54 passed |
| `python -m compileall -q src` | OK |
| 源码 API smoke | `/api/ui/bootstrap`、`/api/predictions/live`、`/api/learning/status`、`/api/backtest/diagnostics`、`/api/position/scenario` 均 200 |
| 打包程序 API smoke | V3.8.0 / `sn-terminal-v3.8.0`，7 周期预测卡返回正常 |
| release 单包检查 | `release/SNInsightTerminal_Setup.exe` 单独保留 |

## 渲染验证

使用本地 Chrome headless 截图确认 Web 首屏不再空白，截图输出：

```text
reports/v38_web_smoke.png
```

当前环境没有 Browser 插件，Node 执行被系统拒绝，Python Playwright 未安装，因此渲染验证采用 Chrome headless screenshot + API smoke + 静态合同测试组合。

## 合规说明

持仓情景模块仅提供观察区、风险区和不确定性提示，不输出“必须买入/必须卖出/保证盈利/保证方向正确”等确定性交易建议。所有预测、信号、报告和情景结果仅为沪锡期货量化投研参考，不构成投资建议。
