# SNInsightTerminal / SN_futures 全项目审计与改造计划

生成时间：2026-05-18  
审计范围：当前本地项目根目录 `C:\Users\Henry Austin\Desktop\SN_futures`  
核心品种：上海期货交易所沪锡期货 `SHFE SN`

> 合规边界：本系统所有预测、信号、回测、报告、持仓情景仅用于量化投研参考，不构成投资建议、交易建议、收益承诺或风险承诺；不接入实盘交易接口。

## 1. 当前项目结构树

```text
SN_futures/
├─ app_launcher.py                         # 桌面/本地 API/worker 统一启动入口
├─ pyproject.toml                          # Python 项目元数据与可选依赖分组
├─ requirements.txt / requirements.lock     # 当前运行依赖锁定记录
├─ README.md / RELEASE_NOTES.md             # 发布说明；README 当前内容过短，需要恢复完整说明
├─ CODEX_AUDIT_PLAN.md                      # 本轮审计与改造计划
├─ config/
│  ├─ horizons.yaml                         # 七周期预测配置
│  ├─ data_sources.yaml                     # 免费/公开数据源说明
│  ├─ event_sources.yaml                    # 事件源分层配置
│  ├─ event_taxonomy.yaml                   # 沪锡事件分类与实体词典
│  ├─ event_windows.yaml                    # 七周期事件窗口
│  ├─ event_scoring.yaml                    # 事件打分阈值
│  └─ model_registry.yaml                   # 模型注册与晋级策略说明
├─ src/sn_futures/
│  ├─ api_server.py                         # 本地 Web API 路由
│  ├─ v2_api.py                             # Web API 聚合层/展示合同/诊断接口
│  ├─ desktop_app.py                        # Tkinter 桌面启动器与设置界面
│  ├─ data.py / market_data_hub.py          # 历史/实时行情、新闻宏观数据装载
│  ├─ api_clients.py                        # 新浪、Alpha Vantage、NewsAPI 等客户端
│  ├─ settings_store.py                     # API key 本地加密存储与环境变量读取
│  ├─ contracts.py                          # 主力合约/流动性/换月逻辑
│  ├─ trading_calendar.py                   # SHFE SN 交易时段与未来索引
│  ├─ data_quality.py                       # 数据质量报告
│  ├─ features.py / event_features.py       # 价格量仓与事件特征
│  ├─ event_*.py / news_*.py                # 事件结构化、事件库、新闻政策处理
│  ├─ directional_v2.py / direction_ensemble.py
│  │                                        # 方向优先、候选池与一致性逻辑
│  ├─ modeling.py / light_ml.py / multimodal.py
│  │                                        # 模型池、轻量 ML、多模态预测
│  ├─ unified_forecast.py                   # 统一预测结果生成与守门
│  ├─ pipeline.py                           # 离线/实时预测流水线
│  ├─ backtest.py                           # 信号构造、回测与绩效指标
│  ├─ prediction_history.py                 # 预测快照、兑现验证与历史记录
│  ├─ reporting.py                          # 日/周/月/事件报告生成
│  ├─ position_scenario.py                  # 合规持仓情景观察区
│  ├─ hardware.py                           # CPU/GPU/算力画像
│  └─ diagnostics/                          # 真实性、隔离、路径、事件、资源审计
├─ ui_web/
│  ├─ index.html                            # 内置 Web 终端入口
│  ├─ app.js                                # 原生 JS 终端逻辑、图表、按钮、面板
│  └─ styles.css                            # 深色金融终端样式
├─ tests/                                   # 单元/合同/回归测试
├─ packaging/
│  ├─ build_windows_package.ps1             # Windows 正式安装包构建脚本
│  ├─ *.spec                                # PyInstaller spec
│  └─ installer/                            # 原生安装器与快捷方式脚本
├─ scripts/                                 # GPU runtime bootstrap、图标生成等
├─ reports/                                 # 审计、晋级、事件消融、完成报告
├─ app_data/outputs/                        # 本地生成预测/报告/回测样例输出
├─ outputs/                                 # 旧/样例输出目录
└─ release/SNInsightTerminal_Setup.exe       # 当前唯一正式安装包
```

