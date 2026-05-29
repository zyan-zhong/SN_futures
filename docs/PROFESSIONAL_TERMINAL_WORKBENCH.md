# Professional Terminal Workbench

This workbench organizes SNInsightTerminal around the daily workflow of an institutional or private research user. It does not change model logic, does not publish an active model, and does not generate customer predictions.

## Navigation

The main navigation now has ten task-oriented entries:

1. 总览
2. 行情监控
3. 新闻与事件
4. 因子研究
5. 训练数据
6. 模型研究
7. 回测验证
8. 预测观察
9. 报告中心
10. 设置与诊断

Technical source diagnostics, model-governance details, and position scenarios remain available under advanced mode so the original functionality is preserved without crowding the default workflow.

## Page Responsibilities

`行情监控` shows realtime quote, price history, volume, open interest when available, main contract, provider attempts, cache state, symbol mapping, and a market refresh action.

`新闻与事件` separates model-eligible events, display-only news, excluded news, query group statistics, relevance score, exclusion reason, and event factor input status.

`因子研究` shows feature coverage, online readiness, Feature Store v3/v4 status, factor group coverage, latest factor values, usable fields, excluded fields, field sources, and manifest paths.

`训练数据` shows dataset v1/v2/v3/v4 status, sample counts, feature counts, label distribution, leakage check, date range, dataset paths, and manifest path.

`模型研究` shows candidate research, OOF trace, high-confidence subsets, calibration/stability summaries, institutional validation, promotion dry-run, and artifacts.

`回测验证` shows regular backtest diagnostics plus research backtest equity curves, drawdown paths, trades, metrics, cost stress, regime stress, DSR/PBO, Reality Check, and export paths.

`预测观察` stays active-model only. If there is no promotion-gated active model, it clearly explains why no customer prediction is generated and links to model research, backtest validation, and data coverage.

`报告中心` keeps customer reports and includes the Artifact Center.

## Visual Validation

Playwright checks that every main page opens, is not blank, does not show `undefined/null/NaN`, does not expose API key headers or URL key parameters, and has no horizontal overflow on desktop, tablet, and mobile viewports.

## Compliance Boundary

The workbench is a research terminal. Research backtests and OOF diagnostics are not live active predictions and do not constitute investment advice. Baseline or fake predictions must not be shown as customer predictions.
