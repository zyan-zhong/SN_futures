import { getJson, postJson } from "./client";
import type {
  BacktestDiagnostics,
  DataSourceStatus,
  DiagnosticsExportPayload,
  EventEvidencePayload,
  FeatureCoveragePayload,
  FeatureStoreStatus,
  FactorDiagnosticsPayload,
  ForecastPathPayload,
  FullReportPayload,
  LearningStatus,
  ModelHealth,
  NewsEventsPayload,
  NewsRelevanceDiagnosticsPayload,
  PositionScenarioInput,
  PositionScenarioResult,
  PriceHistoryPayload,
  PredictionCard,
  ReportItem,
  RuntimeDiagnostics,
  RefreshStatus,
  ProviderStatusDetailPayload,
  ProviderTestPayload,
  RefreshLastErrorPayload,
  SystemHealth,
  TerminalSnapshot,
  TerminalSummary,
  TerminalSettingsStatus,
  KeyDiagnosticsPayload,
  TrainingDatasetStatus,
  CandidateTrainingStatus,
  CandidateDiagnosticsPayload,
  WalkForwardResultsPayload,
  PromotionReportPayload,
  ActiveModelStatus,
  ModelResearchExperimentDetail,
  ModelResearchExperimentList,
  ThresholdOptimizationPayload,
  InstitutionalValidationReport,
  InstitutionalStressTests,
  OOFTraceSamplePayload,
  OOFTraceSummary,
  OOFIntegrityReport,
  HighConfidenceReport,
  OnlineDataSourceRegistry,
  OnlineFeatureReadinessPayload,
  CandidateV3ResearchPayload,
  ResearchArtifactsPayload,
  ResearchBacktestPayload,
  ResearchEquityCurvePayload,
  StrategyOptimizationPayload
} from "./types";

export function getTerminalDocs() {
  return getJson<Record<string, unknown>>("/api/terminal/docs");
}

export function getTerminalSummary() {
  return getJson<TerminalSummary>("/api/terminal/summary");
}

export function getTerminalSnapshot() {
  return getJson<TerminalSnapshot>("/api/terminal/snapshot");
}

export async function getPredictions() {
  const payload = await getJson<{ predictions?: PredictionCard[] }>("/api/terminal/predictions");
  return payload.predictions ?? [];
}

export function getModelHealth() {
  return getJson<ModelHealth>("/api/terminal/model-health");
}

export function getLearningStatus() {
  return getJson<LearningStatus>("/api/terminal/learning-status");
}

export function getBacktestDiagnostics(horizon = "tomorrow") {
  return getJson<BacktestDiagnostics>(`/api/terminal/backtest-diagnostics?horizon=${encodeURIComponent(horizon)}`);
}

export function postPositionScenario(input: PositionScenarioInput) {
  return postJson<PositionScenarioResult>("/api/terminal/position-scenario", input);
}

export async function getReports() {
  const payload = await getJson<{ reports?: ReportItem[] }>("/api/terminal/reports");
  return payload.reports ?? [];
}

export async function getDataStatus() {
  const payload = await getJson<{ sources?: DataSourceStatus[] }>("/api/terminal/data-status");
  return payload.sources ?? [];
}

export function getOnlineDataSourcesStatus() {
  return getJson<OnlineDataSourceRegistry>("/api/terminal/online-data-sources/status");
}

export function getSystemHealth() {
  return getJson<SystemHealth>("/api/terminal/system-health");
}

export function getSettingsStatus() {
  return getJson<TerminalSettingsStatus>("/api/terminal/settings/status");
}

export function getKeyDiagnostics() {
  return getJson<KeyDiagnosticsPayload>("/api/terminal/settings/key-diagnostics");
}

export function getRuntimeDiagnostics() {
  return getJson<RuntimeDiagnostics>("/api/terminal/runtime-diagnostics");
}

export function getRefreshStatus() {
  return getJson<RefreshStatus>("/api/terminal/refresh/status");
}

export function getRefreshHistory() {
  return getJson<{ history?: RefreshStatus[]; count?: number }>("/api/terminal/refresh/history");
}

export function getRefreshLastError() {
  return getJson<RefreshLastErrorPayload>("/api/terminal/refresh/last-error");
}

export function getProviderStatusDetail() {
  return getJson<ProviderStatusDetailPayload>("/api/terminal/providers/status-detail");
}

export function testProvider(provider: "market" | "newsapi" | "alpha_vantage" | "shfe_public" | "akshare_news" | "miit_policy") {
  return postJson<ProviderTestPayload>("/api/terminal/providers/test", { provider });
}

