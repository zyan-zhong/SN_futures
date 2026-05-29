# 私有发行版预配置 API Key

## Prompt 55A-private 后刷新链路验收

私有安装包首次启动后，内置发行方 key 会先导入用户目录 `config/secrets.json`，随后数据刷新链路应满足：

- `GET /api/terminal/settings/status`：Alpha Vantage 与 NewsAPI 均为 `configured=true`，只显示 `source` 和 `masked`。
- `GET /api/terminal/settings/key-diagnostics`：`can_read=true`，不返回完整 key。
- `POST /api/terminal/refresh/cross-market`：不再返回 `key_missing`；成功时写入 `outputs/fundamentals/sn_cross_market.json` 和 `outputs/fundamentals/fx_macro_provider_status.json`。
- `POST /api/terminal/newsapi/test`：使用 `X-Api-Key` header，不把 key 放入 URL。
- `POST /api/terminal/refresh/news`：写入 `outputs/events/news_raw.json`、`news_events_filtered.json`、`event_factor_inputs.json`、`news_relevance_report.json` 和 `news_provider_status.json`。
- `scripts/scan_runtime_secrets.ps1`：允许用户配置文件存在，但 logs/cache/outputs/frontend dist/release logs 中不得出现完整 key。

本验收仍不训练模型、不发布 active、不生成客户预测、不使用 baseline 或 fake prediction。

本说明对应私有/offline release 场景：发行方可以在安装包内部携带默认 Alpha Vantage / NewsAPI key，让客户首次安装后即开即用。该方案不适合公开 GitHub release。

## 目标

1. 客户安装后不必手动配置第三方 key，也能自动尝试 cross-market 与新闻刷新。
2. 设置页仍保留填写、替换、重置 key 的能力。
3. UI 和 API 只显示 `configured`、`source`、`masked`，不显示完整 key。
4. 真实 key 不写入源码、前端、文档、测试、日志、cache、诊断包或 Git。

## 构建输入

私有构建支持两种本机输入方式：

- 环境变量：`SN_BUNDLE_KEYS_ENABLED=1`、`SN_BUNDLE_ALPHA_VANTAGE_KEY`、`SN_BUNDLE_NEWSAPI_KEY`。
- 本机私有文件：`packaging/private_release_keys.json`。

`packaging/private_release_keys.json` 和 `build/private_bundle_seed.json` 已加入 `.gitignore`，不得提交。

## 构建流程

私有构建命令：

```powershell
.\packaging\build_release.ps1 `
  -PrivateBundleKeys `
  -PrivateKeysFile "packaging/private_release_keys.json" `
  -AllowEmbeddedProviderKeys `
  -NodePath "C:\Program Files\nodejs\node.exe" `
  -NpmPath "C:\Program Files\nodejs\npm.cmd"
```

启用 `-PrivateBundleKeys` 后，构建脚本会生成临时 `build/private_bundle_seed.json`，PyInstaller 将其放入 bundle 内部的 `private/private_bundle_seed.json`。构建日志只输出脱敏状态，构建完成后删除明文临时 seed。

公开构建默认不包含 private seed。

## 首次启动导入

启动器启动时调用 `import_private_bundle_keys_if_needed()`：

1. 检查 bundle 内部 `private/private_bundle_seed.json`。
2. 如果用户目录 `config/secrets.json` 不存在或缺少某个 key，只导入缺失项。
3. 如果用户已有自定义 key，不覆盖。
4. 导入后的来源记录为 `private_bundle`。
5. reset 后可恢复发行方默认 key。

provider 运行期不直接读取 bundle seed，只通过统一 resolver 读取用户目录 secrets、环境变量或开发 `.env`。

## 设置页行为

设置页显示：

- Alpha Vantage：已预配置 / 用户自定义 / 未配置。
- NewsAPI：已预配置 / 用户自定义 / 未配置。
- 测试连接按钮。
- 替换 key 输入框。
- 重置为发行方默认按钮。

页面不把 key 写入本地浏览器存储，不把 key 放入 URL，不显示完整 key。

## 安全限制

私有安装包内置 key 无法防止高级用户逆向提取，因此仅适用于内部测试或私有交付。公开 GitHub release 不应包含发行方 key。长期正式方案建议使用 managed data proxy / license token，由发行方服务器维护第三方 API key。

## 验收

私有版安装后 smoke 使用：

```powershell
.\packaging\smoke_installed.ps1 -RunBrowserSmoke -ExpectPrivateBundleKeys
```

验收要点：

- `settings/status` 中 Alpha Vantage 和 NewsAPI 均 `configured=true`。
- `key-diagnostics` 只返回 masked/source。
- `newsapi/test` 不再返回 key_missing。
- runtime secret scan 不在 logs/cache/outputs/frontend/dist 中发现完整 key。
- `/terminal`、`/legacy` 和静态文件服务不能访问 private seed。
