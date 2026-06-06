# SNInsightTerminal 客户验收清单

适用版本：`0.3.1-beta.1`  
适用安装包：`release/SNInsightTerminal_Setup.exe`

## 安装与启动

- [x] 双击安装包可完成安装。
- [x] 安装过程不要求管理员权限。
- [x] 开始菜单快捷方式已创建。
- [x] 点击快捷方式后可自动启动本地后端。
- [x] 浏览器可打开专业终端 `/terminal`。
- [x] 旧版终端 `/legacy` 仍可访问。
- [x] 若 Windows SmartScreen 提示未知发布者，已知当前内部测试版未代码签名。

## 首次使用

- [x] 首次启动向导可用。
- [x] 向导说明系统用途和合规边界。
- [x] 可跳过 API key 配置并进入系统。
- [x] 可保存 Alpha Vantage key。
- [x] 可保存 NewsAPI key。
- [x] 设置页只显示脱敏 key。
- [x] 密钥仅保存在本机用户目录，不写入前端，不上传。

## 发行前最终质量门禁

- [ ] 数据源配置：Alpha Vantage / NewsAPI / Tushare / Local API Provider key 未配置时显示“未配置”，已配置时只显示脱敏值。
- [ ] 一键刷新：触发后只通过 provider/API 拉取真实数据；失败时显示失败原因、cache/stale 状态，不要求用户手动导入。
- [ ] 数据状态：展示 runtime root、source、as_of、fetched_at、cache_status、stale_status、blocking_reasons 和数据水位。
- [ ] 新闻/政策事件：区分 fetched_at、source_published_at、available_at；无发布时间的政策页不得作为高权重事件入模。
- [ ] Feature Store gate：sample/demo/baseline/display_overlay/live_quote 不得进入训练特征；不满足 point-in-time 时返回 blocked。
- [ ] 预测原因：无 active model、数据缺失、stale cache、sample_data_used 或 baseline_used 时只显示 blocked card，不生成伪预测。
- [ ] 回测原因：无真实历史 bars、无 signal manifest、sample_data_used 或 baseline_used 时 blocked，不生成 equity curve。
- [ ] 报告免责声明：所有报告、预测、回测和风险情景输出均清晰标注“研究参考，不构成投资建议”。
- [ ] 发行包排除：`.env`、`secrets.json`、private keys、runtime cache、SQLite、logs、outputs、e2e screenshots 和安装包构建产物不进入源码仓库或安装包。
- [ ] 安装后 smoke：使用隔离 `SN_DATA_DIR` / `SN_INSIGHT_DATA_DIR`；首次启动时 provider key 均显示未配置；`/api/terminal/predictions` 在无 key/无真实数据时返回 blocked/empty，且 `sample_data_used=false`、`baseline_used=false`、`customer_prediction_generated=false`。

## 终端页面

- [x] Dashboard 显示系统状态。
- [x] Dashboard 显示主合约、最新价和更新时间。
- [x] Dashboard 显示数据质量。
- [x] Dashboard 显示模型状态。
- [x] Dashboard 显示当前研究信号。
- [x] 七周期预测页面可见。
- [x] 预测卡片在无交易点位时显示“暂无交易点位”。
- [x] 数据质量不足时显示“已降级为研究观察”。
- [x] 行情图表显示真实数据、样例数据或清晰空状态。
- [x] 事件监控显示真实新闻、样例新闻或清晰空状态。
- [x] 报告中心显示报告全文、样例报告或清晰空状态。
- [x] 因子分析页面可见。
- [x] 数据源状态页解释“未配置”。
- [x] “一键刷新数据”入口可见。
- [x] 技术明细默认折叠。
- [x] 合规声明可见。

## 稳定性与安全

- [x] 任意模块错误不会导致整页白屏。
- [x] API 失败时显示中文错误提示。
- [x] 前端不显示完整 API key。
- [x] 前端不保存 key 到 localStorage。
- [x] 日志不包含完整 key。
- [x] 页面不包含收益承诺或确定性买卖指令文案。
- [x] `/api/terminal/docs` 可访问。
- [x] 浏览器视觉验收截图已生成。

## 卸载

- [x] 卸载成功。
- [x] 安装目录删除。
- [x] 开始菜单快捷方式删除。
- [x] 用户数据目录默认保留：`%LOCALAPPDATA%\SNInsightTerminal`
- [x] 文档说明如何手动删除用户数据。

## 合规确认

- [x] 系统不接实盘交易接口。
- [x] 系统不构成投资建议。
- [x] 系统不承诺收益。
- [x] 所有输出仅供沪锡期货量化投研参考。
