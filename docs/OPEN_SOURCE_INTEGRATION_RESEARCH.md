# 开源量化项目融合调研

日期：2026-06-05

适用范围：SNInsightTerminal / 本地沪锡期货（SHFE SN）单品种量化投研终端。

合规声明：本文仅用于系统架构调研和工程设计参考，不构成投资建议，不涉及自动实盘交易、自动下单或资金托管。

## 结论摘要

本轮不建议直接引入任何大型量化框架作为运行时依赖。更适合的路线是：保留本项目的本地 API Provider Hub、真实数据审计、point-in-time manifest、单品种回测和本地 Web 终端边界，从外部项目中借鉴小范围架构思想。

推荐融合方向：

- 数据工作流：借鉴 Qlib 的 data handler、processor pipeline、实验记录和 point-in-time 数据库思想，但不要直接搬入其全量数据格式和市场假设。
- Feature Store：借鉴 Qlib 的 processor graph 和数据集 handler 分层，结合本项目现有 FeatureStoreManifest、watermark、provenance gate 做本地化实现。
- 回测引擎：借鉴 LEAN / Zipline / backtrader 的 bar-by-bar 或 event-driven 分层，借鉴 vectorbt 的向量化诊断和参数扫描思想，但本项目应维护独立、可审计的单品种回测内核。
- 国内期货工程边界：借鉴 vn.py 的接口适配、模块边界和国内期货生态经验，但当前不接交易网关，不引入自动交易路径。
- RL / advanced model：暂缓。FinRL 的强化学习环境建模可作为后续研究参考，但当前优先级应低于真实数据审计、标签无泄漏、模型校准和回测可审计。

## 评估准则

- 本地 Windows 用户可安装，不依赖远端 managed service。
- 数据来自 API 或公开数据源，不要求用户手动导入。
- 单品种 SHFE SN，不需要多资产组合交易框架作为默认路径。
- 预测、训练、回测必须基于真实数据、point-in-time 约束和可审计 manifest。
- 不引入可能污染真实数据边界的 sample/demo/baseline 结果。
- 不引入与项目目标冲突的实盘交易、自动下单、资金托管默认路径。
- License、维护状态、依赖体量和 Windows 适配成本必须可控。

## 项目评估

