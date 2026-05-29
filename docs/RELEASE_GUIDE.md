# SNInsightTerminal 发行指南

当前客户级内部测试版本：`0.3.0-beta.1`

本文档用于 Windows 正式安装包的构建、安装后检查和用户数据管理。系统仅用于沪锡期货 SN 量化投研参考，不构成投资建议，不承诺收益，不接实盘交易接口。

## 1. 构建环境

正式发行环境建议使用 Windows 10/11，并安装：

- Python 3.10 或更高版本。
- Node.js LTS 与 npm。
- PyInstaller。
- Inno Setup，并确保 `ISCC.exe` 可在 PowerShell 中调用。

当前 Codex 环境中 `node.exe` 权限不可用，因此不能在该环境生成正式安装包。请在本机修复 Node.js/npm 后运行发行脚本。

## 2. 构建命令

在项目根目录执行：

```powershell
.\packaging\build_release.ps1
```

脚本会依次执行：

- Python 编译检查。
- `pytest -q`。
- 前端 `npm install`、`npm run typecheck`、`npm run build`。
- 检查 `frontend/dist/index.html`。
- PyInstaller onedir 构建。
- onedir 启动 smoke。
- Inno Setup 打包。
- 生成 SHA256 校验文件。

如果 Node/npm、PyInstaller 或 Inno Setup 缺失，脚本会中文提示并停止，不生成半成品安装包。

## 3. 安装包位置

成功后生成：

```text
release/SNInsightTerminal_Setup.exe
release/SHA256SUMS.txt
```

正式发布前请确认 `release/` 中只保留一个正式安装包：`SNInsightTerminal_Setup.exe`。

## 4. 普通用户安装方式

用户双击 `SNInsightTerminal_Setup.exe` 后，默认安装到：

```text
%LOCALAPPDATA%\Programs\SNInsightTerminal
```

安装器会创建开始菜单快捷方式，并可选创建桌面快捷方式。用户点击快捷方式后，桌面启动器会：

- 初始化用户数据目录。
- 自动选择可用端口，优先 `8765`，再尝试 `8766` 到 `8769`。
- 启动本地后端。
- 打开浏览器访问 `http://127.0.0.1:<port>/terminal`。

旧版终端仍保留在 `/legacy`，用于兼容和排障。

## 5. 首次配置 API Key

系统没有配置 API key 也可以启动；数据源会显示“未配置”。

首次启动体验：

1. 安装后点击开始菜单或桌面快捷方式。
2. 浏览器打开 `/terminal`。
3. 如果 Alpha Vantage 或 NewsAPI 未配置，终端会显示首次启动向导。
4. 可以立即配置，也可以选择“稍后配置”或“不再自动弹出”。
5. 跳过配置不会阻止进入终端，相关数据源会显示“未配置”。

设置页配置方式：

1. 打开专业终端设置页。
2. 查看 Alpha Vantage / NewsAPI 是否已配置。
3. 输入 Alpha Vantage 或 NewsAPI key。
4. 点击保存单个密钥，或点击“同时保存”。
5. 保存后输入框会清空，界面只显示脱敏结果。

重置方式：

1. 打开专业终端设置页。
2. 点击“清除本机密钥”。
3. 再次确认。
4. 系统只清除 `secrets.json` 中的密钥，不删除报告、日志、缓存、模型和其它用户数据。

密钥仅保存在本机用户目录：

```text
%LOCALAPPDATA%\SNInsightTerminal\config\secrets.json
```

密钥不会写入前端，不会写入安装目录，不会上传。界面和 API 只显示脱敏值。

私有/offline 发行版可以预配置发行方默认 Alpha Vantage / NewsAPI key。首次启动时默认 key 会导入到用户目录 `config/secrets.json`，设置页显示“已预配置”，客户仍可替换为自己的 key。公开 GitHub release 不应包含发行方 key。

日志位置：

