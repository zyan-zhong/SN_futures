# 沪锡期货机构级预测预警 Windows 终端迭代优化方案

合规提示：本方案仅用于上海期货交易所沪锡期货（SN）量化投研、仿真验证、报告生成与风险管理支持，不构成投资建议、收益承诺或实盘交易引导。

## 1. 软件迭代优化整体方案

### 1.1 迭代目标
- 预测精度升级：在现有多因子 + 市场状态 + 集成预测框架上，补充沪锡专属高频字段、动态风险模板和更严格因子筛选，提升样本外稳定性。
- 报告体系落地：将单一 demo 报告升级为日/周/月/事件四类自动报告，全部由本地数据、因子诊断、回测结果自动填充。
- UI/UX 重构：将原始单页工具化界面升级为侧边导航、顶部快捷操作、报告中心、AI 问答、设置中心的 Windows 终端结构。
- 易用性与稳定性优化：加入参数模板、普通/专业双模式、自动备份、本地问答、报告目录管理，并保持可打包安装。

### 1.2 已落地代码基座
- 模型配置与模板：`src/sn_futures/config.py`
- 本地设置与备份：`src/sn_futures/settings_store.py`
- 本地问答：`src/sn_futures/local_assistant.py`
- 多报告引擎：`src/sn_futures/reporting.py`
- 轻量模型组件：`src/sn_futures/light_ml.py`
- 新桌面终端：`src/sn_futures/desktop_app.py`
- 原生安装器：`packaging/installer/NativeSetup.cs`

## 2. 预测模型精度升级详细方案

### 2.1 数据层升级
- 新增高频替代字段：
  - `myanmar_clearance_tons`
  - `port_arrivals_tons`
  - `downstream_orders_idx`
  - `bonded_inventory_delta`
  - `lme_overnight_return`
  - `domestic_open_gap`
  - `delivery_month_flag`
  - `warrant_cancelled`
  - `maintenance_days`
  - `pv_installation_lead`
  - `arb_fund_flow`
  - `holiday_gap_flag`
- 实现位置：`src/sn_futures/data.py`
- 迭代规则：
  - 对伦锡隔夜收益与国内开盘缺口做前置映射。
  - 对交割月、节假日、事件日保留真实波动，不做平滑。
  - 异常清洗仅针对疑似采集错误，不覆盖真实事件冲击。

### 2.2 因子层升级
- 新增沪锡专属因子：
  - `delivery_basis_momentum`
  - `warrant_cancel_ratio`
  - `arb_fund_flow_factor`
  - `tc_rc_delta_5`
  - `smelter_maintenance_expectation`
  - `downstream_order_accel`
  - `customs_arrival_gap`
  - `pv_install_lead_surprise`
  - `bonded_delta_shock`
  - `overnight_lme_domestic_gap`
  - `cross_market_gap_factor`
  - `event_vol_regime_shift`
  - `delivery_liquidity_stress`
  - `holiday_gap_stress`
- 实现位置：`src/sn_futures/features.py`
- 新规则：
  - 因子筛选阈值收紧为 `VIF < 3`。
  - 默认最少保留 `14` 个因子，最多 `24` 个因子。
  - 因子库按技术/流量/基本面/宏观事件四层筛选。

### 2.3 模型层升级
- 模型组件优化：
  - 用轻量本地实现替代 `scipy/sklearn` 依赖，降低打包体积与安装卡顿风险。
  - 新增 `StandardScalerLite`、`RidgeRegressorLite`、`RandomSubspaceRegressorLite`、`StagewiseBoostingRegressorLite`、`LogisticRegressionLite`、`KMeansLite`。
- 实现位置：`src/sn_futures/light_ml.py`
- 训练逻辑：
  - 仍使用时间序列滚动训练。
  - 保留状态识别 + 基模型 + 元模型的结构。
  - 通过模板化风险配置控制信号门槛、止盈止损和回测风险暴露。

### 2.4 自迭代与失效监控升级
- 当前落地项：
  - 参数模板 `conservative / balanced / aggressive`
  - 风险档位 `cautious / balanced / active`
  - 启发式最佳模板切换按钮
  - 自动备份与历史版本保留
- 建议下一阶段继续接入：
  - 周度因子 IC/ICIR 自动监控面板
  - 连续偏差预警
  - 版本回滚日志

## 3. 投研报告体系全量落地方案

### 3.1 已落地四类报告
- 日报：`build_daily_report`
- 周报：`build_weekly_report`
- 月报：`build_monthly_report`
- 事件专项：`build_event_report`
- 实现位置：`src/sn_futures/reporting.py`

### 3.2 数据填充逻辑
- 输入源：
  - 原始行情与产业链数据 `raw`
  - 预测结果 `predictions`
  - 回测指标 `metrics`
  - 信号结果 `signals`
  - 交易明细 `trades`
  - 因子诊断 `diagnostics`
