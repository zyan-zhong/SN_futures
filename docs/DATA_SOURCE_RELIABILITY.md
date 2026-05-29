# 数据源可靠性与行情刷新链路

本项目本轮将沪锡 SN 行情刷新从“只读旧缓存”升级为可解释 provider 链路。刷新不会生成假行情；若实时源失败，会继续尝试后续源，并在有最近成功缓存时明确显示“使用缓存”。

## Provider 顺序

1. 本地最近成功缓存 `last_good_market.json`：只作为兜底，不冒充实时行情。
2. Sina 实时行情：优先使用 `nf_SN0` 等沪锡连续合约符号。
3. AKShare 内盘实时行情：可用时作为第二实时源。
4. AKShare 内盘历史行情：用于补齐历史图表和数据质量评分。
5. SHFE public：作为日线、结算、仓单、库存等官方校验源，不作为实时主行情源。
6. Alpha Vantage：只作为宏观、汇率、外盘辅助，不作为沪锡主行情主源。

## 沪锡符号规范

系统统一将 `SN`、`sn`、`SN0`、`SHFE.sn2406` 等输入规范化为 Sina 可用形式，例如 `nf_SN0` 或 `nf_SN2406`。这样避免不同模块混用 `SN`、`SN0`、`shfe/sn` 导致 provider 请求失败。

## 输出文件

行情刷新会写入用户数据目录的 `outputs/`：

- `sn_market_history.json`
- `sn_live_snapshot.json`
- `data_watermark.json`
- `market_provider_status.json`
- `last_good_market.json`

## 失败解释

如果所有实时/历史源均失败且没有缓存，状态为“所有行情源失败”。如果有最近成功缓存，状态为“使用最近成功缓存”，并降低数据质量，不再显示成单纯“数据源失败”。

## 排查步骤

1. 在终端点击“一键刷新数据”或“刷新行情”。
2. 打开“数据源状态”查看每个 provider 的最近尝试时间、错误原因和建议操作。
3. 运行 `scripts/diagnose_runtime_data.ps1` 生成运行期诊断。
4. 检查 `outputs/market_provider_status.json` 和 `outputs/last_good_market.json`。
# 可观测性 API 补充

0.3.2-beta.1 后新增以下接口，帮助用户知道“为什么失败、下一步怎么做”：

- `GET /api/terminal/refresh/last-error`：返回最近一次刷新失败、跳过或错误原因。
- `GET /api/terminal/providers/status-detail`：返回 provider 链路明细、刷新状态和数据源状态。
- `POST /api/terminal/providers/test`：支持 `market / newsapi / shfe_public / akshare_news / miit_policy`，返回脱敏测试结果。
- `POST /api/terminal/diagnostics/export`：导出脱敏诊断包到 `%LOCALAPPDATA%\SNInsightTerminal\logs\diagnostics_bundle.json`。

刷新步骤会补充记录 `provider_attempts / used_symbol / request_params_sanitized / status_code / row_count / cache_hit / cache_age / last_success_time / last_error_time / error_type / error_message_zh / next_actions_zh`，并写入 `outputs/refresh_status.json`、`outputs/refresh_history.json` 和 `logs/refresh_YYYYMMDD.log`。
# Prompt 50S SHFE Public Reliability

数据源状态页不再只显示笼统的“SHFE public 不可用”。新的状态拆分为：

- SHFE 官网直连：`blocked_by_waf`、`accessible`、`unavailable`。
- AKShare SHFE 库存：正常、函数不可用、无锡数据、请求失败。
- AKShare 仓单：正常、函数不可用、无锡数据、请求失败。
- 现货基差：正常、函数不可用、无锡数据、字段不匹配、请求失败。
- 交易所日线 / 持仓：正常、函数不可用、无锡数据、字段不匹配、请求失败。
- 会员持仓排名：正常、函数不可用、无锡数据、请求失败。

`blocked_by_waf` 表示 SHFE 官网直连被人机验证阻断；系统会继续尝试 AKShare/缓存辅助源，并且该状态不影响主行情链路。所有辅助源失败时只给出原因和下一步建议，不伪造锡相关基本面数据。

# Prompt 51S 在线数据源矩阵

数据源状态页新增“在线数据源矩阵”，把公开在线源、API key 源、LME 探测层和托管数据代理拆开展示。矩阵明确显示：

- 数据类别。
- 当前来源。
- 是否需要 key。
- 是否需要客户上传文件，固定为“否”。
- 当前状态。
- 最近成功时间。
- 下一步建议。

客户不需要 CSV/Excel。系统会自动尝试 AKShare、Alpha Vantage、NewsAPI 和可选托管代理；如果公开源没有沪锡相关行、被限流、缺 key 或需要付费数据源，页面会显示真实原因，不会伪造库存、仓单、基差、LME tin 或宏观数据。
