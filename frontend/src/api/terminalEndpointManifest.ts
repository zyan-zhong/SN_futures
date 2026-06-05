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
