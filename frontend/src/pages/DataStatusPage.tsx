import { useEffect, useState } from "react";
import type { FeatureStoreStatus, FeatureStoreV12InputContractPayload, ManagedDataBackfillPlannerPayload, ManagedDataProductionCacheGatePayload, ManagedDataQualityPayload, ManagedPitReplayPayload, ManagedProxyAuditPayload, ManagedProxyConfigWizardPayload, ManagedProxyEndpointSmokePayload, ManagedProxyHealthPayload, ManagedProxyOperatorRunbookPayload, ManagedProxyQuarantineContractPayload, ManagedProxyQuarantineSnapshotPayload, ManagedProxyReliabilityPayload, ManagedProxySampleFixturePayload, ManagedProxySchemaMappingPayload, ManagedProxySetupPayload, TerminalSnapshot } from "../api/types";
import type { PageKey } from "../App";
import { buildManagedDataProductionCacheDryRun, checkManagedProxyHealth, exportDiagnosticsBundle, getDataConsistencyReport, getFeatureStoreV12, getFeatureStoreV12InputContract, getManagedDataBackfillPlan, getManagedDataProductionCacheGate, getManagedDataQuality, getManagedPitReplay, getManagedProxyAudit, getManagedProxyConfigWizard, getManagedProxyEndpointSmoke, getManagedProxyHealth, getManagedProxyOperatorRunbook, getManagedProxyQuarantineContract, getManagedProxyQuarantineSnapshot, getManagedProxyReliability, getManagedProxySampleFixture, getManagedProxySchemaMapping, getManagedProxySetup, getOnlineDataSourcesStatus, getRefreshLastError, importManagedProxySampleFixture, promoteQuarantineToResearchCache, pullManagedProxyQuarantineSnapshot, refreshFeatureStoreV12InputContract, refreshManagedDataBackfillPlan, refreshManagedDataProductionCacheGate, refreshManagedDataQuality, refreshManagedProxyConfigWizard, refreshManagedProxyOperatorRunbook, refreshManagedProxySchemaMapping, refreshManagedProxySetup, runManagedPitReplay, runManagedProxyAudit, runManagedProxyCanary, runManagedProxyContractDryRun, runManagedProxyEndpointSmoke, runManagedProxyQuarantineContract, runManagedProxySampleFixtureContractTests, testProvider } from "../api/terminal";
import { ErrorBoundary } from "../components/common/ErrorBoundary";
import { DataTable } from "../components/common/DataTable";
import { DataSourceStatusPanel } from "../components/data/DataSourceStatusPanel";
import { RefreshTaskPanel } from "../components/data/RefreshTaskPanel";
import { RuntimeDiagnosticsPanel } from "../components/data/RuntimeDiagnosticsPanel";
import { SectionCard } from "../components/layout/SectionCard";

function sanitizeVisibleSecretTerms(value: unknown): string {
  return String(value ?? "")
    .replace(/X-Api-Key/g, "安全请求头")
    .replace(/apikey=/g, "key 参数")
    .replace(/apiKey=/g, "key 参数")
    .replace(/Bearer /g, "授权头 ");
}

function summarizeValueKeys(value: unknown): string {
  if (!value || typeof value !== "object") return "none";
  if (Array.isArray(value)) {
    return value.map((item) => summarizeValueKeys(item)).filter(Boolean).slice(0, 4).join(" / ") || "empty";
  }
  const keys = Object.keys(value as Record<string, unknown>).slice(0, 6);
  return keys.length ? keys.join(", ") : "empty";
}