## 2. 主要模块职责

| 类别 | 主要文件 | 当前职责 |
| --- | --- | --- |
| 后端入口 | `app_launcher.py`, `src/sn_futures/api_server.py` | 根据参数启动本地 API server、live worker 或 Tkinter 桌面端；API server 提供静态 Web 与 JSON API。 |
| 前端入口 | `ui_web/index.html`, `ui_web/app.js`, `ui_web/styles.css` | 本地 Web 终端、七周期卡片、图表、事件证据、学习回测、持仓情景和报告预览。 |
| API 路由 | `src/sn_futures/api_server.py` | `GET /api/predictions/live`、`/api/charts/price-forecast`、`/api/events/*`、`/api/models/*`、`/api/learning/status`、`POST /api/tasks/run`、`POST /api/position/scenario` 等。 |
| API 聚合 | `src/sn_futures/v2_api.py` | 将 pipeline 输出、事件库、诊断、模型健康、图表 payload 和 UI bootstrap 统一转换为 Web 合同。 |
| 数据源 | `api_clients.py`, `market_data_hub.py`, `data.py`, `contracts.py`, `trading_calendar.py` | 行情、新闻、宏观、实时快照、主力合约、交易时段和缓存限频。 |
| 因子模块 | `features.py`, `event_features.py`, `event_taxonomy.py`, `regime.py`, `price_risk.py` | 技术因子、量仓/波动/基差代理、事件窗口聚合、市场状态和风险特征。 |
| 模型模块 | `modeling.py`, `light_ml.py`, `multimodal.py`, `directional_v2.py`, `direction_ensemble.py`, `unified_forecast.py` | 轻量 ML、方向候选池、多周期预测卡、概率校准、价格路径守门、统一预测结果。 |
| 回测模块 | `backtest.py`, `prediction_history.py`, `research_v2.py` | 信号回测、指标计算、预测快照/兑现验证、候选研究流水线。 |
| 报告模块 | `reporting.py`, `v2_api.py` report endpoints | 生成日/周/月/事件报告、Web 报告预览和报告清单。 |
| 配置文件 | `config/*.yaml`, `pyproject.toml`, `requirements*` | 七周期、事件源、事件分类、模型注册、依赖分组。 |
| 测试文件 | `tests/test_*.py` | 交易日历、URL 安全、事件入模、七周期隔离、方向概率、路径连续、UI 合同等。 |
| 构建/打包 | `packaging/build_windows_package.ps1`, `packaging/*.spec`, `packaging/installer/*` | PyInstaller 打包、原生安装器、快捷方式、release 单包产出。 |

## 3. 当前存在的问题

### P0 高优先级

1. **README 内容异常过短**  
   当前 `README.md` 只有两行标题式内容，无法支撑安装、运行、回测、刷新、报告导出、免费数据限制等发行说明。需要恢复完整 README。

2. **配置文件中文存在编码/显示风险**  
   `config/*.yaml` 在当前 PowerShell 输出中出现明显乱码。需要用 UTF-8 读取验证实际文件内容，并在必要时恢复中文原文；否则会影响人工审计、部署说明和配置可维护性。

3. **API 聚合层存在重复定义风险**  
   `src/sn_futures/v2_api.py` 中可见 `get_models_health()`、`get_model_promotion_report()`、`get_system_truth_audit()` 等函数后段重复定义覆盖前段实现。虽然可能是兼容补丁，但长期会增加维护风险，应合并为单一实现。

4. **运行输出与样例输出被纳入项目结构**  
   `app_data/outputs/`、`outputs/` 包含预测、报告、回测样例。可用于演示，但也可能让用户误以为是实时结果。应在 UI 与文档中明确“样例/缓存/实时”的边界，并考虑将实时运行产物移出源码仓库。

5. **模型晋级与训练可视化仍偏合同化**  
   目前 API/测试覆盖了 promotion/status 合同，但需要进一步确认 candidate 训练、walk-forward、事件消融是否在真实数据切片上稳定运行，而不是仅生成状态展示。