| 项目 | GitHub | License | 最近维护状态（2026-06-05 调研） | 主要能力 | 与本项目适配性 | 建议 | 引入成本和风险 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Qlib | <https://github.com/microsoft/qlib> | MIT | GitHub API 显示最近 push 为 2026-04-22，仓库仍活跃；README 支持 Linux / Windows / macOS。 | AI quantitative research workflow、data handler、factor/model workflow、experiment tracking、point-in-time database 思路。 | 高。其 workflow / data handler / recorder 思想很契合本项目的真实数据、manifest、训练和模型治理目标。 | 只借鉴思想，暂不直接依赖。后续可考虑局部兼容其 experiment recorder 概念。 | 全量引入会带来多市场数据格式、复杂依赖、研究流程替换成本；需要防止其样例数据和 benchmark 流程被误用为真实沪锡结果。 |
| FinRL | <https://github.com/AI4Finance-Foundation/FinRL> | MIT | GitHub API 显示 2026-05-25 有 push；README 将 FinRL 定位为经典框架，并引导生产化工作到 FinRL-X / FinRL-Trading。 | 强化学习交易环境、DRL agents、market environment / agent / application 三层结构。 | 中低。可借鉴环境状态、动作、约束建模；但本项目当前不需要 RL 作为主路径。 | 暂缓。只做研究设计参考，不作为依赖。 | RL 对样本量、稳定性、解释性和审计要求很高；容易产生看似专业但不可验证的策略结果；不应在数据治理和回测内核成熟前引入。 |
| vn.py / VeighNa | <https://github.com/vnpy/vnpy> | MIT | GitHub API 显示最近 push 为 2026-05-17；README 显示支持 Windows / Linux / macOS 和 Python 3.10-3.13。 | 国内量化交易工程框架、CTP 等接口生态、模块化应用、数据/策略/回测/风控边界参考。 | 中高。对国内期货、本地安装、provider/adaptor 边界有参考价值；但交易执行能力超出当前系统范围。 | 借鉴工程边界和国内期货数据/接口分层，不接入交易网关。 | 直接依赖会引入自动交易语义、网关配置复杂度和不必要 UI/服务边界；容易偏离“本地投研终端、无自动下单”的产品约束。 |
| vectorbt | <https://github.com/polakowo/vectorbt> | Apache 2.0 with Commons Clause / Fair Code | GitHub API 显示最近 push 为 2026-04-25；仓库仍有更新。 | Pandas / NumPy / Numba 向量化回测、参数扫描、portfolio analytics、walk-forward 和 label generation 思路。 | 中。适合作为研究诊断和参数扫描思想参考，不适合作为默认回测事实来源。 | 只借鉴向量化诊断思想，不直接依赖。 | Commons Clause / Fair Code 对商业化和再分发存在额外约束，需法律复核；向量化回测也容易隐藏事件顺序、滑点、保证金和合约细节。 |
| backtrader | <https://github.com/mementum/backtrader> | GPL-3.0 | GitHub API 显示最近 push 为 2024-08-19，最新 commit 日期为 2023-04-19；维护节奏偏慢。 | bar-by-bar / event-driven backtesting、data feed、broker abstraction、strategy lifecycle。 | 中。事件驱动思想适合本项目回测内核，但项目维护和 license 不适合直接集成。 | 只借鉴事件驱动生命周期，不直接依赖。 | GPL-3.0 copyleft 不适合直接嵌入闭源或私有发行路径；维护偏慢；默认能力覆盖较广但不是沪锡单品种审计化设计。 |
| QuantConnect LEAN | <https://github.com/QuantConnect/Lean> | Apache-2.0 | GitHub API 显示最近 push 为 2026-06-03，最新 commit 日期为 2026-05-29；维护活跃。 | 专业 event-driven algorithmic trading platform、data subscription、security object、portfolio / transaction / risk / result handler 分层、CLI 本地回测。 | 中。架构分层非常有参考价值，但系统体量和运行方式与本项目不匹配。 | 借鉴 engine / data subscription / result handler 分层，不直接依赖。 | C# / .NET / Docker / 多资产 / 实盘交易语义带来高集成成本；直接引入会显著扩大安装和维护复杂度。 |
| NautilusTrader | <https://github.com/nautechsystems/nautilus_trader> | LGPL-3.0 | GitHub API 显示最近 push 为 2026-06-04；维护非常活跃。 | Rust-native trading engine、deterministic simulation、message bus、cache、adapter、live/backtest parity。 | 中。deterministic clock、message bus、adapter/cache 思路值得参考；但项目定位是交易引擎。 | 只借鉴 deterministic simulation 和 adapter/cache 思想，不直接依赖。 | LGPL-3.0、Rust/native 依赖、实时交易能力和多市场复杂度都不适合作为本地单品种投研终端默认依赖。 |
| Zipline Reloaded | <https://github.com/stefan-jansen/zipline-reloaded> | Apache-2.0 | GitHub API 显示最近 push 为 2026-01-06，最新 commit 日期为 2025-11-13；维护状态良好。 | Event-driven backtesting、data portal、trading calendar、performance output、PyData 集成。 | 中。calendar / data portal / performance result 思路有价值，但默认假设更偏股票和美股生态。 | 借鉴 trading calendar、data portal 和 performance report 边界，不直接依赖。 | 直接适配 SHFE 期货合约、保证金、夜盘、换月和本地数据审计需要大量改造。 |

## 推荐融合路线

### 1. Data Workflow

借鉴 Qlib 的数据处理链路，但保持本项目的 Local API Provider Hub：

- Provider 负责 fetch / normalize / validate / manifest，不返回 raw secret。
- Raw store 和 normalized store 分离，所有结果写 source、as_of、fetched_at、schema_version、content_hash。
- 以 data_kind 区分 realtime_quote、daily_bar、inventory、warehouse_receipt、settlement、positions、news、policy、macro。
- Processor pipeline 只处理已经通过 provenance gate 的数据。
- Experiment / report / prediction 不允许从 UI display payload 反推输入。

