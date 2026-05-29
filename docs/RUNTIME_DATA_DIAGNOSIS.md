# 运行期数据诊断说明

本文件用于解释：为什么安装后 `/terminal` 能打开，但网页终端可能没有数据、图表、新闻或报告。

## 1. 当前诊断结论

专业终端前端本身只负责展示后端 `/api/terminal/*` 返回的数据。当前 terminal API 主要聚合运行期缓存、报告文件、模型状态和数据源状态；它不会在页面打开时自动伪造行情、预测、新闻或报告。

因此，安装后页面为空通常不是前端渲染失败，而是运行期数据链路尚未生成对应文件：

- 没有预测缓存：`sn_unified_forecast.json`、`sn_live_predictions.json`、`sn_live_snapshot.json`
- 没有报告 Markdown：日报、周报、月报、事件报告
- 没有新闻/事件库记录
- 外部数据源未配置或尚未实际请求验证
- 数据刷新、新闻刷新、预测生成、报告生成任务尚未运行

## 2. 需要检查的用户数据目录

默认用户数据目录：

```text
%LOCALAPPDATA%\SNInsightTerminal
```

关键子目录：

```text
outputs/
reports/
data/
cache/
config/
logs/
```

## 3. 关键输出文件

预测缓存文件：

```text
outputs/sn_unified_forecast.json
outputs/sn_live_predictions.json
outputs/sn_live_snapshot.json
```

报告文件：

```text
reports/sn_daily_report.md
reports/sn_weekly_report.md
reports/sn_monthly_report.md
reports/sn_event_report.md
```

新闻/事件库可能位于：

```text
data/event_store.sqlite
data/news_events.sqlite
data/events.sqlite
```

## 4. 新增诊断 API

启动后端后访问：

```text
GET /api/terminal/runtime-diagnostics
```

该接口会返回：

- 用户数据目录
- 预测输出目录
- 报告目录
- 配置目录
- 是否存在 secrets.json
- Alpha Vantage / NewsAPI 是否已配置
- 预测文件是否存在、是否合法、是否包含预测卡片
- 报告文件是否存在、正文长度
- 新闻/事件库是否存在、事件数量
- terminal API 内部服务是否可调用
- 数据缺口结论
- 中文下一步建议

该接口只读，不会抓取行情，不会生成预测，不会伪造新闻，不会写入真实密钥。

## 5. 新增诊断脚本

在 PowerShell 中运行：

```powershell
.\scripts\diagnose_runtime_data.ps1
```

如果后端端口不是 8765：

```powershell
.\scripts\diagnose_runtime_data.ps1 -BaseUrl "http://127.0.0.1:8766"
```

脚本会把结果保存到：

```text
%LOCALAPPDATA%\SNInsightTerminal\logs\runtime_diagnostics.json
```

## 6. 如何判断根因

如果 `no_cache_files=true`：

说明预测缓存文件不存在，需要运行数据刷新和预测生成任务。

如果 `no_predictions=true`：

说明文件可能存在，但没有可展示的七周期预测卡片。

如果 `no_reports=true`：

说明报告 Markdown 不存在或内容为空，需要运行报告生成任务。

如果 `no_news_events=true`：

说明新闻/事件库没有记录，需要运行新闻/事件刷新任务，并检查 NewsAPI 或本地事件源配置。

如果 `no_provider_validation=true`：

说明当前只能看到“已配置/未配置”状态，尚未对 provider 做真实请求验证。

如果 `frontend_only_shell=true`：

说明前端和 API 壳已经启动，但运行期数据尚未生成。这是用户看到“没有数据、没有图表、没有新闻”的最常见原因。

## 7. 下一步修复计划

建议进入 Prompt 25：数据刷新任务中心。

目标是把以下动作做成可点击、可审计、可在安装后首次使用时引导执行的任务：

1. 刷新行情与数据水位。
2. 验证 Alpha Vantage / NewsAPI provider。
3. 拉取新闻与关键事件。
4. 构建事件与因子特征。
5. 生成七周期预测缓存。
6. 生成日报、周报、月报和事件报告。
7. 将任务进度、失败原因和最近成功时间展示到终端。

## 8. 合规声明

SNInsightTerminal 仅供沪锡期货量化投研参考，不构成投资建议，不承诺收益，不接实盘交易。