export function DataStatusPage({
  snapshot,
  onNavigate,
  onRefresh
}: {
  snapshot?: TerminalSnapshot | null;
  onNavigate?: (page: PageKey) => void;
  onRefresh?: () => void;
}) {
  const [providerResult, setProviderResult] = useState("尚未测试数据源。");
  const [lastError, setLastError] = useState("尚未查看最近错误。");
  const [diagnosticsPath, setDiagnosticsPath] = useState("");
  const [onlineSources, setOnlineSources] = useState<Array<Record<string, unknown>>>([]);
  const [consistencyReport, setConsistencyReport] = useState<Record<string, unknown> | null>(null);
  const [managedProxyHealth, setManagedProxyHealth] = useState<ManagedProxyHealthPayload | null>(null);
  const [managedProxyOperatorRunbook, setManagedProxyOperatorRunbook] = useState<ManagedProxyOperatorRunbookPayload | null>(null);
  const [managedProxyWizard, setManagedProxyWizard] = useState<ManagedProxyConfigWizardPayload | null>(null);
  const [managedProxySetup, setManagedProxySetup] = useState<ManagedProxySetupPayload | null>(null);
  const [managedProxySchemaMapping, setManagedProxySchemaMapping] = useState<ManagedProxySchemaMappingPayload | null>(null);
  const [managedProxySampleFixture, setManagedProxySampleFixture] = useState<ManagedProxySampleFixturePayload | null>(null);
  const [managedProxyEndpointSmoke, setManagedProxyEndpointSmoke] = useState<ManagedProxyEndpointSmokePayload | null>(null);
  const [managedProxyQuarantineSnapshot, setManagedProxyQuarantineSnapshot] = useState<ManagedProxyQuarantineSnapshotPayload | null>(null);
  const [managedProxyQuarantineContract, setManagedProxyQuarantineContract] = useState<ManagedProxyQuarantineContractPayload | null>(null);
  const [managedDataBackfillPlan, setManagedDataBackfillPlan] = useState<ManagedDataBackfillPlannerPayload | null>(null);
  const [managedDataProductionCacheGate, setManagedDataProductionCacheGate] = useState<ManagedDataProductionCacheGatePayload | null>(null);
  const [managedProxyReliability, setManagedProxyReliability] = useState<ManagedProxyReliabilityPayload | null>(null);
  const [managedDataQuality, setManagedDataQuality] = useState<ManagedDataQualityPayload | null>(null);
  const [managedProxyAudit, setManagedProxyAudit] = useState<ManagedProxyAuditPayload | null>(null);
  const [managedPitReplay, setManagedPitReplay] = useState<ManagedPitReplayPayload | null>(null);
  const [featureStoreV12, setFeatureStoreV12] = useState<FeatureStoreStatus | null>(null);
  const [featureStoreV12InputContract, setFeatureStoreV12InputContract] = useState<FeatureStoreV12InputContractPayload | null>(null);
  const [managedProxyWizardRefreshing, setManagedProxyWizardRefreshing] = useState(false);
  const [managedProxyOperatorRunbookRefreshing, setManagedProxyOperatorRunbookRefreshing] = useState(false);
  const [managedProxySetupRefreshing, setManagedProxySetupRefreshing] = useState(false);
  const [managedProxySchemaMappingRefreshing, setManagedProxySchemaMappingRefreshing] = useState(false);
  const [managedProxySampleFixtureRunning, setManagedProxySampleFixtureRunning] = useState(false);
  const [managedProxyEndpointSmokeRunning, setManagedProxyEndpointSmokeRunning] = useState(false);
  const [managedProxyQuarantineSnapshotRunning, setManagedProxyQuarantineSnapshotRunning] = useState(false);
  const [managedProxyQuarantineContractRunning, setManagedProxyQuarantineContractRunning] = useState(false);
  const [managedDataBackfillPlanRefreshing, setManagedDataBackfillPlanRefreshing] = useState(false);
  const [managedDataProductionCacheGateRefreshing, setManagedDataProductionCacheGateRefreshing] = useState(false);
  const [featureStoreV12InputContractRefreshing, setFeatureStoreV12InputContractRefreshing] = useState(false);
  const [managedProxyDryRunning, setManagedProxyDryRunning] = useState(false);
  const [managedProxyChecking, setManagedProxyChecking] = useState(false);
  const [managedProxyCanaryRunning, setManagedProxyCanaryRunning] = useState(false);
  const [managedDataQualityRefreshing, setManagedDataQualityRefreshing] = useState(false);
  const [managedProxyAuditing, setManagedProxyAuditing] = useState(false);
  const [managedPitReplaying, setManagedPitReplaying] = useState(false);

  useEffect(() => {
    void getOnlineDataSourcesStatus()
      .then((payload) => setOnlineSources((payload.sources || []) as Array<Record<string, unknown>>))
      .catch(() => setOnlineSources([]));
  }, []);

  const refreshConsistencyReport = () => {
    void getDataConsistencyReport()
      .then((payload) => setConsistencyReport(payload as Record<string, unknown>))
      .catch(() => setConsistencyReport({ status: "failed", message_zh: "数据一致性报告暂不可用。" }));
  };

  useEffect(() => {
    refreshConsistencyReport();
  }, []);

  const refreshManagedProxyWizardStatus = () => {
    void getManagedProxyConfigWizard()
      .then((payload) => setManagedProxyWizard(payload))
      .catch(() =>
        setManagedProxyWizard({
          status: "blocked",
          blocking_reasons: ["managed_proxy_config_wizard_unavailable"],
          next_allowed_action: "fix_managed_proxy_config_templates",
          training_invoked: false,
          active_updated: false,
          customer_prediction_generated: false,
        }),
      );
  };

  const refreshManagedProxyOperatorRunbookStatus = () => {
    void getManagedProxyOperatorRunbook()
      .then((payload) => setManagedProxyOperatorRunbook(payload))
      .catch(() =>
        setManagedProxyOperatorRunbook({
          status: "blocked",
          blocking_reasons: ["managed_proxy_operator_runbook_unavailable"],
          next_allowed_action: "fix_operator_runbook_templates",
          training_invoked: false,
          active_updated: false,
          customer_prediction_generated: false,
        }),
      );
  };

  const refreshManagedProxySetupStatus = () => {
    void getManagedProxySetup()
      .then((payload) => setManagedProxySetup(payload))
      .catch(() =>
        setManagedProxySetup({
          status: "blocked",
          blocking_reasons: ["managed_proxy_setup_unavailable"],
          next_allowed_action: "enable_managed_proxy",
          managed_proxy_health_allowed: false,
          pit_audit_allowed: false,
          feature_store_v12_allowed: false,
        }),
      );
  };

  const refreshManagedProxySchemaMappingStatus = () => {
    void getManagedProxySchemaMapping()
      .then((payload) => setManagedProxySchemaMapping(payload))
      .catch(() =>
        setManagedProxySchemaMapping({
          status: "blocked",
          blocking_reasons: ["managed_proxy_schema_mapping_unavailable"],
          schema_mapping_ready: false,
          training_invoked: false,
          active_updated: false,
          customer_prediction_generated: false,
        }),
      );
  };

  const refreshManagedProxySampleFixtureStatus = () => {
    void getManagedProxySampleFixture()
      .then((payload) => setManagedProxySampleFixture(payload))
      .catch(() =>
        setManagedProxySampleFixture({
          status: "blocked",
          blocking_reasons: ["managed_proxy_sample_fixture_unavailable"],
          sample_data_used: true,
          production_eligible: false,
          feature_store_v12_allowed: false,
          training_invoked: false,
          active_updated: false,
          customer_prediction_generated: false,
        }),
      );
  };

  const refreshManagedProxyEndpointSmokeStatus = () => {
    void getManagedProxyEndpointSmoke()
      .then((payload) => setManagedProxyEndpointSmoke(payload))
      .catch(() =>
        setManagedProxyEndpointSmoke({
          status: "blocked",
          auth_status: "not_run",
          endpoint_reachable: false,
          response_format_status: "not_run",
          token_echo_status: "not_run",
          schema_field_names_seen: [],
          required_fields_present: [],
          timestamp_fields_present: [],
          sample_row_count: 0,
          raw_rows_persisted: false,
          managed_data_cache_updated: false,
          feature_store_v12_allowed: false,
          blocking_reasons: ["managed_proxy_endpoint_smoke_unavailable"],
          training_invoked: false,
          active_updated: false,
          customer_prediction_generated: false,
        }),
      );
  };

  const refreshManagedProxyQuarantineSnapshotStatus = () => {
    void getManagedProxyQuarantineSnapshot()
      .then((payload) => setManagedProxyQuarantineSnapshot(payload))
      .catch(() =>
        setManagedProxyQuarantineSnapshot({
          status: "blocked",
          snapshot_pulled: false,
          snapshot_row_count: 0,
          row_budget: 5,
          quarantine_path: "",
          preview_path: "",
          redacted_preview: {},
          schema_field_names_seen: [],
          timestamp_fields_seen: [],
          required_fields_seen: [],
          missing_required_fields: [],
          missing_timestamp_fields: [],
          secret_safety_status: "not_run",
          raw_rows_persisted: false,
          managed_cache_updated: false,
          production_eligible: false,
          feature_store_v12_allowed: false,
          blocking_reasons: ["managed_proxy_quarantine_snapshot_unavailable"],
          training_invoked: false,
          active_updated: false,
          customer_prediction_generated: false,
        }),
      );
  };

  const refreshManagedProxyQuarantineContractStatus = () => {
    void getManagedProxyQuarantineContract()
      .then((payload) => setManagedProxyQuarantineContract(payload))
      .catch(() =>
        setManagedProxyQuarantineContract({
          status: "blocked",
          row_count: 0,
          schema_contract_status: "not_run",
          pit_replay_status: "not_run",
          pit_audit_status: "not_run",
          data_quality_status: "not_run",
          research_cache_promotion_allowed: false,
          research_cache_written: false,
          production_eligible: false,
          feature_store_v12_allowed: false,
          blocking_reasons: ["managed_proxy_quarantine_contract_unavailable"],
          training_invoked: false,
          active_updated: false,
          customer_prediction_generated: false,
        }),
      );
  };

  const refreshManagedDataBackfillPlanStatus = () => {
    void getManagedDataBackfillPlan()
      .then((payload) => setManagedDataBackfillPlan(payload))
      .catch(() =>
        setManagedDataBackfillPlan({
          status: "blocked",
          required_date_range: { date_start: "", date_end: "", source: "missing" },
          target_horizons: ["1d", "5d", "10d", "20d"],
          coverage_budget: {
            min_row_count: 252,
            min_date_coverage_ratio: 0.95,
            min_timestamp_coverage: 1,
            min_pit_replay_pass_rate: 1,
            min_quality_score: 0.9,
            allowed_duplicate_key_count: 0,
          },
          batch_plan: { status: "blocked", batch_count: 0, batches: [], dry_run_only: true },
          retry_policy: {},
          abort_conditions: ["token echo detected", "auth failure", "schema drift", "PIT leakage", "data quality fail"],
          human_approval_checklist: [],
          production_cache_write_allowed: false,
          feature_store_v12_allowed: false,
          rows_fetched: false,
          historical_backfill_executed: false,
          production_cache_written: false,
          blocking_reasons: ["managed_data_backfill_planner_unavailable"],
          warning_reasons: [],
          training_invoked: false,
          active_updated: false,
          customer_prediction_generated: false,
        }),
      );
  };

  const refreshManagedDataProductionCacheGateStatus = () => {
    void getManagedDataProductionCacheGate()
      .then((payload) => setManagedDataProductionCacheGate(payload))
      .catch(() =>
        setManagedDataProductionCacheGate({
          status: "blocked",
          gate_version: "managed_data_production_cache_gate_v1",
          production_cache_write_allowed: false,
          production_cache_written: false,
          feature_store_v12_allowed: false,
          precondition_checks: [],
          dry_run_plan: { status: "blocked" },
          human_approval_checklist: [],
          rollback_plan: [],
          blocking_reasons: ["managed_data_production_cache_gate_unavailable"],
          warning_reasons: ["no production cache write performed"],
          training_invoked: false,
          active_updated: false,
          customer_prediction_generated: false,
        }),
      );
  };

  const refreshManagedProxyHealth = () => {
    void getManagedProxyHealth()
      .then((payload) => setManagedProxyHealth(payload))
      .catch(() =>
        setManagedProxyHealth({
          status: "blocked",
          provider_status: "unavailable",
          blocking_reasons: ["managed_proxy_health_unavailable"],
          v12_allowed: false,
        }),
      );
  };

  const refreshManagedProxyReliability = () => {
    void getManagedProxyReliability()
      .then((payload) => setManagedProxyReliability(payload))
      .catch(() =>
        setManagedProxyReliability({
          status: "blocked",
          canary_status: "not_run",
          circuit_breaker_status: "closed",
          cache_staleness_status: "not_run",
          schema_drift_status: "not_run",
          blocking_reasons: ["managed_proxy_reliability_unavailable"],
          next_allowed_action: "run_managed_proxy_canary",
          training_invoked: false,
          active_updated: false,
          customer_prediction_generated: false,
        }),
      );
  };

  const refreshManagedDataQualityStatus = () => {
    void getManagedDataQuality()
      .then((payload) => setManagedDataQuality(payload))
      .catch(() =>
        setManagedDataQuality({
          status: "blocked",
          row_count: 0,
          quality_score: 0,
          gate_passed: false,
          blocking_reasons: ["managed_data_quality_unavailable"],
          warning_reasons: [],
          training_invoked: false,
          active_updated: false,
          customer_prediction_generated: false,
        }),
      );
  };

  const refreshManagedProxyAudit = () => {
    void getManagedProxyAudit()
      .then((payload) => setManagedProxyAudit(payload))
      .catch(() =>
        setManagedProxyAudit({
          status: "blocked",
          blocking_reasons: ["managed_proxy_audit_unavailable"],
          v12_allowed: false,
        }),
      );
  };

  const refreshManagedPitReplay = () => {
    void getManagedPitReplay()
      .then((payload) => setManagedPitReplay(payload))
      .catch(() =>
        setManagedPitReplay({
          status: "blocked",
          blocking_reasons: ["managed_pit_replay_unavailable"],
          point_in_time_join_ready: false,
          training_invoked: false,
          active_updated: false,
          customer_prediction_generated: false,
        }),
      );
  };

  const refreshFeatureStoreV12InputContractStatus = () => {
    void getFeatureStoreV12InputContract()
      .then((payload) => setFeatureStoreV12InputContract(payload))
      .catch(() =>
        setFeatureStoreV12InputContract({
          status: "blocked",
          contract_version: "feature_store_v12_input_contract_v1",
          input_contract_ready: false,
          feature_store_v12_build_allowed: false,
          missing_required_fields: [],
          missing_timestamp_fields: [],
          coverage_diff: {},
          blocking_reasons: ["feature_store_v12_input_contract_unavailable"],
          warning_reasons: ["no Feature Store v12 build performed"],
          training_invoked: false,
          active_updated: false,
          customer_prediction_generated: false,
        }),
      );
  };

  const refreshFeatureStoreV12 = () => {
    void getFeatureStoreV12()
      .then((payload) => setFeatureStoreV12(payload))
      .catch(() =>
        setFeatureStoreV12({
          status: "blocked",
          feature_store_version: "v12",
          health_status: "unavailable",
          audit_status: "unavailable",
          blocking_reasons: ["feature_store_v12_status_unavailable"],
          training_dataset_v12_allowed: false,
        }),
      );
  };

  useEffect(() => {
    refreshManagedProxyOperatorRunbookStatus();
    refreshManagedProxyWizardStatus();
    refreshManagedProxySetupStatus();
    refreshManagedProxySchemaMappingStatus();
    refreshManagedProxySampleFixtureStatus();
    refreshManagedProxyEndpointSmokeStatus();
    refreshManagedProxyQuarantineSnapshotStatus();
    refreshManagedProxyQuarantineContractStatus();
    refreshManagedDataBackfillPlanStatus();
    refreshManagedDataProductionCacheGateStatus();
    refreshFeatureStoreV12InputContractStatus();
    refreshManagedProxyHealth();
    refreshManagedProxyReliability();
    refreshManagedDataQualityStatus();
    refreshManagedProxyAudit();
    refreshManagedPitReplay();
    refreshFeatureStoreV12();
  }, []);

  async function handleProviderTest(provider: "market" | "newsapi" | "managed_proxy" | "tushare" | "shfe_public" | "akshare_news" | "miit_policy") {
    try {
      const result = await testProvider(provider);
      setProviderResult(result.message_zh || "测试完成。");
    } catch (error) {
      setProviderResult(`测试数据源失败：${error instanceof Error ? error.message : "未知错误"}`);
    }
  }

  async function handleLastError() {
    try {
      const result = await getRefreshLastError();
      const message = String(result.latest_error?.message_zh || result.message_zh || "暂无刷新错误记录。");
      const actions = Array.isArray(result.next_actions_zh) ? result.next_actions_zh.join("；") : "";
      setLastError(actions ? `${message} 下一步：${actions}` : message);
    } catch (error) {
      setLastError(`查看最近错误失败：${error instanceof Error ? error.message : "未知错误"}`);
    }
  }

  async function handleExportDiagnostics() {
    try {
      const result = await exportDiagnosticsBundle();
      const text = [
        `diagnostics_path: ${result.path || "generated"}`,
        `bundle_keys: ${summarizeValueKeys(result.bundle ?? result)}`,
        "details: use Artifact Center or outputs/diagnostics for full files"
      ].join("\n");
      if (navigator.clipboard) {
        await navigator.clipboard.writeText(text);
      }
      setDiagnosticsPath(result.path || "诊断信息已复制。");
    } catch (error) {
      setDiagnosticsPath(`复制诊断信息失败：${error instanceof Error ? error.message : "未知错误"}`);
    }
  }

  async function handleManagedProxyCheck() {
    setManagedProxyChecking(true);
    try {
      const payload = await checkManagedProxyHealth({ force: true });
      setManagedProxyHealth(payload);
      refreshFeatureStoreV12();
    } catch (error) {
      setManagedProxyHealth({
        status: "blocked",
        provider_status: "check_failed",
        blocking_reasons: [error instanceof Error ? error.message : "managed_proxy_check_failed"],
        v12_allowed: false,
      });
    } finally {
      setManagedProxyChecking(false);
    }
  }

  async function handleManagedProxyCanary() {
    setManagedProxyCanaryRunning(true);
    try {
      const payload = await runManagedProxyCanary();
      setManagedProxyReliability(payload);
    } catch (error) {
      setManagedProxyReliability({
        status: "blocked",
        canary_status: "failed",
        circuit_breaker_status: "closed",
        cache_staleness_status: "not_run",
        schema_drift_status: "not_run",
        blocking_reasons: [error instanceof Error ? error.message : "managed_proxy_canary_failed"],
        next_allowed_action: "fix_managed_proxy_reliability",
        training_invoked: false,
        active_updated: false,
        customer_prediction_generated: false,
      });
    } finally {
      setManagedProxyCanaryRunning(false);
    }
  }

  async function handleManagedDataQualityRefresh() {
    setManagedDataQualityRefreshing(true);
    try {
      const payload = await refreshManagedDataQuality();
      setManagedDataQuality(payload);
      refreshFeatureStoreV12();
    } catch (error) {
      setManagedDataQuality({
        status: "blocked",
        row_count: 0,
        quality_score: 0,
        gate_passed: false,
        blocking_reasons: [error instanceof Error ? error.message : "managed_data_quality_refresh_failed"],
        warning_reasons: [],
        training_invoked: false,
        active_updated: false,
        customer_prediction_generated: false,
      });
    } finally {
      setManagedDataQualityRefreshing(false);
    }
  }

  async function handleManagedProxySetupRefresh() {
    setManagedProxySetupRefreshing(true);
    try {
      const payload = await refreshManagedProxySetup();
      setManagedProxySetup(payload);
    } catch (error) {
      setManagedProxySetup({
        status: "blocked",
        blocking_reasons: [error instanceof Error ? error.message : "managed_proxy_setup_refresh_failed"],
        next_allowed_action: "enable_managed_proxy",
        managed_proxy_health_allowed: false,
        pit_audit_allowed: false,
        feature_store_v12_allowed: false,
      });
    } finally {
      setManagedProxySetupRefreshing(false);
    }
  }

  async function handleManagedProxyWizardRefresh() {
    setManagedProxyWizardRefreshing(true);
    try {
      const payload = await refreshManagedProxyConfigWizard();
      setManagedProxyWizard(payload);
    } catch (error) {
      setManagedProxyWizard({
        status: "blocked",
        blocking_reasons: [error instanceof Error ? error.message : "managed_proxy_config_wizard_refresh_failed"],
        next_allowed_action: "fix_managed_proxy_config_templates",
        training_invoked: false,
        active_updated: false,
        customer_prediction_generated: false,
      });
    } finally {
      setManagedProxyWizardRefreshing(false);
    }
  }

  async function handleManagedProxyOperatorRunbookRefresh() {
    setManagedProxyOperatorRunbookRefreshing(true);
    try {
      const payload = await refreshManagedProxyOperatorRunbook();
      setManagedProxyOperatorRunbook(payload);
    } catch (error) {
      setManagedProxyOperatorRunbook({
        status: "blocked",
        blocking_reasons: [error instanceof Error ? error.message : "managed_proxy_operator_runbook_refresh_failed"],
        next_allowed_action: "fix_operator_runbook_templates",
        training_invoked: false,
        active_updated: false,
        customer_prediction_generated: false,
      });
    } finally {
      setManagedProxyOperatorRunbookRefreshing(false);
    }
  }

  async function handleManagedProxySchemaMappingRefresh() {
    setManagedProxySchemaMappingRefreshing(true);
    try {
      const payload = await refreshManagedProxySchemaMapping();
      setManagedProxySchemaMapping(payload);
      refreshFeatureStoreV12();
    } catch (error) {
      setManagedProxySchemaMapping({
        status: "blocked",
        blocking_reasons: [error instanceof Error ? error.message : "managed_proxy_schema_mapping_refresh_failed"],
        schema_mapping_ready: false,
        training_invoked: false,
        active_updated: false,
        customer_prediction_generated: false,
      });
    } finally {
      setManagedProxySchemaMappingRefreshing(false);
    }
  }

  async function handleManagedProxySampleFixtureRun() {
    setManagedProxySampleFixtureRunning(true);
    try {
      const payload = await runManagedProxySampleFixtureContractTests();
      setManagedProxySampleFixture(payload);
      refreshFeatureStoreV12();
    } catch (error) {
      setManagedProxySampleFixture({
        status: "blocked",
        blocking_reasons: [error instanceof Error ? error.message : "managed_proxy_sample_fixture_run_failed"],
        sample_data_used: true,
        production_eligible: false,
        feature_store_v12_allowed: false,
        training_invoked: false,
        active_updated: false,
        customer_prediction_generated: false,
      });
    } finally {
      setManagedProxySampleFixtureRunning(false);
    }
  }

  async function handleManagedProxySampleFixtureImport() {
    setManagedProxySampleFixtureRunning(true);
    try {
      const payload = await importManagedProxySampleFixture();
      setManagedProxySampleFixture(payload);
      refreshFeatureStoreV12();
    } catch (error) {
      setManagedProxySampleFixture({
        status: "blocked",
        blocking_reasons: [error instanceof Error ? error.message : "managed_proxy_sample_fixture_import_failed"],
        sample_data_used: true,
        production_eligible: false,
        feature_store_v12_allowed: false,
        training_invoked: false,
        active_updated: false,
        customer_prediction_generated: false,
      });
    } finally {
      setManagedProxySampleFixtureRunning(false);
    }
  }

  async function handleManagedProxyEndpointSmoke() {
    setManagedProxyEndpointSmokeRunning(true);
    try {
      const payload = await runManagedProxyEndpointSmoke();
      setManagedProxyEndpointSmoke(payload);
    } catch (error) {
      setManagedProxyEndpointSmoke({
        status: "blocked",
        auth_status: "not_run",
        endpoint_reachable: false,
        response_format_status: "not_run",
        token_echo_status: "not_run",
        schema_field_names_seen: [],
        required_fields_present: [],
        timestamp_fields_present: [],
        sample_row_count: 0,
        raw_rows_persisted: false,
        managed_data_cache_updated: false,
        feature_store_v12_allowed: false,
        blocking_reasons: [error instanceof Error ? error.message : "managed_proxy_endpoint_smoke_failed"],
        training_invoked: false,
        active_updated: false,
        customer_prediction_generated: false,
      });
    } finally {
      setManagedProxyEndpointSmokeRunning(false);
    }
  }

  async function handleManagedProxyQuarantineSnapshotPull() {
    setManagedProxyQuarantineSnapshotRunning(true);
    try {
      const payload = await pullManagedProxyQuarantineSnapshot({ requested_rows: 1 });
      setManagedProxyQuarantineSnapshot(payload);
      refreshManagedProxyQuarantineContractStatus();
      refreshFeatureStoreV12();
    } catch (error) {
      setManagedProxyQuarantineSnapshot({
        status: "blocked",
        snapshot_pulled: false,
        snapshot_row_count: 0,
        row_budget: 5,
        quarantine_path: "",
        preview_path: "",
        redacted_preview: {},
        schema_field_names_seen: [],
        timestamp_fields_seen: [],
        required_fields_seen: [],
        missing_required_fields: [],
        missing_timestamp_fields: [],
        secret_safety_status: "not_run",
        raw_rows_persisted: false,
        managed_cache_updated: false,
        production_eligible: false,
        feature_store_v12_allowed: false,
        blocking_reasons: [error instanceof Error ? error.message : "managed_proxy_quarantine_snapshot_failed"],
        training_invoked: false,
        active_updated: false,
        customer_prediction_generated: false,
      });
    } finally {
      setManagedProxyQuarantineSnapshotRunning(false);
    }
  }

  async function handleManagedProxyQuarantineContractRun() {
    setManagedProxyQuarantineContractRunning(true);
    try {
      const payload = await runManagedProxyQuarantineContract();
      setManagedProxyQuarantineContract(payload);
      refreshFeatureStoreV12();
    } catch (error) {
      setManagedProxyQuarantineContract({
        status: "blocked",
        row_count: 0,
        schema_contract_status: "not_run",
        pit_replay_status: "not_run",
        pit_audit_status: "not_run",
        data_quality_status: "not_run",
        research_cache_promotion_allowed: false,
        research_cache_written: false,
        production_eligible: false,
        feature_store_v12_allowed: false,
        blocking_reasons: [error instanceof Error ? error.message : "managed_proxy_quarantine_contract_failed"],
        training_invoked: false,
        active_updated: false,
        customer_prediction_generated: false,
      });
    } finally {
      setManagedProxyQuarantineContractRunning(false);
    }
  }

  async function handlePromoteQuarantineToResearchCache() {
    setManagedProxyQuarantineContractRunning(true);
    try {
      const payload = await promoteQuarantineToResearchCache();
      setManagedProxyQuarantineContract(payload);
      refreshManagedDataBackfillPlanStatus();
      refreshManagedDataProductionCacheGateStatus();
      refreshFeatureStoreV12();
    } catch (error) {
      setManagedProxyQuarantineContract({
        status: "blocked",
        row_count: 0,
        schema_contract_status: "not_run",
        pit_replay_status: "not_run",
        pit_audit_status: "not_run",
        data_quality_status: "not_run",
        research_cache_promotion_allowed: false,
        research_cache_written: false,
        production_eligible: false,
        feature_store_v12_allowed: false,
        blocking_reasons: [error instanceof Error ? error.message : "managed_proxy_research_cache_promotion_failed"],
        training_invoked: false,
        active_updated: false,
        customer_prediction_generated: false,
      });
    } finally {
      setManagedProxyQuarantineContractRunning(false);
    }
  }

  async function handleManagedDataBackfillPlanRefresh() {
    setManagedDataBackfillPlanRefreshing(true);
    try {
      const payload = await refreshManagedDataBackfillPlan();
      setManagedDataBackfillPlan(payload);
      refreshManagedDataProductionCacheGateStatus();
      refreshFeatureStoreV12();
    } catch (error) {
      setManagedDataBackfillPlan({
        status: "blocked",
        required_date_range: { date_start: "", date_end: "", source: "missing" },
        target_horizons: ["1d", "5d", "10d", "20d"],
        coverage_budget: {
          min_row_count: 252,
          min_date_coverage_ratio: 0.95,
          min_timestamp_coverage: 1,
          min_pit_replay_pass_rate: 1,
          min_quality_score: 0.9,
          allowed_duplicate_key_count: 0,
        },
        batch_plan: { status: "blocked", batch_count: 0, batches: [], dry_run_only: true },
        retry_policy: {},
        abort_conditions: ["token echo detected", "auth failure", "schema drift", "PIT leakage", "data quality fail"],
        human_approval_checklist: [],
        production_cache_write_allowed: false,
        feature_store_v12_allowed: false,
        rows_fetched: false,
        historical_backfill_executed: false,
        production_cache_written: false,
        blocking_reasons: [error instanceof Error ? error.message : "managed_data_backfill_planner_refresh_failed"],
        warning_reasons: [],
        training_invoked: false,
        active_updated: false,
        customer_prediction_generated: false,
      });
    } finally {
      setManagedDataBackfillPlanRefreshing(false);
    }
  }

  async function handleManagedDataProductionCacheGateRefresh() {
    setManagedDataProductionCacheGateRefreshing(true);
    try {
      const payload = await refreshManagedDataProductionCacheGate();
      setManagedDataProductionCacheGate(payload);
      refreshFeatureStoreV12InputContractStatus();
      refreshFeatureStoreV12();
    } catch (error) {
      setManagedDataProductionCacheGate({
        status: "blocked",
        gate_version: "managed_data_production_cache_gate_v1",
        production_cache_write_allowed: false,
        production_cache_written: false,
        feature_store_v12_allowed: false,
        precondition_checks: [],
        dry_run_plan: { status: "blocked" },
        human_approval_checklist: [],
        rollback_plan: [],
        blocking_reasons: [error instanceof Error ? error.message : "managed_data_production_cache_gate_refresh_failed"],
        warning_reasons: ["no production cache write performed"],
        training_invoked: false,
        active_updated: false,
        customer_prediction_generated: false,
      });
    } finally {
      setManagedDataProductionCacheGateRefreshing(false);
    }
  }

  async function handleManagedDataProductionCacheDryRun() {
    setManagedDataProductionCacheGateRefreshing(true);
    try {
      const payload = await buildManagedDataProductionCacheDryRun();
      setManagedDataProductionCacheGate(payload);
      refreshFeatureStoreV12InputContractStatus();
      refreshFeatureStoreV12();
    } catch (error) {
      setManagedDataProductionCacheGate({
        status: "blocked",
        gate_version: "managed_data_production_cache_gate_v1",
        production_cache_write_allowed: false,
        production_cache_written: false,
        feature_store_v12_allowed: false,
        precondition_checks: [],
        dry_run_plan: { status: "blocked" },
        human_approval_checklist: [],
        rollback_plan: [],
        blocking_reasons: [error instanceof Error ? error.message : "managed_data_production_cache_dry_run_failed"],
        warning_reasons: ["no production cache write performed"],
        training_invoked: false,
        active_updated: false,
        customer_prediction_generated: false,
      });
    } finally {
      setManagedDataProductionCacheGateRefreshing(false);
    }
  }

  async function handleFeatureStoreV12InputContractRefresh() {
    setFeatureStoreV12InputContractRefreshing(true);
    try {
      const payload = await refreshFeatureStoreV12InputContract();
      setFeatureStoreV12InputContract(payload);
      refreshFeatureStoreV12();
    } catch (error) {
      setFeatureStoreV12InputContract({
        status: "blocked",
        contract_version: "feature_store_v12_input_contract_v1",
        input_contract_ready: false,
        feature_store_v12_build_allowed: false,
        blocking_reasons: [error instanceof Error ? error.message : "feature_store_v12_input_contract_refresh_failed"],
        warning_reasons: ["no Feature Store v12 build performed"],
        training_invoked: false,
        active_updated: false,
        customer_prediction_generated: false,
      });
    } finally {
      setFeatureStoreV12InputContractRefreshing(false);
    }
  }

  async function handleManagedProxyContractDryRun() {
    setManagedProxyDryRunning(true);
    try {
      const payload = await runManagedProxyContractDryRun();
      setManagedProxySetup(payload);
    } catch (error) {
      setManagedProxySetup({
        status: "blocked",
        blocking_reasons: [error instanceof Error ? error.message : "managed_proxy_contract_dry_run_failed"],
        next_allowed_action: "fix_managed_proxy_endpoint_contract",
        managed_proxy_health_allowed: false,
        pit_audit_allowed: false,
        feature_store_v12_allowed: false,
      });
    } finally {
      setManagedProxyDryRunning(false);
    }
  }

  async function handleManagedProxyAudit() {
    setManagedProxyAuditing(true);
    try {
      const payload = await runManagedProxyAudit();
      setManagedProxyAudit(payload);
      refreshFeatureStoreV12();
    } catch (error) {
      setManagedProxyAudit({
        status: "blocked",
        blocking_reasons: [error instanceof Error ? error.message : "managed_proxy_audit_failed"],
        v12_allowed: false,
      });
    } finally {
      setManagedProxyAuditing(false);
    }
  }

  async function handleManagedPitReplay() {
    setManagedPitReplaying(true);
    try {
      const payload = await runManagedPitReplay();
      setManagedPitReplay(payload);
      refreshManagedProxyAudit();
      refreshFeatureStoreV12();
    } catch (error) {
      setManagedPitReplay({
        status: "blocked",
        blocking_reasons: [error instanceof Error ? error.message : "managed_pit_replay_failed"],
        point_in_time_join_ready: false,
        training_invoked: false,
        active_updated: false,
        customer_prediction_generated: false,
      });
    } finally {
      setManagedPitReplaying(false);
    }
  }

  function latestDates(): Record<string, unknown> {
    const value = consistencyReport?.latest_dates;
    return value && typeof value === "object" ? (value as Record<string, unknown>) : {};
  }

  function consistencyChecks(): Record<string, unknown> {
    const value = consistencyReport?.checks;
    return value && typeof value === "object" ? (value as Record<string, unknown>) : {};
  }

  const tushare_subinterfaces = Array.isArray(snapshot?.data_status?.tushare_subinterfaces)
    ? (snapshot?.data_status?.tushare_subinterfaces as Array<Record<string, unknown>>)
    : [];
  const tushare_contracts = tushare_subinterfaces.find((row) => row.source_name === "tushare_contracts");
  const tushare_daily = tushare_subinterfaces.find((row) => row.source_name === "tushare_daily");
  const tushare_warehouse = tushare_subinterfaces.find((row) => row.source_name === "tushare_warehouse");
  const tushare_settlement = tushare_subinterfaces.find((row) => row.source_name === "tushare_settlement");
  const tushare_holding = tushare_subinterfaces.find((row) => row.source_name === "tushare_holding");
  const tushareSelectedParams = [tushare_contracts, tushare_daily, tushare_warehouse, tushare_settlement, tushare_holding]
    .map((row) => row?.selected_params)
    .filter(Boolean);
  const operatorRunbookMethods = managedProxyOperatorRunbook?.config_methods || [];
  const operatorRunbookSteps = managedProxyOperatorRunbook?.safe_setup_steps || [];
  const operatorRunbookCommands = managedProxyOperatorRunbook?.verification_commands || [];
  const operatorRunbookBlockingReasons = managedProxyOperatorRunbook?.blocking_reasons || [];
  const operatorRunbookWarnings = managedProxyOperatorRunbook?.warning_reasons || [];
  const managedWizardMethods = managedProxyWizard?.safe_config_methods || [];
  const managedWizardSteps = managedProxyWizard?.setup_steps || [];
  const managedWizardChecklist = managedProxyWizard?.dry_run_checklist || [];
  const managedWizardBlockingReasons = managedProxyWizard?.blocking_reasons || [];
  const managedSetupBlockingReasons = managedProxySetup?.blocking_reasons || [];
  const managedSetupMissingFields = managedProxySetup?.missing_fields || [];
  const managedSetupMissingTimestampFields = managedProxySetup?.missing_timestamp_fields || [];
  const schemaMappingMappedFields = managedProxySchemaMapping?.mapped_fields || [];
  const schemaMappingUnmappedRequiredFields = managedProxySchemaMapping?.unmapped_required_fields || [];
  const schemaMappingAmbiguousMappings = managedProxySchemaMapping?.ambiguous_mappings || [];
  const schemaMappingDuplicateTargets = managedProxySchemaMapping?.duplicate_targets || [];
  const schemaMappingBlockingReasons = managedProxySchemaMapping?.blocking_reasons || [];
  const sampleFixtureBlockingReasons = managedProxySampleFixture?.blocking_reasons || [];
  const sampleFixtureWarnings = managedProxySampleFixture?.warning_reasons || [];
  const endpointSmokeBlockingReasons = managedProxyEndpointSmoke?.blocking_reasons || [];
  const endpointSmokeWarnings = managedProxyEndpointSmoke?.warning_reasons || [];
  const endpointSmokeFieldsSeen = managedProxyEndpointSmoke?.schema_field_names_seen || [];
  const endpointSmokeRequiredFieldsPresent = managedProxyEndpointSmoke?.required_fields_present || [];
  const endpointSmokeTimestampFieldsPresent = managedProxyEndpointSmoke?.timestamp_fields_present || [];
  const quarantineSnapshotBlockingReasons = managedProxyQuarantineSnapshot?.blocking_reasons || [];
  const quarantineSnapshotWarnings = managedProxyQuarantineSnapshot?.warning_reasons || [];
  const quarantineSnapshotFieldsSeen = managedProxyQuarantineSnapshot?.schema_field_names_seen || [];
  const quarantineSnapshotTimestampFieldsSeen = managedProxyQuarantineSnapshot?.timestamp_fields_seen || [];
  const quarantineSnapshotMissingRequiredFields = managedProxyQuarantineSnapshot?.missing_required_fields || [];
  const quarantineSnapshotMissingTimestampFields = managedProxyQuarantineSnapshot?.missing_timestamp_fields || [];
  const quarantineContractBlockingReasons = managedProxyQuarantineContract?.blocking_reasons || [];
  const quarantineContractWarnings = managedProxyQuarantineContract?.warning_reasons || [];
  const backfillPlannerBlockingReasons = managedDataBackfillPlan?.blocking_reasons || [];
  const backfillPlannerWarnings = managedDataBackfillPlan?.warning_reasons || [];
  const backfillDateRange = managedDataBackfillPlan?.required_date_range || {};
  const backfillCoverageBudget = managedDataBackfillPlan?.coverage_budget || {};
  const backfillBatchPlan = managedDataBackfillPlan?.batch_plan || {};
  const backfillAbortConditions = managedDataBackfillPlan?.abort_conditions || [];
  const backfillHumanChecklist = managedDataBackfillPlan?.human_approval_checklist || [];
  const productionCacheGateBlockingReasons = managedDataProductionCacheGate?.blocking_reasons || [];
  const productionCacheGateWarnings = managedDataProductionCacheGate?.warning_reasons || [];
  const productionCachePreconditionChecks = managedDataProductionCacheGate?.precondition_checks || [];
  const productionCacheDryRunPlan = managedDataProductionCacheGate?.dry_run_plan || {};
  const productionCacheHumanChecklist = managedDataProductionCacheGate?.human_approval_checklist || [];
  const v12InputContractBlockingReasons = featureStoreV12InputContract?.blocking_reasons || [];
  const v12InputContractWarnings = featureStoreV12InputContract?.warning_reasons || [];
  const v12InputCoverageDiff = featureStoreV12InputContract?.coverage_diff || {};
  const managedProxyCoverage = managedProxyHealth?.required_field_coverage || {};
  const managedBlockingReasons = managedProxyHealth?.blocking_reasons || [];
  const managedMissingFields = managedProxyHealth?.missing_fields || [];
  const reliabilityBlockingReasons = managedProxyReliability?.blocking_reasons || [];
  const reliabilityWarningReasons = managedProxyReliability?.warning_reasons || [];
  const qualityBlockingReasons = managedDataQuality?.blocking_reasons || [];
  const qualityWarningReasons = managedDataQuality?.warning_reasons || [];
  const qualityNullRates = Object.entries(managedDataQuality?.null_rate_by_field || {})
    .slice(0, 8)
    .map(([field, value]) => `${field}:${value}`)
    .join(", ");
  const auditTimestampCoverage = managedProxyAudit?.field_timestamp_coverage;
  const auditLagSummary = managedProxyAudit?.field_lag_summary;
  const auditLeakage = managedProxyAudit?.leakage_checks || {};
  const auditBlockingReasons = managedProxyAudit?.blocking_reasons || [];
  const replayBlockingReasons = managedPitReplay?.blocking_reasons || [];
  const replaySelectedRows = managedPitReplay?.selected_rows || [];
  const replayRejectedFutureRows = managedPitReplay?.rejected_future_rows || [];
  const featureStoreV12BlockingReasons = featureStoreV12?.blocking_reasons || [];

  return (
    <ErrorBoundary moduleName="数据源状态">
      <div className="page-stack">
        <SectionCard title="数据源可观测性" subtitle="刷新失败时可测试数据源、查看最近错误，并导出脱敏诊断信息。">
          <div className="button-row">
            <button className="ghost-button" type="button" onClick={() => handleProviderTest("market")}>
              测试数据源：行情
            </button>
            <button className="ghost-button" type="button" onClick={() => handleProviderTest("newsapi")}>
              测试数据源：NewsAPI
            </button>
            <button className="ghost-button" type="button" onClick={() => handleProviderTest("managed_proxy")}>
              测试数据源：managed proxy
            </button>
            <button className="ghost-button" type="button" onClick={() => handleProviderTest("tushare")}>
              测试数据源：Tushare
            </button>
            <button className="ghost-button" type="button" onClick={() => handleProviderTest("shfe_public")}>
              测试数据源：SHFE 公共数据
            </button>
            <button className="ghost-button" type="button" onClick={() => handleProviderTest("akshare_news")}>
              测试数据源：AKShare 新闻
            </button>
            <button className="ghost-button" type="button" onClick={() => handleProviderTest("miit_policy")}>
              测试数据源：工信部政策
            </button>
            <button className="ghost-button" type="button" onClick={handleLastError}>
              查看最近错误
            </button>
            <button className="primary-button" type="button" onClick={handleExportDiagnostics}>
              复制诊断信息
            </button>
          </div>
          <div className="reason-list">
            <span>网络失败：检查本机网络、代理或防火墙。</span>
            <span>key 未配置：前往设置页配置，或继续使用缓存/样例模式。</span>
            <span>key 无效：检查密钥是否复制完整。</span>
            <span>被限流：稍后重试，或降低刷新频率。</span>
            <span>返回为空：扩大时间窗口或检查关键词。</span>
            <span>字段不匹配：查看刷新日志中的 provider_attempts。</span>
            <span>非交易时段：等待下一交易窗口。</span>
            <span>缓存过期：点击一键刷新数据。</span>
          </div>
          <p className="muted">测试结果：{providerResult}</p>
          <p className="muted">最近错误：{lastError}</p>
          <p className="muted">打开日志目录提示：请查看本机用户目录下的 logs 文件夹；诊断导出位置：{diagnosticsPath || "尚未导出"}</p>
        </SectionCard>

        <DataSourceStatusPanel
          sources={snapshot?.data_status?.sources}
          logsDir={snapshot?.system_health?.health?.warnings?.find((item) => item.includes("logs"))}
          onSettings={() => onNavigate?.("settings")}
          onRefresh={onRefresh}
        />
        <SectionCard
          title="Managed Proxy Operator Onboarding Runbook"
          subtitle="Local setup verification for endpoint, masked token state, templates, and next safe action."
          actions={
            <button className="secondary-button" type="button" onClick={handleManagedProxyOperatorRunbookRefresh} disabled={managedProxyOperatorRunbookRefreshing}>
              {managedProxyOperatorRunbookRefreshing ? "refreshing..." : "Refresh operator runbook"}
            </button>
          }
        >
          <div className="metric-grid compact">
            <div className="metric-card">
              <span className="metric-label">operator runbook status</span>
              <strong>{managedProxyOperatorRunbook?.status || "blocked"}</strong>
              <small>{managedProxyOperatorRunbook?.runbook_version || "managed_proxy_operator_runbook_v1"}</small>
            </div>
            <div className="metric-card">
              <span className="metric-label">config methods</span>
              <strong>{operatorRunbookMethods.length}</strong>
              <small>{operatorRunbookMethods.join(", ") || "local shell / ignored config"}</small>
            </div>
            <div className="metric-card">
              <span className="metric-label">env template status</span>
              <strong>{managedProxyOperatorRunbook?.env_template_status?.status || "missing"}</strong>
              <small>{(managedProxyOperatorRunbook?.env_template_status?.missing_keys || []).join(", ") || ".env.example"}</small>
            </div>
            <div className="metric-card">
              <span className="metric-label">local config template status</span>
              <strong>{managedProxyOperatorRunbook?.local_config_template_status?.status || "missing"}</strong>
              <small>{(managedProxyOperatorRunbook?.local_config_template_status?.missing_keys || []).join(", ") || "managed_proxy.example.json"}</small>
            </div>
            <div className="metric-card">
              <span className="metric-label">mapping template status</span>
              <strong>{managedProxyOperatorRunbook?.mapping_template_status?.status || "missing"}</strong>
              <small>{(managedProxyOperatorRunbook?.mapping_template_status?.missing_canonical_fields || []).slice(0, 3).join(", ") || "canonical aliases"}</small>
            </div>
            <div className="metric-card">
              <span className="metric-label">gitignore coverage</span>
              <strong>{managedProxyOperatorRunbook?.gitignore_secret_coverage?.status || "missing"}</strong>
              <small>{(managedProxyOperatorRunbook?.gitignore_secret_coverage?.missing_patterns || []).join(", ") || "secret paths covered"}</small>
            </div>
            <div className="metric-card">
              <span className="metric-label">endpoint configured</span>
              <strong>{managedProxyOperatorRunbook?.endpoint_configured ? "true" : "false"}</strong>
              <small>{String(managedProxyOperatorRunbook?.current_config_state?.base_url_source || "none")}</small>
            </div>
            <div className="metric-card">
              <span className="metric-label">token configured</span>
              <strong>{managedProxyOperatorRunbook?.token_configured ? "true" : "false"}</strong>
              <small>{managedProxyOperatorRunbook?.token_masked || "none"}</small>
            </div>
            <div className="metric-card">
              <span className="metric-label">next action</span>
              <strong>{managedProxyOperatorRunbook?.next_allowed_action || "configure_managed_proxy_endpoint_or_token"}</strong>
              <small>report refresh only</small>
            </div>
          </div>
          <div className="notice-card">
            <strong>safe setup steps</strong>
            <p>{sanitizeVisibleSecretTerms(operatorRunbookSteps.slice(0, 5).join(" / ") || "Use local shell or ignored config, then setup dry-run, health, schema mapping, PIT replay, audit and data quality.")}</p>
            <strong>verification commands</strong>
            <p>{sanitizeVisibleSecretTerms(operatorRunbookCommands.slice(0, 5).join(" / ") || "PowerShell placeholders only")}</p>
            <strong>blocking reasons</strong>
            <p>{sanitizeVisibleSecretTerms(operatorRunbookBlockingReasons.join(", ") || "none")}</p>
            <strong>warnings</strong>
            <p>{sanitizeVisibleSecretTerms(operatorRunbookWarnings.join(", ") || "none")}</p>
          </div>
        </SectionCard>
        <SectionCard
          title="Managed Proxy Configuration Wizard"
          subtitle="Safe local setup guide for managed proxy endpoint and masked token verification."
          actions={
            <button className="secondary-button" type="button" onClick={handleManagedProxyWizardRefresh} disabled={managedProxyWizardRefreshing}>
              {managedProxyWizardRefreshing ? "refreshing..." : "Refresh wizard"}
            </button>
          }
        >
          <div className="metric-grid compact">
            <div className="metric-card">
              <span className="metric-label">wizard status</span>
              <strong>{managedProxyWizard?.status || "blocked"}</strong>
              <small>{managedProxyWizard?.wizard_version || "managed_proxy_config_wizard_v1"}</small>
            </div>
            <div className="metric-card">
              <span className="metric-label">safe configuration methods</span>
              <strong>{managedWizardMethods.length || 0}</strong>
              <small>{managedWizardMethods.join(", ") || "environment/local config"}</small>
            </div>
            <div className="metric-card">
              <span className="metric-label">env template status</span>
              <strong>{managedProxyWizard?.env_var_template_status || "missing"}</strong>
              <small>.env.example</small>
            </div>
            <div className="metric-card">
              <span className="metric-label">local config template status</span>
              <strong>{managedProxyWizard?.local_config_template_status || "missing"}</strong>
              <small>config/managed_proxy.example.json</small>
            </div>
            <div className="metric-card">
              <span className="metric-label">gitignore secret coverage</span>
              <strong>{managedProxyWizard?.gitignore_secret_coverage?.status || "missing"}</strong>
              <small>{(managedProxyWizard?.gitignore_secret_coverage?.missing_patterns || []).join(", ") || "covered"}</small>
            </div>
            <div className="metric-card">
              <span className="metric-label">next allowed action</span>
              <strong>{managedProxyWizard?.next_allowed_action || "fix_managed_proxy_config_templates"}</strong>
              <small>no downstream task is triggered</small>
            </div>
          </div>
          <div className="notice-card">
            <strong>setup steps</strong>
            <p>{sanitizeVisibleSecretTerms(managedWizardSteps.slice(0, 4).join(" / ") || "Use local shell or ignored config only.")}</p>
            <strong>dry-run checklist</strong>
            <p>{sanitizeVisibleSecretTerms(managedWizardChecklist.join(" / ") || "setup dry-run / health / PIT audit / masked responses")}</p>
            <strong>blocking reasons</strong>
            <p>{sanitizeVisibleSecretTerms(managedWizardBlockingReasons.join(", ") || "none")}</p>
          </div>
        </SectionCard>
        <SectionCard
          title="Managed Proxy Schema Mapping"
          subtitle="Explicit provider field aliases are checked before schema dry-run and v12 gates."
          actions={
            <button className="secondary-button" type="button" onClick={handleManagedProxySchemaMappingRefresh} disabled={managedProxySchemaMappingRefreshing}>
              {managedProxySchemaMappingRefreshing ? "refreshing..." : "Refresh mapping"}
            </button>
          }
        >
          <div className="metric-grid compact">
            <div className="metric-card">
              <span className="metric-label">mapping status</span>
              <strong>{managedProxySchemaMapping?.status || "blocked"}</strong>
              <small>{managedProxySchemaMapping?.mapping_version || "managed_proxy_schema_mapping_v1"}</small>
            </div>
            <div className="metric-card">
              <span className="metric-label">mapped fields count</span>
              <strong>{schemaMappingMappedFields.length}</strong>
              <small>{schemaMappingMappedFields.slice(0, 4).join(", ") || "none"}</small>
            </div>
            <div className="metric-card">
              <span className="metric-label">unmapped required fields</span>
              <strong>{schemaMappingUnmappedRequiredFields.length}</strong>
              <small>{schemaMappingUnmappedRequiredFields.slice(0, 4).join(", ") || "none"}</small>
            </div>
            <div className="metric-card">
              <span className="metric-label">ambiguous mappings</span>
              <strong>{schemaMappingAmbiguousMappings.length}</strong>
              <small>provider field must not map to multiple canonical fields</small>
            </div>
            <div className="metric-card">
              <span className="metric-label">duplicate targets</span>
              <strong>{schemaMappingDuplicateTargets.length}</strong>
              <small>canonical field must have one provider source</small>
            </div>
            <div className="metric-card">
              <span className="metric-label">mapping ready</span>
              <strong>{managedProxySchemaMapping?.schema_mapping_ready ? "true" : "false"}</strong>
              <small>mapping is an alias contract, not data fill</small>
            </div>
          </div>
          <div className="notice-card">
            <strong>blocking reasons</strong>
            <p>{sanitizeVisibleSecretTerms(schemaMappingBlockingReasons.join(", ") || "none")}</p>
            <strong>timestamp mapping status</strong>
            <p>{sanitizeVisibleSecretTerms(managedProxySchemaMapping?.timestamp_mapping_status || "not_run")}</p>
          </div>
        </SectionCard>
        <SectionCard
          title="Sample Fixture Contract Harness"
          subtitle="Non-sensitive fixture contract tests only; sample fixture cannot unlock v12."
          actions={
            <div className="button-row">
              <button className="secondary-button" type="button" onClick={handleManagedProxySampleFixtureImport} disabled={managedProxySampleFixtureRunning}>
                {managedProxySampleFixtureRunning ? "running..." : "Import sample fixture"}
              </button>
              <button className="secondary-button" type="button" onClick={handleManagedProxySampleFixtureRun} disabled={managedProxySampleFixtureRunning}>
                {managedProxySampleFixtureRunning ? "running..." : "Run sample fixture contract tests"}
              </button>
            </div>
          }
        >
          <div className="metric-grid compact">
            <div className="metric-card">
              <span className="metric-label">fixture status</span>
              <strong>{managedProxySampleFixture?.status || "blocked"}</strong>
              <small>{managedProxySampleFixture?.fixture_version || "managed_proxy_sample_fixture_v1"}</small>
            </div>
            <div className="metric-card">
              <span className="metric-label">row count</span>
              <strong>{managedProxySampleFixture?.row_count ?? 0}</strong>
              <small>fixture rows only</small>
            </div>
            <div className="metric-card">
              <span className="metric-label">sample_data_used</span>
              <strong>{managedProxySampleFixture?.sample_data_used ? "true" : "false"}</strong>
              <small>contract harness marker</small>
            </div>
            <div className="metric-card">
              <span className="metric-label">production_eligible</span>
              <strong>{managedProxySampleFixture?.production_eligible ? "true" : "false"}</strong>
              <small>sample fixture cannot unlock v12</small>
            </div>
            <div className="metric-card">
              <span className="metric-label">schema_contract_status</span>
              <strong>{managedProxySampleFixture?.schema_contract_status || "not_run"}</strong>
              <small>canonical field check</small>
            </div>
            <div className="metric-card">
              <span className="metric-label">pit_replay_status</span>
              <strong>{managedProxySampleFixture?.pit_replay_status || "not_run"}</strong>
              <small>fixture PIT replay</small>
            </div>
            <div className="metric-card">
              <span className="metric-label">data_quality_status</span>
              <strong>{managedProxySampleFixture?.data_quality_status || "not_run"}</strong>
              <small>fixture anomaly gate</small>
            </div>
            <div className="metric-card">
              <span className="metric-label">feature_store_v12_allowed</span>
              <strong>{managedProxySampleFixture?.feature_store_v12_allowed ? "true" : "false"}</strong>
              <small>always false for fixture evidence</small>
            </div>
          </div>
          <div className="notice-card">
            <strong>blocking reasons</strong>
            <p>{sanitizeVisibleSecretTerms(sampleFixtureBlockingReasons.join(", ") || "none")}</p>
            <strong>warnings</strong>
            <p>{sanitizeVisibleSecretTerms(sampleFixtureWarnings.join(", ") || "sample fixture cannot unlock v12")}</p>
            <strong>report</strong>
            <p>{sanitizeVisibleSecretTerms(managedProxySampleFixture?.report_path || "not generated")}</p>
          </div>
        </SectionCard>
        <SectionCard
          title="Endpoint Smoke Test"
          subtitle="Minimal real endpoint check; no raw rows are persisted and v12 remains blocked."
          actions={
            <button className="secondary-button" type="button" onClick={handleManagedProxyEndpointSmoke} disabled={managedProxyEndpointSmokeRunning}>
              {managedProxyEndpointSmokeRunning ? "running..." : "Run endpoint smoke"}
            </button>
          }
        >
          <div className="metric-grid compact">
            <div className="metric-card">
              <span className="metric-label">smoke status</span>
              <strong>{managedProxyEndpointSmoke?.status || "blocked"}</strong>
              <small>{managedProxyEndpointSmoke?.smoke_version || "managed_proxy_endpoint_smoke_v1"}</small>
            </div>
            <div className="metric-card">
              <span className="metric-label">auth_status</span>
              <strong>{managedProxyEndpointSmoke?.auth_status || "not_run"}</strong>
              <small>auth check does not persist rows</small>
            </div>
            <div className="metric-card">
              <span className="metric-label">endpoint_reachable</span>
              <strong>{managedProxyEndpointSmoke?.endpoint_reachable ? "true" : "false"}</strong>
              <small>latency {managedProxyEndpointSmoke?.latency_ms ?? "n/a"} ms</small>
            </div>
            <div className="metric-card">
              <span className="metric-label">response_format_status</span>
              <strong>{managedProxyEndpointSmoke?.response_format_status || "not_run"}</strong>
              <small>{managedProxyEndpointSmoke?.sample_row_count ?? 0} redacted sample rows counted</small>
            </div>
            <div className="metric-card">
              <span className="metric-label">token_echo_status</span>
              <strong>{managedProxyEndpointSmoke?.token_echo_status || "not_run"}</strong>
              <small>token/header values are never displayed</small>
            </div>
            <div className="metric-card">
              <span className="metric-label">schema fields seen</span>
              <strong>{endpointSmokeFieldsSeen.length}</strong>
              <small>{endpointSmokeFieldsSeen.slice(0, 5).join(", ") || "none"}</small>
            </div>
            <div className="metric-card">
              <span className="metric-label">required fields present</span>
              <strong>{endpointSmokeRequiredFieldsPresent.length}</strong>
              <small>{endpointSmokeRequiredFieldsPresent.slice(0, 5).join(", ") || "none"}</small>
            </div>
            <div className="metric-card">
              <span className="metric-label">timestamp fields present</span>
              <strong>{endpointSmokeTimestampFieldsPresent.length}</strong>
              <small>{endpointSmokeTimestampFieldsPresent.join(", ") || "none"}</small>
            </div>
            <div className="metric-card">
              <span className="metric-label">raw_rows_persisted</span>
              <strong>{managedProxyEndpointSmoke?.raw_rows_persisted ? "true" : "false"}</strong>
              <small>managed_data_cache_updated: {managedProxyEndpointSmoke?.managed_data_cache_updated ? "true" : "false"}</small>
            </div>
            <div className="metric-card">
              <span className="metric-label">feature_store_v12_allowed</span>
              <strong>{managedProxyEndpointSmoke?.feature_store_v12_allowed ? "true" : "false"}</strong>
              <small>smoke pass only allows health/schema/PIT next</small>
            </div>
          </div>
          <div className="notice-card">
            <strong>blocking reasons</strong>
            <p>{sanitizeVisibleSecretTerms(endpointSmokeBlockingReasons.join(", ") || "none")}</p>
            <strong>warnings</strong>
            <p>{sanitizeVisibleSecretTerms(endpointSmokeWarnings.join(", ") || "none")}</p>
            <strong>next allowed action</strong>
            <p>{sanitizeVisibleSecretTerms(managedProxyEndpointSmoke?.next_allowed_action || "configure_managed_proxy_endpoint_or_token")}</p>
            <strong>report</strong>
            <p>{sanitizeVisibleSecretTerms(managedProxyEndpointSmoke?.report_path || "not generated")}</p>
          </div>
        </SectionCard>
        <SectionCard
          title="Quarantined Snapshot"
          subtitle="Tiny post-smoke pull into quarantine only; quarantine snapshot cannot unlock v12."
          actions={
            <button className="secondary-button" type="button" onClick={handleManagedProxyQuarantineSnapshotPull} disabled={managedProxyQuarantineSnapshotRunning}>
              {managedProxyQuarantineSnapshotRunning ? "pulling..." : "Pull quarantine snapshot"}
            </button>
          }
        >
          <div className="metric-grid compact">
            <div className="metric-card">
              <span className="metric-label">snapshot status</span>
              <strong>{managedProxyQuarantineSnapshot?.status || "blocked"}</strong>
              <small>{managedProxyQuarantineSnapshot?.snapshot_version || "managed_proxy_quarantine_snapshot_v1"}</small>
            </div>
            <div className="metric-card">
              <span className="metric-label">row budget</span>
              <strong>{managedProxyQuarantineSnapshot?.row_budget ?? 5}</strong>
              <small>fixed small snapshot budget</small>
            </div>
            <div className="metric-card">
              <span className="metric-label">snapshot_row_count</span>
              <strong>{managedProxyQuarantineSnapshot?.snapshot_row_count ?? 0}</strong>
              <small>{managedProxyQuarantineSnapshot?.snapshot_pulled ? "snapshot pulled" : "not pulled"}</small>
            </div>
            <div className="metric-card">
              <span className="metric-label">quarantine path</span>
              <strong>{managedProxyQuarantineSnapshot?.quarantine_path ? "set" : "empty"}</strong>
              <small>{managedProxyQuarantineSnapshot?.quarantine_path || "no quarantine file"}</small>
            </div>
            <div className="metric-card">
              <span className="metric-label">schema/timestamp coverage</span>
              <strong>{quarantineSnapshotFieldsSeen.length}/{quarantineSnapshotTimestampFieldsSeen.length}</strong>
              <small>{quarantineSnapshotTimestampFieldsSeen.join(", ") || "no timestamp fields"}</small>
            </div>
            <div className="metric-card">
              <span className="metric-label">redacted preview status</span>
              <strong>{String(managedProxyQuarantineSnapshot?.redacted_preview?.preview_status || "not_run")}</strong>
              <small>full raw rows are not shown in UI</small>
            </div>
            <div className="metric-card">
              <span className="metric-label">secret safety</span>
              <strong>{managedProxyQuarantineSnapshot?.secret_safety_status || "not_run"}</strong>
              <small>token/header/endpoint are never displayed</small>
            </div>
            <div className="metric-card">
              <span className="metric-label">feature_store_v12_allowed</span>
              <strong>{managedProxyQuarantineSnapshot?.feature_store_v12_allowed ? "true" : "false"}</strong>
              <small>quarantine snapshot cannot unlock v12</small>
            </div>
          </div>
          <div className="notice-card">
            <strong>missing required fields</strong>
            <p>{sanitizeVisibleSecretTerms(quarantineSnapshotMissingRequiredFields.slice(0, 12).join(", ") || "none")}</p>
            <strong>missing timestamp fields</strong>
            <p>{sanitizeVisibleSecretTerms(quarantineSnapshotMissingTimestampFields.join(", ") || "none")}</p>
            <strong>blocking reasons</strong>
            <p>{sanitizeVisibleSecretTerms(quarantineSnapshotBlockingReasons.join(", ") || "none")}</p>
            <strong>warnings</strong>
            <p>{sanitizeVisibleSecretTerms(quarantineSnapshotWarnings.join(", ") || "none")}</p>
            <strong>report</strong>
            <p>{sanitizeVisibleSecretTerms(managedProxyQuarantineSnapshot?.report_path || "not generated")}</p>
          </div>
        </SectionCard>
        <SectionCard
          title="Quarantine Contract / Research Cache Gate"
          subtitle="Runs schema, PIT replay, PIT audit and quality against quarantine only; research cache is not production data."
          actions={
            <div className="button-row">
              <button className="secondary-button" type="button" onClick={handleManagedProxyQuarantineContractRun} disabled={managedProxyQuarantineContractRunning}>
                {managedProxyQuarantineContractRunning ? "running..." : "Run quarantine contract"}
              </button>
              <button className="secondary-button" type="button" onClick={handlePromoteQuarantineToResearchCache} disabled={managedProxyQuarantineContractRunning || !managedProxyQuarantineContract?.research_cache_promotion_allowed}>
                {managedProxyQuarantineContractRunning ? "running..." : "Promote to research cache"}
              </button>
            </div>
          }
        >
          <div className="metric-grid compact">
            <div className="metric-card">
              <span className="metric-label">contract status</span>
              <strong>{managedProxyQuarantineContract?.status || "blocked"}</strong>
              <small>{managedProxyQuarantineContract?.contract_version || "managed_proxy_quarantine_contract_v1"}</small>
            </div>
            <div className="metric-card">
              <span className="metric-label">row count</span>
              <strong>{managedProxyQuarantineContract?.row_count ?? 0}</strong>
              <small>source quarantine rows only</small>
            </div>
            <div className="metric-card">
              <span className="metric-label">schema_contract_status</span>
              <strong>{managedProxyQuarantineContract?.schema_contract_status || "not_run"}</strong>
              <small>canonical field contract</small>
            </div>
            <div className="metric-card">
              <span className="metric-label">pit_replay_status</span>
              <strong>{managedProxyQuarantineContract?.pit_replay_status || "not_run"}</strong>
              <small>PIT replay contract</small>
            </div>
            <div className="metric-card">
              <span className="metric-label">pit_audit_status</span>
              <strong>{managedProxyQuarantineContract?.pit_audit_status || "not_run"}</strong>
              <small>PIT audit contract</small>
            </div>
            <div className="metric-card">
              <span className="metric-label">data_quality_status</span>
              <strong>{managedProxyQuarantineContract?.data_quality_status || "not_run"}</strong>
              <small>quality/anomaly gate</small>
            </div>
            <div className="metric-card">
              <span className="metric-label">research cache allowed</span>
              <strong>{managedProxyQuarantineContract?.research_cache_promotion_allowed ? "true" : "false"}</strong>
              <small>allowed only after all contracts pass</small>
            </div>
            <div className="metric-card">
              <span className="metric-label">research cache written</span>
              <strong>{managedProxyQuarantineContract?.research_cache_written ? "true" : "false"}</strong>
              <small>{managedProxyQuarantineContract?.research_cache_path || "not written"}</small>
            </div>
            <div className="metric-card">
              <span className="metric-label">production_eligible</span>
              <strong>{managedProxyQuarantineContract?.production_eligible ? "true" : "false"}</strong>
              <small>research cache remains non-production</small>
            </div>
            <div className="metric-card">
              <span className="metric-label">feature_store_v12_allowed</span>
              <strong>{managedProxyQuarantineContract?.feature_store_v12_allowed ? "true" : "false"}</strong>
              <small>v12 still blocked until production managed data exists</small>
            </div>
          </div>
          <div className="notice-card">
            <strong>blocking reasons</strong>
            <p>{sanitizeVisibleSecretTerms(quarantineContractBlockingReasons.join(", ") || "none")}</p>
            <strong>warnings</strong>
            <p>{sanitizeVisibleSecretTerms(quarantineContractWarnings.join(", ") || "research cache cannot unlock v12")}</p>
            <strong>source quarantine path</strong>
            <p>{sanitizeVisibleSecretTerms(managedProxyQuarantineContract?.source_quarantine_path || "missing")}</p>
            <strong>report</strong>
            <p>{sanitizeVisibleSecretTerms(managedProxyQuarantineContract?.report_path || "not generated")}</p>
          </div>
        </SectionCard>
        <SectionCard
          title="Real Managed Data Backfill Planner"
          subtitle="Defines historical backfill date range, coverage budget and abort rules; planner does not execute backfill."
          actions={
            <button className="secondary-button" type="button" onClick={handleManagedDataBackfillPlanRefresh} disabled={managedDataBackfillPlanRefreshing}>
              {managedDataBackfillPlanRefreshing ? "refreshing..." : "Refresh backfill plan"}
            </button>
          }
        >
          <div className="metric-grid compact">
            <div className="metric-card">
              <span className="metric-label">planner status</span>
              <strong>{managedDataBackfillPlan?.status || "blocked"}</strong>
              <small>{managedDataBackfillPlan?.planner_version || "managed_data_backfill_planner_v1"}</small>
            </div>
            <div className="metric-card">
              <span className="metric-label">required date range</span>
              <strong>{String(backfillDateRange.date_start || "missing")}</strong>
              <small>{String(backfillDateRange.date_end || "missing")} / {String(backfillDateRange.source || "missing")}</small>
            </div>
            <div className="metric-card">
              <span className="metric-label">coverage budget</span>
              <strong>{String(backfillCoverageBudget.min_row_count ?? 0)}</strong>
              <small>min date ratio {String(backfillCoverageBudget.min_date_coverage_ratio ?? 0)}</small>
            </div>
            <div className="metric-card">
              <span className="metric-label">timestamp coverage</span>
              <strong>{String(backfillCoverageBudget.min_timestamp_coverage ?? 0)}</strong>
              <small>PIT replay pass {String(backfillCoverageBudget.min_pit_replay_pass_rate ?? 0)}</small>
            </div>
            <div className="metric-card">
              <span className="metric-label">quality requirement</span>
              <strong>{String(backfillCoverageBudget.min_quality_score ?? 0)}</strong>
              <small>duplicates allowed {String(backfillCoverageBudget.allowed_duplicate_key_count ?? 0)}</small>
            </div>
            <div className="metric-card">
              <span className="metric-label">batch plan</span>
              <strong>{String(backfillBatchPlan.batch_count ?? 0)}</strong>
              <small>{String(backfillBatchPlan.status || "blocked")} / dry run {backfillBatchPlan.dry_run_only ? "true" : "false"}</small>
            </div>
            <div className="metric-card">
              <span className="metric-label">production_cache_write_allowed</span>
              <strong>{managedDataBackfillPlan?.production_cache_write_allowed ? "true" : "false"}</strong>
              <small>planner never writes production cache</small>
            </div>
            <div className="metric-card">
              <span className="metric-label">feature_store_v12_allowed</span>
              <strong>{managedDataBackfillPlan?.feature_store_v12_allowed ? "true" : "false"}</strong>
              <small>plan readiness cannot unlock v12</small>
            </div>
            <div className="metric-card">
              <span className="metric-label">rows_fetched</span>
              <strong>{managedDataBackfillPlan?.rows_fetched ? "true" : "false"}</strong>
              <small>no historical backfill is executed</small>
            </div>
          </div>
          <div className="notice-card">
            <strong>abort conditions</strong>
            <p>{sanitizeVisibleSecretTerms(backfillAbortConditions.join(", ") || "token echo detected, auth failure, schema drift, PIT leakage, data quality fail")}</p>
            <strong>human approval checklist</strong>
            <p>{sanitizeVisibleSecretTerms(backfillHumanChecklist.slice(0, 5).join(" / ") || "review endpoint smoke, quarantine contract, row budget and abort conditions")}</p>
            <strong>blocking reasons</strong>
            <p>{sanitizeVisibleSecretTerms(backfillPlannerBlockingReasons.join(", ") || "none")}</p>
            <strong>warnings</strong>
            <p>{sanitizeVisibleSecretTerms(backfillPlannerWarnings.join(", ") || "planner does not execute backfill")}</p>
            <strong>report</strong>
            <p>{sanitizeVisibleSecretTerms(managedDataBackfillPlan?.report_path || "not generated")}</p>
          </div>
        </SectionCard>
        <SectionCard
          title="Production Managed Cache Gate"
          subtitle="Checks promotion prerequisites and dry-run boundaries; no production cache write performed."
          actions={
            <div className="button-row">
              <button className="secondary-button" type="button" onClick={handleManagedDataProductionCacheGateRefresh} disabled={managedDataProductionCacheGateRefreshing}>
                {managedDataProductionCacheGateRefreshing ? "refreshing..." : "Refresh gate"}
              </button>
              <button className="secondary-button" type="button" onClick={handleManagedDataProductionCacheDryRun} disabled={managedDataProductionCacheGateRefreshing}>
                {managedDataProductionCacheGateRefreshing ? "running..." : "Build dry-run plan"}
              </button>
            </div>
          }
        >
          <div className="metric-grid compact">
            <div className="metric-card">
              <span className="metric-label">gate status</span>
              <strong>{managedDataProductionCacheGate?.status || "blocked"}</strong>
              <small>{managedDataProductionCacheGate?.gate_version || "managed_data_production_cache_gate_v1"}</small>
            </div>
            <div className="metric-card">
              <span className="metric-label">production_cache_write_allowed</span>
              <strong>{managedDataProductionCacheGate?.production_cache_write_allowed ? "true" : "false"}</strong>
              <small>actual cache write remains disabled</small>
            </div>
            <div className="metric-card">
              <span className="metric-label">production_cache_written</span>
              <strong>{managedDataProductionCacheGate?.production_cache_written ? "true" : "false"}</strong>
              <small>dry-run does not write production cache</small>
            </div>
            <div className="metric-card">
              <span className="metric-label">feature_store_v12_allowed</span>
              <strong>{managedDataProductionCacheGate?.feature_store_v12_allowed ? "true" : "false"}</strong>
              <small>v12 waits for explicit future production cache write</small>
            </div>
            <div className="metric-card">
              <span className="metric-label">precondition checks</span>
              <strong>{productionCachePreconditionChecks.filter((item) => item.passed).length}/{productionCachePreconditionChecks.length}</strong>
              <small>{productionCachePreconditionChecks.slice(0, 2).map((item) => item.name || item.status).join(" / ") || "not run"}</small>
            </div>
            <div className="metric-card">
              <span className="metric-label">dry-run plan</span>
              <strong>{String(productionCacheDryRunPlan.status || "blocked")}</strong>
              <small>rows {String(productionCacheDryRunPlan.expected_row_count ?? 0)}</small>
            </div>
          </div>
          <div className="notice-card">
            <strong>precondition checks</strong>
            <p>{sanitizeVisibleSecretTerms(productionCachePreconditionChecks.map((item) => `${item.name || "check"}:${item.status || (item.passed ? "pass" : "blocked")}`).join(", ") || "not run")}</p>
            <strong>dry-run plan</strong>
            <p>{sanitizeVisibleSecretTerms(String(productionCacheDryRunPlan.explicit_note || "No write performed; research cache is not production cache."))}</p>
            <strong>human approval checklist</strong>
            <p>{sanitizeVisibleSecretTerms(productionCacheHumanChecklist.slice(0, 7).join(" / ") || "verify endpoint, PIT audit, quality, secret scan, research cache and rollback plan")}</p>
            <strong>blocking reasons</strong>
            <p>{sanitizeVisibleSecretTerms(productionCacheGateBlockingReasons.join(", ") || "none")}</p>
            <strong>warnings</strong>
            <p>{sanitizeVisibleSecretTerms(productionCacheGateWarnings.join(", ") || "no production cache write performed")}</p>
            <strong>report</strong>
            <p>{sanitizeVisibleSecretTerms(managedDataProductionCacheGate?.report_path || "not generated")}</p>
          </div>
        </SectionCard>
        <SectionCard
          title="v12 Input Contract"
          subtitle="Compares production managed cache against v12 fields, timestamps, PIT, quality and coverage; does not build Feature Store v12."
          actions={
            <button className="secondary-button" type="button" onClick={handleFeatureStoreV12InputContractRefresh} disabled={featureStoreV12InputContractRefreshing}>
              {featureStoreV12InputContractRefreshing ? "refreshing..." : "Refresh input contract"}
            </button>
          }
        >
          <div className="metric-grid compact">
            <div className="metric-card">
              <span className="metric-label">input_contract_ready</span>
              <strong>{featureStoreV12InputContract?.input_contract_ready ? "true" : "false"}</strong>
              <small>{featureStoreV12InputContract?.status || "blocked"}</small>
            </div>
            <div className="metric-card">
              <span className="metric-label">missing_required_fields</span>
              <strong>{featureStoreV12InputContract?.missing_required_fields?.length || 0}</strong>
              <small>{(featureStoreV12InputContract?.missing_required_fields || []).slice(0, 4).join(", ") || "none"}</small>
            </div>
            <div className="metric-card">
              <span className="metric-label">missing_timestamp_fields</span>
              <strong>{featureStoreV12InputContract?.missing_timestamp_fields?.length || 0}</strong>
              <small>{(featureStoreV12InputContract?.missing_timestamp_fields || []).slice(0, 4).join(", ") || "none"}</small>
            </div>
            <div className="metric-card">
              <span className="metric-label">coverage diff</span>
              <strong>{String(v12InputCoverageDiff.row_count ?? 0)}</strong>
              <small>date ratio {String(v12InputCoverageDiff.date_coverage_ratio ?? 0)}</small>
            </div>
            <div className="metric-card">
              <span className="metric-label">feature_store_v12_build_allowed</span>
              <strong>{featureStoreV12InputContract?.feature_store_v12_build_allowed ? "true" : "false"}</strong>
              <small>input contract never builds v12 automatically</small>
            </div>
            <div className="metric-card">
              <span className="metric-label">report</span>
              <strong>{featureStoreV12InputContract?.contract_version || "feature_store_v12_input_contract_v1"}</strong>
              <small>{sanitizeVisibleSecretTerms(featureStoreV12InputContract?.report_path || "not generated")}</small>
            </div>
          </div>
          <div className="notice-card">
            <strong>blocking reasons</strong>
            <p>{sanitizeVisibleSecretTerms(v12InputContractBlockingReasons.join(", ") || "none")}</p>
            <strong>warnings</strong>
            <p>{sanitizeVisibleSecretTerms(v12InputContractWarnings.join(", ") || "input contract is necessary but does not trigger build")}</p>
          </div>
        </SectionCard>
        <SectionCard
          title="Managed Proxy Setup"
          subtitle="Validates secure local configuration and endpoint contract before health, PIT audit, or v12 gates."
          actions={
            <div className="button-row">
              <button className="secondary-button" type="button" onClick={handleManagedProxySetupRefresh} disabled={managedProxySetupRefreshing}>
                {managedProxySetupRefreshing ? "refreshing..." : "Refresh setup"}
              </button>
              <button className="secondary-button" type="button" onClick={handleManagedProxyContractDryRun} disabled={managedProxyDryRunning}>
                {managedProxyDryRunning ? "validating..." : "Run contract dry-run"}
              </button>
            </div>
          }
        >
          <div className="metric-grid compact">
            <div className="metric-card">
              <span className="metric-label">setup status</span>
              <strong>{managedProxySetup?.status || "blocked"}</strong>
              <small>{managedProxySetup?.setup_version || "managed_proxy_setup_v1"}</small>
            </div>
            <div className="metric-card">
              <span className="metric-label">enabled / configured</span>
              <strong>{managedProxySetup?.enabled ? "enabled" : "disabled"}</strong>
              <small>{managedProxySetup?.configured ? "configured" : "not configured"}</small>
            </div>
            <div className="metric-card">
              <span className="metric-label">endpoint configured</span>
              <strong>{managedProxySetup?.base_url_configured ? "yes" : "no"}</strong>
              <small>{managedProxySetup?.base_url_source || "none"}</small>
            </div>
            <div className="metric-card">
              <span className="metric-label">token configured</span>
              <strong>{managedProxySetup?.token_configured ? "yes" : "no"}</strong>
              <small>{managedProxySetup?.token_masked || "not configured"}</small>
            </div>
            <div className="metric-card">
              <span className="metric-label">endpoint contract status</span>
              <strong>{managedProxySetup?.endpoint_contract_status || "not_run"}</strong>
              <small>timeout {managedProxySetup?.timeout_seconds ?? 20}s</small>
            </div>
            <div className="metric-card">
              <span className="metric-label">schema contract status</span>
              <strong>{managedProxySetup?.schema_contract_status || "not_run"}</strong>
              <small>{managedProxySetup?.dry_run_row_count ?? 0} dry-run rows</small>
            </div>
            <div className="metric-card">
              <span className="metric-label">PIT timestamp contract status</span>
              <strong>{managedProxySetup?.pit_timestamp_contract_status || "not_run"}</strong>
              <small>{managedProxySetup?.pit_audit_allowed ? "PIT audit allowed" : "PIT audit blocked"}</small>
            </div>
            <div className="metric-card">
              <span className="metric-label">v12 build gate</span>
              <strong>{managedProxySetup?.feature_store_v12_allowed ? "allowed" : "blocked"}</strong>
              <small>setup never builds v12 automatically</small>
            </div>
          </div>
          <div className="notice-card">
            <strong>missing fields</strong>
            <p>{sanitizeVisibleSecretTerms(managedSetupMissingFields.slice(0, 12).join(", ") || "none")}</p>
            <strong>missing timestamp fields</strong>
            <p>{sanitizeVisibleSecretTerms(managedSetupMissingTimestampFields.join(", ") || "none")}</p>
            <strong>blocking reasons</strong>
            <p>{sanitizeVisibleSecretTerms(managedSetupBlockingReasons.join(", ") || "none")}</p>
            <strong>next allowed action</strong>
            <p>{sanitizeVisibleSecretTerms(managedProxySetup?.next_allowed_action || "enable_managed_proxy")}</p>
          </div>
        </SectionCard>
        <SectionCard
          title="Managed Data / Proxy Health"
          subtitle="Checks real managed endpoint/token and required fundamentals before allowing Feature Store v12."
          actions={
            <button className="secondary-button" type="button" onClick={handleManagedProxyCheck} disabled={managedProxyChecking}>
              {managedProxyChecking ? "checking..." : "Check proxy health"}
            </button>
          }
        >
          <div className="metric-grid compact">
            <div className="metric-card">
              <span className="metric-label">enabled / configured</span>
              <strong>{managedProxyHealth?.enabled ? "enabled" : "disabled"}</strong>
              <small>{managedProxyHealth?.configured ? "configured" : "not configured"}</small>
            </div>
            <div className="metric-card">
              <span className="metric-label">endpoint configured</span>
              <strong>{managedProxyHealth?.endpoint_configured ? "yes" : "no"}</strong>
              <small>endpoint value is not displayed</small>
            </div>
            <div className="metric-card">
              <span className="metric-label">token masked</span>
              <strong>{managedProxyHealth?.token_masked || "not configured"}</strong>
              <small>{managedProxyHealth?.token_source || "none"}</small>
            </div>
            <div className="metric-card">
              <span className="metric-label">last refresh time</span>
              <strong>{managedProxyHealth?.last_refresh_time || managedProxyHealth?.last_success_time || "missing"}</strong>
              <small>{managedProxyHealth?.from_cache ? "using cache" : managedProxyHealth?.provider_status || "not checked"}</small>
            </div>
            <div className="metric-card">
              <span className="metric-label">required field coverage</span>
              <strong>{managedProxyCoverage.label || "0/0"}</strong>
              <small>{managedProxyCoverage.ratio ?? 0}</small>
            </div>
            <div className="metric-card">
              <span className="metric-label">v12 readiness</span>
              <strong>{managedProxyHealth?.v12_allowed ? "allowed" : "blocked"}</strong>
              <small>{managedProxyHealth?.no_fake_data ? "no fake data" : "pending"}</small>
            </div>
          </div>
          <div className="notice-card">
            <strong>blocking reasons</strong>
            <p>{sanitizeVisibleSecretTerms(managedBlockingReasons.join(", ") || "none")}</p>
            <strong>missing fields</strong>
            <p>{sanitizeVisibleSecretTerms(managedMissingFields.slice(0, 12).join(", ") || "none")}</p>
            <strong>next allowed action</strong>
            <p>{sanitizeVisibleSecretTerms(managedProxyHealth?.next_allowed_action || "configure_managed_proxy_endpoint_and_token")}</p>
          </div>
          <div className="notice-card">
            <div className="button-row">
              <strong>Reliability Guardrail</strong>
              <button className="secondary-button" type="button" onClick={handleManagedProxyCanary} disabled={managedProxyCanaryRunning}>
                {managedProxyCanaryRunning ? "running..." : "Run canary"}
              </button>
            </div>
            <div className="metric-grid compact">
              <div className="metric-card">
                <span className="metric-label">canary status</span>
                <strong>{managedProxyReliability?.canary_status || "not_run"}</strong>
                <small>{managedProxyReliability?.status || "blocked"}</small>
              </div>
              <div className="metric-card">
                <span className="metric-label">latency</span>
                <strong>{managedProxyReliability?.latency_ms ?? "missing"}</strong>
                <small>median {managedProxyReliability?.latency_summary?.median_ms ?? "n/a"} ms</small>
              </div>
              <div className="metric-card">
                <span className="metric-label">error rate</span>
                <strong>{managedProxyReliability?.error_rate ?? 0}</strong>
                <small>timeouts {managedProxyReliability?.timeout_count ?? 0}</small>
              </div>
              <div className="metric-card">
                <span className="metric-label">circuit breaker</span>
                <strong>{managedProxyReliability?.circuit_breaker_status || "closed"}</strong>
                <small>failures {managedProxyReliability?.consecutive_failure_count ?? 0}</small>
              </div>
              <div className="metric-card">
                <span className="metric-label">cache staleness</span>
                <strong>{managedProxyReliability?.cache_staleness_status || "not_run"}</strong>
                <small>age {managedProxyReliability?.cache_age_hours ?? "n/a"} h</small>
              </div>
              <div className="metric-card">
                <span className="metric-label">schema drift</span>
                <strong>{managedProxyReliability?.schema_drift_status || "not_run"}</strong>
                <small>{(managedProxyReliability?.schema_missing_fields || []).slice(0, 3).join(", ") || "no missing fields"}</small>
              </div>
            </div>
            <strong>blocking reasons</strong>
            <p>{sanitizeVisibleSecretTerms(reliabilityBlockingReasons.join(", ") || "none")}</p>
            <strong>warning reasons</strong>
            <p>{sanitizeVisibleSecretTerms(reliabilityWarningReasons.join(", ") || "none")}</p>
            <strong>next allowed action</strong>
            <p>{sanitizeVisibleSecretTerms(managedProxyReliability?.next_allowed_action || "run_managed_proxy_canary")}</p>
          </div>
          <div className="notice-card">
            <div className="button-row">
              <strong>Data Quality Scorecard</strong>
              <button className="secondary-button" type="button" onClick={handleManagedDataQualityRefresh} disabled={managedDataQualityRefreshing}>
                {managedDataQualityRefreshing ? "refreshing..." : "Refresh data quality"}
              </button>
            </div>
            <div className="metric-grid compact">
              <div className="metric-card">
                <span className="metric-label">quality score</span>
                <strong>{managedDataQuality?.quality_score ?? 0}</strong>
                <small>{managedDataQuality?.status || "blocked"}</small>
              </div>
              <div className="metric-card">
                <span className="metric-label">gate result</span>
                <strong>{managedDataQuality?.gate_passed ? "pass" : "blocked"}</strong>
                <small>{managedDataQuality?.quality_version || "managed_data_quality_v1"}</small>
              </div>
              <div className="metric-card">
                <span className="metric-label">row count</span>
                <strong>{managedDataQuality?.row_count ?? 0}</strong>
                <small>{managedDataQuality?.date_range?.date_start || "missing"} - {managedDataQuality?.date_range?.date_end || "missing"}</small>
              </div>
              <div className="metric-card">
                <span className="metric-label">duplicate count</span>
                <strong>{managedDataQuality?.duplicate_key_count ?? 0}</strong>
                <small>timestamp key duplicates fail the gate</small>
              </div>
              <div className="metric-card">
                <span className="metric-label">invalid values</span>
                <strong>{managedDataQuality?.invalid_value_count ?? 0}</strong>
                <small>negative inventory / impossible open interest</small>
              </div>
              <div className="metric-card">
                <span className="metric-label">outliers</span>
                <strong>{managedDataQuality?.outlier_summary?.outlier_count ?? 0}</strong>
                <small>{managedDataQuality?.outlier_summary?.status || "not_run"}</small>
              </div>
              <div className="metric-card">
                <span className="metric-label">contract switch anomalies</span>
                <strong>{managedDataQuality?.contract_switch_anomaly_summary?.max_consecutive_switches ?? 0}</strong>
                <small>{managedDataQuality?.contract_switch_anomaly_summary?.status || "not_run"}</small>
              </div>
              <div className="metric-card">
                <span className="metric-label">missing rates</span>
                <strong>{Object.keys(managedDataQuality?.null_rate_by_field || {}).length}</strong>
                <small>{sanitizeVisibleSecretTerms(qualityNullRates || "missing")}</small>
              </div>
            </div>
            <strong>blocking reasons</strong>
            <p>{sanitizeVisibleSecretTerms(qualityBlockingReasons.join(", ") || "none")}</p>
            <strong>warning reasons</strong>
            <p>{sanitizeVisibleSecretTerms(qualityWarningReasons.join(", ") || "none")}</p>
          </div>
          <div className="notice-card">
            <div className="button-row">
              <strong>Point-in-Time Audit</strong>
              <button className="secondary-button" type="button" onClick={handleManagedProxyAudit} disabled={managedProxyAuditing}>
                {managedProxyAuditing ? "auditing..." : "Run PIT audit"}
              </button>
            </div>
            <div className="metric-grid compact">
              <div className="metric-card">
                <span className="metric-label">audit status</span>
                <strong>{managedProxyAudit?.status || "blocked"}</strong>
                <small>PIT pass/fail: {auditLeakage.point_in_time_join_ready ? "pass" : "fail"}</small>
              </div>
              <div className="metric-card">
                <span className="metric-label">timestamp coverage</span>
                <strong>{auditTimestampCoverage?.complete_rows ?? 0}/{auditTimestampCoverage?.row_count ?? 0}</strong>
                <small>{auditTimestampCoverage?.complete_ratio ?? 0}</small>
              </div>
              <div className="metric-card">
                <span className="metric-label">required timestamp fields</span>
                <strong>{managedProxyAudit?.required_timestamp_fields?.length || 0}</strong>
                <small>{(managedProxyAudit?.required_timestamp_fields || ["source_timestamp", "asof_date", "ingest_timestamp"]).join(", ")}</small>
              </div>
              <div className="metric-card">
                <span className="metric-label">missing timestamp fields</span>
                <strong>{managedProxyAudit?.missing_timestamp_fields?.length || 0}</strong>
                <small>{(managedProxyAudit?.missing_timestamp_fields || []).join(", ") || "none"}</small>
              </div>
              <div className="metric-card">
                <span className="metric-label">lag summary</span>
                <strong>{auditLagSummary?.median_lag_days ?? "missing"}</strong>
                <small>min {auditLagSummary?.min_lag_days ?? "n/a"} / max {auditLagSummary?.max_lag_days ?? "n/a"}</small>
              </div>
              <div className="metric-card">
                <span className="metric-label">whether Feature Store v12 build is allowed</span>
                <strong>{managedProxyHealth?.v12_allowed && managedProxyAudit?.status === "ready" ? "allowed" : "blocked"}</strong>
                <small>health + audit must both pass</small>
              </div>
            </div>
            <strong>blocking reasons</strong>
            <p>{sanitizeVisibleSecretTerms(auditBlockingReasons.join(", ") || "none")}</p>
            <strong>leakage checks</strong>
            <p>{sanitizeVisibleSecretTerms(Object.entries(auditLeakage).map(([key, value]) => `${key}:${value}`).join(", ") || "not checked")}</p>
            <div className="button-row">
              <strong>PIT Replay</strong>
              <button className="secondary-button" type="button" onClick={handleManagedPitReplay} disabled={managedPitReplaying}>
                {managedPitReplaying ? "replaying..." : "Run PIT replay"}
              </button>
            </div>
            <div className="metric-grid compact">
              <div className="metric-card">
                <span className="metric-label">status</span>
                <strong>{managedPitReplay?.status || "blocked"}</strong>
                <small>{managedPitReplay?.replay_version || "pit_replay_v1"}</small>
              </div>
              <div className="metric-card">
                <span className="metric-label">cases passed/failed</span>
                <strong>{managedPitReplay?.cases_passed ?? 0}/{managedPitReplay?.cases_failed ?? 0}</strong>
                <small>cases run: {managedPitReplay?.cases_run ?? 0}</small>
              </div>
              <div className="metric-card">
                <span className="metric-label">future rows rejected</span>
                <strong>{replayRejectedFutureRows.length}</strong>
                <small>future rows are never selected</small>
              </div>
              <div className="metric-card">
                <span className="metric-label">selected row rule</span>
                <strong>latest asof/source before cutoff</strong>
                <small>{replaySelectedRows[0]?.row_id ? String(replaySelectedRows[0].row_id) : "no selected row"}</small>
              </div>
              <div className="metric-card">
                <span className="metric-label">deterministic tie-break</span>
                <strong>{managedPitReplay?.deterministic_tiebreak_status || "not_run"}</strong>
                <small>ingest misuse: {managedPitReplay?.ingest_timestamp_misuse_detected ? "yes" : "no"}</small>
              </div>
              <div className="metric-card">
                <span className="metric-label">PIT join ready</span>
                <strong>{managedPitReplay?.point_in_time_join_ready ? "true" : "false"}</strong>
                <small>replay does not build v12</small>
              </div>
            </div>
            <strong>replay blocking reasons</strong>
            <p>{sanitizeVisibleSecretTerms(replayBlockingReasons.join(", ") || "none")}</p>
          </div>
          <div className="notice-card">
            <strong>Feature Store v12</strong>
            <div className="metric-grid compact">
              <div className="metric-card">
                <span className="metric-label">v12 status</span>
                <strong>{featureStoreV12?.status || "not_built"}</strong>
                <small>{featureStoreV12?.feature_store_version || "v12"}</small>
              </div>
              <div className="metric-card">
                <span className="metric-label">health status</span>
                <strong>{featureStoreV12?.health_status || "missing"}</strong>
                <small>audit status: {featureStoreV12?.audit_status || "missing"}</small>
              </div>
              <div className="metric-card">
                <span className="metric-label">managed field coverage</span>
                <strong>{featureStoreV12?.managed_field_coverage?.label || "0/0"}</strong>
                <small>{(featureStoreV12?.missing_fundamental_fields || []).slice(0, 4).join(", ") || "complete"}</small>
              </div>
              <div className="metric-card">
                <span className="metric-label">timestamp coverage</span>
                <strong>{featureStoreV12?.timestamp_field_coverage?.label || "0/0"}</strong>
                <small>{(featureStoreV12?.missing_timestamp_fields || []).slice(0, 4).join(", ") || "complete"}</small>
              </div>
              <div className="metric-card">
                <span className="metric-label">PIT join / no-lookahead</span>
                <strong>{featureStoreV12?.point_in_time_join_ready ? "ready" : "blocked"}</strong>
                <small>{featureStoreV12?.no_lookahead_pass ? "pass" : "blocked"}</small>
              </div>
              <div className="metric-card">
                <span className="metric-label">training dataset v12 allowed</span>
                <strong>{featureStoreV12?.training_dataset_v12_allowed ? "true" : "false"}</strong>
                <small>never auto-triggered here</small>
              </div>
            </div>
            <strong>blocking reasons</strong>
            <p>{sanitizeVisibleSecretTerms(featureStoreV12BlockingReasons.join(", ") || "none")}</p>
          </div>
        </SectionCard>
        <SectionCard title="Tushare futures subinterfaces" subtitle="contract info / daily / warehouse / settlement / holding status share the same provider status source.">
          <DataTable
            data={tushare_subinterfaces}
            columns={[
              { key: "source_name", title: "subinterface", render: (row) => sanitizeVisibleSecretTerms(row.source_name || row.label || "unknown") },
              { key: "status", title: "status", render: (row) => sanitizeVisibleSecretTerms(row.status || "missing") },
              { key: "row_count", title: "rows" },
              { key: "selected_params", title: "selected_params", render: (row) => sanitizeVisibleSecretTerms(summarizeValueKeys(row.selected_params)) },
              { key: "last_success_time", title: "last_success_time", render: (row) => sanitizeVisibleSecretTerms(row.last_success_time || "missing") },
              { key: "error_message_zh", title: "reason", render: (row) => sanitizeVisibleSecretTerms(row.error_message_zh || row.status || "") },
            ]}
          />
          <p className="muted">selected_params summary: {sanitizeVisibleSecretTerms(summarizeValueKeys(tushareSelectedParams))}</p>
          {String(tushare_warehouse?.status || "") === "no_sn_rows" ? (
            <div className="notice-card">
              <strong>warehouse_missing_policy</strong>
              <span>当前无真实沪锡仓单数据，系统未伪造字段；模型将使用缺失风险标记。</span>
            </div>
          ) : null}
        </SectionCard>
        <SectionCard
          title="数据一致性报告"
          subtitle="核对行情、图表、行情分析和数据水位是否指向同一最新日期。"
          actions={
            <button
              className="primary-button"
              type="button"
              onClick={() => {
                refreshConsistencyReport();
                onRefresh?.();
              }}
            >
              一键重新加载
            </button>
          }
        >
          <div className="metric-grid compact">
            <div className="metric-card">
              <span className="metric-label">当前最新数据时间</span>
              <strong>{sanitizeVisibleSecretTerms(latestDates().market_history || "数据暂缺")}</strong>
              <small>market history</small>
            </div>
            <div className="metric-card">
              <span className="metric-label">页面数据时间</span>
              <strong>{sanitizeVisibleSecretTerms(consistencyReport?.generated_at || "数据暂缺")}</strong>
              <small>report generated_at</small>
            </div>
            <div className="metric-card">
              <span className="metric-label">一致性</span>
              <strong>{sanitizeVisibleSecretTerms(consistencyReport?.status || "checking")}</strong>
              <small>{sanitizeVisibleSecretTerms(consistencyReport?.message_zh || "正在读取")}</small>
            </div>
            <div className="metric-card">
              <span className="metric-label">样例退场</span>
              <strong>{consistencyReport?.sample_mode_active ? "仍有样例" : "已退场"}</strong>
              <small>{sanitizeVisibleSecretTerms(consistencyReport?.current_data_mode || "unknown")}</small>
            </div>
          </div>
          <DataTable
            data={[
              { item: "price-history", latest_date: latestDates().price_history, ok: consistencyChecks().price_history_matches_market_history },
              { item: "chart payload", latest_date: latestDates().price_chart, ok: consistencyChecks().chart_matches_market_history },
              { item: "market-analysis", latest_date: latestDates().market_analysis, ok: consistencyChecks().analysis_matches_market_history },
              { item: "sample boundary", latest_date: latestDates().market_history, ok: consistencyChecks().sample_retired_after_real_refresh },
            ]}
            columns={[
              { key: "item", title: "检查项" },
              { key: "latest_date", title: "最新日期", render: (row) => sanitizeVisibleSecretTerms(row.latest_date || "数据暂缺") },
              { key: "ok", title: "状态", render: (row) => (row.ok ? "一致" : "需检查") },
            ]}
          />
        </SectionCard>
        <SectionCard title="在线数据源矩阵" subtitle="客户不需要 CSV/Excel；系统自动尝试公开在线源、API key 源和可选托管源。">
          <DataTable
            data={onlineSources}
            columns={[
              { key: "category", title: "数据类别" },
              { key: "source_id", title: "当前来源" },
              { key: "provider", title: "provider" },
              { key: "requires_key", title: "是否需要 key", render: (row) => (row.requires_key ? "是" : "否") },
              { key: "requires_paid_account", title: "是否需要托管/付费源", render: (row) => (row.requires_paid_account ? "可能需要" : "否") },
              { key: "client_upload_required", title: "是否需要客户上传文件", render: () => "否" },
              { key: "status", title: "状态" },
              { key: "row_count", title: "行数" },
              { key: "from_cache", title: "缓存", render: (row) => (row.from_cache ? "使用缓存" : "否") },
              { key: "last_success_time", title: "最近成功时间" },
              { key: "cooldown_until", title: "下次重试", render: (row) => sanitizeVisibleSecretTerms(row.cooldown_until || "无") },
              { key: "legal_note", title: "当前阻断原因", render: (row) => sanitizeVisibleSecretTerms(row.legal_note || row.status || "暂无") },
              { key: "next_actions_zh", title: "下一步建议", render: (row) => sanitizeVisibleSecretTerms(Array.isArray(row.next_actions_zh) ? row.next_actions_zh.join("；") : "查看诊断") },
            ]}
          />
          <p className="muted">
            当前公开在线源未返回沪锡相关行时，系统不会伪造数据。完整 LME、现货、库存和基差可通过发行方托管数据服务补齐。
          </p>
          <div className="notice-card">
            <strong>managed proxy structured fundamentals</strong>
            <p>
              managed proxy 状态会显示 success / using_cache / token_missing / endpoint_missing / network_failed。失败时可使用最近成功缓存。
            </p>
            <p>
              managed proxy v11 minimal real loop 会刷新真实 spot_price / spot_premium / spot_futures_basis / shfe_inventory /
              shfe_warehouse_receipt / lme_tin_close / lme_inventory / near-far close；无数据时只显示 blocked，不伪造字段。
            </p>
            <p>
              managed fundamentals schema: shfe_warehouse_receipt / shfe_inventory / spot_price / spot_premium /
              spot_futures_basis / lme_tin_close / lme_inventory. no_fake_data: true.
            </p>
          </div>
          <div className="notice-card">
            <strong>Tushare futures fundamentals</strong>
            <p>
              Tushare 状态会显示 success / token_missing / rate_limited / no_sn_rows。该源用于沪锡合约、日线、仓单、结算参数、持仓排名和交易日历，不用于实盘交易。
            </p>
          </div>
          <div className="notice-card">
            <strong>Alpha Vantage cross-market refresh states</strong>
            <p>
              rate_limited / using_cache_rate_limited / cooldown_until / last_success_time 会用于说明 USD/CNY、US10Y 和 copper proxy
              是最新刷新、使用最近成功缓存，还是正在等待下一次重试窗口。
            </p>
          </div>
        </SectionCard>
        <RefreshTaskPanel initialStatus={snapshot?.refresh_status} onAfterRefresh={onRefresh} />
        <RuntimeDiagnosticsPanel />
      </div>
    </ErrorBoundary>
  );
}
