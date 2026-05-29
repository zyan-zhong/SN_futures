# SNInsightTerminal V3.1.0 Hotfix 根因审计报告

生成时间：2026-05-15  
品种范围：SHFE 沪锡期货 SN  
审计结论：本轮不相信旧完成声明，按源码和测试结果确认链路。已修复可落地问题；未完成完整七周期重训的部分明确标注为后续 challenger/promotion 工作，不伪造成绩。

## A. 链接链路审计

### 发现的根因

- `event_url_resolver.py` 的可信域白名单缺少 `miit.gov.cn`、`mofcom.gov.cn`、`ndrc.gov.cn`、`cniia.org.cn` 等政策源根域，导致合法政策文章被误拦截。
- 旧解析逻辑对请求异常返回 `blocked`，没有 `raw_fallback` 语义，容易把可展示但暂时无法联网解析的文章误判为不可打开。
- 前端新闻按钮存在 `window.open(direct, ...)` 直开分支，绕过后端统一校验；这会造成前端、后端对白名单和 canonical URL 判断不一致。
- 事件库与新闻库的 URL resolve 返回字段不统一，缺少稳定的 `final_open_url`、`blocked_reason`，UI 只能显示笼统“未进白名单”。

### 已修复

- `event_url_resolver.py` 增加可信根域和子域匹配，使用 `urlparse().hostname`，避免 `evilshfe.com.cn` 伪匹配。
- canonical URL 保留 path/query，不再无理由降级到根域名。
- 网络解析失败时，可信域 URL 返回 `raw_fallback`，不删除事件、不截断文章路径。
- `event_store.resolve_event_url()` 和 `news_store.resolve_event_url()` 统一返回 `final_open_url`、`blocked_reason`、`url_status`。
- `ui_web/app.js` 删除新闻原文直开 fallback，缺少 `event_id` 时阻止前端绕过后端。

### 覆盖测试

- `test_canonical_url_preserves_article_path.py`
- `test_trusted_domain_subdomain_policy.py`
- `test_policy_article_url_not_downgraded_to_root.py`
- `test_shmet_article_open_flow.py`
- `test_external_open_backend_validation.py`

## B. 中性率根因审计

### 发现的根因

- live 预测实际使用 `direction_ensemble.py` 的方向集成层；此前的 DirectionFirst 相关文件并不等于完整替代 live prediction。
- 旧三分类概率在中性方向时使用固定 `neutral_base_by_horizon`，长周期默认值高达 `0.70/0.76`，导致 1-2 周、1-3 月更容易长期中性。
- 前端 `renderCards()` 和详情弹窗仍存在 `0.5` 概率兜底，后端缺字段时会被 UI 显示成 50%/50%，掩盖真实 payload 缺失。
- 事件特征、样本不足、数据质量低等原因已经进入方向候选，但缺少可见的 `p_edge/edge_score/neutral_rate_diagnosis`。

### 已修复

- 中性概率改为由显式 `p_edge` 驱动：概率边际、候选共识、ensemble score、数据质量、候选冲突和短线分钟线可用性共同决定。
- 冲突或数据不足时仍可主动中性化，但会返回 `neutral_rate_diagnosis`，不再无解释固定高基准。
- 输出新增 `p_edge`、`edge_score`、`signal_strength`、`neutral_rate_diagnosis`，并写入每张预测卡。
- 前端删除概率兜底；缺少 `p_up/p_down/p_neutral` 时显示 `missing_payload_error`，不再填假 50%。

### 仍需诚实说明

- 本轮是 Hotfix，不执行完整七周期重训；因此不能声称方向准确率已经显著提升。
- 后续 challenger 必须通过 walk-forward + promotion gate 后才能替换 active。

## C. 七周期独立性审计

### 源码状态

- 现有 `horizon` 测试确认七周期 future index、prediction cache key、registry key、预测数组不完全相同。
- `event_window` 与 `event_feature_hash` 已按 horizon 区分。
- 运行版本已升级到 `APP_VERSION=V3.1.0`、`BUILD_ID=sn-terminal-v3.1.0`，降低旧缓存混用风险。

### 已验证规则

- `test_horizon_isolation.py`：future index、预测数组、registry key 独立。
- `test_horizon_event_window_isolation.py`：事件窗口和 event feature hash 区分。
- `test_truth_audit_contract.py`：重复 scaler 能被模型独立性审计识别。

### 风险提示

- 本轮未重新训练完整七周期 artifact；若用户已有旧 active 模型，系统应继续以 registry/promotion gate 控制上线，不应无条件替换。

## D. 价格路径审计

### 源码状态

- 现有 forecast path guard 已覆盖：第一预测点连续性、center 非死直线、lower <= center <= upper、极端跳变 repair。
- `test_forecast_path_continuity.py` 已通过，说明路径守门在单元层面有效。

### 风险提示

- 本轮没有用真实最新行情重新训练收益路径模型；价格中枢准确性仍取决于 active model 与真实数据源质量。
- 如果方向与价格路径冲突，应降级 confidence 并显示冲突，不应硬改价格来伪造一致。

## E. 测试结果

- `python -m unittest discover -s tests -p "test*.py" -v`：Ran 42 tests OK。
- `pytest -q`：42 passed。

## 合规说明

本系统所有预测、信号、报告、情景分析仅用于沪锡期货量化投研参考，不构成任何投资建议、交易建议、收益承诺或风险承诺。期货交易具有高杠杆和高风险，模型可能因数据延迟、事件误判、市场结构变化而失效。
