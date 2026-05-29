# SNInsightTerminal Changelog

## 0.3.3-beta.1 - 2026-05-21

- 发布 real-market-only 客户内部测试版，纳入 Prompt 36R/37R 的真实行情 provider 链路和端到端验收。
- 行情刷新拆分为实时行情、历史行情、SHFE public 辅助和 last good cache；实时成功不再阻断历史行情刷新。
- 验证 Sina 实时行情与 AKShare 历史行情均可返回真实数据；本机 smoke 得到 `final_status=full_success`、历史行数 2710。
- 明确 no-baseline 策略：无 active model 不生成预测，真实历史行情不足不生成回测，不使用 baseline 或 fake prediction 填空。
- 增加 `scripts/smoke_market_data_refresh.ps1`，可输出 provider attempts、price-history、runtime diagnostics 和 no-baseline 结论。
- Playwright 增加行情刷新后图表/失败原因可见性验收，并确认前端不出现 baseline/fake 文案。
- 继续保留合规边界：不构成投资建议，不承诺收益，不接实盘交易。

## 0.3.2-beta.1 - 2026-05-21

- 修复行情刷新失败时的可解释性：刷新步骤记录 provider_attempts、状态码、返回条数、缓存命中、最近成功/失败时间、错误类型、中文错误原因和下一步建议。
- 修复新闻与政策源长期误显示“已过期”的问题：NewsAPI 未配置显示“未配置”，AKShare 新闻/工信部政策未启用显示“未启用”，SHFE 公共数据按日线/库存/仓单节奏判断。
- 优化 NewsAPI 查询策略：使用 X-Api-Key header，多组中英文锡产业关键词，默认 7 天查询，0 结果回退 30 天，并记录每组 query 结果。
- 增强数据质量评分说明：质量分由行情最新价、历史行情、新闻、事件、报告、预测、模型健康分项组成，不再固定约 60%。
- 修复系统状态与行情涨跌颜色语义：系统正常使用蓝/青，风险使用黄/红；行情上涨红色、下跌绿色。
- 新增可观测性 API：refresh last-error、provider status-detail、providers/test、diagnostics/export。
- 数据源状态页新增“测试数据源”“查看最近错误”“复制诊断信息”和错误原因/下一步建议。
- 继续保持合规边界：不构成投资建议，不承诺收益，不接实盘交易。

## 0.3.1-beta.1 - 2026-05-21

- 新增运行期数据刷新任务中心，支持“一键刷新数据”，按步骤处理行情、新闻、事件、特征、预测和报告。
- 新增真实展示 API：行情历史、预测路径、新闻事件、事件证据、报告全文和因子诊断。
- 新增安全合规的样例数据模式。首次安装且无 API key、无缓存时可展示界面结构、图表样式和样例报告，但所有样例均醒目标记，不作为真实行情或预测。
- 前端接入刷新、图表、新闻、报告全文和因子诊断 API，Dashboard、七周期预测、事件监控、报告中心、因子分析、数据源状态页均可显示真实数据、样例数据或清晰空状态。
- 新增 Playwright 浏览器视觉验收，覆盖 Dashboard、七周期预测、事件监控、报告中心、设置页，并保存截图。
- 增强安装后 smoke，支持 `-RunBrowserSmoke`，验证 `/terminal` 非空白、设置 API 脱敏、卸载保留用户数据。
- 修复打包后启动器健康检查过严的问题：`/api/terminal/docs` 作为硬就绪条件，`system-health` 慢启动不再导致程序退出。
- 保留旧版终端 `/legacy`。
- 合规边界不变：仅供沪锡期货量化投研参考，不构成投资建议，不承诺收益，不接实盘交易。

## 0.3.0-beta.1 - 2026-05-20

- 新增客户级首次启动向导。
- 优化设置页和本地密钥配置体验，密钥只保存在本机用户目录并脱敏显示。
- 优化 Dashboard 状态 Banner 和 6 个核心状态卡。
- 优化七周期预测卡片、图表容器、DataTable、报告中心和数据源状态页。
- 接入 ErrorBoundary、响应式布局、可访问性改进和 UI 合同检查脚本。
- 完成 Windows 安装包框架、桌面启动器、用户数据目录和安装后 smoke 验证。