```text
%LOCALAPPDATA%\SNInsightTerminal\logs
```

如果浏览器没有自动打开，可手动访问终端地址；实际端口可在启动器输出或日志中查看。

## 6. 用户数据目录

Windows 用户数据根目录：

```text
%LOCALAPPDATA%\SNInsightTerminal
```

目录结构：

- `data/`：本地数据。
- `cache/`：缓存。
- `logs/`：日志。
- `reports/`：报告。
- `models/`：模型文件。
- `config/`：用户配置和本机密钥。
- `registry/`：模型注册表。
- `outputs/`：运行输出。

安装目录可以是只读目录；运行时数据不会写回 PyInstaller 安装目录。

## 7. 卸载说明

卸载程序默认删除安装目录，但保留用户数据目录：

```text
%LOCALAPPDATA%\SNInsightTerminal
```

如需彻底清理，可在卸载后手动删除该目录。删除前请确认已经备份本地报告、模型和配置。

## 8. 安装后 Smoke

安装后可运行：

```powershell
.\packaging\smoke_installed.ps1
```

脚本会检查：

- 安装后的 `SNInsightTerminal.exe`。
- `/api/terminal/docs`。
- `/terminal`。
- `/legacy`。
- `/api/terminal/data-status`。
- 用户数据目录。
- 默认配置文件。
- 日志和密钥泄露风险。

## 9. 常见问题

### Node/npm 不可用

请安装 Node.js LTS，或修复 `node.exe Access is denied` 权限问题。正式包必须先构建 `frontend/dist`。

### frontend/dist 缺失

运行：

```powershell
cd frontend
npm install
npm run build
```

然后重新执行 `.\packaging\build_release.ps1`。

### 端口被占用

启动器会自动尝试 `8765` 到 `8769`。如果全部被占用，请关闭占用端口的程序，或使用：

```powershell
SNInsightTerminal.exe --port 8770
```

### 后端启动失败

查看日志：

```text
%LOCALAPPDATA%\SNInsightTerminal\logs\launcher.log
```

### 数据源未配置

进入设置页配置 API key。未配置时系统仍可运行，但相关数据源会显示“未配置”。

### 安装后打不开浏览器

可手动打开：

```text
http://127.0.0.1:8765/terminal
```

如果端口不同，请查看启动器输出或日志。

## 10. 合规声明

SNInsightTerminal 仅用于沪锡期货 SN 量化投研、回测、报告和风险管理辅助。不构成投资建议、交易建议、收益承诺或风险承诺。期货交易具有高杠杆和高风险，模型可能因数据延迟、市场结构变化、新闻误读或极端事件而失效。用户需独立判断并自行承担风险。
## 代码签名与 SmartScreen

当前安装包未进行代码签名，Windows 可能显示“未知发布者”或 SmartScreen 提示。未签名不影响本地测试和内部验证，但会影响外部用户信任。

如果后续面向外部用户发布，建议购买代码签名证书，并在发行流水线中加入 Microsoft SignTool 步骤。本轮不执行代码签名，也不把签名失败作为安装包 smoke 的阻断项。

请勿为了绕过 SmartScreen 而弱化安全检查、打包真实密钥或关闭合规提示。

## 11. 前端 UI 合同检查

每次修改专业终端前端后，建议先运行客户级 UI 合同检查：

```powershell
cd frontend
npm run check:ui
```

该检查会扫描 `frontend/src` 和 `frontend/index.html`，确认：

- 不出现“保证盈利”“稳赚”“建议买入”“建议卖出”等禁用文案。
- 必须保留“不构成投资建议”“不承诺收益”“不接实盘交易”“暂无交易点位”“已降级为研究观察”等客户级提示。
- 技术明细默认折叠，并使用“技术明细 / 开发调试信息”标题。
- 前端不保存 API key、token、secret、password、authorization 等敏感信息到 localStorage。
- `ErrorBoundary` 和 `FirstRunWizard` 文件存在。