- 自动生成内容：
  - 封面指标
  - 行情复盘
  - 驱动归因
  - 预测区间
  - 风险提示
  - 信号验证
  - 因子诊断表

### 3.3 输出与管理
- 输出目录：
  - `outputs/sn_demo_report.md`
  - `outputs/reports/sn_daily_report.md`
  - `outputs/reports/sn_weekly_report.md`
  - `outputs/reports/sn_monthly_report.md`
  - `outputs/reports/sn_event_report.md`
  - `outputs/reports/report_manifest.json`
- 报告中心可按 manifest 加载历史文件并预览。

### 3.4 后续增强建议
- 新增 HTML 报告导出层。
- 将 SVG 图表嵌入报告。
- 批量导出 ZIP。
- 加密分享页生成器。

## 4. UI/UX 全量重构设计规范

### 4.1 视觉规范
- 主色：`#165DFF`
- 背景：
  - Light：`#F5F7FA`
  - Dark：`#121212`
- 终端结构：
  - 顶部标题 + 合规提示
  - 顶部快捷操作条
  - 左侧固定导航
  - 中央多视图内容区
  - 底部状态栏

### 4.2 已落地视图
- Dashboard
- Reports
- AI Q&A
- Docs
- Settings

### 4.3 交互策略
- 普通模式：
  - 隐藏 AI Q&A 与设置中心入口
  - 保留核心行情、预测、报告
- 专业模式：
  - 开放全部视图
  - 开放模板切换、备份、问答和高级回测按钮
- 快捷操作：
  - `Run Demo`
  - `Import CSV`
  - `Generate Reports`
  - `Backtest Current`
  - `Switch Best Model`
  - `Backup Data`
  - `Focus Mode`

## 5. 易用性与稳定性优化方案

### 5.1 易用性升级
- 本地持久化设置：
  - 主题
  - 用户模式
  - 参数模板
  - 风险档位
  - 默认报告类型
- 自动备份：
  - 手动一键备份
  - 专业模式下自动备份
- 本地问答：
  - 基于当前预测、风控、报告、因子结果自动回答

### 5.2 稳定性升级
- 去除重量级 `scipy/sklearn` 打包依赖，减少安装器卡顿。
- 原生 C# 安装器替代 Python onefile 安装壳。
- 预测与安装器均保留烟雾测试入口。
- 失败时保留错误弹窗与状态栏提示。

### 5.3 推荐下一阶段
- 加入 SQLite 本地状态库。
- 增加崩溃日志自动归档。
- 增加 72 小时长稳测试脚本。

## 6. 合规与风控体系升级方案

### 6.1 合规保留项
- 全终端保持 research-only 定位。
- 禁止实盘接口、开户链接、收益承诺。
- 所有报告与问答自动附加免责声明。
- 自动拦截敏感违规措辞。

### 6.2 风控升级项
- 参数模板映射到：
  - 置信度阈值
  - 上涨/下跌概率阈值
  - 单笔风险预算
  - 风险暴露压缩分位
  - 盈亏比目标
- 已实现位置：
  - `src/sn_futures/config.py`
  - `src/sn_futures/backtest.py`

### 6.3 后续建议
- 账户权益录入与保证金占用估算面板
- 极端波动 99% 分位提醒
- 模型漂移预警与信号暂停机制

## 7. 软件迭代测试与发布标准

### 7.1 功能测试
- 运行 `python examples/run_pipeline.py`
- 校验输出文件是否完整生成
- 校验四类报告是否均可预览
- 校验普通/专业模式切换

### 7.2 性能与稳定性测试
- 运行 `python -m compileall src packaging app_launcher.py`
- 运行安装器烟雾测试
- 运行桌面端烟雾测试
- 建议补充 8h / 24h / 72h 常驻运行测试

### 7.3 打包发布标准
- 主安装包：`release/SNInsightTerminal_Setup.exe`
- 便携目录：`release/SNInsightTerminal_Portable`
- 构建脚本：`packaging/build_windows_package.ps1`
- 安装器入口：`packaging/installer/NativeSetup.cs`

## 8. 落地实施时间规划

### 第 1 周
- 完成高频替代字段和新增因子接入
- 完成模板化风控配置
- 完成报告引擎替换

### 第 2 周
- 完成桌面端 UI 重构
- 完成普通/专业双模式
- 完成本地问答与报告中心

### 第 3 周
- 完成账户风险监控面板
- 完成 HTML 报告导出
- 完成崩溃日志和自动恢复

### 第 4 周
- 完成精度回归测试
- 完成长稳测试
- 完成最终安装包发布验收

免责提示：本方案及软件输出仅用于沪锡期货量化投研参考，不构成投资建议，期货交易有风险，投资需谨慎。