export function getNewsApiStatus() {
  return getJson<ProviderTestPayload>("/api/terminal/newsapi/status");
}

export function testNewsApiConnection() {
  return postJson<ProviderTestPayload>("/api/terminal/newsapi/test", {});
}

export function exportDiagnosticsBundle() {
  return postJson<DiagnosticsExportPayload>("/api/terminal/diagnostics/export", {});
}

export function runRefreshTask(kind: "all" | "market" | "news" | "cross-market" | "predictions" | "reports", force = false) {
  return postJson<RefreshStatus>(`/api/terminal/refresh/${kind}`, { force });
}

export function refreshAll(force = false) {
  return runRefreshTask("all", force);
}

export function refreshMarket(force = false) {
  return runRefreshTask("market", force);
}

export function refreshNews(force = false) {
  return runRefreshTask("news", force);
}

export function refreshCrossMarket(force = false) {
  return runRefreshTask("cross-market", force);
}

export function refreshPredictions(force = false) {
  return runRefreshTask("predictions", force);
}

export function refreshReports(force = false) {
  return runRefreshTask("reports", force);
}

export function getPriceHistory() {
  return getJson<PriceHistoryPayload>("/api/terminal/charts/price-history");
}

export function getForecastPath() {
  return getJson<ForecastPathPayload>("/api/terminal/charts/forecast-path");
}

export function getNewsEvents() {
  return getJson<NewsEventsPayload>("/api/terminal/events/news");
}

export function getNewsRelevanceDiagnostics() {
  return getJson<NewsRelevanceDiagnosticsPayload>("/api/terminal/events/relevance-diagnostics");
}

export function getEventEvidence(horizon = "tomorrow") {
  return getJson<EventEvidencePayload>(`/api/terminal/events/evidence?horizon=${encodeURIComponent(horizon)}`);
}

export function getFullReport(type = "daily") {
  return getJson<FullReportPayload>(`/api/terminal/reports/full?type=${encodeURIComponent(type)}`);
}

export function getFactorDiagnostics() {
  return getJson<FactorDiagnosticsPayload>("/api/terminal/factors/diagnostics");
}

export function getFeatureCoverage() {
  return getJson<FeatureCoveragePayload>("/api/terminal/factors/coverage");
}

export function getOnlineFeatureReadiness() {
  return getJson<OnlineFeatureReadinessPayload>("/api/terminal/factors/online-readiness");
}

export function buildFeatureStore(input: { version?: string } = {}) {
  return postJson<FeatureStoreStatus>("/api/terminal/feature-store/build", input);
}

export function getFeatureStoreStatus(version = "v3") {
  return getJson<FeatureStoreStatus>(`/api/terminal/feature-store/status?version=${encodeURIComponent(version)}`);
}

export function buildTrainingDataset(input: { horizons?: number[]; min_feature_coverage?: number; dataset_version?: string; feature_store_version?: string; feature_set?: string } = {}) {
  return postJson<TrainingDatasetStatus>("/api/terminal/training-dataset/build", input);
}

export function getTrainingDatasetStatus(datasetVersion = "v1") {
  return getJson<TrainingDatasetStatus>(`/api/terminal/training-dataset/status?dataset_version=${encodeURIComponent(datasetVersion)}`);
}

export function trainCandidateModel(input: {
  horizons?: string[];
  candidate_version?: string;
  dataset_version?: string;
  feature_set?: string;
  label_variants?: string[];
  models?: string[];
  calibration?: string[];
  no_trade_filters?: string[];
} = {}) {
  return postJson<CandidateTrainingStatus>("/api/terminal/models/train-candidate", input);
}

export function getCandidateStatus(candidateVersion = "v1") {
  return getJson<CandidateTrainingStatus>(`/api/terminal/models/candidate-status?candidate_version=${encodeURIComponent(candidateVersion)}`);
}

export function getWalkForwardResults(horizon?: string, candidateVersion = "v1") {
  const suffix = horizon ? `?horizon=${encodeURIComponent(horizon)}` : "";
  const joiner = suffix ? "&" : "?";
  return getJson<WalkForwardResultsPayload>(`/api/terminal/models/walk-forward-results${suffix}${joiner}candidate_version=${encodeURIComponent(candidateVersion)}`);
}

export function promoteCandidateModel(input: { candidate_version?: string; dry_run?: boolean } = {}) {
  return postJson<PromotionReportPayload>("/api/terminal/models/promote-candidate", input);
}

export function getActiveModelStatus() {
  return getJson<ActiveModelStatus>("/api/terminal/models/active-status");
}

