# SNInsightTerminal 发行产物状态

生成时间：2026-05-19

## 1. 当前 release 目录

当前存在：

```text
release/SNInsightTerminal_Setup.exe
```

文件信息：

- 文件时间：2026-05-16 11:40:10
- 文件大小：52,022,272 bytes
- SHA256：`FD8D1F15E59E1964B8FC0927E7F567DA02C4C8845C48A8ADCDDB17406B8546BA`

## 2. 重要状态说明

该安装包是旧包，不是 Prompt 15 或 Prompt 16 新构建产物。

原因：

- 当前环境 `node.exe` 执行失败：`Access is denied`。
- 当前环境没有可用 `npm` / `npm.cmd`。
- `frontend/dist/index.html` 不存在。
- 未执行新的 `packaging/build_release.ps1` 完整流程。

因此不能把该旧包当作本轮新版本成功产物。

## 3. 旧包用途

该旧包仅可作为历史回退参考，不代表当前新专业终端、Terminal API、settings API、发行 launcher 和新前端能力已经打入安装包。

如果需要临时交付，应明确标注：

```text
旧包仅供回退，不代表新终端功能。
```

## 4. 新版本产物要求

新的正式安装包必须通过以下流程重新生成：

```powershell
.\packaging\build_release.ps1
```

正式成功条件：

- Python 编译检查通过。
- `pytest -q` 通过。
- 前端 `npm install`、`npm run typecheck`、`npm run build` 通过。
- `frontend/dist/index.html` 存在。
- PyInstaller onedir 构建成功。
- onedir smoke 成功。
- Inno Setup 成功生成：

```text
release/SNInsightTerminal_Setup.exe
release/SHA256SUMS.txt
```

## 5. 当前阻断项

当前仍需在本机修复：

- Node.js LTS / npm 可用性。
- Inno Setup `ISCC.exe` 可用性。
- 新前端 `frontend/dist` 构建。

完成后才能进入正式安装包构建与安装后验收。
