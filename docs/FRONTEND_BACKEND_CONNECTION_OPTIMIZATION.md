# Frontend Backend Connection Optimization

This document records the terminal connection strategy used to keep the UI responsive without changing model behavior.

## First Screen

- The React shell loads the dashboard eagerly and requests `/api/terminal/snapshot-lite`.
- `snapshot-lite` returns only summary and refresh status for connection readiness.
- Other pages load their own data after navigation.
- A slow snapshot no longer blocks non-dashboard pages.

## Frontend Loading

- Heavy pages are loaded with `React.lazy` and `Suspense`.
- ECharts remains in a separate Vite chunk and chart components lazy-load the renderer.
- Polling uses exponential backoff and pauses while the page is hidden.
- API calls use `AbortController` timeouts.
- GET calls dedupe in-flight requests by path.

## Backend Connection Rules

- Light APIs use short TTL cache.
- Medium APIs read local manifests and cached payloads.
- Heavy work is task-backed and should not block HTTP request/response.
- Task logs and cache payloads are sanitized before writing.

## Timeouts

| Request Type | Timeout |
| --- | ---: |
| Light GET | `5s` |
| Default GET | `15s` |
| Task start | `30s` |
| Task status polling | `5s` |

## User Experience Rules

- Page-level skeletons replace global blocking loading gates.
- API failure renders page or card-level error states instead of a blank terminal.
- Stale cached data must be marked with cache metadata.
- Research backtests, candidate training, and validation must remain research-only until an explicit gate and manual approval flow succeeds.
