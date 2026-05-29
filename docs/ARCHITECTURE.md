# SNInsightTerminal 系统架构

本文说明当前沪锡期货 SN 量化投研终端的主要分层和模块职责。系统目标是保持本地化运行、真实数据优先、方向预测优先、回测可验证、报告合规可追溯。

## 1. 数据层

主要文件：

- `src/sn_futures/market_data_hub.py`
- `src/sn_futures/data.py`
- `src/sn_futures/api_clients.py`
- `src/sn_futures/news_store.py`
- `src/sn_futures/event_store.py`
- `src/sn_futures/event_url_resolver.py`
- `src/sn_futures/settings_store.py`
- `src/sn_futures/config.py`

职责：

- 接入沪锡相关行情、宏观、新闻政策、事件和缓存数据。
- 通过环境变量、`.env` 和本地加密配置读取 API key。
- 缺少 key 或数据源失败时返回可解释状态，不用假数据伪装真实数据。
- 记录数据源时间、抓取时间、缓存状态和失败原因。

## 2. 因子层

主要文件：

- `src/sn_futures/features.py`
- `src/sn_futures/event_features.py`
- `src/sn_futures/news_policy.py`
- `src/sn_futures/regime.py`
- `src/sn_futures/data_quality.py`

职责：

- 构建价格、成交量、持仓、波动率、动量、市场状态、新闻政策事件等特征。
- 输出数据质量报告，识别缺失、重复、异常跳变和 stale 数据。
- 为不同预测周期提供可复用基础因子和事件因子。

## 3. 标签层

主要文件：

- `src/sn_futures/directional_v2.py`
- `src/sn_futures/direction_ensemble.py`
- `src/sn_futures/horizon_registry.py`
- `src/sn_futures/trading_calendar.py`

职责：

- 按沪锡交易时间和预测周期生成方向标签、未来收益标签和交易时间索引。
- 区分短周期、日线和中长期周期，避免用自然日粗暴生成未来时间。
- 在休市时使用最近有效行情和下一有效交易时间，避免因休市静止价格造成假中性。

## 4. 模型层

主要文件：

- `src/sn_futures/modeling.py`
- `src/sn_futures/light_ml.py`
- `src/sn_futures/multimodal.py`
- `src/sn_futures/unified_forecast.py`
- `src/sn_futures/forecast_math.py`
- `src/sn_futures/price_risk.py`
- `src/sn_futures/policy_bandit.py`

职责：

- 生成方向优先、多周期预测。
- 价格路径应以最新有效价格为锚，预测未来收益或收益路径，再还原为价格中枢和区间。
- 通过路径守门、概率校准和事件解释减少不合理跳变、死直线和无解释区间发散。
- Bandit/RL 层只作为阈值和风控辅助，不直接替代价格预测。

## 5. 回测层

主要文件：

- `src/sn_futures/backtest.py`
- `src/sn_futures/prediction_history.py`
- `src/sn_futures/research_v2.py`

职责：

- 进行历史验证、预测兑现、收益风险诊断和 baseline 对比。
- 严格区分待兑现预测和已兑现样本。
- 重要指标包括方向命中率、强信号命中率、Brier/ECE、MAE/RMSE、区间覆盖率、回撤和收益风险。

## 6. 模型治理层

主要文件：

- `src/sn_futures/model_registry.py`
- `src/sn_futures/research_v2.py`
- `src/sn_futures/hardware.py`
- `src/sn_futures/pipeline.py`

职责：

- 管理 active、candidate、rollback、retired 模型版本。
- 记录模型版本、训练窗口、特征版本、回测结果、晋级状态和回滚原因。
- 根据 CPU/GPU 资源选择训练策略，但候选模型必须通过验证后才能晋级 active。

## 7. API 层

主要文件：

- `src/sn_futures/api_server.py`
- `src/sn_futures/v2_api.py`

职责：

- 向 Web UI 和外部调用提供本地 HTTP API。
- 核心接口包括预测、图表、事件证据、模型健康、数据水位、任务状态、报告预览、持仓情景等。
- API 应只返回真实后端 payload；字段缺失时应明确报错，不能让前端兜底生成假概率。

## 8. UI 层

主要目录：

- `ui_web/index.html`
- `ui_web/app.js`
- `ui_web/styles.css`
- `src/sn_futures/desktop_app.py`

职责：

- Web 终端展示七周期预测卡、历史/预测图表、事件证据、模型证据、数据新鲜度、系统审计和报告预览。
- 桌面端负责启动器、设置、API key 配置和本地服务入口。
- UI 文案应中文化，原始技术字段只放在技术明细折叠区。

## 9. 报告层

主要文件：

- `src/sn_futures/reporting.py`
- `docs/sn_report_templates.md`

职责：

- 生成沪锡期货多周期方向预测与事件驱动分析报告。
- 报告应包含数据源、水位、方向矩阵、价格区间、新闻政策、回测表现、模型版本、风险提示和正式合规声明。
- 报告不得出现保证收益、确定性买卖建议或实盘交易引导。

## 10. 配置与运行

主要文件：

- `.env.example`
- `.gitignore`
- `pyproject.toml`
- `requirements.txt`
- `app_launcher.py`

职责：

- `.env.example` 只提供占位符，不保存真实 key。
- `.gitignore` 忽略本地 `.env`、数据库、缓存、日志和临时下载数据。
- README 提供本地安装、测试、运行和常见问题说明。

## 11. 当前改造原则

- 不删除已有核心功能。
- 不使用 mock 数据伪装真实行情、新闻、预测或回测。
- 不用未来函数或数据泄露提升指标。
- 不在日志、README、前端或示例文件中写入真实 API key。
- 所有预测、信号、报告和持仓情景均仅为量化投研参考，不构成投资建议。
