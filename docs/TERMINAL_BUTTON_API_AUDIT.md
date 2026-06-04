# Terminal Button API Audit

Scope: SNInsightTerminal terminal pages only. Heavy actions are either backed by `/api/terminal/tasks/start` or by terminal APIs that return task status through the same backend task queue helper (`_task_response` / `start_task`). E2E clicks use mocks for heavy POST actions and never click active release or backend shutdown.

| 页面 | 按钮名 | API | 方法 | 重任务 | task queue | loading state | disabled 防重复点击 | 成功/失败状态 | E2E 覆盖 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 总览 | 一键刷新数据 | runRefreshTask -> /api/terminal/refresh/all | POST | yes | yes | yes | yes | yes | mocked |
| 总览 | 查看状态 | getRefreshStatus -> /api/terminal/refresh/status | GET | no | no | yes | no | yes | yes |
| 总览 | 刷新行情 | runRefreshTask -> /api/terminal/refresh/market | POST | yes | yes | yes | yes | yes | mocked |
| 总览 | 刷新新闻 | runRefreshTask -> /api/terminal/refresh/news | POST | yes | yes | yes | yes | yes | mocked |
| 总览 | 检查预测条件 | runRefreshTask -> /api/terminal/refresh/predictions | POST | yes | yes | yes | yes | yes | mocked |
| 总览 | 生成报告 | runRefreshTask -> /api/terminal/refresh/reports | POST | yes | yes | yes | yes | yes | mocked |
| 行情 | 刷新市场数据 | refreshMarket -> /api/terminal/refresh/market | POST | yes | yes | yes | yes | yes | mocked |
| 行情监控 | 刷新市场数据 | refreshMarket -> /api/terminal/refresh/market | POST | yes | yes | yes | yes | yes | mocked |
| 新闻与事件 | 刷新新闻事件 | refreshNews -> /api/terminal/refresh/news | POST | yes | yes | yes | yes | yes | mocked |
| 新闻与事件 | 前往设置 | setPage(settings) | UI | no | no | yes | no | navigation | yes |
| 新闻与事件 | 空状态刷新新闻 | refreshNews -> /api/terminal/refresh/news | POST | yes | yes | yes | yes | yes | mocked |
| 新闻与事件 | 空状态前往设置 | setPage(settings) | UI | no | no | yes | no | navigation | yes |
| 数据 | 测试数据源: 行情 | testProvider(market) -> /api/terminal/providers/test | POST | no | no | yes | yes | yes | mocked |
| 数据 | 测试数据源: NewsAPI | testProvider(newsapi) -> /api/terminal/providers/test | POST | no | no | yes | yes | yes | mocked |
| 数据 | 测试数据源: managed proxy | testProvider(managed_proxy) -> /api/terminal/providers/test | POST | no | no | yes | yes | yes | mocked |
| 数据 | 测试数据源: Tushare | testProvider(tushare) -> /api/terminal/providers/test | POST | no | no | yes | yes | yes | mocked |
| 数据 | 测试数据源: SHFE public | testProvider(shfe_public) -> /api/terminal/providers/test | POST | no | no | yes | yes | yes | mocked |
| 数据 | 测试数据源: AKShare news | testProvider(akshare_news) -> /api/terminal/providers/test | POST | no | no | yes | yes | yes | mocked |
| 数据 | 测试数据源: MIIT policy | testProvider(miit_policy) -> /api/terminal/providers/test | POST | no | no | yes | yes | yes | mocked |
| 数据 | 查看最近错误 | getRefreshLastError -> /api/terminal/refresh/last-error | GET | no | no | yes | no | yes | yes |
| 数据 | 复制诊断信息 | exportDiagnosticsBundle -> /api/terminal/diagnostics/export | POST | no | no | yes | yes | copy-only | mocked |
| 数据 | 前往设置 | setPage(settings) | UI | no | no | yes | no | navigation | yes |
| 数据 | 刷新状态 | onRefresh snapshot | UI | no | no | yes | no | yes | yes |
| 数据 | 查看日志位置 | clipboard logs_dir | UI | no | no | yes | yes | copy-only | static-contract |
| 数据 | 一键重新加载 | getDataConsistencyReport + onRefresh | GET | no | no | yes | no | yes | yes |
| 数据 | 刷新任务: 全部 | runRefreshTask -> /api/terminal/refresh/all | POST | yes | yes | yes | yes | yes | mocked |
| 数据 | 刷新任务: 行情 | runRefreshTask -> /api/terminal/refresh/market | POST | yes | yes | yes | yes | yes | mocked |
| 数据 | 刷新任务: 新闻 | runRefreshTask -> /api/terminal/refresh/news | POST | yes | yes | yes | yes | yes | mocked |
| 数据 | 刷新任务: 预测条件 | runRefreshTask -> /api/terminal/refresh/predictions | POST | yes | yes | yes | yes | yes | mocked |
| 数据 | 刷新任务: 报告 | runRefreshTask -> /api/terminal/refresh/reports | POST | yes | yes | yes | yes | yes | mocked |
| 数据 | 运行期诊断刷新 | getRuntimeDiagnostics -> /api/terminal/runtime-diagnostics | GET | no | no | yes | no | yes | yes |
| 因子研究 | 一键构建 Feature Store | buildFeatureStore -> /api/terminal/feature-store/build | POST | yes | yes | yes | yes | yes | mocked |
| 因子研究 | 刷新 Feature Store 状态 | getFeatureStoreStatus -> /api/terminal/feature-store/status | GET | no | no | yes | no | yes | yes |
| 因子研究 | 刷新 candidate_v6 准入 | getCandidateV6Readiness -> /api/terminal/models/candidate-v6/readiness | GET | no | no | yes | no | yes | yes |
| 训练数据 | 构建训练数据集 | buildTrainingDataset -> /api/terminal/training-dataset/build | POST | yes | yes | yes | yes | yes | mocked |
| 训练数据 | 刷新训练数据状态 | getTrainingDatasetStatus -> /api/terminal/training-dataset/status | GET | no | no | yes | no | yes | yes |
| 研究 | 运行实验 | runModelExperiment -> /api/terminal/research/run-model-experiment | POST | yes | yes | yes | yes | yes | mocked |
| 研究 | 手动运行学习调度器 | runLearningScheduler -> /api/terminal/learning-scheduler/run | POST | yes | yes | yes | yes | yes | mocked |
| 研究 | 暂停学习调度器 | pauseLearningScheduler -> /api/terminal/learning-scheduler/pause | POST | no | no | yes | yes | yes | mocked |
| 研究 | 恢复学习调度器 | resumeLearningScheduler -> /api/terminal/learning-scheduler/resume | POST | no | no | yes | yes | yes | mocked |
| 研究 | 选择实验 | setSelectedId | UI | no | no | yes | no | navigation | yes |
| 研究 | 运行 candidate_v3 | runCandidateV3Research -> /api/terminal/research/run-candidate-v3 | POST | yes | yes | yes | yes | yes | mocked |
| 研究 | 运行 candidate_v4 | runCandidateV4Research -> /api/terminal/research/run-candidate-v4 | POST | yes | yes | yes | yes | yes | mocked |
| 研究 | 运行 candidate_v6 | runCandidateV6Research -> /api/terminal/research/run-candidate-v6 | POST | yes | yes | yes | yes | yes | mocked |
| 研究 | 审批发布 active | approveActiveModel -> /api/terminal/models/approve-active | POST | no | no | yes | yes | manual-danger | manual-danger |
| 模型研究 | 刷新候选诊断 | getCandidateDiagnostics -> /api/terminal/models/candidate-diagnostics | GET | no | no | yes | no | yes | yes |
| 模型研究 | 训练候选模型 | trainCandidateModel -> /api/terminal/models/train-candidate | POST | yes | yes | yes | yes | yes | mocked |
| 模型研究 | 加载 Walk Forward | getWalkForwardResults -> /api/terminal/models/walk-forward | GET | no | no | yes | no | yes | yes |
| 模型研究 | Promotion dry-run | promoteCandidateModel -> /api/terminal/models/promote-candidate?dry_run=true | POST | no | no | yes | yes | yes | mocked |
| 模型研究 | 机构级验证 | runInstitutionalValidation -> /api/terminal/validation/run-institutional-check | POST | yes | yes | yes | yes | yes | mocked |
| 回测验证 | 运行研究回测 | runResearchBacktest -> /api/terminal/research/run-backtest | POST | yes | yes | yes | yes | yes | mocked |
| 回测验证 | 运行机构级验证 | runInstitutionalValidation -> /api/terminal/validation/run-institutional-check | POST | yes | yes | yes | yes | yes | mocked |
| 预测观察 | 刷新真实数据 | refreshMarket -> /api/terminal/refresh/market | POST | yes | yes | yes | yes | yes | mocked |
| 预测观察 | 刷新 active 预测 | refreshPredictions -> /api/terminal/refresh/predictions | POST | yes | yes | yes | yes | yes | mocked |
| 预测观察 | 刷新页面 | onRefresh snapshot | UI | no | no | yes | no | yes | yes |
| 预测观察 | 前往模型研究 | setPage(research) | UI | no | no | yes | no | navigation | yes |
| 预测观察 | 前往治理 | setPage(governance) | UI | no | no | yes | no | navigation | yes |
| 预测观察 | 前往回测 | setPage(backtest) | UI | no | no | yes | no | navigation | yes |
| 预测观察 | 前往因子 | setPage(factors) | UI | no | no | yes | no | navigation | yes |
| 预测观察 | 前往数据 | setPage(data) | UI | no | no | yes | no | navigation | yes |
| 预测观察 | 前往设置 | setPage(settings) | UI | no | no | yes | no | navigation | yes |
| 预测观察 | 切换分组 | setGroup | UI | no | no | yes | no | navigation | yes |
| 报告 | 生成报告 | getFullReport -> /api/terminal/reports/full | GET | no | no | yes | yes | yes | yes |
| 报告 | 空状态生成报告 | getFullReport -> /api/terminal/reports/full | GET | no | no | yes | yes | yes | yes |
| Artifact Center | 刷新资料 | getResearchArtifacts -> /api/terminal/research/artifacts | GET | no | no | yes | no | yes | yes |
| Artifact Center | 复制摘要 | clipboard artifact summary | UI | no | no | yes | yes | copy-only | yes |
| Artifact Center | 复制 Markdown | clipboard report markdown | UI | no | no | yes | yes | copy-only | yes |
| Artifact Center | 下载 Markdown | browser download blob | UI | no | no | yes | yes | copy-only | yes |
| 设置 | 切换简洁模式 | setUIMode(simple) | UI | no | no | yes | no | navigation | yes |
| 设置 | 切换专业模式 | setUIMode(professional) | UI | no | no | yes | no | navigation | yes |
| 设置 | 显示/隐藏 Alpha | setShowAlpha | UI | no | no | yes | no | navigation | yes |
| 设置 | 显示/隐藏 NewsAPI | setShowNews | UI | no | no | yes | no | navigation | yes |
| 设置 | 保存 Alpha Vantage | saveSettingsSecrets -> /api/terminal/settings/secrets | POST | no | no | yes | yes | yes | mocked |
| 设置 | 保存 NewsAPI | saveSettingsSecrets -> /api/terminal/settings/secrets | POST | no | no | yes | yes | yes | mocked |
| 设置 | 同时保存 keys | saveSettingsSecrets -> /api/terminal/settings/secrets | POST | no | no | yes | yes | yes | mocked |
| 设置 | 重置本机密钥 | resetSettingsSecrets -> /api/terminal/settings/reset | POST | no | no | yes | yes | yes | mocked |
| 设置 | 测试 Alpha Vantage | testProvider(alpha_vantage) -> /api/terminal/providers/test | POST | no | no | yes | yes | yes | mocked |
| 设置 | 测试 NewsAPI | testProvider(newsapi) -> /api/terminal/providers/test | POST | no | no | yes | yes | yes | mocked |
| 设置 | 刷新 key diagnostics | getKeyDiagnostics -> /api/terminal/settings/key-diagnostics | GET | no | no | yes | no | yes | yes |
| 设置 | 显示/隐藏 Tushare token | setShowTushareToken | UI | no | no | yes | no | navigation | yes |
| 设置 | 保存 Tushare token | saveSettingsSecrets -> /api/terminal/settings/secrets | POST | no | no | yes | yes | yes | mocked |
| 设置 | 测试 Tushare | testProvider(tushare) -> /api/terminal/providers/test | POST | no | no | yes | yes | yes | mocked |
| 设置 | 显示/隐藏 Managed token | setShowManagedToken | UI | no | no | yes | no | navigation | yes |
| 设置 | 保存 Managed Proxy | saveSettingsSecrets -> /api/terminal/settings/secrets | POST | no | no | yes | yes | yes | mocked |
| 设置 | 测试 Managed Proxy | testProvider(managed_proxy) -> /api/terminal/providers/test | POST | no | no | yes | yes | yes | mocked |
| 设置与诊断 | 测试连接 | getDataStatus + getSystemHealth + getProcessStatus | GET | no | no | yes | yes | yes | yes |
| 设置与诊断 | 刷新后台状态 | getProcessStatus -> /api/terminal/system/process-status | GET | no | no | yes | no | yes | yes |
| 设置与诊断 | 停止后台服务 | shutdownBackend -> /api/terminal/system/shutdown | POST | no | no | yes | yes | manual-danger | manual-danger |
| 设置与诊断 | 生成完整系统 TXT 报告 | generateFullSystemTxtReport -> /api/terminal/reports/full-system-txt | POST | yes | yes | yes | yes | yes | mocked |
| 设置与诊断 | 下载 TXT | local generated report path | UI | no | no | yes | yes | copy-only | yes |
| 设置与诊断 | 下载诊断包 | local diagnostics zip path | UI | no | no | yes | yes | copy-only | yes |
| 设置与诊断 | 复制报告摘要 | clipboard full report summary | UI | no | no | yes | yes | copy-only | yes |
| 设置与诊断 | 生成系统修复计划 | buildSystemRepairPlan -> /api/terminal/diagnostics/build-repair-plan | POST | yes | yes | yes | yes | yes | mocked |
| 设置与诊断 | 下载 repair_plan.md | local repair plan path | UI | no | no | yes | yes | copy-only | yes |
| 设置与诊断 | 复制修复摘要 | clipboard repair plan summary | UI | no | no | yes | yes | copy-only | yes |

| Model Research | Run candidate_v7 | runCandidateV7Research -> /api/terminal/research/run-candidate-v7 | POST | yes | yes | yes | yes | yes | mocked |
| Factor Research | warehouse_missing_policy | getFeatureStoreStatus("v7") -> /api/terminal/feature-store/status | GET | no | no | yes | no | yes | static-contract |
| Data Status | inventory_missing_flag | getDataStatus -> /api/terminal/data-status | GET | no | no | yes | no | yes | static-contract |

## Copy Reductions

- The repeated "CSV/Excel" customer wording is single-sourced on the online source matrix and removed from factor/settings helper copy.
- Long raw diagnostics JSON is no longer copied into the visible Data page; the copy action now emits a compact path/key summary.
- Tushare selected params are summarized by key names instead of rendering raw JSON.
- Technical details remain folded in `TechnicalDetailsDrawer`; high-risk controls are marked as manual-danger and are excluded from E2E safe clicks.