如果 `check:ui` 失败，不应继续构建安装包。修复前端文案或安全问题后，再运行：

```powershell
npm run typecheck
npm run build
npm run check:ui
```

本轮前端优化只更新源码和 `frontend/dist`。如果要把优化写入 `release/SNInsightTerminal_Setup.exe`，仍需重新运行：

```powershell
.\packaging\build_release.ps1
```
## 12. 私有发行版预配置 Key 构建

私有构建要求本机提供 `packaging/private_release_keys.json` 或 `SN_BUNDLE_*` 环境变量。真实 key 不写入源码、文档、测试、前端或 Git。

```powershell
.\packaging\build_release.ps1 `
  -PrivateBundleKeys `
  -PrivateKeysFile "packaging/private_release_keys.json" `
  -AllowEmbeddedProviderKeys `
  -NodePath "C:\Program Files\nodejs\node.exe" `
  -NpmPath "C:\Program Files\nodejs\npm.cmd"
```

安装后验收：

```powershell
.\packaging\smoke_installed.ps1 -RunBrowserSmoke -ExpectPrivateBundleKeys
```

私有版限制：安装包内部的 seed 不能防止高级用户逆向提取，因此只适合内部/私有交付。长期正式方案建议使用 managed data proxy / license token。

## 13. 0.3.0-beta.1 客户级构建说明

本版应确认 Prompt 19-22 的 UI/UX 优化已经进入安装包：

- 首次启动向导和设置页优化。
- Dashboard 状态 Banner 与 6 个核心状态卡。
- 七周期预测卡片业务化展示。
- 图表、DataTable、报告中心和数据源状态优化。
- ErrorBoundary、响应式布局、可访问性和 `npm run check:ui`。

构建前必须运行：

```powershell
cd frontend
npm install
npm run typecheck
npm run build
npm run check:ui
cd ..
python -m compileall -q .
pytest -q
python -m unittest discover -s tests -p "test*.py" -v
```

正式构建：

```powershell
.\packaging\build_release.ps1 `
  -NodePath "C:\Program Files\nodejs\node.exe" `
  -NpmPath "C:\Program Files\nodejs\npm.cmd"
```

构建后必须运行：

```powershell
.\packaging\smoke_installed.ps1
```

客户级验收清单见 `docs/CUSTOMER_ACCEPTANCE_CHECKLIST.md`。客户交付报告见 `docs/CUSTOMER_RELEASE_REPORT.md`。

后续可选优化：

- 代码签名与 SmartScreen 信任提升。
- 浏览器自动化视觉回归。
- 减小 ECharts chunk。
- 增加在线更新机制。
## 0.3.0-beta.1 客户级内部测试版构建结果

本轮客户级安装包已重新构建，Prompt 19-22 的首次启动向导、设置页、Dashboard、七周期预测页、图表、表格、报告中心、数据源状态、错误边界、响应式和可访问性优化已经进入安装包。

发行产物：

```text
release/SNInsightTerminal_Setup.exe
```

构建与验收结果：

- 版本：`0.3.0-beta.1`
- 安装包时间戳：`2026-05-20 02:08:26 +08:00`
- SHA256：`A84E29E6DD7F6F71C4D3B5864DE0C3D9DB307B7A513FFDCCFC5A4EEF57EDCB2B`
- 前端 `typecheck/build/check:ui`：通过
- Python `compileall/pytest/unittest`：通过
- PyInstaller onedir：通过
- Inno Setup：通过
- 安装后 smoke：通过

重要说明：

- 当前内部测试包未代码签名，Windows SmartScreen 可能提示未知发布者。
- 安装包不包含 `.env`、`secrets.json`、本地 SQLite、cache、logs 或真实 API key。
- 卸载默认保留 `%LOCALAPPDATA%\SNInsightTerminal` 用户数据目录。
- 系统不接入实盘交易接口，不构成投资建议，不承诺收益。
