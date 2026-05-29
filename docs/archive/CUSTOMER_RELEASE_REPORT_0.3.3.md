# SNInsightTerminal 0.3.3-beta.1 real-market-only 内部测试版交付报告

## 安装包

- 版本：`0.3.3-beta.1`
- 安装包：`release/SNInsightTerminal_Setup.exe`
- 构建时间：`2026-05-21 21:34:35 +08:00`
- 文件大小：`33.87 MB`
- SHA256：`57256265AA8B586BDCE0DA0D7F2818EE608AA7177C1CC744F40BCC7D8DF43A7B`

## real-market-only 策略

- 只使用真实行情 provider 与最近成功缓存。
- 不生成 baseline prediction。
- 不生成 baseline backtest。
- 无 active model 时不生成预测。
- 真实历史行情不足时不生成回测。
- sample data 只用于 UI 演示，并带明显样例标识，不进入真实分析。
- last good cache 只作为缓存展示，不冒充新行情。

## 验收结果

- 前端：`npm run typecheck`、`npm run build`、`npm run check:ui`、`npm run test:e2e` 全部通过。
- Python：`python -m compileall -q .` 通过，`pytest -q` 为 `269 passed`，`unittest` 为 `Ran 164 tests OK`。
- 真实行情 smoke：通过，`final_status=full_success`，Sina 实时行情成功，AKShare 历史行情成功，历史行数 `2710`，price-history API 可展示 `500` 个图表点。
- 安装后 smoke：`packaging/smoke_installed.ps1 -RunBrowserSmoke` 通过。
- 浏览器验收：`/terminal`、`/legacy` 可访问；Playwright 7 项浏览器 smoke 全部通过。
- 安全检查：settings API 只返回脱敏 key；日志未发现完整 mock key；安装包不包含 `.env` 或 `secrets.json`。
- 卸载验收：安装目录删除，用户数据目录默认保留。

## 已知限制

- 当前内部测试版未代码签名，Windows SmartScreen 可能提示未知发布者。
- 外部免费数据源可能受网络、限流、交易时段和字段变化影响；失败时终端会展示 provider 尝试、错误原因和下一步建议。
- ECharts bundle 仍有体积警告，属于后续性能优化项，不阻断本次交付。

## 合规声明

本系统仅供沪锡期货量化投研参考，不构成投资建议，不承诺收益，不接实盘交易。
