# Performance Budget

SNInsightTerminal uses explicit latency budgets so the visual terminal stays responsive while research workflows remain asynchronous.

## Budgets

| Area | Target |
| --- | ---: |
| `/terminal` first visible screen | `< 2s` |
| `/api/terminal/summary` | `< 300ms` |
| `/api/terminal/system-health` | `< 300ms` |
| `/api/terminal/snapshot-lite` | `< 500ms` |
| Page navigation | `< 500ms` |
| First chart paint | `< 1s` |
| INP target | `< 200ms` |

## API Classes

| Class | APIs | Rule |
| --- | --- | --- |
| Light | `summary`, `system-health`, `snapshot-lite`, `settings/status` | Must not refresh providers, train models, run validation, or scan large artifact trees. |
| Medium | `data-status`, `price-history`, `market-analysis`, `feature-store/status`, `training-dataset/status` | May read local JSON/CSV manifests and cached summaries. |
| Heavy | `refresh-all`, training, validation, research backtest, artifact archive | Must run through task APIs or return cached status. |

## Current Diagnostic Snapshot

Measured through `run_api_performance_diagnostics()` on this workstation:

| Endpoint | Result |
| --- | --- |
| `/api/terminal/summary` | within budget, cached response available |
| `/api/terminal/system-health` | within budget, no provider checks |
| `/api/terminal/snapshot-lite` | within budget, first-screen payload only |
| `/api/terminal/data-status` | within budget, cached response available |
| `/api/terminal/research/artifacts` | within budget, cached response available |

## Guardrails

- `snapshot-lite` is the first-screen connection API and omits predictions, backtest diagnostics, data-status, model-health, and validation payloads.
- `system-health` is lightweight and does not call provider checks or truth-audit providers.
- Heavy jobs start through `/api/terminal/tasks/start` or task-backed aliases and return a `task_id` quickly.
- Cache entries include `generated_at`, `cache_hit`, and `cache_age_seconds`.
- Refresh/build operations invalidate affected cache prefixes.
- No cache entry may contain provider keys or private bundle seed contents.