### P1 中优先级

6. **依赖管理不一致**  
   `pyproject.toml` 的核心依赖较轻，但 `requirements.txt` 包含 `torch/xgboost/lightgbm/shap/arch/hmmlearn` 等重依赖。需要明确 CPU-Lite、ML、GPU、research 的安装边界。

7. **前后端命名仍带历史包袱**  
   文件名 `v2_api.py`、API server 版本 `SNInsightV2API/1.1` 与实际 V3.x 产品不一致，易造成维护混乱。建议保留兼容导入，但新增更清晰的 `web_api_contract.py` 或逐步重命名。

8. **Tkinter 与 Web 双入口职责重叠**  
   `desktop_app.py` 体量很大，既包含设置、UI、预测触发又承担兼容职责。建议后续收敛为“启动器/设置/日志/兜底”，主交互全部走 Web。

9. **事件源真实抓取覆盖需要二次验收**  
   事件 schema、store、taxonomy、feature 已存在，但应对 Tier 1/Tier 2/Tier 3 provider 做联网/限流/失败缓存的真实验收，防止“结构有了、数据不足”。

10. **模型目标与评价需要更集中**  
    当前方向模型、multimodal、unified forecast、display calibration 分散在多个模块。建议建立单一 `DirectionFirstEngine` 门面，所有 live/backtest/report 共用。

### P2 低优先级

11. **Web UI 无构建链，优点是简单，缺点是静态合同靠测试维护**  
    当前无 `package.json`，无需 npm build/lint；后续如果 UI 继续复杂化，可考虑保持原生 JS 但增加静态检查脚本。

12. **报告样式仍可加强**  
    报告生成以 Markdown 为主，正式 PDF/HTML 导出与打印样式仍可继续完善。

## 4. 安全扫描结论

- 未发现用户提供过的真实 Alpha Vantage / NewsAPI key 明文硬编码。
- 未发现 `sk-...`、`Bearer ...` 等典型高危密钥。
- 发现的是环境变量名、未配置提示、测试错误码和客户端参数名，例如 `SN_ALPHA_VANTAGE_KEY`、`SN_NEWSAPI_KEY`、`apiKey`。
- `settings_store.py` 当前从环境变量读取，并支持本地加密存储。后续建议在 README 中强调不要提交本地 `api_keys.json`。

## 5. 建议修改文件清单

| 优先级 | 文件 | 建议 |
| --- | --- | --- |
| P0 | `README.md` | 恢复完整安装/运行/测试/打包/数据源限制说明。 |
| P0 | `config/*.yaml` | 验证并修复中文编码；保留机器可读英文 key，中文说明统一 UTF-8。 |
| P0 | `src/sn_futures/v2_api.py` | 合并重复函数定义；拆出 UI 展示合同、诊断合同、图表合同，降低单文件复杂度。 |
| P0 | `src/sn_futures/api_server.py` | 将路由表从长 `if/elif` 拆成显式 route map，便于测试和新增接口。 |
| P0 | `app_data/outputs/`, `outputs/` | 明确样例/缓存属性；考虑只保留最小 demo fixtures，真实运行输出迁移到用户数据目录。 |
| P1 | `src/sn_futures/pipeline.py` | 将 candidate 训练、walk-forward、promotion gate 的真实执行路径和状态落库进一步统一。 |
| P1 | `src/sn_futures/unified_forecast.py` | 继续强化“方向优先 -> return path -> interval guard”的唯一核心链路。 |
| P1 | `src/sn_futures/event_features.py`, `event_store.py`, `market_data_hub.py` | 验证事件真实入库、available_at、防未来函数、七周期窗口隔离。 |
| P1 | `ui_web/app.js`, `ui_web/index.html`, `ui_web/styles.css` | 继续收敛 UI 文案、长文本展开、按钮任务状态和指标矩阵交互。 |
| P1 | `pyproject.toml`, `requirements.txt`, `requirements.lock` | 统一 core/ml/gpu/research 依赖边界，避免普通用户安装重依赖失败。 |
| P2 | `src/sn_futures/desktop_app.py` | 瘦身为启动器和设置中心；复杂展示迁移到 Web。 |
| P2 | `src/sn_futures/reporting.py` | 增强 HTML/PDF 报告样式和图表嵌入。 |

