# Terminal Performance Optimization

## 发现的问题

- `/api/terminal/snapshot` 历史上聚合 predictions、model-health、learning-status、backtest、data-status 和 system-health，连接首屏容易被慢组件拖住。
- `/api/terminal/system-health` 曾调用深度真实性审计 provider，不适合作为轻量健康检查。
- 前端 API client 之前没有统一 timeout，也没有请求去重。
- 轮询使用固定 interval，页面不可见时仍会请求。
- Vite 主 chunk 曾超过 500k warning。

## 修复内容

后端：

- 新增 `api_response_cache.py`，给 summary、snapshot、model-health、data-status、feature coverage、artifacts 加 TTL 缓存。
- 新增 `task_queue_service.py`，让 refresh-all 和 candidate training 返回 task_id。
- 新增 `performance_diagnostics_service.py`，输出 `outputs/performance/api_performance_report.json`。
- `snapshot` 改为 lite snapshot，不同步嵌入重模块。
- `system-health` 改为 lightweight，不调用慢 provider。

前端：

- API client 使用 `AbortController` timeout。
- GET 请求支持 request deduping。
- 轮询失败后指数退避，页面隐藏时暂停。
- 非总览页面不被 snapshot loading gate 阻塞。
- Vite 使用 manualChunks 拆分 `react-vendor`、`echarts`、`vendor`。

## 验证方式

- `GET /api/terminal/performance/diagnostics`
- 查看 `outputs/performance/api_performance_report.json`
- Playwright E2E 验证页面可打开、无全局白屏、移动端无横向溢出。

## 不改变的边界

- 不改模型逻辑。
- 不发布 active。
- 不生成客户预测。
- 不降低 promotion gate。
