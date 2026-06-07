import { getJson, postJson } from "./client";
import type {
  AuditableBacktestPayload,
  BacktestDiagnostics,
  ResearchBacktestPayload,
  ResearchEquityCurvePayload
} from "./types/backtest";
import type { TerminalTaskStatus } from "./types/tasks";

export function getBacktestDiagnostics(horizon = "tomorrow") {
  return getJson<BacktestDiagnostics>(`/api/terminal/backtest-diagnostics?horizon=${encodeURIComponent(horizon)}`);
}

export function runResearchBacktest(input: { candidate_version?: string; version?: string; horizons?: string[] } = {}) {
  return postJson<TerminalTaskStatus>("/api/terminal/research/run-backtest", input, { timeoutMs: 30000 });
}

export function getAuditableResearchBacktest(input: { run_id?: string; input_id?: string } = {}) {
  const params = new URLSearchParams();
  if (input.run_id) params.set("run_id", input.run_id);
  if (input.input_id) params.set("input_id", input.input_id);
  const suffix = params.toString() ? `?${params.toString()}` : "";
  return getJson<AuditableBacktestPayload>(`/api/terminal/backtest/auditable${suffix}`, { timeoutMs: 10000, dedupe: false });
}

export function getResearchBacktestReport(runId?: string, candidateVersion = "v3") {
  const params = new URLSearchParams({ candidate_version: candidateVersion });
  if (runId) params.set("run_id", runId);
  return getJson<ResearchBacktestPayload>(`/api/terminal/research/backtest-report?${params.toString()}`);
}

export function getResearchEquityCurve(horizon = "1d", runId?: string, candidateVersion = "v3") {
  const params = new URLSearchParams({ horizon, candidate_version: candidateVersion });
  if (runId) params.set("run_id", runId);
  return getJson<ResearchEquityCurvePayload>(`/api/terminal/research/equity-curve?${params.toString()}`);
}

export function optimizeResearchStrategy(input: { candidate_version?: string; version?: string; horizons?: string[] } = {}) {
  return postJson<TerminalTaskStatus>("/api/terminal/research/optimize-strategy", input, { timeoutMs: 30000 });
}