export function getPromotionReport(candidateVersion = "v1") {
  return getJson<PromotionReportPayload>(`/api/terminal/models/promotion-report?candidate_version=${encodeURIComponent(candidateVersion)}`);
}

export function getCandidateDiagnostics() {
  return getJson<CandidateDiagnosticsPayload>("/api/terminal/models/candidate-diagnostics");
}

export function runModelExperiment(input: {
  horizons?: string[];
  label_variant?: string;
  feature_set?: string;
  model_family?: string;
  regressor_family?: string;
} = {}) {
  return postJson<ModelResearchExperimentDetail>("/api/terminal/research/run-model-experiment", input);
}

export function getModelResearchExperiments() {
  return getJson<ModelResearchExperimentList>("/api/terminal/research/experiments");
}

export function getModelResearchExperimentDetail(id: string) {
  return getJson<ModelResearchExperimentDetail>(`/api/terminal/research/experiment-detail?id=${encodeURIComponent(id)}`);
}

export function getThresholdOptimization(id: string) {
  return getJson<ThresholdOptimizationPayload>(`/api/terminal/research/threshold-optimization?id=${encodeURIComponent(id)}`);
}

export function getOOFTraceSummary(horizon = "1d", candidateVersion = "v1") {
  return getJson<OOFTraceSummary>(`/api/terminal/models/oof-trace-summary?horizon=${encodeURIComponent(horizon)}&candidate_version=${encodeURIComponent(candidateVersion)}`);
}

export function getOOFTraceSample(horizon = "1d", limit = 200, candidateVersion = "v1") {
  return getJson<OOFTraceSamplePayload>(`/api/terminal/models/oof-trace-sample?horizon=${encodeURIComponent(horizon)}&limit=${encodeURIComponent(String(limit))}&candidate_version=${encodeURIComponent(candidateVersion)}`);
}

export function getOOFIntegrityReport(candidateVersion = "v1") {
  return getJson<OOFIntegrityReport>(`/api/terminal/models/oof-integrity-report?candidate_version=${encodeURIComponent(candidateVersion)}`);
}

export function getHighConfidenceReport(horizon = "1d", candidateVersion = "v1") {
  return getJson<HighConfidenceReport>(`/api/terminal/models/high-confidence-report?horizon=${encodeURIComponent(horizon)}&candidate_version=${encodeURIComponent(candidateVersion)}`);
}

export function getResearchOOFTraceSummary(id: string) {
  return getJson<OOFTraceSummary>(`/api/terminal/research/oof-trace-summary?id=${encodeURIComponent(id)}`);
}

export function runCandidateV3Research(input: { horizons?: string[] } = {}) {
  return postJson<CandidateV3ResearchPayload>("/api/terminal/research/run-candidate-v3", input);
}

export function runResearchBacktest(input: { candidate_version?: string; horizons?: string[] } = {}) {
  return postJson<ResearchBacktestPayload>("/api/terminal/research/run-backtest", input);
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

export function getResearchArtifacts(runId?: string) {
  const suffix = runId ? `?run_id=${encodeURIComponent(runId)}` : "";
  return getJson<ResearchArtifactsPayload>(`/api/terminal/research/artifacts${suffix}`);
}

export function optimizeResearchStrategy(input: { candidate_version?: string; horizons?: string[] } = {}) {
  return postJson<StrategyOptimizationPayload>("/api/terminal/research/optimize-strategy", input);
}

export function runInstitutionalValidation(input: { candidate_version?: string; dry_run?: boolean } = {}) {
  return postJson<InstitutionalValidationReport>("/api/terminal/validation/run-institutional-check", input);
}

export function getInstitutionalValidationReport(candidateVersion = "v1") {
  return getJson<InstitutionalValidationReport>(`/api/terminal/validation/report?candidate_version=${encodeURIComponent(candidateVersion)}`);
}

export function getInstitutionalStressTests(candidateVersion = "v1") {
  return getJson<InstitutionalStressTests>(`/api/terminal/validation/stress-tests?candidate_version=${encodeURIComponent(candidateVersion)}`);
}

export function saveSettingsSecrets(input: { SN_ALPHA_VANTAGE_KEY?: string; SN_NEWSAPI_KEY?: string; SN_MANAGED_DATA_PROXY_TOKEN?: string }) {
  return postJson<TerminalSettingsStatus>("/api/terminal/settings/secrets", input);
}

export function resetSettingsSecrets() {
  return postJson<TerminalSettingsStatus>("/api/terminal/settings/reset", {});
}