## 6. 推荐分阶段修改顺序

### Phase 1：发行与安全基线

1. 恢复完整 README 与故障排查说明。
2. 修复/确认 `config/*.yaml` 编码。
3. 明确运行输出目录边界，避免缓存/样例被误判为实时数据。
4. 保持 API key 只来自环境变量或本地加密配置。

### Phase 2：后端合同瘦身与路由稳定

1. 合并 `v2_api.py` 的重复定义。
2. 为 API server 建立 route map。
3. 增加 API smoke 脚本，覆盖 bootstrap、predictions、chart、events、learning、position。
4. 保持现有 URL 向后兼容。

### Phase 3：模型真实性与回测闭环

1. 固化七周期独立 dataset/feature/scaler/cache/model id。
2. 统一 DirectionFirstEngine：edge -> up/down -> calibration -> return path -> interval guard。
3. 对每个 horizon 输出 active/candidate/baseline 的真实 walk-forward 对比。
4. candidate 未通过 promotion gate 不替换 active。

### Phase 4：事件数据与关键时间分析

1. 对 Tier 1 官方源做 provider smoke。
2. 加强 FOMC、美元/利率、国内节假日、海关/统计局、SHFE 仓单库存、海外供应事件特征。
3. 做事件消融报告，不夸大无增益事件。

### Phase 5：UI 与报告专业化

1. 完成多周期方向矩阵、事件证据、模型证据、学习回测、持仓情景的交互细节。
2. 报告从 Markdown 预览升级为正式 HTML/PDF 样式。
3. 保留技术明细折叠区，但默认业务展示全中文。

## 7. 潜在风险点

- **免费数据源不稳定**：AkShare、NewsAPI、Alpha Vantage、公开网页抓取可能限流或字段变化。
- **预测准确性不可承诺**：应继续展示真实 walk-forward 与已兑现验证，不写固定胜率承诺。
- **事件入模防泄露复杂**：必须坚持 `available_at <= prediction_time`。
- **短周期数据粒度不足**：没有分钟线/快照时不能把短周期验证伪装成真实命中。
- **重依赖打包风险**：GPU/Torch/SHAP/XGBoost 不应进入默认 CPU-Lite 包。
- **本地缓存污染**：旧输出文件可能影响用户判断，需在 UI 显示数据时间、source timestamp、fetch timestamp 和 stale/fallback。
- **文件命名历史包袱**：`v2_api.py` 等名称与 V3.x 产品不一致，后续重构要保持兼容。

## 8. 本地运行和测试命令

### 安装依赖

```powershell
python -m pip install -r requirements.txt
python -m pip install -e .[dev]
```

### 启动本地 API / Web 终端

```powershell
$env:PYTHONPATH='src'
python app_launcher.py --api-server --api-port 8765
```

访问：

```text
http://127.0.0.1:8765/
```

### 运行预测流水线示例

```powershell
$env:PYTHONPATH='src'
python examples/run_pipeline.py
```

### 轻量检查

```powershell
python -m compileall -q .
pytest -q
```

### 构建 Windows 安装包

```powershell
.\packaging\build_windows_package.ps1 -BuildFlavor cpu -Version V3.8
```

## 9. 下一步建议执行的 Prompt

建议下一轮 Prompt：

> 请按 `CODEX_AUDIT_PLAN.md` 的 Phase 1 执行发行与安全基线修复：恢复完整 README，验证并修复 `config/*.yaml` UTF-8 中文编码，明确运行输出与样例输出边界，并保持所有 API key 只从环境变量或本地加密配置读取。不要改模型逻辑，不要删除功能；完成后运行 `python -m compileall -q .` 和 `pytest -q`。