不建议直接采用 Qlib 数据目录作为本项目主格式。沪锡单品种系统更需要本地 API 水位、provider manifest 和用户数据目录隔离。

### 2. Feature Store

借鉴 Qlib 的 handler / processor / dataset 分层，并保留本项目 FeatureStoreManifest：

- 每次 feature build 写 input_manifests、as_of_cutoff、point_in_time_join_rules、forward_fill_rules。
- 所有 label、future return、display_overlay、latest_quote_marker 都进入 excluded_fields。
- 新闻/政策事件必须使用 available_at，而不是 fetched_at 伪装事件发生时间。
- stale cross-market data 不应进入 usable_fields，除非 manifest 明确降权或阻塞原因。

### 3. Backtest Engine

建议本项目继续维护独立回测内核，而不是直接接入外部框架：

- 从 LEAN / Zipline / backtrader 借鉴 engine、data feed、broker simulation、result handler 分层。
- 从 vectorbt 借鉴向量化参数扫描和快速诊断，但只作为研究辅助，不作为最终审计回测结果。
- 输入必须是 immutable historical bars、signal manifest、contract metadata、cost / slippage / margin / calendar manifest。
- 回测结果必须写 BacktestManifest，包含 lookahead_check_pass、sample_data_used、baseline_used 和 blocked_reasons。

### 4. RL / Advanced Model

FinRL 的环境建模思路可以记录为远期研究方向，但当前应暂缓：

- 沪锡单品种样本量有限，RL 很容易过拟合。
- RL 输出解释性弱，不适合作为当前客户级预测主路径。
- 在真实数据水位、标签、回测、校准和模型晋级门槛稳定前，不应引入 RL 依赖。

### 5. 国内期货和交易接口边界

vn.py 对国内期货接口生态有价值，但当前系统明确不做自动交易：

- 可以借鉴 provider / gateway / app 的模块边界命名。
- 可以借鉴国内期货合约、夜盘、交易日、保证金和手续费建模经验。
- 不接入 CTP 交易网关，不提供下单、撤单、账户、资金或持仓执行接口。

## 不建议直接引入的原因

- 大型框架会带来不必要的多资产、多市场和实盘交易语义。
- 部分 license 不适合直接嵌入：backtrader 为 GPL-3.0，vectorbt 带 Commons Clause / Fair Code，NautilusTrader 为 LGPL-3.0。
- 多数框架自带 sample data、demo notebook 或 benchmark workflow，若边界不清，会违反本项目“不得用样例数据冒充真实结果”的 P0 原则。
- Windows 安装和本地发行包体积会显著增加。
- 外部框架默认输出不一定包含本项目要求的 source、as_of、fetched_at、content_hash、cache_status、stale_status、blocking_reasons。

## 后续落地建议

1. 新增 `docs/ARCHITECTURE_DECISIONS_OPEN_SOURCE.md` 或 ADR，明确“默认不直接依赖大型量化框架”。
2. 在本项目内部实现 `DataWorkflowManifest` 和 `ExperimentRunManifest`，借鉴 Qlib recorder，但保持本地 schema。
3. 回测引擎按单品种 bar-by-bar 继续推进，先覆盖手续费、滑点、保证金、夜盘交易日和换月，再考虑向量化诊断。
4. 建立 provider adapter checklist，借鉴 vn.py / NautilusTrader 的 adapter 边界，但只用于数据抓取，不用于交易。
5. RL 只保留研究路线，不进入默认 UI 预测、模型晋级或客户交付链路。

## 本轮调研来源

- Qlib: <https://github.com/microsoft/qlib>
- FinRL: <https://github.com/AI4Finance-Foundation/FinRL>
- vn.py / VeighNa: <https://github.com/vnpy/vnpy>
- vectorbt: <https://github.com/polakowo/vectorbt>
- backtrader: <https://github.com/mementum/backtrader>
- QuantConnect LEAN: <https://github.com/QuantConnect/Lean>
- NautilusTrader: <https://github.com/nautechsystems/nautilus_trader>
- Zipline Reloaded: <https://github.com/stefan-jansen/zipline-reloaded>
