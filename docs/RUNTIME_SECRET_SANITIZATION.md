# 运行期密钥脱敏与泄露扫描

## Prompt 55A-private regression scan

本轮新增回归要求：

- `scan_runtime_secrets.ps1` 对 logs/cache/outputs/frontend dist/release logs 中的单条 `possible_secret` 也必须返回非零退出码。
- `config/secrets.json` 允许存在但不读取、不打印内容。
- `packaging/private_release_keys.json` 与 bundle 内部 `private_bundle_seed.json` 只记录存在状态，不读取内容。
- HTTP cache 中的 Alpha Vantage URL 必须脱敏 `apikey`，NewsAPI header 不得写入缓存或日志。

本说明对应 Prompt 54S。目标是防止 Alpha Vantage、NewsAPI、托管数据 token 等敏感信息进入日志、cache、API 响应、诊断包、前端或仓库。

## 统一脱敏工具

实现位置：

- `src/sn_futures/utils/secret_sanitizer.py`

提供：

- `sanitize_text(text)`
- `sanitize_url(url)`
- `sanitize_mapping(obj)`
- `contains_secret_like_value(text)`

覆盖格式：

- `apikey=`
- `apiKey=`
- `api_key=`
- `X-Api-Key`
- `Authorization`
- `Bearer`
- `SN_ALPHA_VANTAGE_KEY`
- `SN_NEWSAPI_KEY`
- `SN_MANAGED_DATA_PROXY_TOKEN`
- 远端错误消息中带回 key 的情况

## 写入前脱敏

以下内容写入前必须脱敏：

- provider error message
- request URL
- cache metadata
- diagnostics bundle
- refresh status/history
- runtime logs

`config/secrets.json` 是唯一允许在运行期用户目录中保存真实 key 的位置，且只在本机用户目录中存在，不读取内容用于扫描输出。私有/offline 安装包内部可以包含 `private/private_bundle_seed.json` 作为首次启动导入来源，但不得由 `/terminal`、`/legacy` 或静态文件服务暴露。

## 扫描脚本

脚本：

- `scripts/scan_runtime_secrets.ps1`

扫描范围：

- `%LOCALAPPDATA%\SNInsightTerminal\logs`
- `%LOCALAPPDATA%\SNInsightTerminal\outputs`
- `%LOCALAPPDATA%\SNInsightTerminal\cache`
- `release_build_log.txt`
- `frontend/dist`
- 可选 release onedir：传入 `-IncludeRelease`
- 可选源码和 packaging 检查：传入 `-IncludeSourceTree`

输出：

- `%LOCALAPPDATA%\SNInsightTerminal\logs\runtime_secret_scan.json`

如果发现疑似完整 key，脚本返回非零状态；如果仅发现 `config/secrets.json`，只记录“配置文件存在”，不打印内容。私有构建内部 seed 可用 `-AllowPrivateBundleSeed` 区分为“private bundle seed 存在”，但扫描仍不得打印内容。

## 边界

- 不把真实 key 写入 Git。
- 不把真实 key 写入前端。
- 公开 release 包不得包含真实 key；私有/offline release 可以在 bundle 内部携带发行方默认 seed，但构建日志、前端、runtime 日志、cache 和诊断包仍不得泄露完整 key。
- 不把完整 header 或 URL query 参数写入诊断包。
# Candidate v2 secret boundary

The v2 feature, training, candidate, OOF, institutional validation, and promotion dry-run pipeline must not serialize provider secrets into manifests, datasets, OOF traces, model registries, validation reports, logs, cache files, diagnostics bundles, or frontend assets.

The v2 dataset manifest records only feature names and runtime data availability. It must not include `SN_ALPHA_VANTAGE_KEY`, `SN_NEWSAPI_KEY`, private bundle seed values, request headers, or raw provider URLs containing `apikey`.

## Tushare Token Boundary

`SN_TUSHARE_TOKEN` is covered by the same runtime secret boundary as other provider credentials. Source code, docs, tests, frontend bundles, logs, cache, outputs, diagnostics bundles, and release logs must not contain the complete token. The scanner treats `packaging/private_release_keys.json`, private bundle seeds, and user `config/secrets.json` as allowed private locations whose contents are not printed.

Terminal APIs and frontend screens may show only `configured`, `source`, and `masked`. Provider error messages are sanitized before they are returned or written.
