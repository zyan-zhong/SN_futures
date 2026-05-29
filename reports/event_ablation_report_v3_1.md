# V3.1.0 事件消融报告

本轮修复事件链路与 URL 打开，不声称事件因子已通过完整消融证明带来稳定收益。

## 已验证

- 事件库 append-only，不因 provider 失败清空旧事件。
- 事件有 available_at 时可进入 feature matrix。
- future available_at 事件会被过滤，避免未来函数。
- UI 能显示 recognized/used/rejected 统计和过滤原因。

## 未宣称

- 未宣称新闻政策显著提升所有周期方向准确率。
- 未宣称 event_ablation_gain 已稳定为正。
- 未无条件提升 active model。

## 后续消融口径

每个 horizon 必须比较：

- price_only baseline
- event_only baseline
- price_plus_event candidate
- price_plus_event_plus_macro candidate

若事件模型无稳定增益，UI 应显示“事件因子暂未带来稳定增益”，但仍可作为解释和风险提示。
