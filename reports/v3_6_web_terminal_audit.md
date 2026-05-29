# SNInsightTerminal V3.6 Web 终端与模型治理审计报告

生成日期：2026-05-16

## 一、Web 终端无显示根因

源码检查确认，`ui_web/app.js` 存在编码破坏与截断字符串，典型表现包括：

- 中文字符串被破坏为乱码，部分引号与模板字符串被截断。
- 浏览器加载 `/app.js` 时会发生 JavaScript 语法错误。
- API 路由与静态资源路由本身可返回 200，因此根因不是后端 API 不可达，而是前端脚本不可执行。

## 二、已实施修复

- 全量重写 `ui_web/app.js`，保留无构建依赖的原生 JavaScript 架构。
- 删除前端概率兜底逻辑。缺少 `p_up / p_down / p_neutral` 时显示 `missing_payload_error`，不补 0.5 或假中性。
- 更新 `ui_web/index.html` 为 V3.6 结构，确保 DOM id 与渲染函数一一对应。
- 增强 `ui_web/styles.css`，支持顶部状态栏、七周期方向矩阵、主图表区、事件证据、模型证据、数据新鲜度、系统审计和报告预览。
- 移除对外部 CDN ECharts 的硬依赖。ECharts 可用时优先使用；不可用时使用内置 SVG fallback，避免离线空白。
- 增加全局错误边界。API 失败、字段缺失、图表库不可用或数据 stale 时，页面内显示明确错误，不允许整页空白。
- 原文打开继续统一走后端 `/api/events/open`，前端不绕过后端安全校验。

## 三、API 合同检查

V3.6 Web 首页依赖以下接口：

- `GET /api/ui/bootstrap`
- `GET /api/predictions/live`
- `GET /api/charts/price-forecast?horizon=...`
- `GET /api/events/evidence?horizon=...`
- `GET /api/models/health`
- `GET /api/model/promotion-report?horizon=...`
- `GET /api/news/policy-impact`
- `GET /api/data/watermark`
- `GET /api/diagnostics/system-truth`

前端不再推导 forecast 时间戳，价格图只渲染后端返回的 `history` 与 `forecast`。

## 四、模型增强边界

本轮继续保持受控模型增强轨道：

- `train_candidate`、`walk_forward`、`event_ablation`、`promotion_check` 只能生成候选、审计和报告。
- candidate 未通过 direction-first 指标、概率校准、事件消融、路径连续性和 promotion gate 时，不得替换 active。
- GPU/深度模型只作为 challenger/research，不绕过 promotion gate。
- 如果真实 walk-forward 没有提升，系统必须显示 candidate failed 或 active retained，不得宣称模型准确率提升。

## 五、验证要求

必须通过：

```powershell
$env:PYTHONPATH='src'
python -m unittest discover -s tests -p "test*.py" -v
pytest -q
python -m compileall -q src
```

前端专项验证：

- `ui_web/app.js` 无乱码哨兵。
- `ui_web/app.js` 无前端 0.5 假概率兜底。
- `ui_web/index.html` 包含所有 JS 访问的 DOM id。
- 无外部 CDN 强依赖。
- 图表可在 ECharts 不存在时使用 SVG fallback 渲染。

## 六、合规说明

本终端所有预测、信号、报告、回测与持仓情景均仅为沪锡期货量化投研参考，不构成投资建议、交易建议、收益承诺或风险承诺。期货交易有风险，投资需谨慎。
