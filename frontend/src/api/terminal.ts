import { getJson, postJson } from "./client";
import type {
  BacktestDiagnostics,
  DataSourceStatus,
  DataConsistencyReport,
  DiagnosticsExportPayload,
  EventEvidencePayload,
  FeatureCoveragePayload,
  FeatureStoreStatus,
  FactorDiagnosticsPayload,
  ForecastPathPayload,
  FullReportPayload,
  FullSystemReportPayload,
  SystemRepairPlanPayload,
  LearningStatus,
  LearningSchedulerStatus,
  ManagedDataBackfillPlannerPayload,
  ManagedDataProductionCacheGatePayload,
  FeatureStoreV12InputContractPayload,
  FeatureStoreV12BuildPlanPayload,
  FeatureStoreV12ControlledBuildPayload,
  ManagedDataQualityPayload,
  LocalApiProviderHubPayload,
  ManagedProxyConfigHandoffPayload,
  ManagedProxyAuditPayload,
  ManagedPitReplayPayload,
  ManagedProxyConfigWizardPayload,
  ManagedProxyEndpointSmokePayload,
  ManagedProxyHealthPayload,
  ManagedProxyOperatorRunbookPayload,
  ManagedProxyQuarantineContractPayload,
  ManagedProxyQuarantineSnapshotPayload,
  ManagedProxyReliabilityPayload,
  ManagedProxySampleFixturePayload,
  ManagedProxySchemaMappingPayload,
  ManagedProxySetupPayload,
  ProviderCredentialsPayload,
  ProviderSmokePayload,
  MarketAnalysisPayload,
  ModelHealth,
  NewsEventsPayload,
  NewsRelevanceDiagnosticsPayload,
  NewsSourceQualityReport,
  PositionScenarioInput,
  PositionScenarioResult,
  PriceHistoryPayload,
  PredictionCard,
  ReportItem,
  RuntimeDiagnostics,
  SetupActionTelemetryPayload,
  SetupActionRunPayload,
  SetupChecklistSafeActionPayload,
  SetupChecklistStatusPayload,
  RefreshStatus,
  BackendShutdownPayload,
  ProviderStatusDetailPayload,
  ProviderTestPayload,
  ProcessStatusPayload,
  RefreshLastErrorPayload,
  SystemHealth,
  TerminalSnapshot,
  TerminalSummary,
  TerminalSettingsStatus,
  KeyDiagnosticsPayload,
  TrainingDatasetStatus,
  CandidateTrainingStatus,
  CandidateV6ReadinessPayload,
  CandidateDiagnosticsPayload,
  WalkForwardResultsPayload,
  PromotionReportPayload,
  ActiveModelStatus,
  ActiveAbsenceDiagnosticsPayload,
  ActiveReleaseApprovalPayload,
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
  CandidateV4ResearchPayload,
  CandidateV10ResearchPayload,
  CandidateV12ResearchPayload,
  CandidateV8DiagnosticsPayload,
  CPCVValidationPayload,
  YearConcentrationPayload,
  CostStressAttributionPayload,
  V10CostRemediationPayload,
  CandidateV10RemediationPreflightPayload,
  ShadowModeReadinessPayload,
  ShadowOutputContractPayload,
  ShadowReplayPayload,
  ModelRegistrySafetyPayload,
  GovernanceAccessControlPayload,
  GovernanceObservabilityPayload,
  IncidentDrillPayload,
  ManualApprovalPayload,
  EvidenceBundlePayload,
  ExternalAuditExportPayload,
  ProductionCutoverChecklistPayload,
  PromotionDryRunEvidencePayload,
  ModelCardPayload,
  GovernanceMaturityMatrixPayload,
  PostReleaseMonitoringSpecPayload,
  RollbackRehearsalPayload,
  EvidenceFreshnessPayload,
  HypothesisRegistryPayload,
  AntiPHackingLedgerPayload,
  ResearchRunLedgerPayload,
  ReadinessDagPayload,
  PredictionWorkspaceStatusPayload,
  ResearchDecisionBoardPayload,
  ResearchArtifactsPayload,
  ResearchBacktestPayload,
  ResearchEquityCurvePayload,
  StrategyOptimizationPayload,
  TaskNotificationsPayload,
  TerminalTaskList,
  TerminalTaskStatus
} from "./types";

function asRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === "object" && !Array.isArray(value) ? (value as Record<string, unknown>) : {};
}

function asArray<T>(value: unknown): T[] {
  return Array.isArray(value) ? (value as T[]) : [];
}

export function getTerminalDocs() {
  return getJson<Record<string, unknown>>("/api/terminal/docs");
}

export function getTerminalSummary() {
  return getJson<TerminalSummary>("/api/terminal/summary", { timeoutMs: 5000 });
}

export function getTerminalSnapshot() {
  return getJson<TerminalSnapshot>("/api/terminal/snapshot", { timeoutMs: 5000 });
}

export function getTerminalSnapshotLite() {
  return getJson<TerminalSnapshot>("/api/terminal/snapshot-lite", { timeoutMs: 5000 });
}

export async function getPredictions() {
  const payload = asRecord(await getJson<{ predictions?: PredictionCard[] } | null>("/api/terminal/predictions"));
  return asArray<PredictionCard>(payload.predictions);
}

