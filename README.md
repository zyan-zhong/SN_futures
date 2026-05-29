# SNInsightTerminal / 沪锡期货量化投研终端

当前客户级内部测试版：`0.3.1-beta.1`

SNInsightTerminal 是面向上海期货交易所沪锡期货（SHFE SN）的本地量化投研终端，覆盖数据源接入、因子工程、标签体系、方向优先模型、回测诊断、模型治理、新闻事件分析、报告生成、持仓情景辅助和客户级中文 Web 终端。

## 合规声明

- 本项目所有输出仅用于研究、教学和量化投研辅助，不构成投资建议。
- 本项目不承诺收益，不保证方向正确。
- 本项目不接实盘交易接口，不提供自动下单、资金托管或交易执行功能。
- 期货交易具有高杠杆和高风险，用户需独立判断并自行承担风险。

## 普通用户安装方式

1. 下载或获取安装包：`release/SNInsightTerminal_Setup.exe`
2. 双击安装包并按向导完成安装。
3. 点击开始菜单或桌面快捷方式启动。
4. 浏览器会自动打开专业终端：`http://127.0.0.1:<实际端口>/terminal`
5. 首次启动向导中可以配置 Alpha Vantage / NewsAPI key，也可以跳过配置。
6. 未配置外部数据源时，系统仍可进入终端，并显示“未配置”或“样例数据模式”。
7. 点击“一键刷新数据”可尝试生成真实行情、新闻、事件、预测和报告展示。

旧版终端保留在：`http://127.0.0.1:<实际端口>/legacy`

## API Key 配置

密钥只保存在本机用户目录，不写入前端、不上传、不显示完整值。

用户数据目录：

```text
%LOCALAPPDATA%\SNInsightTerminal
```

密钥文件位置：

```text
%LOCALAPPDATA%\SNInsightTerminal\config\secrets.json
```

也可以在开发环境使用 `.env`：

```powershell
Copy-Item .env.example .env
notepad .env
```

`.env.example` 只包含占位符，请不要把真实 key 写入代码、README、日志或前端文件。

## 开发者本地运行

建议使用 Python 3.10+。

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

启动后端：

```powershell
$env:PYTHONPATH = "$PWD\src"
python -m sn_futures.api_server
```

启动新版前端开发服务：

```powershell
cd frontend
npm install
npm run dev
```

访问：

```text
http://127.0.0.1:5173/terminal/
```

## 前端检查

```powershell
cd frontend
npm install
npm run typecheck
npm run build
npm run check:ui
npm run test:e2e
```

E2E 截图输出目录：

```text
e2e-artifacts/screenshots/
```

## Python 测试

```powershell
python -m compileall -q .
pytest -q
python -m unittest discover -s tests -p "test*.py" -v
```

当前 0.3.1-beta.1 验证结果：

- `pytest -q`：`213 passed`
- `unittest`：`Ran 164 tests OK`

## 发行构建

需要：

- Python
- Node.js LTS 或可用 Node/npm
- PyInstaller
- Inno Setup

构建命令：

```powershell
.\packaging\build_release.ps1 `
  -NodePath "C:\Program Files\nodejs\node.exe" `
  -NpmPath "C:\Program Files\nodejs\npm.cmd"
```

构建产物：

```text
release/SNInsightTerminal_Setup.exe
release/SHA256SUMS.txt
```

安装后 smoke：

```powershell
.\packaging\smoke_installed.ps1 -RunBrowserSmoke
```

## 0.3.1-beta.1 交付信息

- 安装包路径：`release/SNInsightTerminal_Setup.exe`
- 安装包时间戳：`2026-05-21 02:28:32 +08:00`
- SHA256：`E2BEAABC6D721172155FEBD9BE1ED4D4DFBDDCE531D85DB1E42D78879A021251`
- 客户验收清单：`docs/CUSTOMER_ACCEPTANCE_CHECKLIST.md`
- 客户交付报告：`docs/CUSTOMER_RELEASE_REPORT.md`

## 常见问题

### 打开后没有真实数据

首次安装且未配置 key、未刷新数据时，终端会显示样例数据或空状态。请进入终端点击“一键刷新数据”，或在设置页配置 Alpha Vantage / NewsAPI key。

### Node/npm 不可用

请安装 Node.js LTS，或在构建脚本中显式传入：

```powershell
-NodePath "C:\Program Files\nodejs\node.exe" -NpmPath "C:\Program Files\nodejs\npm.cmd"
```

### 浏览器没有自动打开

后端启动后可手动访问：

```text
http://127.0.0.1:8765/terminal
```

如端口被占用，启动器会尝试 `8766-8769`。

### 如何查看日志

```text
%LOCALAPPDATA%\SNInsightTerminal\logs
```

### 如何卸载和删除用户数据

卸载程序默认删除安装目录，但保留用户数据目录：

```text
%LOCALAPPDATA%\SNInsightTerminal
```

如需彻底清理，可手动删除该目录。

### Windows SmartScreen 提示未知发布者

当前内部测试版未进行代码签名，Windows 可能提示未知发布者。后续面向外部用户发布时建议增加代码签名流程。
# 0.3.2-beta.1 数据源可靠性更新

本版本重点修复行情、新闻、政策与 SHFE 公共数据源的运行期可观测性：

- NewsAPI 未配置时显示“未配置”，不会误显示“已过期”。
- 工信部政策源按周/月级 TTL 判断，7 天内正常，7-30 天较旧但可参考，30 天后才过期。
- SHFE 公共数据按日线、仓单、库存、结算节奏判断，非交易时段不直接判定失败。
- 本地行情缓存存在时显示“使用缓存”，不会误显示为单纯“数据源失败”。
- 数据源状态页提供“测试数据源”“查看最近错误”“复制诊断信息”。
- 诊断导出文件位于 `%LOCALAPPDATA%\SNInsightTerminal\logs\diagnostics_bundle.json`，不包含完整 API key。
## 0.3.3-beta.1 real-market-only 当前版本说明

- 当前客户级内部测试版：`0.3.3-beta.1`
- 本版只使用真实行情 provider 链路：Sina 实时行情、AKShare 历史行情、SHFE public 辅助状态和 last good cache。
- 不生成 baseline 预测，不生成 baseline 回测，不使用随机或样例数据冒充真实行情、预测或回测。
- 无 active model 时不生成预测；真实历史行情不足时不生成回测。
- sample data 仅用于 UI 演示，并带有醒目标识；last good cache 仅作为缓存展示，不冒充新行情。
- 可用 `scripts/smoke_market_data_refresh.ps1` 验证真实行情链路和 provider attempts。
