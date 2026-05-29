# SNInsightTerminal 发行环境诊断

生成时间：2026-05-19

本报告用于解释为什么历史上可以生成安装包，而当前新发行流程在 Codex 环境中遇到 `node.exe Access is denied` 与 `npm 不可用`。

## 1. 已发现的旧打包能力

项目中仍保留多套旧打包脚本和配置：

- `packaging/build_windows_package.ps1`
  - 旧版 Windows 打包主脚本。
  - 支持 `cpu/gpu` flavor。
  - 使用旧 `SNInsightTerminalApp.spec` / `SNInsightTerminalAppGpu.spec`。
  - 使用 `packaging/installer/NativeSetup.cs` 编译原生安装器。
  - 会归档旧 release 产物。
  - 旧流程主要打包旧 UI 和 Python 应用，不依赖 Vite/React 前端构建。
- `packaging/SNInsightTerminalApp.spec`
  - 旧 CPU app PyInstaller spec。
- `packaging/SNInsightTerminalAppGpu.spec`
  - 旧 GPU app PyInstaller spec。
- `packaging/SNInsightTerminalSetup.spec`
  - 更早期 setup 相关 spec。
- `packaging/installer/NativeSetup.cs`
  - 旧安装器核心。
- `packaging/installer/install.cmd`
  - 旧安装辅助脚本。
- `packaging/installer/create_shortcuts.ps1`
  - 旧快捷方式创建脚本。

结论：之前本地能生成安装包，最可能使用的是旧 `packaging/build_windows_package.ps1` 流程。该流程不需要 Node/npm，因为旧 UI 是静态原生 JS，不需要 Vite build。

## 2. 现有发行产物

当前 `release/` 中存在：

- `release/SNInsightTerminal_Setup.exe`
  - 文件时间：2026-05-16 11:40:10
  - 文件大小：52,022,272 bytes
  - 这是旧包，不是 Prompt 15 之后的新构建产物。

当前 `release_archive/` 中存在多次旧归档，包括：

- `archive_20260516_113716`
- `archive_20260516_101938`
- `archive_20260516_020536`
- `archive_20260516_013702`
- 多个 2026-05-15 与 2026-05-14 的归档目录

这些归档说明旧打包链路此前确实多次运行过。

## 3. 当前前端构建产物状态

检查结果：

- `frontend/dist/index.html`：不存在。
- `frontend/dist/assets`：不存在。
- `frontend/node_modules`：不存在。
- `frontend/package-lock.json`：不存在。

结论：新专业终端尚未构建，无法进入正式安装包发行。正式新包必须先生成 `frontend/dist`。

## 4. 当前 Node/npm 诊断结果

当前 Codex 环境检测到：

- `where.exe node`：
  - `C:\Program Files\WindowsApps\OpenAI.Codex_26.513.4821.0_x64__2p2nqsd0c76g0\app\resources\node.exe`
- `Get-Command node -All`：
  - 同上，版本元数据为 24.14.0.0。
- 执行 `node -v`：
  - 失败：`Access is denied`
- `where.exe npm`：
  - 未找到。
- `Get-Command npm / npm.cmd`：
  - 未找到。

结论：当前 PATH 指向 Codex App 内置资源目录中的 `node.exe`，但该可执行文件被当前 PowerShell 进程拒绝执行；同时没有可用 `npm.cmd`。这不是项目代码错误，而是当前执行环境工具链不可用。

## 5. PyInstaller 与 Inno Setup 诊断结果

当前环境检测到：

- `pyinstaller --version`：6.19.0
- `python -m PyInstaller --version`：6.19.0

当前未检测到：

- `ISCC.exe`
- 常见路径下的 Inno Setup 6

结论：PyInstaller 可用；Inno Setup 未配置或未加入 PATH。若要生成最终 `SNInsightTerminal_Setup.exe`，仍需安装或配置 Inno Setup。

## 6. 新旧打包流程差异

旧流程：

- 入口：`packaging/build_windows_package.ps1`
- UI：旧静态 UI
- 不需要 Node/npm
- 使用 C# 原生安装器生成 setup
- 产物可直接写入 `release/SNInsightTerminal_Setup.exe`

新流程：

- 入口：`packaging/build_release.ps1`
- UI：新 `frontend/` Vite + React + TypeScript 专业终端
- 必须先生成 `frontend/dist`
- 使用 PyInstaller onedir + Inno Setup
- 默认不删除旧 release 包，避免误删可回退产物

## 7. 本轮修复方向

已增强：

- 新增 `packaging/diagnose_release_env.ps1`，用于工具链诊断。
- 增强 `packaging/build_release.ps1`：
  - 支持 `-NodePath`
  - 支持 `-NpmPath`
  - 支持 `-UseExistingFrontendDist`
  - 支持 `-SkipFrontendBuild`
  - 支持 `-SkipInstaller`
  - 支持 `-SkipSmoke`
  - 支持 `-CleanRelease`
  - 默认不删除旧 release 产物
  - Node 失败后继续尝试其他候选路径
  - npm 优先查找 `npm.cmd`
  - 构建日志写入 `release_build_log.txt`

## 8. 建议操作

若要在本机生成新正式安装包：

1. 安装或修复 Node.js LTS。
2. 确认 `node -v` 与 `npm.cmd -v` 可执行。
3. 安装 PyInstaller。
4. 安装 Inno Setup 6，并确认 `ISCC.exe` 可执行。
5. 运行：

```powershell
.\packaging\diagnose_release_env.ps1
.\packaging\build_release.ps1
```

如果已经在另一台机器上生成了 `frontend/dist`，可临时复用：

```powershell
.\packaging\build_release.ps1 -UseExistingFrontendDist
```

但这不等同于重新构建前端，正式发行仍建议完整执行前端构建。
