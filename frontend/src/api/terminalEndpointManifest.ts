export const terminalEndpointDomains = {
  market: [
    "/api/terminal/summary",
    "/api/terminal/snapshot",
    "/api/terminal/data-status",
    "/api/terminal/market-analysis"
  ],
  events: [
    "/api/terminal/events/news",
    "/api/terminal/events/relevance-diagnostics",
    "/api/terminal/events/source-quality-report",
    "/api/terminal/events/evidence"
  ],
  features: [
    "/api/terminal/feature-store/build",
    "/api/terminal/feature-store/v12",
    "/api/terminal/feature-store/v12-input-contract",
    "/api/terminal/training-dataset/status"
  ],
  models: [
    "/api/terminal/model-health",
    "/api/terminal/models/active-status",
    "/api/terminal/models/candidate-status",
    "/api/terminal/models/promotion-report"
  ],
  backtest: [
    "/api/terminal/backtest-diagnostics",
    "/api/terminal/backtest/auditable",
    "/api/terminal/research/run-backtest",
    "/api/terminal/research/backtest-report",
    "/api/terminal/research/equity-curve",
    "/api/terminal/research/optimize-strategy"
  ],
  settings: [
    "/api/terminal/settings/status",
    "/api/terminal/settings/secrets",
    "/api/terminal/settings/key-diagnostics",
    "/api/terminal/local-api-provider/hub"
  ],
  tasks: [
    "/api/terminal/tasks/start",
    "/api/terminal/tasks/status",
    "/api/terminal/tasks/recent",
    "/api/terminal/tasks/cancel"
  ]
} as const;

export const terminalEndpointsCoveredBySharedClient = [
  "/api/terminal/refresh/all",
  "/api/terminal/refresh/cross-market",
  "/api/terminal/refresh/market",
  "/api/terminal/refresh/news",
  "/api/terminal/refresh/predictions",
  "/api/terminal/refresh/reports"
] as const;

export const terminalEndpointsWithoutDedicatedClient = [
  "/api/terminal/charts/drawdown",
  "/api/terminal/charts/equity-curve",
  "/api/terminal/charts/volume",
  "/api/terminal/events/relevance-report",
  "/api/terminal/performance/diagnostics",
  "/api/terminal/refresh/fundamentals",
  "/api/terminal/refresh/managed-proxy",
  "/api/terminal/refresh/tushare",
  "/api/terminal/research/optimize-multi-objective",
  "/api/terminal/research/run-candidate-v5",
  "/api/terminal/research/run-cpcv-validation"
] as const;
