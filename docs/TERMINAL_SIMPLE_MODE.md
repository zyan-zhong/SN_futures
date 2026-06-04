# Terminal Simple Mode

Simple mode is the default SNInsightTerminal workspace. It keeps the terminal usable when the user only needs status, market context, data freshness, research state, reports, and settings.

## Default Navigation

Simple mode shows six entries:

1. 总览
2. 行情
3. 数据
4. 研究
5. 报告
6. 设置

Professional mode keeps the full research workbench:

1. 行情监控
2. 新闻与事件
3. 因子研究
4. 训练数据
5. 模型研究
6. 回测验证
7. 预测观察
8. 报告中心
9. Artifact Center
10. 设置与诊断

## Overview Contract

The simple overview shows exactly six cards:

- 系统状态
- 数据最新
- 行情分析
- 模型状态
- 最近回测
- 下一步

Detailed refresh logs, model diagnostics, factor manifests, and provider internals stay available in professional mode.

## Task UX

Long-running work uses the fixed global task bar. Page content is not cleared while tasks run. Refresh actions keep stale data visible, disable duplicate clicks, and update only the current page data when the task finishes.

## Policy

Simple mode does not change model logic, does not publish active models, and does not generate predictions. It only changes information architecture and presentation.