export function getModelHealth() {
  return getJson<ModelHealth>("/api/terminal/model-health");
}

export function getLearningStatus() {
  return getJson<LearningStatus>("/api/terminal/learning-status");
}

export function getLearningSchedulerStatus() {
  return getJson<LearningSchedulerStatus>("/api/terminal/learning-scheduler/status");
}

export function runLearningScheduler(input: { force?: boolean; manual?: boolean; tasks?: string[] } = {}) {
  return postJson<TerminalTaskStatus>("/api/terminal/learning-scheduler/run", input, { timeoutMs: 30000 });
}

export function pauseLearningScheduler(reason = "") {
  return postJson<LearningSchedulerStatus>("/api/terminal/learning-scheduler/pause", { reason_zh: reason });
}

export function resumeLearningScheduler() {
  return postJson<LearningSchedulerStatus>("/api/terminal/learning-scheduler/resume", {});
}

export function getBacktestDiagnostics(horizon = "tomorrow") {
  return getJson<BacktestDiagnostics>(`/api/terminal/backtest-diagnostics?horizon=${encodeURIComponent(horizon)}`);
}

export function postPositionScenario(input: PositionScenarioInput) {
  return postJson<PositionScenarioResult>("/api/terminal/position-scenario", input);
}

export async function getReports() {
  const payload = asRecord(await getJson<{ reports?: ReportItem[] } | null>("/api/terminal/reports"));
  return asArray<ReportItem>(payload.reports);
}

export async function getDataStatus() {
  const payload = asRecord(await getDataStatusPayload());
  return asArray<DataSourceStatus>(payload.sources);
}

export function getDataStatusPayload() {
  return getJson<{ sources?: DataSourceStatus[]; provider_status_canonical?: Record<string, unknown> } | null>("/api/terminal/data-status");
}

export function getOnlineDataSourcesStatus() {
  return getJson<OnlineDataSourceRegistry>("/api/terminal/online-data-sources/status");
}

export function getDataConsistencyReport() {
  return getJson<DataConsistencyReport>("/api/terminal/data-consistency-report", { timeoutMs: 10000, dedupe: false });
}

export function getSystemHealth() {
  return getJson<SystemHealth>("/api/terminal/system-health");
}

export function getProcessStatus() {
  return getJson<ProcessStatusPayload>("/api/terminal/system/process-status", { timeoutMs: 5000, dedupe: false });
}

export function shutdownBackend(reason = "frontend") {
  return postJson<BackendShutdownPayload>("/api/terminal/system/shutdown", { reason }, { timeoutMs: 5000 });
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

export function testProvider(provider: "market" | "newsapi" | "alpha_vantage" | "managed_proxy" | "tushare" | "shfe_public" | "akshare_news" | "miit_policy") {
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

export function generateFullSystemTxtReport() {
  return postJson<FullSystemReportPayload>("/api/terminal/reports/full-system-txt", {}, { timeoutMs: 30000 });
}

export function getLatestFullSystemTxtReport() {
  return getJson<FullSystemReportPayload>("/api/terminal/reports/full-system-txt/latest", { timeoutMs: 10000 });
}

export function buildSystemRepairPlan() {
  return postJson<SystemRepairPlanPayload>("/api/terminal/diagnostics/build-repair-plan", {}, { timeoutMs: 30000 });
}

export function getLatestSystemRepairPlan() {
  return getJson<SystemRepairPlanPayload>("/api/terminal/diagnostics/repair-plan", { timeoutMs: 10000, dedupe: false });
}

export function runRefreshTask(kind: "all" | "market" | "news" | "cross-market" | "predictions" | "reports", force = false) {
  return postJson<TerminalTaskStatus>(`/api/terminal/refresh/${kind}`, { force }, { timeoutMs: 30000 });
}

export function startTerminalTask(kind: string, payload: Record<string, unknown> = {}) {
  return postJson<TerminalTaskStatus>("/api/terminal/tasks/start", { ...payload, kind }, { timeoutMs: 30000 });
}

export function getTerminalTaskStatus(taskId: string) {
  return getJson<TerminalTaskStatus>(`/api/terminal/tasks/status?id=${encodeURIComponent(taskId)}`, { timeoutMs: 5000, dedupe: false });
}

export function getRecentTerminalTasks(limit = 20) {
  return getJson<TerminalTaskList>(`/api/terminal/tasks/recent?limit=${encodeURIComponent(String(limit))}`, { timeoutMs: 5000, dedupe: false });
}

export function getTaskNotifications(limit = 20) {
  return getJson<TaskNotificationsPayload>(`/api/terminal/task-notifications?limit=${encodeURIComponent(String(limit))}`, { timeoutMs: 5000, dedupe: false });
}

export function cancelTerminalTask(taskId: string) {
  return postJson<TerminalTaskStatus>(`/api/terminal/tasks/cancel?id=${encodeURIComponent(taskId)}`, {}, { timeoutMs: 5000 });
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

export function getMarketAnalysis() {
  return getJson<MarketAnalysisPayload>("/api/terminal/market-analysis");
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

export function getNewsSourceQualityReport() {
  return getJson<NewsSourceQualityReport>("/api/terminal/events/source-quality-report");
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
  return postJson<TerminalTaskStatus>("/api/terminal/feature-store/build", input, { timeoutMs: 30000 });
}

export function getFeatureStoreV12() {
  return getJson<FeatureStoreStatus>("/api/terminal/feature-store/v12", { timeoutMs: 10000, dedupe: false });
}

export function getFeatureStoreV12InputContract() {
  return getJson<FeatureStoreV12InputContractPayload>("/api/terminal/feature-store/v12-input-contract", { timeoutMs: 10000, dedupe: false });
}

export function refreshFeatureStoreV12InputContract() {
  return postJson<FeatureStoreV12InputContractPayload>("/api/terminal/feature-store/refresh-v12-input-contract", {}, { timeoutMs: 30000 });
}

export function getFeatureStoreV12BuildPlan() {
  return getJson<FeatureStoreV12BuildPlanPayload>("/api/terminal/feature-store/v12-build-plan", { timeoutMs: 10000, dedupe: false });
}

export function refreshFeatureStoreV12BuildPlan() {
  return postJson<FeatureStoreV12BuildPlanPayload>("/api/terminal/feature-store/refresh-v12-build-plan", {}, { timeoutMs: 30000 });
}

export function getFeatureStoreV12ControlledBuild() {
  return getJson<FeatureStoreV12ControlledBuildPayload>("/api/terminal/feature-store/v12-controlled-build", { timeoutMs: 10000, dedupe: false });
}

export function runFeatureStoreV12ControlledBuild() {
  return postJson<FeatureStoreV12ControlledBuildPayload>("/api/terminal/feature-store/run-v12-controlled-build", {}, { timeoutMs: 30000 });
}

export function buildFeatureStoreV12() {
  return postJson<TerminalTaskStatus>("/api/terminal/feature-store/build-v12", {}, { timeoutMs: 30000 });
}

export function refreshManagedProxyV11(input: { force?: boolean } = {}) {
  return postJson<TerminalTaskStatus>("/api/terminal/refresh/managed-proxy-v11", input, { timeoutMs: 30000 });
}

export function getManagedProxyHealth() {
  return getJson<ManagedProxyHealthPayload>("/api/terminal/managed-proxy/health", { timeoutMs: 10000, dedupe: false });
}

export function getManagedProxySetup() {
  return getJson<ManagedProxySetupPayload>("/api/terminal/managed-proxy/setup", { timeoutMs: 10000, dedupe: false });
}

export const setupChecklistSafeActionIds = [
  "refresh_provider_credentials",
  "refresh_config_handoff",
  "refresh_operator_runbook",
  "refresh_managed_proxy_setup",
  "run_provider_smoke",
  "run_sample_fixture_contract",
  "refresh_schema_mapping",
  "run_pit_replay",
  "run_pit_audit",
  "refresh_data_quality",
  "refresh_decision_board"
] as const;

export function getSetupChecklistStatus() {
  return getJson<SetupChecklistStatusPayload>("/api/terminal/setup-checklist/status", { timeoutMs: 10000, dedupe: false });
}

export function runSetupChecklistSafeAction(input: { action_id: string }) {
  return postJson<SetupChecklistSafeActionPayload>("/api/terminal/setup-checklist/run-safe-action", input, { timeoutMs: 30000 });
}

export function getSetupActionHistory() {
  return getJson<{ action_history?: SetupActionRunPayload[]; history_count?: number; successful_action_count?: number; failed_action_count?: number; blocked_action_count?: number }>(
    "/api/terminal/setup-checklist/action-history",
    { timeoutMs: 10000, dedupe: false }
  );
}

export function getSetupActionTelemetry() {
  return getJson<SetupActionTelemetryPayload>("/api/terminal/setup-checklist/action-telemetry", { timeoutMs: 10000, dedupe: false });
}

export function getManagedProxyConfigWizard() {
  return getJson<ManagedProxyConfigWizardPayload>("/api/terminal/managed-proxy/config-wizard", { timeoutMs: 10000, dedupe: false });
}

export function getLocalApiProviderHub() {
  return getJson<LocalApiProviderHubPayload>("/api/terminal/local-api-provider/hub", { timeoutMs: 10000, dedupe: false });
}

export function refreshLocalApiProviderHub() {
  return postJson<LocalApiProviderHubPayload>("/api/terminal/local-api-provider/refresh-hub", {}, { timeoutMs: 10000 });
}

export function getProviderCredentials() {
  return getJson<ProviderCredentialsPayload>("/api/terminal/local-api-provider/credentials", { timeoutMs: 10000, dedupe: false });
}

export function refreshProviderCredentials() {
  return postJson<ProviderCredentialsPayload>("/api/terminal/local-api-provider/refresh-credentials", {}, { timeoutMs: 10000 });
}

export function getProviderSmoke() {
  return getJson<ProviderSmokePayload>("/api/terminal/local-api-provider/smoke", { timeoutMs: 10000, dedupe: false });
}

export function runProviderSmokeTest(input: { provider?: string; provider_id?: string } = {}) {
  return postJson<ProviderSmokePayload>("/api/terminal/local-api-provider/run-smoke", input, { timeoutMs: 30000 });
}

export function refreshManagedProxyConfigWizard() {
  return postJson<ManagedProxyConfigWizardPayload>("/api/terminal/managed-proxy/refresh-config-wizard", {}, { timeoutMs: 10000 });
}

export function getManagedProxyConfigHandoff() {
  return getJson<ManagedProxyConfigHandoffPayload>("/api/terminal/managed-proxy/config-handoff", { timeoutMs: 10000, dedupe: false });
}

export function refreshManagedProxyConfigHandoff() {
  return postJson<ManagedProxyConfigHandoffPayload>("/api/terminal/managed-proxy/refresh-config-handoff", {}, { timeoutMs: 10000 });
}

export function getManagedProxyOperatorRunbook() {
  return getJson<ManagedProxyOperatorRunbookPayload>("/api/terminal/managed-proxy/operator-runbook", { timeoutMs: 10000, dedupe: false });
}

export function refreshManagedProxyOperatorRunbook() {
  return postJson<ManagedProxyOperatorRunbookPayload>("/api/terminal/managed-proxy/refresh-operator-runbook", {}, { timeoutMs: 10000 });
}

export function getManagedProxySchemaMapping() {
  return getJson<ManagedProxySchemaMappingPayload>("/api/terminal/managed-proxy/schema-mapping", { timeoutMs: 10000, dedupe: false });
}

export function refreshManagedProxySchemaMapping() {
  return postJson<ManagedProxySchemaMappingPayload>("/api/terminal/managed-proxy/refresh-schema-mapping", {}, { timeoutMs: 10000 });
}

export function refreshManagedProxySetup() {
  return postJson<ManagedProxySetupPayload>("/api/terminal/managed-proxy/refresh-setup", {}, { timeoutMs: 10000 });
}

export function getManagedProxyEndpointContract() {
  return getJson<ManagedProxySetupPayload>("/api/terminal/managed-proxy/endpoint-contract", { timeoutMs: 10000, dedupe: false });
}

export function runManagedProxyContractDryRun() {
  return postJson<ManagedProxySetupPayload>("/api/terminal/managed-proxy/run-contract-dry-run", {}, { timeoutMs: 30000 });
}

export function checkManagedProxyHealth(input: { force?: boolean } = {}) {
  return postJson<ManagedProxyHealthPayload>("/api/terminal/managed-proxy/check", input, { timeoutMs: 30000 });
}

export function getManagedProxyReadiness() {
  return getJson<ManagedProxyHealthPayload>("/api/terminal/managed-proxy/readiness", { timeoutMs: 10000, dedupe: false });
}

export function getManagedProxyReliability() {
  return getJson<ManagedProxyReliabilityPayload>("/api/terminal/managed-proxy/reliability", { timeoutMs: 10000, dedupe: false });
}

export function runManagedProxyCanary() {
  return postJson<ManagedProxyReliabilityPayload>("/api/terminal/managed-proxy/run-canary", {}, { timeoutMs: 30000 });
}

export function getManagedDataQuality() {
  return getJson<ManagedDataQualityPayload>("/api/terminal/managed-proxy/data-quality", { timeoutMs: 10000, dedupe: false });
}

export function refreshManagedDataQuality() {
  return postJson<ManagedDataQualityPayload>("/api/terminal/managed-proxy/refresh-data-quality", {}, { timeoutMs: 30000 });
}

export function getManagedProxyAudit() {
  return getJson<ManagedProxyAuditPayload>("/api/terminal/managed-proxy/audit", { timeoutMs: 10000, dedupe: false });
}

export function runManagedProxyAudit() {
  return postJson<ManagedProxyAuditPayload>("/api/terminal/managed-proxy/run-audit", {}, { timeoutMs: 30000 });
}

export function getManagedProxyAuditReadiness() {
  return getJson<ManagedProxyAuditPayload>("/api/terminal/managed-proxy/audit-readiness", { timeoutMs: 10000, dedupe: false });
}

export function getManagedPitReplay() {
  return getJson<ManagedPitReplayPayload>("/api/terminal/managed-proxy/pit-replay", { timeoutMs: 10000, dedupe: false });
}

export function runManagedPitReplay() {
  return postJson<ManagedPitReplayPayload>("/api/terminal/managed-proxy/run-pit-replay", {}, { timeoutMs: 30000 });
}

export function getManagedProxySampleFixture() {
  return getJson<ManagedProxySampleFixturePayload>("/api/terminal/managed-proxy/sample-fixture", { timeoutMs: 10000, dedupe: false });
}

export function importManagedProxySampleFixture() {
  return postJson<ManagedProxySampleFixturePayload>("/api/terminal/managed-proxy/import-sample-fixture", {}, { timeoutMs: 30000 });
}

export function runManagedProxySampleFixtureContractTests() {
  return postJson<ManagedProxySampleFixturePayload>("/api/terminal/managed-proxy/run-sample-fixture-contract-tests", {}, { timeoutMs: 30000 });
}

export function getManagedProxyEndpointSmoke() {
  return getJson<ManagedProxyEndpointSmokePayload>("/api/terminal/managed-proxy/endpoint-smoke", { timeoutMs: 10000, dedupe: false });
}

export function runManagedProxyEndpointSmoke() {
  return postJson<ManagedProxyEndpointSmokePayload>("/api/terminal/managed-proxy/run-endpoint-smoke", {}, { timeoutMs: 30000 });
}

export function getManagedProxyQuarantineSnapshot() {
  return getJson<ManagedProxyQuarantineSnapshotPayload>("/api/terminal/managed-proxy/quarantine-snapshot", { timeoutMs: 10000, dedupe: false });
}

export function pullManagedProxyQuarantineSnapshot(input: { requested_rows?: number } = {}) {
  return postJson<ManagedProxyQuarantineSnapshotPayload>("/api/terminal/managed-proxy/pull-quarantine-snapshot", input, { timeoutMs: 30000 });
}

export function getManagedProxyQuarantineContract() {
  return getJson<ManagedProxyQuarantineContractPayload>("/api/terminal/managed-proxy/quarantine-contract", { timeoutMs: 10000, dedupe: false });
}

export function runManagedProxyQuarantineContract() {
  return postJson<ManagedProxyQuarantineContractPayload>("/api/terminal/managed-proxy/run-quarantine-contract", {}, { timeoutMs: 30000 });
}

export function promoteQuarantineToResearchCache() {
  return postJson<ManagedProxyQuarantineContractPayload>("/api/terminal/managed-proxy/promote-quarantine-to-research-cache", {}, { timeoutMs: 30000 });
}

export function getManagedDataBackfillPlan() {
  return getJson<ManagedDataBackfillPlannerPayload>("/api/terminal/managed-proxy/backfill-plan", { timeoutMs: 10000, dedupe: false });
}

export function refreshManagedDataBackfillPlan() {
  return postJson<ManagedDataBackfillPlannerPayload>("/api/terminal/managed-proxy/refresh-backfill-plan", {}, { timeoutMs: 30000 });
}

export function getManagedDataProductionCacheGate() {
  return getJson<ManagedDataProductionCacheGatePayload>("/api/terminal/managed-proxy/production-cache-gate", { timeoutMs: 10000, dedupe: false });
}

export function refreshManagedDataProductionCacheGate() {
  return postJson<ManagedDataProductionCacheGatePayload>("/api/terminal/managed-proxy/refresh-production-cache-gate", {}, { timeoutMs: 30000 });
}

export function buildManagedDataProductionCacheDryRun() {
  return postJson<ManagedDataProductionCacheGatePayload>("/api/terminal/managed-proxy/build-production-cache-dry-run", {}, { timeoutMs: 30000 });
}

export function getFeatureStoreStatus(version = "v3") {
  return getJson<FeatureStoreStatus>(`/api/terminal/feature-store/status?version=${encodeURIComponent(version)}`);
}

export function buildTrainingDataset(input: { horizons?: number[]; min_feature_coverage?: number; dataset_version?: string; feature_store_version?: string; feature_set?: string } = {}) {
  return postJson<TerminalTaskStatus>("/api/terminal/training-dataset/build", input, { timeoutMs: 30000 });
}

export function getTrainingDatasetStatus(datasetVersion = "v1") {
  return getJson<TrainingDatasetStatus>(`/api/terminal/training-dataset/status?dataset_version=${encodeURIComponent(datasetVersion)}`);
}

export function getTrainingDatasetV12() {
  return getJson<TrainingDatasetStatus>("/api/terminal/training-dataset/v12", { timeoutMs: 10000, dedupe: false });
}

export function buildTrainingDatasetV12() {
  return postJson<TerminalTaskStatus>("/api/terminal/training-dataset/build-v12", {}, { timeoutMs: 30000 });
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
  return postJson<TerminalTaskStatus>("/api/terminal/models/train-candidate", input, { timeoutMs: 30000 });
}

export function getCandidateStatus(candidateVersion = "v1") {
  return getJson<CandidateTrainingStatus>(`/api/terminal/models/candidate-status?candidate_version=${encodeURIComponent(candidateVersion)}`);
}

export function getCandidateV6Readiness() {
  return getJson<CandidateV6ReadinessPayload>("/api/terminal/models/candidate-v6/readiness", { timeoutMs: 10000, dedupe: false });
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

export function getActiveAbsenceDiagnostics() {
  return getJson<ActiveAbsenceDiagnosticsPayload>("/api/terminal/models/active-absence-diagnostics");
}

export function approveActiveModel(input: {
  candidate_version?: string;
  approval_phrase: string;
  approver?: string;
  notes?: string;
}) {
  return postJson<ActiveReleaseApprovalPayload>("/api/terminal/models/approve-active", input);
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
  return postJson<TerminalTaskStatus>("/api/terminal/research/run-model-experiment", input, { timeoutMs: 30000 });
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
  return postJson<TerminalTaskStatus>("/api/terminal/research/run-candidate-v3", input, { timeoutMs: 30000 });
}

export function runCandidateV4Research(input: { horizons?: string[] } = {}) {
  return postJson<TerminalTaskStatus>("/api/terminal/research/run-candidate-v4", input, { timeoutMs: 30000 });
}

export function runCandidateV6Research(input: { horizons?: string[] } = {}) {
  return postJson<TerminalTaskStatus>("/api/terminal/research/run-candidate-v6", input, { timeoutMs: 30000 });
}

export function runCandidateV7Research(input: { horizons?: string[] } = {}) {
  return postJson<TerminalTaskStatus>("/api/terminal/research/run-candidate-v7", input, { timeoutMs: 30000 });
}

export function runCandidateV8Research(input: { horizons?: string[] } = {}) {
  return postJson<TerminalTaskStatus>("/api/terminal/research/run-candidate-v8", input, { timeoutMs: 30000 });
}

export function runCandidateV9Research(input: { horizons?: string[] } = {}) {
  return postJson<TerminalTaskStatus>("/api/terminal/research/run-candidate-v9", input, { timeoutMs: 30000 });
}

export function runCandidateV10Research(input: { horizons?: string[] } = {}) {
  return postJson<TerminalTaskStatus>("/api/terminal/research/run-candidate-v10", input, { timeoutMs: 30000 });
}

export function getCandidateV10Report() {
  return getJson<CandidateV10ResearchPayload>("/api/terminal/research/candidate-v10-report", { timeoutMs: 10000, dedupe: false });
}

export function runCandidateV12Research(input: { horizons?: string[] } = {}) {
  return postJson<TerminalTaskStatus>("/api/terminal/research/run-candidate-v12", input, { timeoutMs: 30000 });
}

export function getCandidateV12Report() {
  return getJson<CandidateV12ResearchPayload>("/api/terminal/research/candidate-v12-report", { timeoutMs: 10000, dedupe: false });
}

export function getYearConcentration() {
  return getJson<YearConcentrationPayload>("/api/terminal/research/year-concentration", { timeoutMs: 10000, dedupe: false });
}

export function refreshYearConcentration() {
  return postJson<YearConcentrationPayload>("/api/terminal/research/refresh-year-concentration", {}, { timeoutMs: 15000 });
}

export function getCostStressAttribution() {
  return getJson<CostStressAttributionPayload>("/api/terminal/research/cost-stress-attribution", { timeoutMs: 10000, dedupe: false });
}

export function refreshCostStressAttribution() {
  return postJson<CostStressAttributionPayload>("/api/terminal/research/refresh-cost-stress-attribution", {}, { timeoutMs: 15000 });
}

export function getV10CostRemediation() {
  return getJson<V10CostRemediationPayload>("/api/terminal/research/v10-cost-remediation", { timeoutMs: 10000, dedupe: false });
}

export function refreshV10CostRemediation() {
  return postJson<V10CostRemediationPayload>("/api/terminal/research/refresh-v10-cost-remediation", {}, { timeoutMs: 15000 });
}

export function getV10RemediationPreflight() {
  return getJson<CandidateV10RemediationPreflightPayload>("/api/terminal/research/v10-remediation-preflight", { timeoutMs: 10000, dedupe: false });
}

export function refreshV10RemediationPreflight() {
  return postJson<CandidateV10RemediationPreflightPayload>("/api/terminal/research/refresh-v10-remediation-preflight", {}, { timeoutMs: 15000 });
}

export function getShadowModeReadiness() {
  return getJson<ShadowModeReadinessPayload>("/api/terminal/research/shadow-mode-readiness", { timeoutMs: 10000, dedupe: false });
}

export function refreshShadowModeReadiness() {
  return postJson<ShadowModeReadinessPayload>("/api/terminal/research/refresh-shadow-mode-readiness", {}, { timeoutMs: 15000 });
}

export function getShadowOutputContract() {
  return getJson<ShadowOutputContractPayload>("/api/terminal/governance/shadow-output-contract", { timeoutMs: 10000, dedupe: false });
}

export function refreshShadowOutputContract() {
  return postJson<ShadowOutputContractPayload>("/api/terminal/governance/refresh-shadow-output-contract", {}, { timeoutMs: 15000 });
}

export function buildShadowOutputDryRun(input: { candidate_version?: string; horizon?: string; instrument?: string } = {}) {
  return postJson<ShadowOutputContractPayload>("/api/terminal/governance/build-shadow-output-dry-run", input, { timeoutMs: 15000 });
}

export function getShadowReplay() {
  return getJson<ShadowReplayPayload>("/api/terminal/governance/shadow-replay", { timeoutMs: 10000, dedupe: false });
}

export function refreshShadowReplay(input: { candidate_version?: string } = {}) {
  return postJson<ShadowReplayPayload>("/api/terminal/governance/refresh-shadow-replay", input, { timeoutMs: 15000 });
}

export function getPostReleaseMonitoringSpec() {
  return getJson<PostReleaseMonitoringSpecPayload>("/api/terminal/governance/post-release-monitoring-spec", { timeoutMs: 10000, dedupe: false });
}

export function refreshPostReleaseMonitoringSpec() {
  return postJson<PostReleaseMonitoringSpecPayload>("/api/terminal/governance/refresh-post-release-monitoring-spec", {}, { timeoutMs: 15000 });
}

export function getRollbackRehearsal() {
  return getJson<RollbackRehearsalPayload>("/api/terminal/governance/rollback-rehearsal", { timeoutMs: 10000, dedupe: false });
}

export function refreshRollbackRehearsal() {
  return postJson<RollbackRehearsalPayload>("/api/terminal/governance/refresh-rollback-rehearsal", {}, { timeoutMs: 15000 });
}

export function simulateArtifactQuarantine() {
  return postJson<RollbackRehearsalPayload>("/api/terminal/governance/simulate-artifact-quarantine", {}, { timeoutMs: 15000 });
}

export function getModelRegistrySafety() {
  return getJson<ModelRegistrySafetyPayload>("/api/terminal/research/model-registry-safety", { timeoutMs: 10000, dedupe: false });
}

export function refreshModelRegistrySafety() {
  return postJson<ModelRegistrySafetyPayload>("/api/terminal/research/refresh-model-registry-safety", {}, { timeoutMs: 15000 });
}

export function getGovernanceAccessControl() {
  return getJson<GovernanceAccessControlPayload>("/api/terminal/governance/access-control", { timeoutMs: 10000, dedupe: false });
}

export function refreshGovernanceAccessControl() {
  return postJson<GovernanceAccessControlPayload>("/api/terminal/governance/refresh-access-control", {}, { timeoutMs: 15000 });
}

export function getGovernanceObservability() {
  return getJson<GovernanceObservabilityPayload>("/api/terminal/governance/observability", { timeoutMs: 10000, dedupe: false });
}

export function refreshGovernanceObservability() {
  return postJson<GovernanceObservabilityPayload>("/api/terminal/governance/refresh-observability", {}, { timeoutMs: 15000 });
}

export function getIncidentDrill() {
  return getJson<IncidentDrillPayload>("/api/terminal/governance/incident-drill", { timeoutMs: 10000, dedupe: false });
}

export function runIncidentDrill(input: { simulation_only?: boolean } = { simulation_only: true }) {
  return postJson<IncidentDrillPayload>("/api/terminal/governance/run-incident-drill", input, { timeoutMs: 15000 });
}

export function refreshLockdownState() {
  return postJson<IncidentDrillPayload>("/api/terminal/governance/refresh-lockdown-state", {}, { timeoutMs: 15000 });
}

export function getManualApproval() {
  return getJson<ManualApprovalPayload>("/api/terminal/governance/manual-approval", { timeoutMs: 10000, dedupe: false });
}

export function refreshManualApproval() {
  return postJson<ManualApprovalPayload>("/api/terminal/governance/refresh-manual-approval", {}, { timeoutMs: 15000 });
}

export function createManualApprovalRequest(input: { requested_action?: string; candidate_version?: string; expires_in_hours?: number } = {}) {
  return postJson<ManualApprovalPayload>("/api/terminal/governance/create-manual-approval-request", input, { timeoutMs: 15000 });
}

export function recordManualApprovalDecision(input: { decision: string; reviewers: Array<Record<string, unknown>>; notes?: string }) {
  return postJson<ManualApprovalPayload>("/api/terminal/governance/record-manual-approval-decision", input, { timeoutMs: 15000 });
}

export function getEvidenceBundle() {
  return getJson<EvidenceBundlePayload>("/api/terminal/research/evidence-bundle", { timeoutMs: 10000, dedupe: false });
}

export function refreshEvidenceBundle() {
  return postJson<EvidenceBundlePayload>("/api/terminal/research/refresh-evidence-bundle", {}, { timeoutMs: 15000 });
}

export function getExternalAuditExport() {
  return getJson<ExternalAuditExportPayload>("/api/terminal/governance/external-audit-export", { timeoutMs: 10000, dedupe: false });
}

export function refreshExternalAuditExport() {
  return postJson<ExternalAuditExportPayload>("/api/terminal/governance/refresh-external-audit-export", {}, { timeoutMs: 15000 });
}

export function getProductionCutoverChecklist() {
  return getJson<ProductionCutoverChecklistPayload>("/api/terminal/governance/production-cutover-checklist", { timeoutMs: 10000, dedupe: false });
}

export function refreshProductionCutoverChecklist() {
  return postJson<ProductionCutoverChecklistPayload>("/api/terminal/governance/refresh-production-cutover-checklist", {}, { timeoutMs: 15000 });
}

export function buildNoopReleasePlan(input: { candidate_version?: string } = {}) {
  return postJson<ProductionCutoverChecklistPayload>("/api/terminal/governance/build-noop-release-plan", input, { timeoutMs: 15000 });
}

export function getPromotionDryRunEvidence() {
  return getJson<PromotionDryRunEvidencePayload>("/api/terminal/governance/promotion-dry-run-evidence", { timeoutMs: 10000, dedupe: false });
}

export function refreshPromotionDryRunEvidence(input: { candidate_version?: string } = {}) {
  return postJson<PromotionDryRunEvidencePayload>("/api/terminal/governance/refresh-promotion-dry-run-evidence", input, { timeoutMs: 15000 });
}

export function getModelCard() {
  return getJson<ModelCardPayload>("/api/terminal/governance/model-card", { timeoutMs: 10000, dedupe: false });
}

export function refreshModelCard() {
  return postJson<ModelCardPayload>("/api/terminal/governance/refresh-model-card", {}, { timeoutMs: 15000 });
}

export function getGovernanceMaturityMatrix() {
  return getJson<GovernanceMaturityMatrixPayload>("/api/terminal/governance/maturity-matrix", { timeoutMs: 10000, dedupe: false });
}

export function refreshGovernanceMaturityMatrix() {
  return postJson<GovernanceMaturityMatrixPayload>("/api/terminal/governance/refresh-maturity-matrix", {}, { timeoutMs: 15000 });
}

export function getEvidenceFreshness() {
  return getJson<EvidenceFreshnessPayload>("/api/terminal/research/evidence-freshness", { timeoutMs: 10000, dedupe: false });
}

export function refreshEvidenceFreshness() {
  return postJson<EvidenceFreshnessPayload>("/api/terminal/research/refresh-evidence-freshness", {}, { timeoutMs: 15000 });
}

export function getHypothesisRegistry() {
  return getJson<HypothesisRegistryPayload>("/api/terminal/research/hypothesis-registry", { timeoutMs: 10000, dedupe: false });
}

export function createHypothesisTemplate(input: { remediation_id?: string; hypothesis_id?: string } = {}) {
  return postJson<Record<string, unknown>>("/api/terminal/research/create-hypothesis-template", input, { timeoutMs: 10000 });
}

export function refreshAntiPHackingLedger() {
  return postJson<AntiPHackingLedgerPayload>("/api/terminal/research/refresh-anti-p-hacking-ledger", {}, { timeoutMs: 10000 });
}

export function getRunLedger() {
  return getJson<ResearchRunLedgerPayload>("/api/terminal/research/run-ledger", { timeoutMs: 10000, dedupe: false });
}

export function refreshRunLedger() {
  return postJson<ResearchRunLedgerPayload>("/api/terminal/research/refresh-run-ledger", {}, { timeoutMs: 15000 });
}

export function getReadinessDag() {
  return getJson<ReadinessDagPayload>("/api/terminal/research/readiness-dag", { timeoutMs: 10000, dedupe: false });
}

export function refreshReadinessDag() {
  return postJson<ReadinessDagPayload>("/api/terminal/research/refresh-readiness-dag", {}, { timeoutMs: 15000 });
}

export function runSafeReadinessChecks() {
  return postJson<ReadinessDagPayload>("/api/terminal/research/run-safe-readiness-checks", {}, { timeoutMs: 30000 });
}

export function getResearchDecisionBoard() {
  return getJson<ResearchDecisionBoardPayload>("/api/terminal/research/decision-board", { timeoutMs: 10000, dedupe: false });
}

export function getPredictionWorkspaceStatus() {
  return getJson<PredictionWorkspaceStatusPayload>("/api/terminal/prediction-workspace/status", { timeoutMs: 10000, dedupe: false });
}

export function refreshResearchDecisionBoard() {
  return postJson<ResearchDecisionBoardPayload>("/api/terminal/research/refresh-decision-board", {}, { timeoutMs: 15000 });
}

export function getCandidateV8Diagnostics() {
  return getJson<CandidateV8DiagnosticsPayload>("/api/terminal/research/candidate-v8-diagnostics", { timeoutMs: 10000, dedupe: false });
}

export function getCpcvValidationReport(candidateVersion = "v9") {
  return getJson<CPCVValidationPayload>(`/api/terminal/research/cpcv-report?candidate_version=${encodeURIComponent(candidateVersion)}`, { timeoutMs: 30000, dedupe: false });
}

export function runResearchBacktest(input: { candidate_version?: string; version?: string; horizons?: string[] } = {}) {
  return postJson<TerminalTaskStatus>("/api/terminal/research/run-backtest", input, { timeoutMs: 30000 });
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

export function getResearchArtifacts(runId?: string, candidateVersion?: string) {
  const params = new URLSearchParams();
  if (runId) params.set("run_id", runId);
  if (candidateVersion) params.set("candidate_version", candidateVersion);
  const suffix = params.toString() ? `?${params.toString()}` : "";
  return getJson<ResearchArtifactsPayload>(`/api/terminal/research/artifacts${suffix}`);
}

export function optimizeResearchStrategy(input: { candidate_version?: string; version?: string; horizons?: string[] } = {}) {
  return postJson<TerminalTaskStatus>("/api/terminal/research/optimize-strategy", input, { timeoutMs: 30000 });
}

export function runInstitutionalValidation(input: { candidate_version?: string; dry_run?: boolean } = {}) {
  return postJson<TerminalTaskStatus>("/api/terminal/validation/run-institutional-check", input, { timeoutMs: 30000 });
}

export function getInstitutionalValidationReport(candidateVersion = "v1") {
  return getJson<InstitutionalValidationReport>(`/api/terminal/validation/report?candidate_version=${encodeURIComponent(candidateVersion)}`);
}

export function getInstitutionalStressTests(candidateVersion = "v1") {
  return getJson<InstitutionalStressTests>(`/api/terminal/validation/stress-tests?candidate_version=${encodeURIComponent(candidateVersion)}`);
}

export function saveSettingsSecrets(input: {
  SN_ALPHA_VANTAGE_KEY?: string;
  SN_NEWSAPI_KEY?: string;
  SN_TUSHARE_TOKEN?: string;
  SN_LOCAL_API_PROVIDER_ENABLED?: string;
  SN_LOCAL_API_PROVIDER_ID?: string;
  SN_LOCAL_API_PROVIDER_BASE_URL?: string;
  SN_LOCAL_API_PROVIDER_TOKEN?: string;
  SN_MANAGED_DATA_PROXY_TOKEN?: string;
  SN_MANAGED_DATA_PROXY_URL?: string;
}) {
  return postJson<TerminalSettingsStatus>("/api/terminal/settings/secrets", input);
}

export function resetSettingsSecrets() {
  return postJson<TerminalSettingsStatus>("/api/terminal/settings/reset", {});
}
